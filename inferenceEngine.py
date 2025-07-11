from typing import Tuple, List, Dict, Optional
import random
from knowledgeBase import KnowledgeBase

class InferenceEngine:
    """Inference Engine using logical reasoning for the Wumpus World AI Agent"""
    
    def __init__(self, knowledge_base: KnowledgeBase):
        self.kb = knowledge_base
        self.last_inference = ""
        self.last_reasoning = ""
        self.visited_positions = []
        self.loop_detection_threshold = 3
        
    def determine_next_action(self, current_pos: Tuple[int, int], percepts: List[str], grid_size: int = 10) -> str:
        """Determine the next action using logical inference"""
        self.last_reasoning = ""
        
        # Check if gold is present and can be grabbed
        if "Glitter" in percepts:
            self.last_reasoning = "Gold detected at current position - grabbing it!"
            self.last_inference = "Glitter(x,y) → Grab"
            return "GRAB"
        
        # If we have gold, try to return to start
        if self.kb.gold_cell and current_pos != (0, 0):
            action = self._find_path_to_exit(current_pos)
            if action:
                self.last_reasoning = "Have gold - returning to exit at (0,0)"
                return action
        
        # Check for wumpus shooting opportunity
        if self._should_shoot_wumpus(current_pos, percepts):
            direction = self._get_wumpus_direction(current_pos)
            if direction:
                self.last_reasoning = f"Wumpus detected in {direction} direction - shooting arrow"
                self.last_inference = "Stench(x,y) ∧ WumpusDirection → Shoot"
                return f"SHOOT_{direction}"
        
        # Forward chaining: infer new knowledge
        self._forward_chaining(current_pos, percepts)
        
        # Backward chaining: determine safe moves
        safe_moves = self._backward_chaining(current_pos, grid_size)
        
        if safe_moves:
            # Choose the best safe move
            best_move = self._choose_best_move(safe_moves, current_pos)
            self.last_reasoning = f"Safe moves available: {safe_moves}. Choosing: {best_move}"
            return best_move
        
        # If no safe moves, use probabilistic reasoning
        probable_safe_moves = self._probabilistic_reasoning(current_pos, grid_size)
        
        if probable_safe_moves:
            best_move = probable_safe_moves[0]
            self.last_reasoning = f"No certain safe moves. Using probabilistic reasoning: {best_move}"
            return best_move
        
        # Last resort: random valid move
        valid_moves = self._get_valid_moves(current_pos, grid_size)
        if valid_moves:
            move = random.choice(valid_moves)
            self.last_reasoning = f"No safe options found. Making random move: {move}"
            return move
        
        self.last_reasoning = "No valid moves available"
        return "STAY"
    
    def _forward_chaining(self, position: Tuple[int, int], percepts: List[str]):
        """Apply forward chaining to infer new knowledge"""
        x, y = position
        
        # Rule: Breeze(x,y) → Pit(adjacent_to(x,y))
        if "Breeze" in percepts:
            adjacent_cells = self._get_adjacent_positions(position, 10)
            for cell in adjacent_cells:
                if cell not in self.kb.visited_cells:
                    self.kb.danger_cells.add(cell)
                    cx, cy = cell
                    self.kb.facts.add(f"PossiblePit({cx},{cy})")
        
        # Rule: ¬Breeze(x,y) → ¬Pit(adjacent_to(x,y))
        if "Breeze" not in percepts:
            adjacent_cells = self._get_adjacent_positions(position, 10)
            for cell in adjacent_cells:
                self.kb.safe_cells.add(cell)
                cx, cy = cell
                self.kb.facts.add(f"Safe({cx},{cy})")
                self.kb.danger_cells.discard(cell)
        
        # Similar rules for Stench and Wumpus
        if "Stench" in percepts and self.kb.wumpus_alive:
            adjacent_cells = self._get_adjacent_positions(position, 10)
            for cell in adjacent_cells:
                if cell not in self.kb.visited_cells:
                    cx, cy = cell
                    self.kb.facts.add(f"PossibleWumpus({cx},{cy})")
        
        if "Stench" not in percepts or not self.kb.wumpus_alive:
            adjacent_cells = self._get_adjacent_positions(position, 10)
            for cell in adjacent_cells:
                if self.kb.wumpus_cell != cell:
                    self.kb.safe_cells.add(cell)
                    cx, cy = cell
                    self.kb.facts.add(f"SafeFromWumpus({cx},{cy})")
    
    def _backward_chaining(self, position: Tuple[int, int], grid_size: int) -> List[str]:
        """Apply backward chaining to find safe moves"""
        safe_moves = []
        
        # Goal: Safe(next_position)
        possible_moves = ["UP", "DOWN", "LEFT", "RIGHT"]
        
        for move in possible_moves:
            next_pos = self._get_next_position(position, move, grid_size)
            if next_pos and self._is_provably_safe(next_pos):
                safe_moves.append(f"MOVE_{move}")
        
        return safe_moves
    
    def _is_provably_safe(self, position: Tuple[int, int]) -> bool:
        """Check if a position is provably safe using resolution"""
        # A position is provably safe if:
        # 1. It's already marked as safe
        # 2. We can prove no pits and no wumpus
        
        if position in self.kb.safe_cells:
            return True
        
        if position in self.kb.visited_cells:
            return True
        
        if position in self.kb.danger_cells:
            return False
        
        # Check if we can prove safety through adjacent cells
        adjacent_visited = [pos for pos in self._get_adjacent_positions(position, 10) 
                           if pos in self.kb.visited_cells]
        
        for adj_pos in adjacent_visited:
            x, y = adj_pos
            # If adjacent cell has no breeze, this cell is safe from pits
            if f"¬Breeze({x},{y})" in self.kb.facts:
                # If also safe from wumpus, it's completely safe
                if not self.kb.wumpus_alive or f"SafeFromWumpus({position[0]},{position[1]})" in self.kb.facts:
                    return True
        
        return False
    
    def _probabilistic_reasoning(self, position: Tuple[int, int], grid_size: int) -> List[str]:
        """Use probabilistic reasoning when certain inference fails"""
        moves_with_probability = []
        possible_moves = ["UP", "DOWN", "LEFT", "RIGHT"]
        
        for move in possible_moves:
            next_pos = self._get_next_position(position, move, grid_size)
            if next_pos:
                safety_probability = self._calculate_safety_probability(next_pos)
                if safety_probability > 0.3:  # Threshold for acceptable risk
                    moves_with_probability.append((f"MOVE_{move}", safety_probability))
        
        # Sort by probability (highest first)
        moves_with_probability.sort(key=lambda x: x[1], reverse=True)
        
        return [move for move, prob in moves_with_probability]
    
    def _calculate_safety_probability(self, position: Tuple[int, int]) -> float:
        """Calculate probability that a position is safe"""
        if position in self.kb.safe_cells:
            return 1.0
        
        if position in self.kb.danger_cells:
            return 0.1
        
        if position in self.kb.visited_cells:
            return 1.0
        
        # Base probability for unknown cells
        base_probability = 0.7
        
        # Adjust based on adjacent cells
        adjacent_positions = self._get_adjacent_positions(position, 10)
        safe_adjacent = sum(1 for pos in adjacent_positions if pos in self.kb.safe_cells)
        total_adjacent = len(adjacent_positions)
        
        if total_adjacent > 0:
            safety_factor = safe_adjacent / total_adjacent
            return base_probability * (0.5 + 0.5 * safety_factor)
        
        return base_probability
    
    def _choose_best_move(self, safe_moves: List[str], current_pos: Tuple[int, int]) -> str:
        """Choose the best move from available safe moves"""
        # Avoid loops
        moves_without_loops = []
        
        for move in safe_moves:
            next_pos = self._get_next_position(current_pos, move.split("_")[1], 10)
            if not self._would_create_loop(next_pos):
                moves_without_loops.append(move)
        
        if moves_without_loops:
            safe_moves = moves_without_loops
        
        # Prefer moves towards unvisited safe areas
        if len(safe_moves) == 1:
            return safe_moves[0]
        
        # Score moves based on exploration potential
        scored_moves = []
        for move in safe_moves:
            direction = move.split("_")[1]
            next_pos = self._get_next_position(current_pos, direction, 10)
            score = self._calculate_exploration_score(next_pos)
            scored_moves.append((move, score))
        
        # Sort by score (highest first)
        scored_moves.sort(key=lambda x: x[1], reverse=True)
        
        return scored_moves[0][0]
    
    def _calculate_exploration_score(self, position: Tuple[int, int]) -> float:
        """Calculate exploration score for a position"""
        if position in self.kb.visited_cells:
            return 0.0
        
        # Higher score for positions that might reveal new information
        adjacent_unvisited = [pos for pos in self._get_adjacent_positions(position, 10)
                            if pos not in self.kb.visited_cells]
        
        return len(adjacent_unvisited) + random.random() * 0.1
    
    def _would_create_loop(self, position: Tuple[int, int]) -> bool:
        """Check if moving to position would create a loop"""
        recent_positions = self.visited_positions[-self.loop_detection_threshold:]
        return recent_positions.count(position) >= 2
    
    def _should_shoot_wumpus(self, position: Tuple[int, int], percepts: List[str]) -> bool:
        """Determine if the agent should shoot the wumpus"""
        return ("Stench" in percepts and 
                self.kb.wumpus_alive and 
                self._get_wumpus_direction(position) is not None)
    
    def _get_wumpus_direction(self, position: Tuple[int, int]) -> Optional[str]:
        """Get direction to shoot wumpus if it can be determined"""
        x, y = position
        
        # Check each direction for possible wumpus
        directions = [
            ("UP", (x, y-1)),
            ("DOWN", (x, y+1)),
            ("LEFT", (x-1, y)),
            ("RIGHT", (x+1, y))
        ]
        
        for direction, pos in directions:
            if pos in self.kb.danger_cells:
                px, py = pos
                if f"PossibleWumpus({px},{py})" in self.kb.facts:
                    return direction
        
        return None
    
    def _find_path_to_exit(self, current_pos: Tuple[int, int]) -> Optional[str]:
        """Find path back to exit (0,0) using A* algorithm"""
        # Simple pathfinding - move towards (0,0) via safe cells
        x, y = current_pos
        target_x, target_y = 0, 0
        
        # Prefer moves that get us closer to exit
        if x > target_x and self._is_provably_safe((x-1, y)):
            return "MOVE_LEFT"
        elif x < target_x and self._is_provably_safe((x+1, y)):
            return "MOVE_RIGHT"
        elif y > target_y and self._is_provably_safe((x, y-1)):
            return "MOVE_UP"
        elif y < target_y and self._is_provably_safe((x, y+1)):
            return "MOVE_DOWN"
        
        return None
    
    def _get_valid_moves(self, position: Tuple[int, int], grid_size: int) -> List[str]:
        """Get all valid moves from current position"""
        moves = []
        possible_moves = ["UP", "DOWN", "LEFT", "RIGHT"]
        
        for move in possible_moves:
            next_pos = self._get_next_position(position, move, grid_size)
            if next_pos:
                moves.append(f"MOVE_{move}")
        
        return moves
    
    def _get_next_position(self, position: Tuple[int, int], direction: str, grid_size: int) -> Optional[Tuple[int, int]]:
        """Get next position given direction"""
        x, y = position
        
        if direction == "UP" and y > 0:
            return (x, y - 1)
        elif direction == "DOWN" and y < grid_size - 1:
            return (x, y + 1)
        elif direction == "LEFT" and x > 0:
            return (x - 1, y)
        elif direction == "RIGHT" and x < grid_size - 1:
            return (x + 1, y)
        
        return None
    
    def _get_adjacent_positions(self, position: Tuple[int, int], grid_size: int) -> List[Tuple[int, int]]:
        """Get all valid adjacent positions"""
        x, y = position
        adjacent = []
        
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            new_x, new_y = x + dx, y + dy
            if 0 <= new_x < grid_size and 0 <= new_y < grid_size:
                adjacent.append((new_x, new_y))
        
        return adjacent
    
    def get_last_inference(self) -> str:
        """Get the last logical inference made"""
        return self.last_inference
    
    def get_last_reasoning(self) -> str:
        """Get the last reasoning process"""
        return self.last_reasoning