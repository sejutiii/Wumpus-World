from typing import Tuple, List, Optional
import random
from collections import deque
from knowledgeBase import PropositionalKB

class InferenceEngine:
    def __init__(self, knowledge_base: PropositionalKB):
        self.kb = knowledge_base
        self.last_inference = ""
        self.last_reasoning = ""
        self.visited_positions = [(0, 0)]
        self.move_history = []
        self.max_history_length = 8
        
    def determine_next_action(self, current_pos: Tuple[int, int], percepts: List[str], grid_size: int) -> str:
        self.last_reasoning = ""
        self.visited_positions.append(current_pos)
        self.move_history.append(current_pos)
        if len(self.move_history) > self.max_history_length:
            self.move_history.pop(0)
        
        if "Glitter" in percepts:
            self.last_reasoning = "Gold detected - grabbing it!"
            self.last_inference = "Glitter(x,y) → Grab"
            return "GRAB"
        
        if self.kb.has_gold_location() and current_pos != (0, 0):
            action = self._find_safe_path_to_exit(current_pos)
            if action:
                self.last_reasoning = "Have gold - returning to (0,0)"
                self.last_inference = "GoldFound ∧ Position(x,y) ≠ (0,0) → MoveToExit"
                return action
        
        next_move = self._choose_safe_move(current_pos)
        if not next_move:
            self.last_reasoning = "No valid moves available"
            self.last_inference = "NoValidMoves → Stay"
            return "STAY"
        
        nx, ny = next_move
        direction = self._get_direction(current_pos, next_move)
        pit_conf = self.kb.get_confidence((nx, ny), 'pit')
        
        if pit_conf == 0.0:
            self.last_reasoning = f"Moving to safe cell ({nx},{ny})"
            self.last_inference = f"Safe({nx},{ny}) → Move_{direction}"
        else:
            self.last_reasoning = f"Emergency move to ({nx},{ny}), pit risk: {pit_conf*100:.0f}%"
            self.last_inference = f"NoSafeOptions → Move_{direction}"
        
        return f"MOVE_{direction}"
    
    def _choose_safe_move(self, current_pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        adj_cells = self._get_adjacent_cells(current_pos)
        
        # Priority 1: Safe unvisited cells (pit and wumpus confidence = 0.0)
        safe_unvisited = [
            cell for cell in adj_cells
            if (self.kb.get_confidence(cell, 'pit') == 0.0 and 
                self.kb.get_confidence(cell, 'wumpus') == 0.0 and
                not self.kb.query(f"Visited({cell[0]},{cell[1]})"))
        ]
        if safe_unvisited:
            best_cell = max(safe_unvisited, key=self._exploration_score, default=safe_unvisited[0])
            self.last_reasoning = f"Exploring safe unvisited cell {best_cell}"
            return best_cell
        
        # Priority 2: Safe visited cells, avoiding loops
        safe_visited = [
            cell for cell in adj_cells
            if (self.kb.get_confidence(cell, 'pit') == 0.0 and 
                self.kb.get_confidence(cell, 'wumpus') == 0.0 and
                self.kb.query(f"Visited({cell[0]},{cell[1]})") and
                not self._would_create_loop(cell))
        ]
        if safe_visited:
            best_cell = min(safe_visited, key=self._distance_to_unvisited, default=safe_visited[0])
            self.last_reasoning = f"Backtracking to safe visited cell {best_cell}"
            return best_cell
        
        # Priority 3: Non-loop cell with lowest pit risk
        non_loop_cells = [cell for cell in adj_cells if not self._would_create_loop(cell)]
        if non_loop_cells:
            best_cell = min(non_loop_cells, key=lambda cell: self.kb.get_confidence(cell, 'pit'))
            self.last_reasoning = f"Emergency: lowest pit risk cell {best_cell}"
            return best_cell
        
        # Final fallback: any adjacent cell
        if adj_cells:
            return random.choice(adj_cells)
        
        return None
    
    def _exploration_score(self, position: Tuple[int, int]) -> int:
        x, y = position
        score = 0
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if (0 <= nx < self.kb.grid_size and 0 <= ny < self.kb.grid_size and
                not self.kb.query(f"Visited({nx},{ny})") and
                self.kb.get_confidence((nx, ny), 'pit') == 0.0 and
                self.kb.get_confidence((nx, ny), 'wumpus') == 0.0):
                score += 3
        return score
    
    def _distance_to_unvisited(self, position: Tuple[int, int]) -> int:
        queue = deque([(position, 0)])
        visited = {position}
        
        while queue:
            (x, y), dist = queue.popleft()
            if not self.kb.query(f"Visited({x},{y})"):
                return dist
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if (0 <= nx < self.kb.grid_size and 0 <= ny < self.kb.grid_size and
                    (nx, ny) not in visited):
                    visited.add((nx, ny))
                    queue.append(((nx, ny), dist + 1))
        return float('inf')
    
    def _would_create_loop(self, position: Tuple[int, int]) -> bool:
        if len(self.move_history) < 4:
            return False
        recent_positions = self.move_history[-4:]
        return recent_positions.count(position) >= 2
    
    def _find_safe_path_to_exit(self, current_pos: Tuple[int, int]) -> Optional[str]:
        queue = deque([(current_pos, [])])
        visited = {current_pos}
        target = (0, 0)
        
        while queue:
            pos, path = queue.popleft()
            if pos == target:
                return self._get_direction(current_pos, path[0]) if path else None
            
            adj_cells = self._get_adjacent_cells(pos)
            # Prioritize safe cells (pit and wumpus confidence = 0.0)
            safe_cells = [
                cell for cell in adj_cells 
                if cell not in visited and 
                self.kb.get_confidence(cell, 'pit') == 0.0 and 
                self.kb.get_confidence(cell, 'wumpus') == 0.0
            ]
            # Fallback to lowest pit risk if no safe cells
            if not safe_cells:
                safe_cells = sorted(
                    [cell for cell in adj_cells if cell not in visited],
                    key=lambda cell: self.kb.get_confidence(cell, 'pit')
                )
            
            for next_pos in safe_cells:
                visited.add(next_pos)
                queue.append((next_pos, path + [next_pos]))
        
        return None
    
    def _get_direction(self, current_pos: Tuple[int, int], next_pos: Tuple[int, int]) -> str:
        x, y = current_pos
        nx, ny = next_pos
        if nx == x and ny == y - 1:
            return "UP"
        elif nx == x and ny == y + 1:
            return "DOWN"
        elif nx == x - 1 and ny == y:
            return "LEFT"
        elif nx == x + 1 and ny == y:
            return "RIGHT"
        return ""
    
    def _get_adjacent_cells(self, position: Tuple[int, int]) -> List[Tuple[int, int]]:
        x, y = position
        adjacent = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            new_x, new_y = x + dx, y + dy
            if 0 <= new_x < self.kb.grid_size and 0 <= new_y < self.kb.grid_size:
                adjacent.append((new_x, new_y))
        return adjacent
    
    def get_last_inference(self) -> str:
        return self.last_inference
    
    def get_last_reasoning(self) -> str:
        return self.last_reasoning
    
    def get_confidence_summary(self) -> str:
        summary = []
        for y in range(self.kb.grid_size):
            for x in range(self.kb.grid_size):
                pit_conf = self.kb.get_confidence((x, y), 'pit')
                wumpus_conf = self.kb.get_confidence((x, y), 'wumpus')
                if pit_conf > 0 or wumpus_conf > 0:
                    summary.append(f"({x},{y}): Pit={pit_conf*100:.0f}%, Wumpus={wumpus_conf*100:.0f}%")
        return "; ".join(summary) if summary else "No threats detected"