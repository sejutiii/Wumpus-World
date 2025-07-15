from typing import List, Tuple, Set, Dict
from collections import deque
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PropositionalKB:
    def __init__(self, grid_size: int):
        self.grid_size = grid_size
        self.facts = set()
        self.rules = []
        self.playing_grid = [["0" for _ in range(grid_size)] for _ in range(grid_size)]
        self.playing_grid[0][0] = "1"
        self.gold_cell = None
        self.cell_confidence = {}  # (x,y) -> {'pit': confidence, 'wumpus': confidence}
        self.has_arrow = True  # NEW: Track if arrow is available
        self.arrow_used = False  # NEW: Track if arrow has been used
        self.last_arrow_target = None

    def add_fact(self, fact: str):
        """Add a fact to the knowledge base"""
        logger.debug(f"Adding fact: {fact}")
        self.facts.add(fact)

    def add_rule(self, premise, conclusion):
        """Add an inference rule: premise → conclusion"""
        logger.debug(f"Adding rule: {premise} → {conclusion}")
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
        logger.debug(f"Setting {threat_type} confidence at {position} to {confidence}")
        self.cell_confidence[position][threat_type] = confidence

    def forward_chain(self):
        """Forward chaining inference"""
        changed = True
        while changed:
            changed = False
            for premise, conclusion in self.rules:
                if self.can_infer(premise) and conclusion not in self.facts:
                    logger.debug(f"Inferring {conclusion} from {premise}")
                    self.facts.add(conclusion)
                    changed = True

    def can_infer(self, premise) -> bool:
        """Check if premise can be satisfied"""
        return (isinstance(premise, str) and premise in self.facts) or \
               (isinstance(premise, tuple) and premise[0] == 'AND' and all(self.can_infer(p) for p in premise[1:])) or \
               (isinstance(premise, tuple) and premise[0] == 'OR' and any(self.can_infer(p) for p in premise[1:]))

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
        
        logger.info(f"Updating KB at {position} with percepts: {percepts}")
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
        logger.debug(f"KB updated, confidence for (1,2): {self.get_confidence((1,2), 'wumpus')}")

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
        visited_or_safe_cells = [pos for pos in adj_cells if self.query(f"Visited({pos[0]},{pos[1]})") or self.query(f"Safe({pos[0]},{pos[1]})")]

        # If all adjacent cells except one are visited or safe, mark the remaining cell as definite pit
        if len(unvisited_cells) == 1 and len(visited_or_safe_cells) == (len(adj_cells) - 1):
            nx, ny = unvisited_cells[0]
            self.set_confidence((nx, ny), 'pit', 1.0)
            self.add_fact(f"DefinitePit({nx},{ny})")
            self._propagate_threat((nx, ny), 'pit')
        else:
            # Mark all unvisited cells as possible pits with 0.5 confidence
            for nx, ny in unvisited_cells:
                if self.get_confidence((nx, ny), 'pit') < 1.0 and self.get_confidence((nx, ny), 'wumpus') < 1.0:
                    self.set_confidence((nx, ny), 'pit', 0.5)
                    self.add_fact(f"PossiblePit({nx},{ny})")

    def _process_stench(self, position: Tuple[int, int]):
        """Process stench percept with logical deduction"""
        adj_cells = self._get_adjacent_cells(position)
        unvisited_cells = [pos for pos in adj_cells if not self.query(f"Visited({pos[0]},{pos[1]})")]

        possible_wumpus = [pos for pos in adj_cells if self.get_confidence(pos, 'wumpus') == 0.5]

        if len(possible_wumpus) == 1:
            nx, ny = possible_wumpus[0]
            self.set_confidence((nx, ny), 'wumpus', 1.0)
            self.add_fact(f"DefiniteWumpus({nx},{ny})")
            self._propagate_threat((nx, ny), 'wumpus')
        elif len(unvisited_cells) == 1:
            nx, ny = unvisited_cells[0]
            self.set_confidence((nx, ny), 'wumpus', 1.0)
            self.add_fact(f"DefiniteWumpus({nx},{ny})")
            self._propagate_threat((nx, ny), 'wumpus')
        else:
            for nx, ny in unvisited_cells:
                if self.get_confidence((nx, ny), 'pit') == 1.0 or self.get_confidence((nx, ny), 'wumpus') == 1.0:
                    continue
                if not self.query(f"Safe({nx},{ny})") or self.get_confidence((nx, ny), 'wumpus') == 0.0:
                    self.set_confidence((nx, ny), 'wumpus', 0.5)
                    self.add_fact(f"PossibleWumpus({nx},{ny})")
                    logger.debug(f"Marked PossibleWumpus at ({nx},{ny}) due to stench at {position}")

    def _process_breeze_and_stench(self, position: Tuple[int, int]):
        """Process both breeze and stench percepts"""
        adj_cells = self._get_adjacent_cells(position)
        unvisited_cells = [pos for pos in adj_cells if not self.query(f"Visited({pos[0]},{pos[1]})")]
    
        for nx, ny in unvisited_cells:
            if self.get_confidence((nx, ny), 'pit') == 1.0 or self.get_confidence((nx, ny), 'wumpus') == 1.0:
                continue
            if not self.query(f"Safe({nx},{ny})"):
                self.set_confidence((nx, ny), 'pit', 0.5)
                self.set_confidence((nx, ny), 'wumpus', 0.5)
                self.add_fact(f"PossiblePit({nx},{ny})")
                self.add_fact(f"PossibleWumpus({nx},{ny})")

    def _propagate_threat(self, position: Tuple[int, int], threat_type: str):
        """Propagate threat confidence to adjacent unvisited cells"""
        adj_cells = self._get_adjacent_cells(position)
        for nx, ny in adj_cells:
            if not self.query(f"Visited({nx},{ny})") and not self.query(f"Safe({nx},{ny})"):
                if threat_type == 'pit' and self.get_confidence((nx, ny), 'pit') < 0.5:
                    self.set_confidence((nx, ny), 'pit', 0.5)
                    self.add_fact(f"PossiblePit({nx},{ny})")
                    logger.debug(f"Propagated PossiblePit to ({nx},{ny}) from {position}")
                elif threat_type == 'wumpus' and self.get_confidence((nx, ny), 'wumpus') < 0.5:
                    self.set_confidence((nx, ny), 'wumpus', 0.5)
                    self.add_fact(f"PossibleWumpus({nx},{ny})")
                    logger.debug(f"Propagated PossibleWumpus to ({nx},{ny}) from {position}")

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
                    self.playing_grid[y][x] = "-1"  # Possible wumpus"

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
        
        for pos, threats in self.cell_confidence.items():
            for threat_type, confidence in threats.items():
                if confidence > 0:
                    summary.append({
                        "type": "confidence",
                        "content": f"{threat_type.capitalize()}({pos[0]},{pos[1]})",
                        "confidence": confidence
                    })
        
        return summary
    
    def use_arrow(self, target_pos: Tuple[int, int]) -> None:
        """Use the arrow on target position"""
        self.has_arrow = False
        self.arrow_used = True
        self.last_arrow_target = target_pos
        logger.info(f"Arrow used on position {target_pos}")

    def process_arrow_result(self, target_pos: Tuple[int, int], heard_scream: bool) -> None:
        """Process the result of shooting the arrow"""
        x, y = target_pos
        if heard_scream:
            # Wumpus was killed
            self.set_confidence(target_pos, 'wumpus', 0.0)
            self.add_fact(f"Safe({x},{y})")
            self.add_fact(f"WumpusKilled({x},{y})")
            logger.info(f"Wumpus killed at {target_pos}, cell is now safe")
        else:
            # No scream - this could mean:
            # 1. Cell was safe (no wumpus)
            # 2. Cell has a pit (if it also has stench and breeze)
            
            # Check if this cell had both stench and breeze indicators
            had_both_threats = (self.get_confidence(target_pos, 'pit') > 0 and 
                              self.get_confidence(target_pos, 'wumpus') > 0)
            
            if had_both_threats:
                # Ambiguous case - could be pit since no wumpus
                # Keep pit confidence, remove wumpus confidence
                self.set_confidence(target_pos, 'wumpus', 0.0)
                logger.info(f"No scream at {target_pos} - could be pit (ambiguous case)")
            else:
                # Cell was safe from the beginning
                self.set_confidence(target_pos, 'wumpus', 0.0)
                self.set_confidence(target_pos, 'pit', 0.0)
                self.add_fact(f"Safe({x},{y})")
                logger.info(f"No scream at {target_pos} - cell was safe")

    def can_reach_unvisited_safely(self, current_pos: Tuple[int, int]) -> bool:
        """Check if there's a path to any unvisited cell without going through definite threats"""
        from collections import deque
        
        queue = deque([current_pos])
        visited = {current_pos}
        max_depth = 15  # Reasonable search depth
        
        while queue:
            pos = queue.popleft()
            
            # Check if this position leads to unvisited safe cells
            for adj_pos in self._get_adjacent_cells(pos):
                if adj_pos in visited:
                    continue
                    
                x, y = adj_pos
                
                # If it's an unvisited safe cell, we can reach it
                if (not self.query(f"Visited({x},{y})") and 
                    (self.query(f"Safe({x},{y})") or 
                     (self.get_confidence(adj_pos, 'pit') < 0.1 and 
                      self.get_confidence(adj_pos, 'wumpus') < 0.1))):
                    return True
                
                # If it's a safe path, add to queue for further exploration
                if (self.query(f"Safe({x},{y})") or 
                    self.query(f"Visited({x},{y})") or
                    (self.get_confidence(adj_pos, 'pit') < 0.1 and 
                     self.get_confidence(adj_pos, 'wumpus') < 0.1)):
                    visited.add(adj_pos)
                    queue.append(adj_pos)
        
        return False

    def get_arrow_targets(self, current_pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get possible arrow targets (adjacent cells with possible/definite wumpus)"""
        if not self.has_arrow:
            return []
        
        targets = []
        for adj_pos in self._get_adjacent_cells(current_pos):
            x, y = adj_pos
            wumpus_conf = self.get_confidence(adj_pos, 'wumpus')
            
            # Target cells with possible or definite wumpus
            if wumpus_conf >= 0.5 and not self.query(f"Visited({x},{y})"):
                targets.append(adj_pos)
        
        return targets