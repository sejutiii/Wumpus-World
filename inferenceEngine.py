from typing import Tuple, List, Optional
import random
from knowledgeBase import PropositionalKB

class InferenceEngine:
    def __init__(self, knowledge_base: PropositionalKB):
        self.kb = knowledge_base
        self.last_inference = ""
        self.last_reasoning = ""
        self.visited_positions = [(0, 0)]
        
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
        
        next_move = self._choose_next_move(current_pos)
        if not next_move:
            self.last_reasoning = "No valid moves available"
            self.last_inference = "NoValidMoves → Stay"
            return "STAY"
        
        nx, ny = next_move
        direction = self._get_direction(current_pos, next_move)
        cell_value = self.kb.playing_grid[ny][nx]
        self.last_reasoning = f"Moving to ({nx},{ny}) with priority: {'Safe unvisited' if cell_value == '0' else 'Visited safe' if cell_value == '1' else 'Possible danger'}"
        self.last_inference = f"SafeOrPrioritized({nx},{ny}) → Move_{direction}"
        return f"MOVE_{direction}"
    
    def _choose_next_move(self, current_pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        adj_cells = self._get_adjacent_cells(current_pos)
        
        # Priority 1: Safe unvisited cells (0)
        safe_cells = []
        for nx, ny in adj_cells:
            cell_ref = f"({nx},{ny})"
            if self.kb.query(f"Safe{cell_ref}") and not self.kb.query(f"Visited{cell_ref}"):
                safe_cells.append((nx, ny))
        
        if safe_cells:
            self.last_reasoning = "Choosing safe unvisited cell (0)"
            return random.choice(safe_cells)
        
        # Priority 2: Already visited cells (1)
        visited_cells = []
        for nx, ny in adj_cells:
            cell_ref = f"({nx},{ny})"
            if self.kb.query(f"Visited{cell_ref}"):
                visited_cells.append((nx, ny))
        
        if visited_cells:
            self.last_reasoning = "No safe unvisited cells, backtracking to visited safe cell (1)"
            return random.choice(visited_cells)
        
        # Priority 3: Take calculated risk with possible dangers
        risk_cells = []
        for nx, ny in adj_cells:
            cell_ref = f"({nx},{ny})"
            if self.kb.query(f"PossibleWumpus{cell_ref}") or self.kb.query(f"PossiblePit{cell_ref}"):
                risk_cells.append((nx, ny))
        
        if risk_cells:
            self.last_reasoning = "No safe cells available, risking move to possible danger cell"
            return random.choice(risk_cells)
        
        return None
    
    def _find_path_to_exit(self, current_pos: Tuple[int, int]) -> Optional[str]:
        x, y = current_pos
        target_x, target_y = 0, 0
        
        if x > target_x and self.kb.query(f"Safe({x-1},{y})"):
            return "MOVE_LEFT"
        elif x < target_x and self.kb.query(f"Safe({x+1},{y})"):
            return "MOVE_RIGHT"
        elif y > target_y and self.kb.query(f"Safe({x},{y-1})"):
            return "MOVE_UP"
        elif y < target_y and self.kb.query(f"Safe({x},{y+1})"):
            return "MOVE_DOWN"
        
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