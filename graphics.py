"""
Graphics utilities for the Wumpus World AI Agent
This module provides helper functions for generating visual representations
and formatting data for the frontend display.
"""

from typing import Dict, List, Tuple, Any
import json

class WumpusGraphics:
    """Graphics and visualization utilities for Wumpus World"""
    
    def __init__(self):
        self.cell_symbols = {
            ".": "empty",
            "W": "wumpus",
            "P": "pit", 
            "G": "gold",
            "A": "agent"
        }
        
        self.colors = {
            "empty": "#f8f9fa",
            "wumpus": "#dc3545",
            "pit": "#343a40",
            "gold": "#ffc107",
            "agent": "#007bff",
            "safe": "#28a745",
            "danger": "#fd7e14",
            "visited": "#6c757d"
        }
    
    def format_grid_for_display(self, grid: List[List[str]], 
                               safe_cells: set = None,
                               danger_cells: set = None,
                               visited_cells: set = None) -> List[List[Dict]]:
        """Format grid data for frontend display with additional metadata"""
        display_grid = []
        
        for y, row in enumerate(grid):
            display_row = []
            for x, cell in enumerate(row):
                cell_data = {
                    "content": cell,
                    "position": [x, y],
                    "symbol": self._get_cell_symbol(cell),
                    "color": self._get_cell_color(cell, (x, y), safe_cells, danger_cells, visited_cells),
                    "is_safe": safe_cells and (x, y) in safe_cells,
                    "is_danger": danger_cells and (x, y) in danger_cells,
                    "is_visited": visited_cells and (x, y) in visited_cells,
                    "tooltip": self._generate_tooltip(cell, (x, y), safe_cells, danger_cells, visited_cells)
                }
                display_row.append(cell_data)
            display_grid.append(display_row)
        
        return display_grid
    
    def _get_cell_symbol(self, cell: str) -> str:
        """Get display symbol for cell content"""
        # Handle compound cells (e.g., "AW" for agent on wumpus)
        if "A" in cell:
            return "agent"
        elif "W" in cell:
            return "wumpus"
        elif "P" in cell:
            return "pit"
        elif "G" in cell:
            return "gold"
        else:
            return "empty"
    
    def _get_cell_color(self, cell: str, position: Tuple[int, int],
                       safe_cells: set, danger_cells: set, visited_cells: set) -> str:
        """Determine cell color based on content and status"""
        # Agent always takes priority
        if "A" in cell:
            return self.colors["agent"]
        
        # Check status-based colors
        if visited_cells and position in visited_cells:
            return self.colors["visited"]
        elif safe_cells and position in safe_cells:
            return self.colors["safe"]
        elif danger_cells and position in danger_cells:
            return self.colors["danger"]
        
        # Default to content-based colors
        symbol = self._get_cell_symbol(cell)
        return self.colors.get(symbol, self.colors["empty"])
    
    def _generate_tooltip(self, cell: str, position: Tuple[int, int],
                         safe_cells: set, danger_cells: set, visited_cells: set) -> str:
        """Generate tooltip text for a cell"""
        x, y = position
        tooltip_parts = [f"Position: ({x}, {y})"]
        
        # Add content information
        if "W" in cell:
            tooltip_parts.append("Contains: Wumpus")
        elif "P" in cell:
            tooltip_parts.append("Contains: Pit")
        elif "G" in cell:
            tooltip_parts.append("Contains: Gold")
        elif "A" in cell:
            tooltip_parts.append("Agent Position")
        
        # Add status information
        if visited_cells and position in visited_cells:
            tooltip_parts.append("Status: Visited")
        elif safe_cells and position in safe_cells:
            tooltip_parts.append("Status: Safe")
        elif danger_cells and position in danger_cells:
            tooltip_parts.append("Status: Dangerous")
        else:
            tooltip_parts.append("Status: Unknown")
        
        return " | ".join(tooltip_parts)
    
    def format_knowledge_base(self, knowledge_summary: List[Dict]) -> Dict:
        """Format knowledge base data for display"""
        categorized_knowledge = {
            "facts": [],
            "inferences": [],
            "rules": [],
            "statistics": {}
        }
        
        fact_count = 0
        inference_count = 0
        
        for item in knowledge_summary:
            if item["type"] == "fact":
                categorized_knowledge["facts"].append({
                    "content": item["content"],
                    "confidence": item.get("confidence", 1.0),
                    "timestamp": item.get("timestamp", "")
                })
                fact_count += 1
            elif item["type"] == "inference":
                categorized_knowledge["inferences"].append({
                    "content": item["content"],
                    "confidence": item.get("confidence", 0.5),
                    "reasoning": item.get("reasoning", "")
                })
                inference_count += 1
        
        categorized_knowledge["statistics"] = {
            "total_facts": fact_count,
            "total_inferences": inference_count,
            "confidence_avg": sum(item.get("confidence", 0) for item in knowledge_summary) / max(len(knowledge_summary), 1)
        }
        
        return categorized_knowledge
    
    def generate_action_visualization(self, action: str, position: Tuple[int, int], 
                                    reasoning: str) -> Dict:
        """Generate visualization data for an agent action"""
        action_data = {
            "action": action,
            "position": position,
            "reasoning": reasoning,
            "timestamp": "",  # Would be added by caller
            "visualization": {}
        }
        
        # Add action-specific visualization data
        if action.startswith("MOVE_"):
            direction = action.split("_")[1]
            action_data["visualization"] = {
                "type": "movement",
                "direction": direction.lower(),
                "arrow_color": self.colors["agent"],
                "animation": "slide"
            }
        elif action.startswith("SHOOT_"):
            direction = action.split("_")[1]
            action_data["visualization"] = {
                "type": "shooting",
                "direction": direction.lower(),
                "effect_color": "#ff6b6b",
                "animation": "flash"
            }
        elif action == "GRAB":
            action_data["visualization"] = {
                "type": "grabbing",
                "effect_color": self.colors["gold"],
                "animation": "glow"
            }
        
        return action_data
    
    def create_performance_chart_data(self, game_history: List[Dict]) -> Dict:
        """Create data for performance visualization charts"""
        if not game_history:
            return {"labels": [], "datasets": []}
        
        steps = list(range(1, len(game_history) + 1))
        scores = [entry.get("score", 0) for entry in game_history]
        knowledge_counts = [len(entry.get("knowledge_base", [])) for entry in game_history]
        
        return {
            "labels": steps,
            "datasets": [
                {
                    "label": "Score",
                    "data": scores,
                    "borderColor": self.colors["agent"],
                    "backgroundColor": self.colors["agent"] + "20",
                    "tension": 0.4
                },
                {
                    "label": "Knowledge Items",
                    "data": knowledge_counts,
                    "borderColor": self.colors["safe"],
                    "backgroundColor": self.colors["safe"] + "20",
                    "tension": 0.4
                }
            ]
        }
    
    def export_game_state(self, game_state: Dict) -> str:
        """Export complete game state as formatted JSON"""
        return json.dumps(game_state, indent=2, ensure_ascii=False)
    
    def generate_ascii_grid(self, grid: List[List[str]]) -> str:
        """Generate ASCII representation of the grid for debugging"""
        ascii_lines = []
        
        # Top border
        ascii_lines.append("+" + "-" * (len(grid[0]) * 2 - 1) + "+")
        
        # Grid content
        for row in grid:
            line = "|"
            for cell in row:
                symbol = cell if cell != "." else " "
                line += symbol + "|"
            ascii_lines.append(line)
        
        # Bottom border
        ascii_lines.append("+" + "-" * (len(grid[0]) * 2 - 1) + "+")
        
        return "\n".join(ascii_lines)