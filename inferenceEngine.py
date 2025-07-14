from typing import Tuple, List, Optional
import random
from collections import deque
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from knowledgeBase import PropositionalKB

class InferenceEngine:
    def __init__(self, knowledge_base: PropositionalKB):
        self.kb = knowledge_base
        self.last_inference = ""
        self.last_reasoning = ""
        self.visited_positions = [(0, 0)]
        self.move_history = []
        self.max_history_length = 10
        self.safety_threshold = 0.1
        self.position_counts = {}

    def determine_next_action(self, current_pos: Tuple[int, int], percepts: List[str], grid_size: int) -> str:
        self.last_reasoning = ""
        self.visited_positions.append(current_pos)
        self.move_history.append(current_pos)
        if len(self.move_history) > self.max_history_length:
            self.move_history.pop(0)
        
        self.position_counts[current_pos] = self.position_counts.get(current_pos, 0) + 1
        
        if "Glitter" in percepts:
            self.last_reasoning = "Gold detected - grabbing it!"
            self.last_inference = "Glitter(x,y) → Grab"
            return "GRAB"
        
        if self.kb.has_gold_location() and current_pos != (0, 0) and "Glitter" not in percepts:
            action = self._find_path_to_exit(current_pos)
            if action:
                self.last_reasoning = "Returning to (0,0) with gold"
                self.last_inference = "GoldFound ∧ Position(x,y) ≠ (0,0) → MoveToExit"
                return action
        
        next_move = self._choose_next_move(current_pos)
        if not next_move:
            adj_cells = self._get_adjacent_cells(current_pos)
            # Prioritize non-deadly cells
            non_deadly_moves = [cell for cell in adj_cells if not self._is_deadly_cell(cell)]
            if non_deadly_moves:
                next_move = min(non_deadly_moves, key=self._threat_score)
                self.last_reasoning = f"Moving to least threatening non-deadly cell ({next_move[0]},{next_move[1]}), threat: {self._threat_score(next_move):.2f}"
                self.last_inference = f"LeastThreat → Move_{self._get_direction(current_pos, next_move)}"
            else:
                # All cells are deadly - move to the least dangerous
                next_move = min(adj_cells, key=self._threat_score)
                threat = self._threat_score(next_move)
                self.last_reasoning = f"Forced move to least dangerous cell ({next_move[0]},{next_move[1]}), threat: {threat:.2f} (all options deadly)"
                self.last_inference = f"ForcedMove → Move_{self._get_direction(current_pos, next_move)}"
        
        logger.info(f"Determining action at {current_pos} - Next move: {next_move}, Reasoning: {self.last_reasoning}")
        nx, ny = next_move
        direction = self._get_direction(current_pos, next_move)
        pit_conf = self.kb.get_confidence((nx, ny), 'pit')
        wumpus_conf = self.kb.get_confidence((nx, ny), 'wumpus')
        logger.debug(f"Move to ({nx},{ny}) - Pit confidence: {pit_conf}, Wumpus confidence: {wumpus_conf}")
        
        if pit_conf < self.safety_threshold and wumpus_conf < self.safety_threshold:
            self.last_reasoning = f"Moving to safe cell ({nx},{ny})"
            self.last_inference = f"Safe({nx},{ny}) → Move_{direction}"
        else:
            self.last_reasoning = f"Risky move to ({nx},{ny}), pit risk: {pit_conf*100:.0f}%, wumpus risk: {wumpus_conf*100:.0f}%"
            self.last_inference = f"RiskyMove → Move_{direction}"
        
        return f"MOVE_{direction}"

    def _choose_next_move(self, current_pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        adj_cells = self._get_adjacent_cells(current_pos)
        playing_grid = self.kb.get_playing_grid()
        
        # Filter out deadly cells and dangerous loops
        adj_cells = [cell for cell in adj_cells if not self._is_dangerous_loop(cell) and not self._is_deadly_cell(cell)]
        
        if not adj_cells:
            logger.warning(f"No safe moves from {current_pos}, all cells deadly or looped")
            return None
        
        unvisited_safe = [
            cell for cell in adj_cells
            if (playing_grid[cell[1]][cell[0]] == "0" and
                not self.kb.query(f"Visited({cell[0]},{cell[1]})"))
        ]
        if unvisited_safe:
            best_cell = max(unvisited_safe, key=lambda cell: (
                self._exploration_score(cell),
                -self.position_counts.get(cell, 0)
            ))
            self.last_reasoning = f"Exploring unvisited safe cell {best_cell}"
            logger.debug(f"Chose unvisited safe cell: {best_cell}")
            return best_cell
        
        path_to_unvisited = self._find_path_to_unvisited_area(current_pos)
        if path_to_unvisited:
            self.last_reasoning = f"Following path to unvisited area via {path_to_unvisited}"
            logger.debug(f"Chose path to unvisited: {path_to_unvisited}")
            return path_to_unvisited
        
        visited_cells = [
            cell for cell in adj_cells
            if playing_grid[cell[1]][cell[0]] == "1"
        ]
        if visited_cells:
            best_cell = min(visited_cells, key=lambda cell: (
                self.position_counts.get(cell, 0),
                self._distance_to_unvisited(cell)
            ))
            self.last_reasoning = f"Backtracking to visited cell {best_cell}"
            logger.debug(f"Chose visited cell: {best_cell}")
            return best_cell
        
        low_threat_cells = [
            cell for cell in adj_cells
            if (self.kb.get_confidence(cell, 'pit') < 0.2 and
                self.kb.get_confidence(cell, 'wumpus') < 0.2 and
                not self.kb.query(f"Visited({cell[0]},{cell[1]})"))
        ]
        if low_threat_cells:
            best_cell = min(low_threat_cells, key=lambda cell: (
                self._threat_score(cell),
                self.position_counts.get(cell, 0)
            ))
            self.last_reasoning = f"Moving to low-threat cell {best_cell}"
            logger.debug(f"Chose low-threat cell: {best_cell}")
            return best_cell
        
        backtrack_cell = self._find_backtrack_cell(current_pos)
        if backtrack_cell:
            self.last_reasoning = f"Backtracking to safer cell {backtrack_cell}"
            logger.debug(f"Chose backtrack cell: {backtrack_cell}")
            return backtrack_cell
        
        return None

    def _find_path_to_unvisited_area(self, current_pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        queue = deque([(current_pos, [])])
        visited = {current_pos}
        max_depth = 5

        while queue:
            pos, path = queue.popleft()
            x, y = pos

            if not self.kb.query(f"Visited({x},{y})") and pos != current_pos:
                return path[0] if path else pos

            if len(path) > max_depth:
                continue

            adj_cells = self._get_adjacent_cells(pos)
            safe_cells = [
                cell for cell in adj_cells
                if (cell not in visited and
                    not self._is_dangerous_loop(cell) and
                    not self._is_deadly_cell(cell) and
                    self.kb.get_confidence(cell, 'pit') < self.safety_threshold and
                    self.kb.get_confidence(cell, 'wumpus') < self.safety_threshold)
            ]

            if not safe_cells:
                safe_cells = [
                    cell for cell in adj_cells
                    if (cell not in visited and
                        not self._is_dangerous_loop(cell) and
                        not self._is_deadly_cell(cell) and
                        self._threat_score(cell) < 0.2)
                ]

            safe_cells.sort(key=lambda cell: (
                self._threat_score(cell),
                self.position_counts.get(cell, 0)
            ))

            for next_pos in safe_cells:
                visited.add(next_pos)
                queue.append((next_pos, path + [next_pos]))

        return None

    def _is_dangerous_loop(self, position: Tuple[int, int]) -> bool:
        if len(self.move_history) >= 4:
            recent_count = self.move_history[-4:].count(position)
            if recent_count >= 2:
                return True
        
        if len(self.move_history) >= 3:
            if self.move_history[-1] == position and self.move_history[-3] == position:
                return True
        
        if self.position_counts.get(position, 0) >= 3:
            return True
        
        return False

    def _is_deadly_cell(self, position: Tuple[int, int]) -> bool:
        pit_conf = self.kb.get_confidence(position, 'pit')
        wumpus_conf = self.kb.get_confidence(position, 'wumpus')
        logger.debug(f"Checking if {position} is deadly - Pit: {pit_conf}, Wumpus: {wumpus_conf}")
        return pit_conf > 0.8 or wumpus_conf > 0.8

    def _find_backtrack_cell(self, current_pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        queue = deque([(current_pos, [])])
        visited = {current_pos}
        max_depth = 3

        while queue:
            pos, path = queue.popleft()
            if len(path) > max_depth:
                continue
            
            adj_cells = self._get_adjacent_cells(pos)
            safe_cells = [
                cell for cell in adj_cells
                if (self.kb.get_confidence(cell, 'pit') < self.safety_threshold and
                    self.kb.get_confidence(cell, 'wumpus') < self.safety_threshold and
                    not self._is_dangerous_loop(cell) and
                    not self._is_deadly_cell(cell))
            ]
            
            if safe_cells:
                return path[0] if path else min(safe_cells, key=lambda cell: self.position_counts.get(cell, 0))
            
            for next_pos in adj_cells:
                if next_pos not in visited and not self._is_dangerous_loop(next_pos) and not self._is_deadly_cell(next_pos):
                    visited.add(next_pos)
                    queue.append((next_pos, path + [next_pos]))
        
        return None

    def _exploration_score(self, position: Tuple[int, int]) -> int:
        x, y = position
        score = 0
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if (0 <= nx < self.kb.grid_size and 0 <= ny < self.kb.grid_size and
                not self.kb.query(f"Visited({nx},{ny})") and
                self.kb.get_confidence((nx, ny), 'pit') < 0.2 and
                self.kb.get_confidence((nx, ny), 'wumpus') < 0.2):
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

    def _find_path_to_exit(self, current_pos: Tuple[int, int]) -> Optional[str]:
        queue = deque([(current_pos, [])])
        visited = {current_pos}
        target = (0, 0)
        max_depth = 4

        while queue:
            pos, path = queue.popleft()
            if pos == target:
                return self._get_direction(current_pos, path[0]) if path else None
            if len(path) > max_depth:
                continue
            
            adj_cells = self._get_adjacent_cells(pos)
            safe_cells = [
                cell for cell in adj_cells
                if (self.kb.get_confidence(cell, 'pit') < self.safety_threshold and
                    self.kb.get_confidence(cell, 'wumpus') < self.safety_threshold and
                    not self._is_dangerous_loop(cell) and
                    not self._is_deadly_cell(cell))
            ]
            if not safe_cells:
                safe_cells = sorted(
                    [cell for cell in adj_cells if cell not in visited and not self._is_dangerous_loop(cell) and not self._is_deadly_cell(cell)],
                    key=self._threat_score
                )
            
            for next_pos in safe_cells:
                if next_pos not in visited:
                    visited.add(next_pos)
                    queue.append((next_pos, path + [next_pos]))
        
        adj_cells = self._get_adjacent_cells(current_pos)
        non_deadly = [cell for cell in adj_cells if not self._is_dangerous_loop(cell) and not self._is_deadly_cell(cell)]
        
        if non_deadly:
            best_cell = min(non_deadly, key=self._threat_score)
            return self._get_direction(current_pos, best_cell)
        
        non_looping = [cell for cell in adj_cells if not self._is_dangerous_loop(cell)]
        if non_looping:
            best_cell = min(non_looping, key=self._threat_score)
            return self._get_direction(current_pos, best_cell)
        
        if adj_cells:
            best_cell = min(adj_cells, key=lambda cell: (
                self._threat_score(cell),
                self.position_counts.get(cell, 0)
            ))
            return self._get_direction(current_pos, best_cell)
        
        return None

    def _threat_score(self, position: Tuple[int, int]) -> float:
        return self.kb.get_confidence(position, 'pit') + self.kb.get_confidence(position, 'wumpus')

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