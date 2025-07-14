from typing import Tuple, List, Optional, Set
import random
from collections import deque
from knowledgeBase import PropositionalKB

class InferenceEngine:
    def __init__(self, knowledge_base: PropositionalKB):
        self.kb = knowledge_base
        self.last_inference = ""
        self.last_reasoning = ""
        self.visited_positions = [(0, 0)]
        self.move_history = []  # Track recent moves for loop detection
        self.max_history_length = 8  # Adjust based on grid size
        
    def determine_next_action(self, current_pos: Tuple[int, int], percepts: List[str], grid_size: int) -> str:
        self.last_reasoning = ""
        self.visited_positions.append(current_pos)
        
        if "Glitter" in percepts:
            self.last_reasoning = "Gold detected at current position - grabbing it!"
            self.last_inference = "Glitter(x,y) → Grab"
            return "GRAB"
        
        if self.kb.has_gold_location() and current_pos != (0, 0):
            action = self._find_path_to_exit(current_pos)
            if action:
                self.last_reasoning = "Have gold - returning to exit at (0,0)"
                self.last_inference = "GoldFound ∧ Position(x,y) ≠ (0,0) → MoveToExit"
                return action
        
        next_move = self._choose_next_move_with_efficient_search(current_pos)
        if not next_move:
            self.last_reasoning = "No valid moves available"
            self.last_inference = "NoValidMoves → Stay"
            return "STAY"
        
        nx, ny = next_move
        direction = self._get_direction(current_pos, next_move)
        
        # Update move history for loop detection
        self.move_history.append(current_pos)
        if len(self.move_history) > self.max_history_length:
            self.move_history.pop(0)
        
        # Enhanced reasoning based on confidence and search strategy
        pit_conf = self.kb.get_confidence((nx, ny), 'pit')
        wumpus_conf = self.kb.get_confidence((nx, ny), 'wumpus')
        
        if pit_conf == 0.0 and wumpus_conf == 0.0:
            if not self.kb.query(f"Visited({nx},{ny})"):
                self.last_reasoning = f"Moving to safe unvisited cell ({nx},{ny}) - optimal for exploration"
                self.last_inference = f"Safe({nx},{ny}) ∧ ¬Visited({nx},{ny}) → Move_{direction}"
            else:
                self.last_reasoning = f"Moving to safe visited cell ({nx},{ny}) - strategic backtrack"
                self.last_inference = f"Safe({nx},{ny}) ∧ Visited({nx},{ny}) → Move_{direction}"
        elif pit_conf == 0.2 or wumpus_conf == 0.2:
            self.last_reasoning = f"Moving to low-risk cell ({nx},{ny}) - confidence: {max(pit_conf, wumpus_conf)*100}%"
            self.last_inference = f"LowRisk({nx},{ny}) → Move_{direction}"
        elif pit_conf == 0.5 or wumpus_conf == 0.5:
            self.last_reasoning = f"Taking calculated risk at ({nx},{ny}) - confidence: {max(pit_conf, wumpus_conf)*100}%"
            self.last_inference = f"ModerateRisk({nx},{ny}) → Move_{direction}"
        else:
            self.last_reasoning = f"Moving to visited cell ({nx},{ny})"
            self.last_inference = f"Visited({nx},{ny}) → Move_{direction}"
        
        return f"MOVE_{direction}"
    
    def _choose_next_move_with_efficient_search(self, current_pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        adj_cells = self._get_adjacent_cells(current_pos)
        
        # Priority 1: Safe unvisited cells (confidence = 0.0 for both pit and wumpus)
        safe_unvisited = []
        for nx, ny in adj_cells:
            if (self.kb.get_confidence((nx, ny), 'pit') == 0.0 and 
                self.kb.get_confidence((nx, ny), 'wumpus') == 0.0 and
                not self.kb.query(f"Visited({nx},{ny})")):
                safe_unvisited.append((nx, ny))
        
        if safe_unvisited:
            # Choose the safe unvisited cell that leads to the most exploration potential
            best_cell = self._select_best_exploration_cell(safe_unvisited, current_pos)
            self.last_reasoning = f"Choosing safe unvisited cell {best_cell} for optimal exploration"
            return best_cell
        
        # Priority 2: Safe visited cells that lead to unvisited areas (avoid loops)
        safe_visited = []
        for nx, ny in adj_cells:
            if (self.kb.get_confidence((nx, ny), 'pit') == 0.0 and 
                self.kb.get_confidence((nx, ny), 'wumpus') == 0.0 and
                self.kb.query(f"Visited({nx},{ny})") and
                not self._would_create_loop((nx, ny))):
                safe_visited.append((nx, ny))
        
        if safe_visited:
            # Choose visited cell that's closest to unvisited areas
            best_cell = self._select_best_backtrack_cell(safe_visited, current_pos)
            self.last_reasoning = f"Backtracking to safe visited cell {best_cell} to reach unvisited areas"
            return best_cell
        
        # Priority 3: Low confidence threats (20%) - prefer unvisited
        low_risk_cells = []
        for nx, ny in adj_cells:
            pit_conf = self.kb.get_confidence((nx, ny), 'pit')
            wumpus_conf = self.kb.get_confidence((nx, ny), 'wumpus')
            if (pit_conf == 0.2 or wumpus_conf == 0.2) and not self._would_create_loop((nx, ny)):
                low_risk_cells.append((nx, ny))
        
        if low_risk_cells:
            # Prefer unvisited over visited in low-risk cells
            unvisited_low_risk = [cell for cell in low_risk_cells if not self.kb.query(f"Visited({cell[0]},{cell[1]})")]
            if unvisited_low_risk:
                best_cell = self._select_best_exploration_cell(unvisited_low_risk, current_pos)
                self.last_reasoning = f"Taking low-risk move to unvisited cell {best_cell}"
                return best_cell
            else:
                self.last_reasoning = "Taking low-risk move to visited cell"
                return random.choice(low_risk_cells)
        
        # Priority 4: Medium confidence threats (50%) - avoid loops
        medium_risk_cells = []
        for nx, ny in adj_cells:
            pit_conf = self.kb.get_confidence((nx, ny), 'pit')
            wumpus_conf = self.kb.get_confidence((nx, ny), 'wumpus')
            if (pit_conf == 0.5 or wumpus_conf == 0.5) and not self._would_create_loop((nx, ny)):
                medium_risk_cells.append((nx, ny))
        
        if medium_risk_cells:
            # Prefer unvisited over visited in medium-risk cells
            unvisited_medium_risk = [cell for cell in medium_risk_cells if not self.kb.query(f"Visited({cell[0]},{cell[1]})")]
            if unvisited_medium_risk:
                best_cell = self._select_best_exploration_cell(unvisited_medium_risk, current_pos)
                self.last_reasoning = f"Taking medium-risk move to unvisited cell {best_cell}"
                return best_cell
            else:
                self.last_reasoning = "Taking medium-risk move to visited cell"
                return random.choice(medium_risk_cells)
        
        # Priority 5: Any non-loop cell (including high-risk as last resort)
        non_loop_cells = [cell for cell in adj_cells if not self._would_create_loop(cell)]
        if non_loop_cells:
            self.last_reasoning = "Last resort: choosing any non-loop cell"
            return random.choice(non_loop_cells)
        
        # Final fallback: any adjacent cell
        if adj_cells:
            self.last_reasoning = "Emergency fallback: choosing any adjacent cell"
            return random.choice(adj_cells)
        
        return None
    
    def _select_best_exploration_cell(self, candidates: List[Tuple[int, int]], current_pos: Tuple[int, int]) -> Tuple[int, int]:
        """Select the candidate cell that leads to the most exploration potential"""
        if not candidates:
            return None
        
        if len(candidates) == 1:
            return candidates[0]
        
        best_cell = None
        best_score = -1
        
        for cell in candidates:
            score = self._calculate_exploration_score(cell)
            if score > best_score:
                best_score = score
                best_cell = cell
        
        return best_cell if best_cell else candidates[0]
    
    def _select_best_backtrack_cell(self, candidates: List[Tuple[int, int]], current_pos: Tuple[int, int]) -> Tuple[int, int]:
        """Select the visited cell that's closest to unvisited areas"""
        if not candidates:
            return None
        
        if len(candidates) == 1:
            return candidates[0]
        
        best_cell = None
        best_distance = float('inf')
        
        for cell in candidates:
            distance = self._distance_to_nearest_unvisited(cell)
            if distance < best_distance:
                best_distance = distance
                best_cell = cell
        
        return best_cell if best_cell else candidates[0]
    
    def _calculate_exploration_score(self, position: Tuple[int, int]) -> int:
        """Calculate exploration potential score for a position"""
        x, y = position
        score = 0
        
        # Count adjacent unvisited safe cells
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if (0 <= nx < self.kb.grid_size and 0 <= ny < self.kb.grid_size and
                not self.kb.query(f"Visited({nx},{ny})") and
                self.kb.get_confidence((nx, ny), 'pit') <= 0.2 and
                self.kb.get_confidence((nx, ny), 'wumpus') <= 0.2):
                score += 3
        
        # Count nearby unvisited cells (2-step distance)
        for dx in [-2, -1, 0, 1, 2]:
            for dy in [-2, -1, 0, 1, 2]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if (0 <= nx < self.kb.grid_size and 0 <= ny < self.kb.grid_size and
                    not self.kb.query(f"Visited({nx},{ny})")):
                    score += 1
        
        return score
    
    def _distance_to_nearest_unvisited(self, position: Tuple[int, int]) -> int:
        """Calculate distance to nearest unvisited cell using BFS"""
        queue = deque([(position, 0)])
        visited = {position}
        
        while queue:
            (x, y), dist = queue.popleft()
            
            # Check if this position is unvisited
            if not self.kb.query(f"Visited({x},{y})"):
                return dist
            
            # Add adjacent cells
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if (0 <= nx < self.kb.grid_size and 0 <= ny < self.kb.grid_size and
                    (nx, ny) not in visited):
                    visited.add((nx, ny))
                    queue.append(((nx, ny), dist + 1))
        
        return float('inf')  # No unvisited cells found
    
    def _would_create_loop(self, position: Tuple[int, int]) -> bool:
        """Check if moving to this position would create a loop"""
        if len(self.move_history) < 4:  # Need at least 4 moves to detect a loop
            return False
        
        # Check if we've been oscillating between positions
        recent_positions = self.move_history[-4:]
        if recent_positions.count(position) >= 2:
            return True
        
        # Check for patterns in recent moves
        if len(self.move_history) >= 6:
            # Check for A-B-A-B pattern
            if (self.move_history[-2] == position and 
                self.move_history[-4] == position and
                self.move_history[-6] == position):
                return True
        
        return False
    
    def _find_path_to_exit(self, current_pos: Tuple[int, int]) -> Optional[str]:
        x, y = current_pos
        target_x, target_y = 0, 0
        
        # Simple pathfinding towards (0,0) with safety checks
        if x > target_x:
            next_pos = (x-1, y)
            if self._is_safe_to_move(next_pos):
                return "MOVE_LEFT"
        elif x < target_x:
            next_pos = (x+1, y)
            if self._is_safe_to_move(next_pos):
                return "MOVE_RIGHT"
        
        if y > target_y:
            next_pos = (x, y-1)
            if self._is_safe_to_move(next_pos):
                return "MOVE_UP"
        elif y < target_y:
            next_pos = (x, y+1)
            if self._is_safe_to_move(next_pos):
                return "MOVE_DOWN"
        
        return None
    
    def _is_safe_to_move(self, position: Tuple[int, int]) -> bool:
        """Check if position is safe to move to"""
        x, y = position
        if not (0 <= x < self.kb.grid_size and 0 <= y < self.kb.grid_size):
            return False
        
        # Consider it safe if visited or has low threat confidence
        if self.kb.query(f"Visited({x},{y})"):
            return True
        
        pit_conf = self.kb.get_confidence((x, y), 'pit')
        wumpus_conf = self.kb.get_confidence((x, y), 'wumpus')
        
        return pit_conf <= 0.2 and wumpus_conf <= 0.2
    
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
        """Get a summary of current confidence levels"""
        summary = []
        for y in range(self.kb.grid_size):
            for x in range(self.kb.grid_size):
                pit_conf = self.kb.get_confidence((x, y), 'pit')
                wumpus_conf = self.kb.get_confidence((x, y), 'wumpus')
                if pit_conf > 0 or wumpus_conf > 0:
                    summary.append(f"({x},{y}): Pit={pit_conf*100:.0f}%, Wumpus={wumpus_conf*100:.0f}%")
        return "; ".join(summary) if summary else "No threats detected"