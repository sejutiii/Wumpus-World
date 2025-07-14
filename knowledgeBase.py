from typing import List, Tuple, Set, Dict
from collections import deque

class PropositionalKB:
    def __init__(self, grid_size: int):
        self.grid_size = grid_size
        self.facts = set()
        self.rules = []
        self.playing_grid = [["0" for _ in range(grid_size)] for _ in range(grid_size)]
        self.playing_grid[0][0] = "1"
        self.gold_cell = None
        
        # Confidence tracking for cells
        self.cell_confidence = {}  # (x,y) -> {'pit': confidence, 'wumpus': confidence}
        
    def add_fact(self, fact: str):
        """Add a fact to the knowledge base"""
        self.facts.add(fact)
        
    def add_rule(self, premise, conclusion):
        """Add an inference rule: premise → conclusion"""
        self.rules.append((premise, conclusion))
        
    def query(self, fact: str) -> bool:
        """Check if a fact can be inferred"""
        return fact in self.facts
        
    def get_confidence(self, position: Tuple[int, int], threat_type: str) -> float:
        """Get confidence level for a threat at position"""
        if position not in self.cell_confidence:
            return 0.0
        return self.cell_confidence[position].get(threat_type, 0.0)
    
    def set_confidence(self, position: Tuple[int, int], threat_type: str, confidence: float):
        """Set confidence level for a threat at position"""
        if position not in self.cell_confidence:
            self.cell_confidence[position] = {'pit': 0.0, 'wumpus': 0.0}
        self.cell_confidence[position][threat_type] = confidence
        
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
        """Update KB based on current percepts with enhanced logical deduction"""
        x, y = position
        current_cell = f"({x},{y})"
        
        # Determine percept type
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
        
        # Process percept and update facts
        if percept == '-':
            self.add_fact(f"NoBreeze{current_cell}")
            self.add_fact(f"NoStench{current_cell}")
            self.add_fact(f"Safe{current_cell}")
            self._mark_adjacent_safe(position)
        
        elif percept == 'B':
            self.add_fact(f"Breeze{current_cell}")
            self.add_fact(f"NoStench{current_cell}")
            self._process_breeze(position)
        
        elif percept == 'S':
            self.add_fact(f"Stench{current_cell}")
            self.add_fact(f"NoBreeze{current_cell}")
            self._process_stench(position)
        
        elif percept == 'T':
            self.add_fact(f"Breeze{current_cell}")
            self.add_fact(f"Stench{current_cell}")
            self._process_breeze_and_stench(position)
        
        elif percept == 'G':
            self.add_fact(f"Glitter{current_cell}")
            self.add_fact(f"Gold{current_cell}")
            self.gold_cell = position
            self.playing_grid[y][x] = "99"
        
        self.add_fact(f"Visited{current_cell}")
        self.playing_grid[y][x] = "1"
        
        self.forward_chain()
        self.update_playing_grid_from_kb()
    
    def _mark_adjacent_safe(self, position: Tuple[int, int]):
        """Mark all adjacent cells as safe"""
        adj_cells = self._get_adjacent_cells(position)
        for nx, ny in adj_cells:
            self.add_fact(f"Safe({nx},{ny})")
            self.set_confidence((nx, ny), 'pit', 0.0)
            self.set_confidence((nx, ny), 'wumpus', 0.0)
    
    def _process_breeze(self, position: Tuple[int, int]):
        """Process breeze percept with logical deduction"""
        adj_cells = self._get_adjacent_cells(position)
        unvisited_cells = [pos for pos in adj_cells if not self.query(f"Visited({pos[0]},{pos[1]})")]
        
        # Check if any adjacent cell is already marked as definite pit
        definite_pits = [pos for pos in adj_cells if self.get_confidence(pos, 'pit') == 1.0]
        
        if definite_pits:
            # We already know where the pit is, lower confidence for others
            for nx, ny in unvisited_cells:
                if (nx, ny) not in definite_pits:
                    current_conf = self.get_confidence((nx, ny), 'pit')
                    if current_conf > 0:
                        self.set_confidence((nx, ny), 'pit', 0.2)  # Lower confidence
        else:
            # Check if any adjacent cell was previously marked as possible pit
            possible_pits = [pos for pos in adj_cells if self.get_confidence(pos, 'pit') == 0.5]
            
            if len(possible_pits) == 1:
                # Only one possible pit, mark it as definite
                nx, ny = possible_pits[0]
                self.set_confidence((nx, ny), 'pit', 1.0)
                self.add_fact(f"DefinitePit({nx},{ny})")
            elif len(unvisited_cells) == 1:
                # Only one unvisited cell, must be the pit
                nx, ny = unvisited_cells[0]
                self.set_confidence((nx, ny), 'pit', 1.0)
                self.add_fact(f"DefinitePit({nx},{ny})")
            else:
                # Multiple possibilities, mark all as possible pits
                for nx, ny in unvisited_cells:
                    if not self.query(f"Safe({nx},{ny})"):
                        self.set_confidence((nx, ny), 'pit', 0.5)
                        self.add_fact(f"PossiblePit({nx},{ny})")
    
    def _process_stench(self, position: Tuple[int, int]):
        """Process stench percept with logical deduction"""
        adj_cells = self._get_adjacent_cells(position)
        unvisited_cells = [pos for pos in adj_cells if not self.query(f"Visited({pos[0]},{pos[1]})")]
        
        # Check if any adjacent cell is already marked as definite wumpus
        definite_wumpus = [pos for pos in adj_cells if self.get_confidence(pos, 'wumpus') == 1.0]
        
        if definite_wumpus:
            # We already know where the wumpus is, lower confidence for others
            for nx, ny in unvisited_cells:
                if (nx, ny) not in definite_wumpus:
                    current_conf = self.get_confidence((nx, ny), 'wumpus')
                    if current_conf > 0:
                        self.set_confidence((nx, ny), 'wumpus', 0.2)  # Lower confidence
        else:
            # Check if any adjacent cell was previously marked as possible wumpus
            possible_wumpus = [pos for pos in adj_cells if self.get_confidence(pos, 'wumpus') == 0.5]
            
            if len(possible_wumpus) == 1:
                # Only one possible wumpus, mark it as definite
                nx, ny = possible_wumpus[0]
                self.set_confidence((nx, ny), 'wumpus', 1.0)
                self.add_fact(f"DefiniteWumpus({nx},{ny})")
            elif len(unvisited_cells) == 1:
                # Only one unvisited cell, must be the wumpus
                nx, ny = unvisited_cells[0]
                self.set_confidence((nx, ny), 'wumpus', 1.0)
                self.add_fact(f"DefiniteWumpus({nx},{ny})")
            else:
                # Multiple possibilities, mark all as possible wumpus
                for nx, ny in unvisited_cells:
                    if not self.query(f"Safe({nx},{ny})"):
                        self.set_confidence((nx, ny), 'wumpus', 0.5)
                        self.add_fact(f"PossibleWumpus({nx},{ny})")
    
    def _process_breeze_and_stench(self, position: Tuple[int, int]):
        """Process both breeze and stench percepts"""
        adj_cells = self._get_adjacent_cells(position)
        unvisited_cells = [pos for pos in adj_cells if not self.query(f"Visited({pos[0]},{pos[1]})")]
        
        # Check for definite threats
        definite_pits = [pos for pos in adj_cells if self.get_confidence(pos, 'pit') == 1.0]
        definite_wumpus = [pos for pos in adj_cells if self.get_confidence(pos, 'wumpus') == 1.0]
        
        if definite_pits:
            # We know where pit is, remaining unvisited cells are possible wumpus
            for nx, ny in unvisited_cells:
                if (nx, ny) not in definite_pits:
                    self.set_confidence((nx, ny), 'wumpus', 0.5)
                    self.add_fact(f"PossibleWumpus({nx},{ny})")
        
        elif definite_wumpus:
            # We know where wumpus is, remaining unvisited cells are possible pits
            for nx, ny in unvisited_cells:
                if (nx, ny) not in definite_wumpus:
                    self.set_confidence((nx, ny), 'pit', 0.5)
                    self.add_fact(f"PossiblePit({nx},{ny})")
        
        else:
            # No definite knowledge, mark all as possible threats
            for nx, ny in unvisited_cells:
                if not self.query(f"Safe({nx},{ny})"):
                    self.set_confidence((nx, ny), 'pit', 0.5)
                    self.set_confidence((nx, ny), 'wumpus', 0.5)
                    self.add_fact(f"PossiblePit({nx},{ny})")
                    self.add_fact(f"PossibleWumpus({nx},{ny})")
    
    def update_playing_grid_from_kb(self):
        """Update playing grid based on KB knowledge and confidence"""
        for y in range(self.grid_size):
            for x in range(self.grid_size):
                cell_ref = f"({x},{y})"
                
                if self.query(f"Visited{cell_ref}"):
                    self.playing_grid[y][x] = "1"
                elif self.query(f"Safe{cell_ref}"):
                    self.playing_grid[y][x] = "0"
                elif self.get_confidence((x, y), 'pit') == 1.0:
                    self.playing_grid[y][x] = "-4"  # Definite pit
                elif self.get_confidence((x, y), 'wumpus') == 1.0:
                    self.playing_grid[y][x] = "-3"  # Definite wumpus
                elif self.get_confidence((x, y), 'pit') == 0.5 and self.get_confidence((x, y), 'wumpus') == 0.5:
                    self.playing_grid[y][x] = "-5"  # Could be either
                elif self.get_confidence((x, y), 'pit') == 0.5:
                    self.playing_grid[y][x] = "-2"  # Possible pit
                elif self.get_confidence((x, y), 'wumpus') == 0.5:
                    self.playing_grid[y][x] = "-1"  # Possible wumpus
                elif self.get_confidence((x, y), 'pit') == 0.2 or self.get_confidence((x, y), 'wumpus') == 0.2:
                    self.playing_grid[y][x] = "-6"  # Low confidence threat
    
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
        
        # Add confidence information
        for pos, threats in self.cell_confidence.items():
            for threat_type, confidence in threats.items():
                if confidence > 0:
                    summary.append({
                        "type": "confidence",
                        "content": f"{threat_type.capitalize()}({pos[0]},{pos[1]})",
                        "confidence": confidence
                    })
        
        return summary