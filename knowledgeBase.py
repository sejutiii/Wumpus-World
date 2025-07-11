from typing import Dict, List, Set, Tuple
import json

class KnowledgeBase:
    """Knowledge Base for the Wumpus World AI Agent using Propositional Logic"""
    
    def __init__(self):
        self.facts: Set[str] = set()
        self.rules: List[str] = []
        self.visited_cells: Set[Tuple[int, int]] = set()
        self.safe_cells: Set[Tuple[int, int]] = set()
        self.danger_cells: Set[Tuple[int, int]] = set()
        self.pit_cells: Set[Tuple[int, int]] = set()
        self.wumpus_cell: Tuple[int, int] = None
        self.gold_cell: Tuple[int, int] = None
        self.wumpus_alive = True
        
        # Initialize basic rules
        self._initialize_rules()
    
    def _initialize_rules(self):
        """Initialize basic logical rules for the Wumpus World"""
        self.rules = [
            "Breeze(x,y) → Pit(adjacent_to(x,y))",
            "Stench(x,y) → Wumpus(adjacent_to(x,y))",
            "¬Breeze(x,y) → ¬Pit(adjacent_to(x,y))",
            "¬Stench(x,y) → ¬Wumpus(adjacent_to(x,y))",
            "Glitter(x,y) → Gold(x,y)",
            "Visit(x,y) ∧ ¬Death → Safe(x,y)"
        ]
    
    def add_percepts(self, position: Tuple[int, int], percepts: List[str]):
        """Add percepts from the current position to the knowledge base"""
        x, y = position
        self.visited_cells.add(position)
        self.safe_cells.add(position)
        
        # Add percept facts
        for percept in percepts:
            if percept == "Breeze":
                self.facts.add(f"Breeze({x},{y})")
                self._infer_pits_from_breeze(position)
            elif percept == "Stench":
                self.facts.add(f"Stench({x},{y})")
                self._infer_wumpus_from_stench(position)
            elif percept == "Glitter":
                self.facts.add(f"Glitter({x},{y})")
                self.gold_cell = position
            elif percept == "Bump":
                self.facts.add(f"Bump({x},{y})")
            elif percept == "Scream":
                self.facts.add(f"Scream")
                self.wumpus_alive = False
        
        # If no breeze, adjacent cells are safe from pits
        if "Breeze" not in percepts:
            self.facts.add(f"¬Breeze({x},{y})")
            self._infer_safe_from_no_breeze(position)
        
        # If no stench, adjacent cells are safe from wumpus
        if "Stench" not in percepts:
            self.facts.add(f"¬Stench({x},{y})")
            self._infer_safe_from_no_stench(position)
    
    def _infer_pits_from_breeze(self, position: Tuple[int, int]):
        """Infer possible pit locations from breeze"""
        adjacent_cells = self._get_adjacent_cells(position)
        unknown_adjacent = [cell for cell in adjacent_cells 
                          if cell not in self.visited_cells and cell not in self.safe_cells]
        
        for cell in unknown_adjacent:
            self.danger_cells.add(cell)
            x, y = cell
            self.facts.add(f"PossiblePit({x},{y})")
    
    def _infer_wumpus_from_stench(self, position: Tuple[int, int]):
        """Infer possible wumpus location from stench"""
        if not self.wumpus_alive:
            return
            
        adjacent_cells = self._get_adjacent_cells(position)
        unknown_adjacent = [cell for cell in adjacent_cells 
                          if cell not in self.visited_cells and cell not in self.safe_cells]
        
        for cell in unknown_adjacent:
            self.danger_cells.add(cell)
            x, y = cell
            self.facts.add(f"PossibleWumpus({x},{y})")
    
    def _infer_safe_from_no_breeze(self, position: Tuple[int, int]):
        """Infer safe cells from absence of breeze"""
        adjacent_cells = self._get_adjacent_cells(position)
        for cell in adjacent_cells:
            if cell not in self.pit_cells:
                self.safe_cells.add(cell)
                x, y = cell
                self.facts.add(f"Safe({x},{y})")
                # Remove from danger if it was there
                self.danger_cells.discard(cell)
    
    def _infer_safe_from_no_stench(self, position: Tuple[int, int]):
        """Infer safe cells from absence of stench"""
        if not self.wumpus_alive:
            return
            
        adjacent_cells = self._get_adjacent_cells(position)
        for cell in adjacent_cells:
            if self.wumpus_cell != cell:
                self.safe_cells.add(cell)
                x, y = cell
                self.facts.add(f"SafeFromWumpus({x},{y})")
    
    def _get_adjacent_cells(self, position: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get valid adjacent cells"""
        x, y = position
        adjacent = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            new_x, new_y = x + dx, y + dy
            if 0 <= new_x < 10 and 0 <= new_y < 10:
                adjacent.append((new_x, new_y))
        return adjacent
    
    def add_fact(self, fact: str):
        """Add a fact to the knowledge base"""
        self.facts.add(fact)
        
        if fact == "WumpusKilled":
            self.wumpus_alive = False
    
    def is_safe(self, position: Tuple[int, int]) -> bool:
        """Check if a position is known to be safe"""
        return position in self.safe_cells
    
    def is_dangerous(self, position: Tuple[int, int]) -> bool:
        """Check if a position is known to be dangerous"""
        return position in self.danger_cells
    
    def get_safe_unvisited_cells(self) -> List[Tuple[int, int]]:
        """Get list of safe cells that haven't been visited"""
        return [cell for cell in self.safe_cells if cell not in self.visited_cells]
    
    def get_knowledge_summary(self) -> List[Dict]:
        """Get a summary of current knowledge for the UI"""
        summary = []
        
        # Add facts
        for fact in sorted(self.facts):
            summary.append({
                "type": "fact",
                "content": fact,
                "confidence": 1.0
            })
        
        # Add inferred safe cells
        for cell in self.safe_cells:
            summary.append({
                "type": "inference",
                "content": f"Safe({cell[0]},{cell[1]})",
                "confidence": 1.0
            })
        
        # Add possible dangers
        for cell in self.danger_cells:
            summary.append({
                "type": "inference",
                "content": f"Dangerous({cell[0]},{cell[1]})",
                "confidence": 0.5
            })
        
        # Add wumpus status
        summary.append({
            "type": "fact",
            "content": f"WumpusAlive: {self.wumpus_alive}",
            "confidence": 1.0
        })
        
        return summary
    
    def get_visited_cells(self) -> Set[Tuple[int, int]]:
        """Get all visited cells"""
        return self.visited_cells.copy()
    
    def has_gold_location(self) -> bool:
        """Check if gold location is known"""
        return self.gold_cell is not None
    
    def get_gold_location(self) -> Tuple[int, int]:
        """Get gold location if known"""
        return self.gold_cell