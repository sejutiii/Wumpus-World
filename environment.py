import random
from typing import List, Tuple, Dict

class WumpusEnvironment:
    """Wumpus World Environment - 10x10 grid implementation"""
    
    def __init__(self):
        self.grid_size = 10
        self.grid = [["." for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        self.wumpus_positions = set()  # Set of (x, y) tuples
        self.wumpus_alive = dict()     # Dict: (x, y) -> bool
        self.gold_position = None
        self.pit_positions = set()
        
    def generate_random_environment(self):
        """Generate a random Wumpus world environment"""
        # Clear the grid
        self.grid = [["." for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        self.pit_positions.clear()
        self.wumpus_positions.clear()
        self.wumpus_alive.clear()
        
        # Place Gold (not at starting position)
        while True:
            x, y = random.randint(0, 9), random.randint(0, 9)
            if (x, y) != (0, 0):
                self.gold_position = (x, y)
                self.grid[y][x] = "G"
                break

        # Place Wumpus (1-3, not at starting, not at gold, not overlapping pits)
        num_wumpus = random.randint(1, 3)
        wumpus_placed = 0
        attempts = 0
        while wumpus_placed < num_wumpus and attempts < 100:
            x, y = random.randint(0, 9), random.randint(0, 9)
            pos = (x, y)
            if (pos != (0, 0) and
                pos != self.gold_position and
                pos not in self.pit_positions and
                pos not in self.wumpus_positions):
                self.wumpus_positions.add(pos)
                self.wumpus_alive[pos] = True
                self.grid[y][x] = "W"
                wumpus_placed += 1
            attempts += 1

        # Place Pits (3-6 pits, not at starting, not at gold, not at wumpus)
        num_pits = random.randint(3, 6)
        pits_placed = 0
        attempts = 0
        while pits_placed < num_pits and attempts < 100:
            x, y = random.randint(0, 9), random.randint(0, 9)
            pos = (x, y)
            if (pos != (0, 0) and 
                pos != self.gold_position and
                pos not in self.pit_positions and
                pos not in self.wumpus_positions):
                self.pit_positions.add(pos)
                self.grid[y][x] = "P"
                pits_placed += 1
            attempts += 1
    
    def load_environment(self, env_data: Dict):
        """Load environment from provided data"""
        if "grid" in env_data:
            grid_data = env_data["grid"]
            self.grid = [[cell for cell in row] for row in grid_data]
            
            # Extract positions from grid
            self.pit_positions.clear()
            self.wumpus_positions.clear()
            self.wumpus_alive.clear()
            for y in range(self.grid_size):
                for x in range(self.grid_size):
                    cell = self.grid[y][x]
                    if "W" in cell:
                        pos = (x, y)
                        self.wumpus_positions.add(pos)
                        self.wumpus_alive[pos] = True
                    elif "G" in cell:
                        self.gold_position = (x, y)
                    elif "P" in cell:
                        self.pit_positions.add((x, y))
    
    def get_percepts(self, position: Tuple[int, int]) -> List[str]:
        """Get percepts at the given position"""
        percepts = []
        x, y = position
        
        # Check for glitter (gold at current position)
        if (x, y) == self.gold_position:
            percepts.append("Glitter")
        
        # Check for breeze (pit in adjacent cell)
        if self._has_adjacent_pit(position):
            percepts.append("Breeze")
        
        # Check for stench (wumpus in adjacent cell)
        if self._has_adjacent_wumpus(position):
            percepts.append("Stench")
        
        return percepts

    def _has_adjacent_pit(self, position: Tuple[int, int]) -> bool:
        """Check if there's a pit in an adjacent cell"""
        adjacent_cells = self._get_adjacent_cells(position)
        return any(cell in self.pit_positions for cell in adjacent_cells)
    
    def _has_adjacent_wumpus(self, position: Tuple[int, int]) -> bool:
        """Check if there's a living wumpus in an adjacent cell"""
        adjacent_cells = self._get_adjacent_cells(position)
        for cell in adjacent_cells:
            if cell in self.wumpus_positions and self.wumpus_alive.get(cell, False):
                return True
        return False

    def _get_adjacent_cells(self, position: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get valid adjacent cells"""
        x, y = position
        adjacent = []
        
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            new_x, new_y = x + dx, y + dy
            if 0 <= new_x < self.grid_size and 0 <= new_y < self.grid_size:
                adjacent.append((new_x, new_y))
        
        return adjacent
    
    def is_valid_position(self, position: Tuple[int, int]) -> bool:
        """Check if position is within grid bounds"""
        x, y = position
        return 0 <= x < self.grid_size and 0 <= y < self.grid_size
    
    def get_cell_contents(self, position: Tuple[int, int]) -> str:
        """Get contents of a specific cell"""
        x, y = position
        if self.is_valid_position(position):
            return self.grid[y][x]
        return ""
    
    def shoot_arrow(self, position: Tuple[int, int], direction: str) -> bool:
        """Shoot arrow in specified direction, return True if any wumpus hit"""
        hit = False
        x, y = position
        while True:
            if direction == "UP":
                y -= 1
            elif direction == "DOWN":
                y += 1
            elif direction == "LEFT":
                x -= 1
            elif direction == "RIGHT":
                x += 1
            
            # Check if arrow is out of bounds
            if not (0 <= x < self.grid_size and 0 <= y < self.grid_size):
                break
            
            # Check if arrow hit any living wumpus
            pos = (x, y)
            if pos in self.wumpus_positions and self.wumpus_alive.get(pos, False):
                self.wumpus_alive[pos] = False
                hit = True
                # Remove 'W' from grid if killed
                self.grid[y][x] = ".",
                # Continue arrow path to allow multi-kill if desired
        return hit

    def get_visible_grid(self, agent_position: Tuple[int, int]) -> List[List[str]]:
        """Get grid representation for display (with agent position marked)"""
        display_grid = [row[:] for row in self.grid]  # Deep copy
        
        # Mark agent position
        agent_x, agent_y = agent_position
        current_cell = display_grid[agent_y][agent_x]
        if current_cell == ".":
            display_grid[agent_y][agent_x] = "A"
        else:
            display_grid[agent_y][agent_x] = "A" + current_cell
        
        return display_grid

    def get_full_grid_state(self) -> Dict:
        """Get complete grid state for debugging/admin view"""
        return {
            "grid": self.grid,
            "wumpus_positions": list(self.wumpus_positions),
            "wumpus_alive": {str(k): v for k, v in self.wumpus_alive.items()},
            "gold_position": self.gold_position,
            "pit_positions": list(self.pit_positions),
            "grid_size": self.grid_size
        }

    def is_dangerous_cell(self, position: Tuple[int, int]) -> bool:
        """Check if a cell contains immediate danger"""
        if position in self.pit_positions:
            return True
        if position in self.wumpus_positions and self.wumpus_alive.get(position, False):
            return True
        return False

    def get_safe_starting_area(self) -> List[Tuple[int, int]]:
        """Get guaranteed safe cells around starting position"""
        # Starting position (0,0) and adjacent cells are guaranteed safe
        safe_cells = [(0, 0)]
        
        # Add adjacent cells if they don't contain dangers
        for pos in self._get_adjacent_cells((0, 0)):
            if not self.is_dangerous_cell(pos):
                safe_cells.append(pos)
        
        return safe_cells