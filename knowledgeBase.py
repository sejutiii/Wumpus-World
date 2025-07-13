from typing import List, Tuple, Set, Dict  # Add Dict here
from collections import deque

class PropositionalKB:
    def __init__(self, grid_size: int):
        self.grid_size = grid_size
        self.facts = set()  # Known facts: "Safe(1,1)", "Breeze(2,1)", etc.
        self.rules = []     # Inference rules
        self.playing_grid = [["0" for _ in range(grid_size)] for _ in range(grid_size)]
        self.playing_grid[0][0] = "1"  # Agent starts at (0,0), mark as visited
        self.gold_cell = None
        
    def add_fact(self, fact: str):
        """Add a fact to the knowledge base"""
        self.facts.add(fact)
        
    def add_rule(self, premise, conclusion):
        """Add an inference rule: premise → conclusion"""
        self.rules.append((premise, conclusion))
        
    def query(self, fact: str) -> bool:
        """Check if a fact can be inferred"""
        return fact in self.facts
        
    def forward_chain(self):
        """Forward chaining inference"""
        changed = True
        while changed:
            changed = False
            for premise, conclusion in self.rules:
                if self.can_infer(premise) and conclusion not in self.facts:
                    self.facts.add(conclusion)
                    changed = True
                    
    def can_infer(self, premise) -> bool:
        """Check if premise can be satisfied"""
        if isinstance(premise, str):
            return premise in self.facts
        elif isinstance(premise, tuple) and premise[0] == 'AND':
            return all(self.can_infer(p) for p in premise[1:])
        elif isinstance(premise, tuple) and premise[0] == 'OR':
            return any(self.can_infer(p) for p in premise[1:])
        return False
    
    def add_wumpus_rules(self):
        """Add domain-specific rules for Wumpus World"""
        for y in range(self.grid_size):
            for x in range(self.grid_size):
                adj_cells = self._get_adjacent_cells((x, y))
                
                no_breeze = f"NoBreeze({x},{y})"
                for nx, ny in adj_cells:
                    self.add_rule(no_breeze, f"NoPit({nx},{ny})")
                
                no_stench = f"NoStench({x},{y})"
                for nx, ny in adj_cells:
                    self.add_rule(no_stench, f"NoWumpus({nx},{ny})")
                
                if adj_cells:
                    for nx, ny in adj_cells:
                        premise = ('AND', f"NoPit({nx},{ny})", f"NoWumpus({nx},{ny})")
                        self.add_rule(premise, f"Safe({nx},{ny})")
    
    def update_knowledge_base(self, position: Tuple[int, int], percepts: List[str]):
        """Update KB based on current percepts"""
        x, y = position
        current_cell = f"({x},{y})"
        
        if not percepts or "Glitter" in percepts:
            percept = "-" if not percepts else "G"
        elif "Breeze" in percepts and "Stench" in percepts:
            percept = "T"
        elif "Breeze" in percepts:
            percept = "B"
        elif "Stench" in percepts:
            percept = "S"
        else:
            percept = "-"
        
        if percept == '-':
            self.add_fact(f"NoBreeze{current_cell}")
            self.add_fact(f"NoStench{current_cell}")
            self.add_fact(f"Safe{current_cell}")
        
        elif percept == 'B':
            self.add_fact(f"Breeze{current_cell}")
            self.add_fact(f"NoStench{current_cell}")
            adj_cells = self._get_adjacent_cells(position)
            for nx, ny in adj_cells:
                self.add_rule(f"Breeze{current_cell}", f"PossiblePit({nx},{ny})")
        
        elif percept == 'S':
            self.add_fact(f"Stench{current_cell}")
            self.add_fact(f"NoBreeze{current_cell}")
            adj_cells = self._get_adjacent_cells(position)
            for nx, ny in adj_cells:
                self.add_rule(f"Stench{current_cell}", f"PossibleWumpus({nx},{ny})")
        
        elif percept == 'T':
            self.add_fact(f"Breeze{current_cell}")
            self.add_fact(f"Stench{current_cell}")
            adj_cells = self._get_adjacent_cells(position)
            for nx, ny in adj_cells:
                self.add_rule(f"Breeze{current_cell}", f"PossiblePit({nx},{ny})")
                self.add_rule(f"Stench{current_cell}", f"PossibleWumpus({nx},{ny})")
        
        elif percept == 'G':
            self.add_fact(f"Glitter{current_cell}")
            self.add_fact(f"Gold{current_cell}")
            self.gold_cell = position
            self.playing_grid[y][x] = "99"
        
        self.add_fact(f"Visited{current_cell}")
        self.playing_grid[y][x] = "1"
        
        self.forward_chain()
        self.update_playing_grid_from_kb()
    
    def update_playing_grid_from_kb(self):
        """Update playing grid based on KB knowledge"""
        for y in range(self.grid_size):
            for x in range(self.grid_size):
                cell_ref = f"({x},{y})"
                
                if self.query(f"Visited{cell_ref}"):
                    self.playing_grid[y][x] = "1"
                elif self.query(f"Safe{cell_ref}"):
                    self.playing_grid[y][x] = "0"
                elif self.query(f"PossibleWumpus{cell_ref}") and self.query(f"PossiblePit{cell_ref}"):
                    self.playing_grid[y][x] = "-5"
                elif self.query(f"PossibleWumpus{cell_ref}"):
                    self.playing_grid[y][x] = "-1"
                elif self.query(f"PossiblePit{cell_ref}"):
                    self.playing_grid[y][x] = "-2"
    
    def set_gold_found(self, position: Tuple[int, int]):
        x, y = position
        self.playing_grid[y][x] = "99"
        self.gold_cell = position
        self.add_fact(f"Gold({x},{y})")
    
    def has_gold_location(self) -> bool:
        return self.gold_cell is not None
    
    def get_gold_location(self) -> Tuple[int, int]:
        return self.gold_cell
    
    def get_playing_grid(self) -> List[List[str]]:
        return [row[:] for row in self.playing_grid]
    
    def all_cells_visited(self) -> bool:
        for row in self.playing_grid:
            if "0" in row:
                return False
        return True
    
    def _get_adjacent_cells(self, position: Tuple[int, int]) -> List[Tuple[int, int]]:
        x, y = position
        adjacent = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            new_x, new_y = x + dx, y + dy
            if 0 <= new_x < self.grid_size and 0 <= new_y < self.grid_size:
                adjacent.append((new_x, new_y))
        return adjacent
    
    def get_knowledge_summary(self) -> List[Dict]:
        summary = []
        for fact in sorted(self.facts):
            summary.append({
                "type": "fact",
                "content": fact,
                "confidence": 1.0
            })
        return summary