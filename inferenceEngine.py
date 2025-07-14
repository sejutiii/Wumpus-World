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
        
        next_move = self._choose_next_move_with_confidence(current_pos)
        if not next_move:
            self.last_reasoning = "No valid moves available"
            self.last_inference = "NoValidMoves → Stay"
            return "STAY"
        
        nx, ny = next_move
        direction = self._get_direction(current_pos, next_move)
        
        # Enhanced reasoning based on confidence
        pit_conf = self.kb.get_confidence((nx, ny), 'pit')
        wumpus_conf = self.kb.get_confidence((nx, ny), 'wumpus')
        
        if pit_conf == 0.0 and wumpus_conf == 0.0:
            self.last_reasoning = f"Moving to safe cell ({nx},{ny})"
            self.last_inference = f"Safe({nx},{ny}) → Move_{direction}"
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
    
    def _choose_next_move_with_confidence(self, current_pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        adj_cells = self._get_adjacent_cells(current_pos)
        
        # Priority 1: Safe unvisited cells (confidence = 0.0 for both pit and wumpus)
        safe_cells = []
        for nx, ny in adj_cells:
            if (self.kb.get_confidence((nx, ny), 'pit') == 0.0 and 
                self.kb.get_confidence((nx, ny), 'wumpus') == 0.0 and
                not self.kb.query(f"Visited({nx},{ny})")):
                safe_cells.append((nx, ny))
        
        if safe_cells:
            self.last_reasoning = "Choosing safe unvisited cell"
            return random.choice(safe_cells)
        
        # Priority 2: Already visited cells
        visited_cells = []
        for nx, ny in adj_cells:
            if self.kb.query(f"Visited({nx},{ny})"):
                visited_cells.append((nx, ny))
        
        if visited_cells:
            self.last_reasoning = "No safe unvisited cells, backtracking to visited cell"
            return random.choice(visited_cells)
        
        # Priority 3: Low confidence threats (20%)
        low_risk_cells = []
        for nx, ny in adj_cells:
            pit_conf = self.kb.get_confidence((nx, ny), 'pit')
            wumpus_conf = self.kb.get_confidence((nx, ny), 'wumpus')
            if pit_conf == 0.2 or wumpus_conf == 0.2:
                low_risk_cells.append((nx, ny))
        
        if low_risk_cells:
            self.last_reasoning = "Taking low-risk move (20% confidence threat)"
            return random.choice(low_risk_cells)
        
        # Priority 4: Medium confidence threats (50%)
        medium_risk_cells = []
        for nx, ny in adj_cells:
            pit_conf = self.kb.get_confidence((nx, ny), 'pit')
            wumpus_conf = self.kb.get_confidence((nx, ny), 'wumpus')
            if pit_conf == 0.5 or wumpus_conf == 0.5:
                medium_risk_cells.append((nx, ny))
        
        if medium_risk_cells:
            self.last_reasoning = "Taking medium-risk move (50% confidence threat)"
            return random.choice(medium_risk_cells)
        
        # Priority 5: High confidence threats (100%) - last resort
        high_risk_cells = []
        for nx, ny in adj_cells:
            pit_conf = self.kb.get_confidence((nx, ny), 'pit')
            wumpus_conf = self.kb.get_confidence((nx, ny), 'wumpus')
            if pit_conf == 1.0 or wumpus_conf == 1.0:
                high_risk_cells.append((nx, ny))
        
        if high_risk_cells:
            self.last_reasoning = "Last resort: moving to high-risk cell (100% confidence threat)"
            return random.choice(high_risk_cells)
        
        return None
    
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