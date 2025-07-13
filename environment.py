import random
from typing import List, Tuple, Dict

class WumpusEnvironment:
    def __init__(self):
        self.grid_size = 10
        self.grid = [["-" for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        self.wumpus_positions = set()
        self.wumpus_alive = dict()
        self.gold_position = None
        self.pit_positions = set()
        
    def load_default_environment(self):
        with open("sample.txt", "r") as f:
            self.grid = [list(line.strip()) for line in f]
        self.grid_size = len(self.grid)
        
        self.pit_positions.clear()
        self.wumpus_positions.clear()
        self.wumpus_alive.clear()
        for y in range(self.grid_size):
            for x in range(self.grid_size):
                cell = self.grid[y][x]
                if cell == "W":
                    pos = (x, y)
                    self.wumpus_positions.add(pos)
                    self.wumpus_alive[pos] = True
                elif cell == "G":
                    self.gold_position = (x, y)
                elif cell == "P":
                    self.pit_positions.add((x, y))
                self.grid[y][x] = "-" if cell not in ["W", "P", "G"] else cell
    
    def generate_random_environment(self):
        self.grid = [["-" for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        self.pit_positions.clear()
        self.wumpus_positions.clear()
        self.wumpus_alive.clear()
        
        while True:
            x, y = random.randint(0, self.grid_size-1), random.randint(0, self.grid_size-1)
            if (x, y) != (0, 0):
                self.gold_position = (x, y)
                self.grid[y][x] = "G"
                break

        num_wumpus = random.randint(1, 3)
        wumpus_placed = 0
        attempts = 0
        while wumpus_placed < num_wumpus and attempts < 100:
            x, y = random.randint(0, self.grid_size-1), random.randint(0, self.grid_size-1)
            pos = (x, y)
            if pos != (0, 0) and pos != self.gold_position and pos not in self.pit_positions:
                self.wumpus_positions.add(pos)
                self.wumpus_alive[pos] = True
                self.grid[y][x] = "W"
                wumpus_placed += 1
            attempts += 1

        num_pits = random.randint(3, 6)
        pits_placed = 0
        attempts = 0
        while pits_placed < num_pits and attempts < 100:
            x, y = random.randint(0, self.grid_size-1), random.randint(0, self.grid_size-1)
            pos = (x, y)
            if pos != (0, 0) and pos != self.gold_position and pos not in self.wumpus_positions:
                self.pit_positions.add(pos)
                self.grid[y][x] = "P"
                pits_placed += 1
            attempts += 1

    def load_environment(self, env_data: Dict):
        if "grid" in env_data:
            grid_data = env_data["grid"]
            self.grid_size = len(grid_data)
            self.grid = [[cell for cell in row] for row in grid_data]
        else:
            self.load_default_environment()
        
        self.pit_positions.clear()
        self.wumpus_positions.clear()
        self.wumpus_alive.clear()
        for y in range(self.grid_size):
            for x in range(self.grid_size):
                cell = self.grid[y][x]
                if cell == "W":
                    pos = (x, y)
                    self.wumpus_positions.add(pos)
                    self.wumpus_alive[pos] = True
                elif cell == "G":
                    self.gold_position = (x, y)
                elif cell == "P":
                    self.pit_positions.add((x, y))
                self.grid[y][x] = "-" if cell not in ["W", "P", "G"] else cell
    
    def get_percepts(self, position: Tuple[int, int]) -> List[str]:
        percepts = []
        x, y = position
        
        if (x, y) == self.gold_position:
            percepts.append("Glitter")
        
        if self._has_adjacent_pit((x, y)):
            percepts.append("Breeze")
        if self._has_adjacent_wumpus((x, y)):
            percepts.append("Stench")
        
        return percepts

    def _has_adjacent_pit(self, position: Tuple[int, int]) -> bool:
        adjacent_cells = self._get_adjacent_cells(position)
        return any(cell in self.pit_positions for cell in adjacent_cells)
    
    def _has_adjacent_wumpus(self, position: Tuple[int, int]) -> bool:
        adjacent_cells = self._get_adjacent_cells(position)
        for cell in adjacent_cells:
            if cell in self.wumpus_positions and self.wumpus_alive.get(cell, False):
                return True
        return False

    def _get_adjacent_cells(self, position: Tuple[int, int]) -> List[Tuple[int, int]]:
        x, y = position
        adjacent = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            new_x, new_y = x + dx, y + dy
            if 0 <= new_x < self.grid_size and 0 <= new_y < self.grid_size:
                adjacent.append((new_x, new_y))
        return adjacent
    
    def is_valid_position(self, position: Tuple[int, int]) -> bool:
        x, y = position
        return 0 <= x < self.grid_size and 0 <= y < self.grid_size
    
    def get_cell_contents(self, position: Tuple[int, int]) -> str:
        x, y = position
        if self.is_valid_position(position):
            if (x, y) in self.wumpus_positions and self.wumpus_alive.get((x, y), False):
                return "W"
            elif (x, y) == self.gold_position:
                return "G"
            elif (x, y) in self.pit_positions:
                return "P"
            return "-"
        return ""
    
    def get_visible_grid(self, agent_position: Tuple[int, int]) -> List[List[str]]:
        display_grid = [row[:] for row in self.grid]
        agent_x, agent_y = agent_position
        current_cell = display_grid[agent_y][agent_x]
        if current_cell == "-":
            display_grid[agent_y][agent_x] = "A"
        else:
            display_grid[agent_y][agent_x] = "A" + current_cell
        return display_grid

    def get_full_grid_state(self) -> Dict:
        return {
            "grid": self.grid,
            "wumpus_positions": list(self.wumpus_positions),
            "wumpus_alive": {str(k): v for k, v in self.wumpus_alive.items()},
            "gold_position": self.gold_position,
            "pit_positions": list(self.pit_positions),
            "grid_size": self.grid_size
        }