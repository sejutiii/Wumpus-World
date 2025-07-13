import tkinter as tk
import random
import time
from collections import deque

# Initialize grid from file
grid = []
with open("sample.txt", "r") as f:
    for line in f:
        grid.append(list(line.strip()))

rows = len(grid)
cols = len(grid[0]) if rows > 0 else 0

# Initialize playing grid with zeroes
playing_grid = [[0 for _ in range(cols)] for _ in range(rows)]
playing_grid[0][0] = 1  # Agent starts at (0,0), mark as visited

# Helper to get adjacent cells
def get_adjacent(x, y):
    for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
        nx, ny = x + dx, y + dy
        if 0 <= nx < cols and 0 <= ny < rows:
            yield nx, ny

# Track adjacent cells to P and W for main grid
adjacent_p = set()
adjacent_w = set()

for y in range(rows):
    for x in range(cols):
        if grid[y][x] == 'P':
            for nx, ny in get_adjacent(x, y):
                if grid[ny][nx] == '-':
                    adjacent_p.add((nx, ny))
        if grid[y][x] == 'W':
            for nx, ny in get_adjacent(x, y):
                if grid[ny][nx] == '-':
                    adjacent_w.add((nx, ny))

for y in range(rows):
    for x in range(cols):
        if grid[y][x] == '-':
            is_breeze = (x, y) in adjacent_p
            is_stench = (x, y) in adjacent_w
            if is_breeze and is_stench:
                grid[y][x] = 'T'
            elif is_breeze:
                grid[y][x] = 'B'
            elif is_stench:
                grid[y][x] = 'S'

# ============== PROPOSITIONAL LOGIC KNOWLEDGE BASE ==============

class PropositionalKB:
    def __init__(self):
        self.facts = set()  # Known facts: "Safe(1,1)", "Breeze(2,1)", etc.
        self.rules = []     # Inference rules
        
    def add_fact(self, fact):
        """Add a fact to the knowledge base"""
        self.facts.add(fact)
        
    def add_rule(self, premise, conclusion):
        """Add an inference rule: premise → conclusion"""
        self.rules.append((premise, conclusion))
        
    def query(self, fact):
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
                    
    def can_infer(self, premise):
        """Check if premise can be satisfied"""
        if isinstance(premise, str):
            return premise in self.facts
        elif isinstance(premise, tuple) and premise[0] == 'AND':
            return all(self.can_infer(p) for p in premise[1:])
        elif isinstance(premise, tuple) and premise[0] == 'OR':
            return any(self.can_infer(p) for p in premise[1:])
        return False

# Initialize Knowledge Base
kb = PropositionalKB()

# Add initial facts
kb.add_fact("Safe(0,0)")  # Starting position is safe
kb.add_fact("Visited(0,0)")

# Add logical rules for Wumpus World
def add_wumpus_rules():
    """Add domain-specific rules for Wumpus World"""
    
    # Rule: If no breeze, then adjacent cells have no pit
    # Rule: If no stench, then adjacent cells have no wumpus
    # Rule: If breeze, then at least one adjacent cell has pit
    # Rule: If stench, then at least one adjacent cell has wumpus
    
    for y in range(rows):
        for x in range(cols):
            # For each cell, add rules about adjacent cells
            adj_cells = list(get_adjacent(x, y))
            
            # If no breeze at (x,y), all adjacent cells are safe from pits
            no_breeze = f"NoBreeze({x},{y})"
            for nx, ny in adj_cells:
                kb.add_rule(no_breeze, f"NoPit({nx},{ny})")
                
            # If no stench at (x,y), all adjacent cells are safe from wumpus
            no_stench = f"NoStench({x},{y})"
            for nx, ny in adj_cells:
                kb.add_rule(no_stench, f"NoWumpus({nx},{ny})")
                
            # If both no breeze and no stench, cell is safe
            if adj_cells:
                for nx, ny in adj_cells:
                    premise = ('AND', f"NoPit({nx},{ny})", f"NoWumpus({nx},{ny})")
                    kb.add_rule(premise, f"Safe({nx},{ny})")

add_wumpus_rules()

def update_knowledge_base(x, y, percept):
    """Update KB based on current percept"""
    current_cell = f"({x},{y})"
    
    if percept == '-':
        # No breeze, no stench
        kb.add_fact(f"NoBreeze{current_cell}")
        kb.add_fact(f"NoStench{current_cell}")
        kb.add_fact(f"Safe{current_cell}")
        
    elif percept == 'B':
        # Breeze detected
        kb.add_fact(f"Breeze{current_cell}")
        kb.add_fact(f"NoStench{current_cell}")
        # Add rule: breeze implies adjacent pit exists
        adj_cells = list(get_adjacent(x, y))
        if adj_cells:
            # At least one adjacent cell has pit
            for nx, ny in adj_cells:
                kb.add_rule(f"Breeze{current_cell}", f"PossiblePit({nx},{ny})")
                
    elif percept == 'S':
        # Stench detected
        kb.add_fact(f"Stench{current_cell}")
        kb.add_fact(f"NoBreeze{current_cell}")
        # Add rule: stench implies adjacent wumpus exists
        adj_cells = list(get_adjacent(x, y))
        if adj_cells:
            for nx, ny in adj_cells:
                kb.add_rule(f"Stench{current_cell}", f"PossibleWumpus({nx},{ny})")
                
    elif percept == 'T':
        # Both breeze and stench
        kb.add_fact(f"Breeze{current_cell}")
        kb.add_fact(f"Stench{current_cell}")
        adj_cells = list(get_adjacent(x, y))
        for nx, ny in adj_cells:
            kb.add_rule(f"Breeze{current_cell}", f"PossiblePit({nx},{ny})")
            kb.add_rule(f"Stench{current_cell}", f"PossibleWumpus({nx},{ny})")
    
    # Mark as visited
    kb.add_fact(f"Visited{current_cell}")
    
    # Apply forward chaining to derive new facts
    kb.forward_chain()

def update_playing_grid_from_kb():
    """Update playing grid based on KB knowledge"""
    for y in range(rows):
        for x in range(cols):
            cell_ref = f"({x},{y})"
            
            if kb.query(f"Visited{cell_ref}"):
                playing_grid[y][x] = 1
            elif kb.query(f"Safe{cell_ref}"):
                playing_grid[y][x] = 0
            elif kb.query(f"PossibleWumpus{cell_ref}") and kb.query(f"PossiblePit{cell_ref}"):
                playing_grid[y][x] = -5  # Could be either
            elif kb.query(f"PossibleWumpus{cell_ref}"):
                playing_grid[y][x] = -1
            elif kb.query(f"PossiblePit{cell_ref}"):
                playing_grid[y][x] = -2

def choose_next_move_logical(x, y):
    """Choose next move based on logical inference"""
    adj_cells = list(get_adjacent(x, y))
    
    # Priority 1: Safe unvisited cells
    safe_cells = []
    for nx, ny in adj_cells:
        cell_ref = f"({nx},{ny})"
        if kb.query(f"Safe{cell_ref}") and not kb.query(f"Visited{cell_ref}"):
            safe_cells.append((nx, ny))
    
    if safe_cells:
        return random.choice(safe_cells)
    
    # Priority 2: Already visited cells (backtrack)
    visited_cells = []
    for nx, ny in adj_cells:
        cell_ref = f"({nx},{ny})"
        if kb.query(f"Visited{cell_ref}"):
            visited_cells.append((nx, ny))
    
    if visited_cells:
        return random.choice(visited_cells)
    
    # Priority 3: Take calculated risk with possible dangers
    risk_cells = []
    for nx, ny in adj_cells:
        cell_ref = f"({nx},{ny})"
        if kb.query(f"PossibleWumpus{cell_ref}") or kb.query(f"PossiblePit{cell_ref}"):
            risk_cells.append((nx, ny))
    
    if risk_cells:
        return random.choice(risk_cells)
    
    return None

def traverse_grid(canvas, label, update_ui):
    x, y = 0, 0  # Start at (0,0)
    visited = set([(x, y)])
    
    while True:
        current_cell = grid[y][x]
        
        # Update knowledge base with current percept
        update_knowledge_base(x, y, current_cell)
        
        # Update playing grid from KB
        update_playing_grid_from_kb()
        
        # Print some KB facts for debugging
        print(f"Position ({x},{y}): {current_cell}")
        print(f"KB size: {len(kb.facts)} facts")
        print('-' * 30)

        # Check termination conditions
        if current_cell == 'G':
            playing_grid[y][x] = 99  # Special marker for gold found
            update_ui()
            canvas.update()
            label.config(text="Result: Win - Gold Found!")
            break
        elif current_cell in ['P', 'W']:
            label.config(text="Result: Lose - Fell into Pit or Killed by Wumpus!")
            break
        elif len(visited) == rows * cols:
            label.config(text="Result: Lose - All cells visited, no Gold found!")
            break
        
        # Choose next move using logical inference
        next_move = choose_next_move_logical(x, y)
        if not next_move:
            label.config(text="Result: Lose - No valid moves left!")
            break
        
        # Mark current cell as visited
        playing_grid[y][x] = 1
        visited.add((x, y))
        
        # Move to next cell
        x, y = next_move
        
        # Update UI
        update_ui()
        canvas.update()
        time.sleep(1.0)

# UI code (same as original)
CELL_SIZE = 32
PADDING = 10

def draw_grid(canvas, grid, is_playing_grid=False, agent_pos=None):
    canvas.delete("all")
    for y, row in enumerate(grid):
        for x, val in enumerate(row):
            x1 = x * CELL_SIZE + PADDING
            y1 = y * CELL_SIZE + PADDING
            x2 = x1 + CELL_SIZE
            y2 = y1 + CELL_SIZE

            color = "white"
            text = ""
            text_color = "black"
            border_color = "gray"
            border_width = 1

            if not is_playing_grid:
                if val == '-' or val == '0':
                    color = "white"
                elif val in ('P', 'W'):
                    color = "red"
                    text = val
                    text_color = "white"
                elif val == 'G':
                    color = "gold"
                    text = "G"
                    text_color = "black"
                elif val == 'T':
                    color = "purple"
                    text = "T"
                    text_color = "white"
                elif val in ('S', 'B'):
                    color = "skyblue"
                    text = val
                    text_color = "black"
            else:
                is_agent = agent_pos == (x, y)
                if val == 0:
                    color = "#f8fafc"
                elif val == 1:
                    color = "#bbf7d0"
                    text = "✓"
                    text_color = "#166534"
                elif val == 99:
                    color = "gold"
                    text = "G"
                    text_color = "#b45309"
                elif val == -1:
                    color = "#fde68a"
                    text = "W?"
                    text_color = "#b45309"
                elif val == -2:
                    color = "#bae6fd"
                    text = "P?"
                    text_color = "#0369a1"
                elif val == -3:
                    color = "#ef4444"
                    text = "W!"
                    text_color = "white"
                elif val == -4:
                    color = "#a16207"
                    text = "P!"
                    text_color = "white"
                elif val == -5:
                    color = "#c4b5fd"
                    text = "?"
                    text_color = "#581c87"
                if is_agent:
                    border_color = "#2563eb"
                    border_width = 3
                else:
                    border_color = "gray"
                    border_width = 1

            canvas.create_rectangle(
                x1, y1, x2, y2,
                fill=color,
                outline=border_color,
                width=border_width
            )
            if text:
                canvas.create_text(
                    (x1 + x2) // 2, (y1 + y2) // 2,
                    text=text,
                    fill=text_color,
                    font=("Arial", 16, "bold")
                )
            if is_playing_grid and agent_pos == (x, y):
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                r = CELL_SIZE // 4
                canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#2563eb", outline="white", width=2)

root = tk.Tk()
root.title("Wumpus World - Propositional Logic")

frame = tk.Frame(root)
frame.pack()

canvas1 = tk.Canvas(frame, width=cols*CELL_SIZE+2*PADDING, height=rows*CELL_SIZE+2*PADDING, bg="white")
canvas1.grid(row=0, column=0, padx=10, pady=10)
canvas2 = tk.Canvas(frame, width=cols*CELL_SIZE+2*PADDING, height=rows*CELL_SIZE+2*PADDING, bg="white")
canvas2.grid(row=0, column=1, padx=10, pady=10)

label1 = tk.Label(frame, text="Main Grid")
label1.grid(row=1, column=0)
label2 = tk.Label(frame, text="Playing Grid (Logic-based)")
label2.grid(row=1, column=1)
result_label = tk.Label(frame, text="Result: ")
result_label.grid(row=2, column=0, columnspan=2)

current_pos = [0, 0]
def update_ui():
    draw_grid(canvas1, grid, is_playing_grid=False)
    draw_grid(canvas2, playing_grid, is_playing_grid=True, agent_pos=current_pos)

update_ui()
canvas2.after(1000, lambda: traverse_grid(canvas2, result_label, update_ui))

root.mainloop()