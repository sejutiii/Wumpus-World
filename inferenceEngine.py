from typing import Tuple, List, Optional
import random
from collections import deque
from knowledgeBase import PropositionalKB

class InferenceEngine:
    def __init__(self, knowledge_base: PropositionalKB):
        self.kb = knowledge_base
        self.last_inference = ""
        self.last_reasoning = ""
        self.visited_positions = [(0, 0)]  # Track visited positions
        self.move_history = []  # Track recent moves for loop detection
        self.max_history_length = 10  # Max history for loop detection
        self.safety_threshold = 0.1  # Threshold for safe cells
        self.position_counts = {}  # Track visit frequency for each position

    def determine_next_action(self, current_pos: Tuple[int, int], percepts: List[str], grid_size: int) -> str:
        self.last_reasoning = ""
        self.visited_positions.append(current_pos)
        self.move_history.append(current_pos)
        if len(self.move_history) > self.max_history_length:
            self.move_history.pop(0)
        
        # Update position visit counts
        self.position_counts[current_pos] = self.position_counts.get(current_pos, 0) + 1
        
        # Handle gold detection
        if "Glitter" in percepts:
            self.last_reasoning = "Gold detected - grabbing it!"
            self.last_inference = "Glitter(x,y) → Grab"
            return "GRAB"
        
        # Return to exit if gold is found
        if self.kb.has_gold_location() and current_pos != (0, 0) and "Glitter" not in percepts:
            action = self._find_path_to_exit(current_pos)
            if action:
                self.last_reasoning = "Returning to (0,0) with gold"
                self.last_inference = "GoldFound ∧ Position(x,y) ≠ (0,0) → MoveToExit"
                return action
        
        # Choose next move
        next_move = self._choose_next_move(current_pos)
        if not next_move:
            # Fallback: Choose least visited, lowest-threat adjacent cell
            adj_cells = self._get_adjacent_cells(current_pos)
            valid_moves = [cell for cell in adj_cells if not self._is_dangerous_loop(cell) and not self._is_deadly_cell(cell)]
            
            if valid_moves:
                next_move = min(valid_moves, key=lambda cell: (
                    self.position_counts.get(cell, 0),
                    self._threat_score(cell)
                ))
                self.last_reasoning = f"Fallback to least visited safe cell ({next_move[0]},{next_move[1]})"
                self.last_inference = f"NoSafeOptions → Move_{self._get_direction(current_pos, next_move)}"
            else:
                # Risky move: Avoid loops, pick least dangerous
                risky_moves = [cell for cell in adj_cells if not self._is_dangerous_loop(cell)]
                if risky_moves:
                    next_move = min(risky_moves, key=self._threat_score)
                    threat = self._threat_score(next_move)
                    self.last_reasoning = f"Forced risky move to ({next_move[0]},{next_move[1]}), threat: {threat:.2f}"
                    self.last_inference = f"ForcedMove → Move_{self._get_direction(current_pos, next_move)}"
                else:
                    # Emergency: Pick any adjacent cell
                    if adj_cells:
                        next_move = min(adj_cells, key=lambda cell: (
                            self._threat_score(cell),
                            self.position_counts.get(cell, 0)
                        ))
                        self.last_reasoning = f"Emergency move to ({next_move[0]},{next_move[1]}) - no other options"
                        self.last_inference = f"EmergencyMove → Move_{self._get_direction(current_pos, next_move)}"
                    else:
                        self.last_reasoning = "No adjacent cells available"
                        self.last_inference = "NoAdjacentCells → Stay"
                        return "STAY"
        
        # Determine direction and safety
        nx, ny = next_move
        direction = self._get_direction(current_pos, next_move)
        pit_conf = self.kb.get_confidence((nx, ny), 'pit')
        wumpus_conf = self.kb.get_confidence((nx, ny), 'wumpus')
        
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
        
        # Filter out dangerous loops and deadly cells
        adj_cells = [cell for cell in adj_cells if not self._is_dangerous_loop(cell) and not self._is_deadly_cell(cell)]
        
        if not adj_cells:
            return None
        
        # Priority 1: Unvisited safe cells
        unvisited_safe = [
            cell for cell in adj_cells
            if (playing_grid[cell[1]][cell[0]] == "0" and
                not self.kb.query(f"Visited({cell[0]},{cell[1]})"))
        ]
        if unvisited_safe:
            best_cell = max(unvisited_safe, key=lambda cell: (
                self._exploration_score(cell),
                -self.position_counts.get(cell, 0)  # Prefer less visited
            ))
            self.last_reasoning = f"Exploring unvisited safe cell {best_cell}"
            return best_cell
        
        # Priority 2: Path to unvisited areas
        path_to_unvisited = self._find_path_to_unvisited_area(current_pos)
        if path_to_unvisited:
            self.last_reasoning = f"Following path to unvisited area via {path_to_unvisited}"
            return path_to_unvisited
        
        # Priority 3: Visited safe cells
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
            return best_cell
        
        # Priority 4: Low-threat unvisited cells
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
            return best_cell
        
        # Priority 5: Backtrack to safer cell
        backtrack_cell = self._find_backtrack_cell(current_pos)
        if backtrack_cell:
            self.last_reasoning = f"Backtracking to safer cell {backtrack_cell}"
            return backtrack_cell
        
        return None

    def _find_path_to_unvisited_area(self, current_pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """
        Find a path to an unvisited area using BFS.
        Args:
            current_pos: Current position of the agent (x, y).
        Returns:
            Optional[Tuple[int, int]]: Next position in the path, or None if no path found.
        """
        queue = deque([(current_pos, [])])  # (position, path)
        visited = {current_pos}
        max_depth = 5  # Limit search depth

        while queue:
            pos, path = queue.popleft()
            x, y = pos

            # Check if position is unvisited (and not current position)
            if not self.kb.query(f"Visited({x},{y})") and pos != current_pos:
                return path[0] if path else pos

            if len(path) > max_depth:
                continue

            # Get adjacent cells
            adj_cells = self._get_adjacent_cells(pos)
            safe_cells = [
                cell for cell in adj_cells
                if (cell not in visited and
                    not self._is_dangerous_loop(cell) and
                    not self._is_deadly_cell(cell) and
                    self.kb.get_confidence(cell, 'pit') < self.safety_threshold and
                    self.kb.get_confidence(cell, 'wumpus') < self.safety_threshold)
            ]

            # Fallback to low-threat cells if no safe cells
            if not safe_cells:
                safe_cells = [
                    cell for cell in adj_cells
                    if (cell not in visited and
                        not self._is_dangerous_loop(cell) and
                        not self._is_deadly_cell(cell) and
                        self._threat_score(cell) < 0.2)
                ]

            # Sort by threat score and visit count
            safe_cells.sort(key=lambda cell: (
                self._threat_score(cell),
                self.position_counts.get(cell, 0)
            ))

            for next_pos in safe_cells:
                visited.add(next_pos)
                queue.append((next_pos, path + [next_pos]))

        return None

    def _is_dangerous_loop(self, position: Tuple[int, int]) -> bool:
        """Detect dangerous loops based on move history and visit counts."""
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
        """Check if a cell is deadly (high confidence of pit or Wumpus)."""
        pit_conf = self.kb.get_confidence(position, 'pit')
        wumpus_conf = self.kb.get_confidence(position, 'wumpus')
        return pit_conf > 0.8 or wumpus_conf > 0.8

    def _find_backtrack_cell(self, current_pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """Find a safe cell to backtrack to using BFS."""
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
        """Calculate exploration score based on unvisited safe neighbors."""
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
        """Calculate distance to nearest unvisited cell using BFS."""
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
        """Find a safe path to (0,0) using BFS."""
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
        
        # Fallback to lowest-threat move toward (0,0)
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
        """Calculate combined threat score for a position."""
        return self.kb.get_confidence(position, 'pit') + self.kb.get_confidence(position, 'wumpus')

    def _get_direction(self, current_pos: Tuple[int, int], next_pos: Tuple[int, int]) -> str:
        """Determine direction from current to next position."""
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
        """Get valid adjacent cells within grid boundaries."""
        x, y = position
        adjacent = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            new_x, new_y = x + dx, y + dy
            if 0 <= new_x < self.kb.grid_size and 0 <= new_y < self.kb.grid_size:
                adjacent.append((new_x, new_y))
        return adjacent

    def get_last_inference(self) -> str:
        """Return the last inference made."""
        return self.last_inference

    def get_last_reasoning(self) -> str:
        """Return the last reasoning explanation."""
        return self.last_reasoning