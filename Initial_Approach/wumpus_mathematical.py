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

# Agent logic
def update_adjacent_cells(x, y):
    current_cell = grid[y][x]
    adj_cells = list(get_adjacent(x, y))
    
    if current_cell == '-':
        # All adjacent cells are safe
        for nx, ny in adj_cells:
            if playing_grid[ny][nx] in [-1, -2, -5]:  # Incorrectly deduced as danger
                playing_grid[ny][nx] = 0  # Mark as safe
    
    elif current_cell == 'S':
        # Handle possible Wumpus
        has_minus_one = any(playing_grid[ny][nx] == -1 for nx, ny in adj_cells)
        zero_cells = [(nx, ny) for nx, ny in adj_cells if playing_grid[ny][nx] == 0]
        
        if has_minus_one:
            for nx, ny in adj_cells:
                if playing_grid[ny][nx] == -1:
                    playing_grid[ny][nx] = -3  # Confirmed Wumpus
        elif len(zero_cells) == 1:
            nx, ny = zero_cells[0]
            playing_grid[ny][nx] = -3  # Only one possible cell, it's Wumpus
        elif len(zero_cells) > 1:
            for nx, ny in zero_cells:
                playing_grid[ny][nx] = -1  # Multiple cells, possibly Wumpus
    
    elif current_cell == 'B':
        # Handle possible Pit
        has_minus_two = any(playing_grid[ny][nx] == -2 for nx, ny in adj_cells)
        zero_cells = [(nx, ny) for nx, ny in adj_cells if playing_grid[ny][nx] == 0]
        
        if has_minus_two:
            for nx, ny in adj_cells:
                if playing_grid[ny][nx] == -2:
                    playing_grid[ny][nx] = -4  # Confirmed Pit
        elif len(zero_cells) == 1:
            nx, ny = zero_cells[0]
            playing_grid[ny][nx] = -4  # Only one possible cell, it's Pit
        elif len(zero_cells) > 1:
            for nx, ny in zero_cells:
                playing_grid[ny][nx] = -2  # Multiple cells, possibly Pit
    
    elif current_cell == 'T':
        # Handle Wumpus or Pit
        has_wumpus = any(playing_grid[ny][nx] in [-1, -3] for nx, ny in adj_cells)
        has_pit = any(playing_grid[ny][nx] in [-2, -4] for nx, ny in adj_cells)
        zero_cells = [(nx, ny) for nx, ny in adj_cells if playing_grid[ny][nx] == 0]
        
        if has_wumpus:
            for nx, ny in adj_cells:
                if playing_grid[ny][nx] in [-1, -3]:
                    playing_grid[ny][nx] = -3  # Confirmed Wumpus
            if len(zero_cells) == 1:
                nx, ny = zero_cells[0]
                playing_grid[ny][nx] = -4  # Only one cell left, it's Pit
            elif len(zero_cells) > 1:
                for nx, ny in zero_cells:
                    playing_grid[ny][nx] = -2  # Multiple cells, possibly Pit
        elif has_pit:
            for nx, ny in adj_cells:
                if playing_grid[ny][nx] in [-2, -4]:
                    playing_grid[ny][nx] = -4  # Confirmed Pit
            if len(zero_cells) == 1:
                nx, ny = zero_cells[0]
                playing_grid[ny][nx] = -3  # Only one cell left, it's Wumpus
            elif len(zero_cells) > 1:
                for nx, ny in zero_cells:
                    playing_grid[ny][nx] = -1  # Multiple cells, possibly Wumpus
        else:
            for nx, ny in zero_cells:
                playing_grid[ny][nx] = -5  # Could be Wumpus or Pit

def choose_next_move(x, y):
    adj_cells = list(get_adjacent(x, y))
    priority_0 = [(nx, ny) for nx, ny in adj_cells if playing_grid[ny][nx] == 0]
    priority_1 = [(nx, ny) for nx, ny in adj_cells if playing_grid[ny][nx] == 1]
    priority_minus_1_2 = [(nx, ny) for nx, ny in adj_cells if playing_grid[ny][nx] in [-1, -2, -5]]
    priority_minus_3_4 = [(nx, ny) for nx, ny in adj_cells if playing_grid[ny][nx] in [-3, -4]]
    
    if priority_0:
        return random.choice(priority_0)
    elif priority_1:
        return random.choice(priority_1)
    elif priority_minus_1_2:
        return random.choice(priority_minus_1_2)
    elif priority_minus_3_4:
        return random.choice(priority_minus_3_4)
    return None  # No valid moves

def traverse_grid(canvas, label, update_ui):
    x, y = 0, 0  # Start at (0,0)
    visited = set([(x, y)])
    
    while True:
        current_cell = grid[y][x]
        
        # Print playing_grid at each iteration
        for row in playing_grid:
            print(' '.join(str(cell).rjust(3) for cell in row))
        print('-' * (4 * cols))

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
        
        # Update adjacent cells based on current cell
        update_adjacent_cells(x, y)
        
        # Choose next move
        next_move = choose_next_move(x, y)
        if not next_move:
            label.config(text="Result: Lose - No valid moves left!")
            break  # <-- Fix: replace 'BREAK' with 'break'
        
        # Mark current cell as visited
        playing_grid[y][x] = 1
        visited.add((x, y))
        
        # Move to next cell
        x, y = next_move
        
        # Update UI
        update_ui()
        canvas.update()
        time.sleep(1.0)  # 1 second delay for visibility (was 0.5)

# UI code
CELL_SIZE = 32
PADDING = 10

def draw_grid(canvas, grid, is_playing_grid=False, agent_pos=None):
    canvas.delete("all")  # Clear canvas
    for y, row in enumerate(grid):
        for x, val in enumerate(row):
            x1 = x * CELL_SIZE + PADDING
            y1 = y * CELL_SIZE + PADDING
            x2 = x1 + CELL_SIZE
            y2 = y1 + CELL_SIZE

            # Improved color and text for playing_grid
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
                    color = "#f8fafc"  # very light gray
                elif val == 1:
                    color = "#bbf7d0"  # light green
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
                    color = "#bae6fd"  # light blue (possible Pit)
                    text = "P?"
                    text_color = "#0369a1"
                elif val == -3:
                    color = "#ef4444"  # red (confirmed Wumpus)
                    text = "W!"
                    text_color = "white"
                elif val == -4:
                    color = "#a16207"  # brown (confirmed Pit)
                    text = "P!"
                    text_color = "white"
                elif val == -5:
                    color = "#c4b5fd"  # purple (possible Wumpus or Pit)
                    text = "?"
                    text_color = "#581c87"
                if is_agent:
                    border_color = "#2563eb"  # blue border for agent
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
            # Draw agent as a circle overlay
            if is_playing_grid and agent_pos == (x, y):
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                r = CELL_SIZE // 4
                canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#2563eb", outline="white", width=2)

root = tk.Tk()
root.title("Wumpus World")

frame = tk.Frame(root)
frame.pack()

canvas1 = tk.Canvas(frame, width=cols*CELL_SIZE+2*PADDING, height=rows*CELL_SIZE+2*PADDING, bg="white")
canvas1.grid(row=0, column=0, padx=10, pady=10)
canvas2 = tk.Canvas(frame, width=cols*CELL_SIZE+2*PADDING, height=rows*CELL_SIZE+2*PADDING, bg="white")
canvas2.grid(row=0, column=1, padx=10, pady=10)

label1 = tk.Label(frame, text="Main Grid")
label1.grid(row=1, column=0)
label2 = tk.Label(frame, text="Playing Grid")
label2.grid(row=1, column=1)
result_label = tk.Label(frame, text="Result: ")
result_label.grid(row=2, column=0, columnspan=2)

# Initialize UI
current_pos = [0, 0]  # Track agent's position
def update_ui():
    draw_grid(canvas1, grid, is_playing_grid=False)
    draw_grid(canvas2, playing_grid, is_playing_grid=True, agent_pos=current_pos)

# Start traversal
update_ui()
canvas2.after(1000, lambda: traverse_grid(canvas2, result_label, update_ui))

root.mainloop()