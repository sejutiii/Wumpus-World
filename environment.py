from typing import List, Tuple, Set
import random

class WumpusEnvironment:
    def __init__(self, grid_size: int = 10):
        self.grid_size = grid_size
        self.grid = None
        self.percepts_grid = None
        self.last_action_result = None 
        
    def load_default_environment(self):
        """Generate a random environment instead of loading from file"""
        self.generate_random_environment()
        
    def generate_random_environment(self):
        """Generate a random environment with 1-3 Wumpuses, 3-6 pits, and 1 gold"""
        # Initialize empty grid
        self.grid = [["-" for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        self.percepts_grid = [["-" for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        
        # Place gold at a random position (not (0,0))
        gold_positions = [(x, y) for x in range(self.grid_size) for y in range(self.grid_size) if (x, y) != (0, 0)]
        gold_pos = random.choice(gold_positions)
        self.grid[gold_pos[1]][gold_pos[0]] = "G"
        self.percepts_grid[gold_pos[1]][gold_pos[0]] = "G"
        
        # Place 1-3 Wumpuses at random positions (not (0,0) or gold)
        num_wumpuses = random.randint(2, 6)
        available_positions = [(x, y) for x in range(self.grid_size) for y in range(self.grid_size) 
                             if (x, y) != (0, 0) and (x, y) != gold_pos]
        wumpus_positions = random.sample(available_positions, num_wumpuses)
        for x, y in wumpus_positions:
            self.grid[y][x] = "W"
            self.percepts_grid[y][x] = "W"
        
        # Update available positions to exclude Wumpuses
        available_positions = [(x, y) for x, y in available_positions if (x, y) not in wumpus_positions]
        
        # Place 3-6 pits at random positions (not (0,0), gold, or Wumpuses)
        num_pits = random.randint(4, 8)
        pit_positions = random.sample(available_positions, min(num_pits, len(available_positions)))
        for x, y in pit_positions:
            self.grid[y][x] = "P"
            self.percepts_grid[y][x] = "P"
        
        # Generate percepts for adjacent cells
        adjacent_p = set()
        adjacent_w = set()
        
        for y in range(self.grid_size):
            for x in range(self.grid_size):
                if self.grid[y][x] == "P":
                    for nx, ny in self._get_adjacent_cells((x, y)):
                        if self.grid[ny][nx] == "-":
                            adjacent_p.add((nx, ny))
                if self.grid[y][x] == "W":
                    for nx, ny in self._get_adjacent_cells((x, y)):
                        if self.grid[ny][nx] == "-":
                            adjacent_w.add((nx, ny))
        
        for y in range(self.grid_size):
            for x in range(self.grid_size):
                if self.grid[y][x] == "-":
                    is_breeze = (x, y) in adjacent_p
                    is_stench = (x, y) in adjacent_w
                    if is_breeze and is_stench:
                        self.percepts_grid[y][x] = "T"
                    elif is_breeze:
                        self.percepts_grid[y][x] = "B"
                    elif is_stench:
                        self.percepts_grid[y][x] = "S"
    
    def load_environment(self, grid: List[List[str]]):
        """Load environment from provided grid"""
        self.grid_size = len(grid)
        self.grid = [row[:] for row in grid]
        self.percepts_grid = [row[:] for row in grid]
        
        # Generate percepts based on pits and Wumpuses
        adjacent_p = set()
        adjacent_w = set()
        
        for y in range(self.grid_size):
            for x in range(self.grid_size):
                if self.grid[y][x] == "P":
                    for nx, ny in self._get_adjacent_cells((x, y)):
                        if self.grid[ny][nx] == "-":
                            adjacent_p.add((nx, ny))
                if self.grid[y][x] == "W":
                    for nx, ny in self._get_adjacent_cells((x, y)):
                        if self.grid[ny][nx] == "-":
                            adjacent_w.add((nx, ny))
        
        for y in range(self.grid_size):
            for x in range(self.grid_size):
                if self.grid[y][x] == "-":
                    is_breeze = (x, y) in adjacent_p
                    is_stench = (x, y) in adjacent_w
                    if is_breeze and is_stench:
                        self.percepts_grid[y][x] = "T"
                    elif is_breeze:
                        self.percepts_grid[y][x] = "B"
                    elif is_stench:
                        self.percepts_grid[y][x] = "S"
    
    def get_visible_grid(self, agent_pos: Tuple[int, int]) -> List[List[str]]:
        """Return grid with only percepts visible at agent's position"""
        visible_grid = [["-" for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        x, y = agent_pos
        visible_grid[y][x] = self.percepts_grid[y][x]
        return visible_grid
    
    def get_percepts(self, position: Tuple[int, int]) -> List[str]:
        """Return percepts at the given position"""
        x, y = position
        cell = self.percepts_grid[y][x]
        percepts = []
        if cell == "B":
            percepts.append("Breeze")
        elif cell == "S":
            percepts.append("Stench")
        elif cell == "T":
            percepts.append("Breeze")
            percepts.append("Stench")
        elif cell == "G":
            percepts.append("Glitter")
        return percepts
    
    def get_cell_contents(self, position: Tuple[int, int]) -> List[str]:
        """Return actual contents of the cell (for checking death conditions)"""
        x, y = position
        cell = self.grid[y][x]
        contents = []
        if cell == "P":
            contents.append("P")
        elif cell == "W":
            contents.append("W")
        elif cell == "G":
            contents.append("G")
        return contents
    
    def is_valid_position(self, position: Tuple[int, int]) -> bool:
        x, y = position
        return 0 <= x < self.grid_size and 0 <= y < self.grid_size
    
    def _get_adjacent_cells(self, position: Tuple[int, int]) -> List[Tuple[int, int]]:
        x, y = position
        adjacent = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            new_x, new_y = x + dx, y + dy
            if 0 <= new_x < self.grid_size and 0 <= new_y < self.grid_size:
                adjacent.append((new_x, new_y))
        return adjacent
    
    def shoot_arrow(self, current_pos: Tuple[int, int], direction: str) -> bool:
        """Shoot arrow in given direction, return True if wumpus was hit"""
        target_pos = self._get_target_position(current_pos, direction)
        if not target_pos or not self.is_valid_position(target_pos):
            return False
        
        x, y = target_pos
        cell_contents = self.grid[y][x]
        
        if cell_contents == "W":
            # Wumpus hit! Remove it and make cell safe
            self.grid[y][x] = "-"
            self.percepts_grid[y][x] = "-"
            self._regenerate_percepts()  # Update percepts after wumpus removal
            logger.info(f"Arrow hit wumpus at {target_pos}")
            return True
        else:
            logger.info(f"Arrow missed - no wumpus at {target_pos}")
            return False
        
    def _get_target_position(self, current_pos: Tuple[int, int], direction: str) -> Tuple[int, int]:
        """Get target position based on direction"""
        x, y = current_pos
        if direction == "UP":
            return (x, y - 1)
        elif direction == "DOWN":
            return (x, y + 1)
        elif direction == "LEFT":
            return (x - 1, y)
        elif direction == "RIGHT":
            return (x + 1, y)
        return None
    
    def _regenerate_percepts(self):
        """Regenerate percepts after environment changes"""
        # Reset percepts grid
        for y in range(self.grid_size):
            for x in range(self.grid_size):
                if self.grid[y][x] in ["P", "W", "G"]:
                    self.percepts_grid[y][x] = self.grid[y][x]
                else:
                    self.percepts_grid[y][x] = "-"
        
        # Generate percepts for adjacent cells
        adjacent_p = set()
        adjacent_w = set()
        
        for y in range(self.grid_size):
            for x in range(self.grid_size):
                if self.grid[y][x] == "P":
                    for nx, ny in self._get_adjacent_cells((x, y)):
                        if self.grid[ny][nx] == "-":
                            adjacent_p.add((nx, ny))
                if self.grid[y][x] == "W":
                    for nx, ny in self._get_adjacent_cells((x, y)):
                        if self.grid[ny][nx] == "-":
                            adjacent_w.add((nx, ny))
        
        for y in range(self.grid_size):
            for x in range(self.grid_size):
                if self.grid[y][x] == "-":
                    is_breeze = (x, y) in adjacent_p
                    is_stench = (x, y) in adjacent_w
                    if is_breeze and is_stench:
                        self.percepts_grid[y][x] = "T"
                    elif is_breeze:
                        self.percepts_grid[y][x] = "B"
                    elif is_stench:
                        self.percepts_grid[y][x] = "S"
    