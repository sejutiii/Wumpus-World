from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
from typing import List, Optional
from pydantic import BaseModel

from environment import WumpusEnvironment
from knowledgeBase import PropositionalKB
from inferenceEngine import InferenceEngine

app = FastAPI(title="Wumpus AI Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                pass

manager = ConnectionManager()

class GameState:
    def __init__(self):
        self.environment = None
        self.knowledge_base = None
        self.inference_engine = None
        self.agent_pos = (0, 0)
        self.agent_alive = True
        self.game_over = False
        self.has_gold = False
        self.visited_cells = {(0, 0)}
        self.game_status = "playing"  # "playing", "won", "lost"
        
    def reset(self, environment_data=None):
        self.environment = WumpusEnvironment(grid_size=10)  # Default size 10
        if environment_data:
            self.environment.load_environment(environment_data)
        else:
            self.environment.load_default_environment()  # Generates random environment
        
        self.knowledge_base = PropositionalKB(self.environment.grid_size)
        self.inference_engine = InferenceEngine(self.knowledge_base)
        self.agent_pos = (0, 0)
        self.agent_alive = True
        self.game_over = False
        self.has_gold = False
        self.visited_cells = {(0, 0)}
        self.game_status = "playing"
        self.knowledge_base.add_fact("Safe(0,0)")
        self.knowledge_base.add_fact("Visited(0,0)")
        self.knowledge_base.add_wumpus_rules()

game_state = GameState()

class EnvironmentRequest(BaseModel):
    grid: List[List[str]]

@app.post("/api/reset")
async def reset_game(env_request: Optional[EnvironmentRequest] = None):
    env_data = env_request.grid if env_request else None
    game_state.reset(env_data)
    
    await manager.broadcast({
        "type": "game_state",
        "data": get_game_state_data()
    })
    
    return {"status": "Game reset successfully"}

@app.post("/api/start")
async def start_game():
    if not game_state.environment:
        game_state.reset()
    
    asyncio.create_task(run_ai_agent())
    
    return {"status": "AI agent started"}

@app.post("/api/step")
async def step_game():
    if game_state.game_over:
        return {"status": "Game is over"}
    
    await execute_agent_step()
    
    return {"status": "Step executed"}

@app.get("/api/state")
async def get_state():
    return get_game_state_data()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_text(json.dumps({
            "type": "game_state",
            "data": get_game_state_data()
        }))
        
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/upload_env")
async def upload_env(file: UploadFile = File(...)):
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are supported")
    content = await file.read()
    try:
        lines = content.decode("utf-8").strip().splitlines()
        grid = [list(line.strip()) for line in lines if line.strip()]
        # Validate grid is square and not empty
        if not grid or any(len(row) != len(grid) for row in grid):
            raise ValueError("Grid must be square and non-empty")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid file format: {e}")
    game_state.reset(grid)
    await manager.broadcast({
        "type": "game_state",
        "data": get_game_state_data()
    })
    return {"status": "Environment uploaded and game reset"}

def get_game_state_data():
    if not game_state.environment:
        return {
            "grid": [["-" for _ in range(10)] for _ in range(10)],
            "playing_grid": [["0" for _ in range(10)] for _ in range(10)],
            "agent_pos": [0, 0],
            "agent_alive": True,
            "game_over": False,
            "has_gold": False,
            "knowledge_base": [],
            "last_inference": "",
            "percepts": [],
            "game_status": "playing"
        }
    
    # Debug: print the full grid to the server console after reset
    print("Full environment grid:")
    for row in game_state.environment.grid:
        print(" ".join(row))
    print("-" * 40)
    return {
        # Show the full environment grid for the Wumpus World grid
        "grid": game_state.environment.grid,
        # Agent's knowledge grid
        "playing_grid": game_state.knowledge_base.get_playing_grid(),
        "agent_pos": list(game_state.agent_pos),
        "agent_alive": game_state.agent_alive,
        "game_over": game_state.game_over,
        "has_gold": game_state.has_gold,
        "knowledge_base": game_state.knowledge_base.get_knowledge_summary(),
        "last_inference": game_state.inference_engine.get_last_inference(),
        "percepts": game_state.environment.get_percepts(game_state.agent_pos),
        "game_status": game_state.game_status
    }

async def run_ai_agent():
    while not game_state.game_over and game_state.agent_alive:
        await execute_agent_step()
        await asyncio.sleep(1.0)

async def execute_agent_step():
    if game_state.game_over or not game_state.agent_alive:
        return
    
    percepts = game_state.environment.get_percepts(game_state.agent_pos)
    
    game_state.knowledge_base.update_knowledge_base(game_state.agent_pos, percepts)
    
    action = game_state.inference_engine.determine_next_action(
        game_state.agent_pos, 
        percepts,
        game_state.environment.grid_size
    )
    
    if not game_state.has_gold:
        if action == "GRAB" and "Glitter" in percepts:
            game_state.has_gold = True
            game_state.knowledge_base.set_gold_found(game_state.agent_pos)
            game_state.game_over = True
            game_state.game_status = "won"
    # Only allow movement after gold is found
    if action.startswith("MOVE_"):
        direction = action.split("_")[1]
        new_pos = get_new_position(game_state.agent_pos, direction)
        if game_state.environment.is_valid_position(new_pos):
            game_state.agent_pos = new_pos
            game_state.visited_cells.add(new_pos)
            cell_contents = game_state.environment.get_cell_contents(new_pos)
            if "P" in cell_contents or "W" in cell_contents:
                game_state.agent_alive = False
                game_state.game_over = True
                game_state.game_status = "lost"
    # Check stopping conditions
    if game_state.has_gold and game_state.agent_pos == (0, 0):
        game_state.game_over = True
        if game_state.game_status != "won":
            game_state.game_status = "won"
    elif len(game_state.visited_cells) == game_state.environment.grid_size * game_state.environment.grid_size:
        game_state.game_over = True
        if game_state.game_status == "playing":
            game_state.game_status = "lost"
    
    await manager.broadcast({
        "type": "game_state",
        "data": get_game_state_data()
    })
    
    await manager.broadcast({
        "type": "agent_action",
        "data": {
            "action": action,
            "position": list(game_state.agent_pos),
            "reasoning": game_state.inference_engine.get_last_reasoning()
        }
    })

def get_new_position(pos, direction):
    x, y = pos
    grid_size = game_state.environment.grid_size
    if direction == "UP":
        return (x, max(0, y - 1))
    elif direction == "DOWN":
        return (x, min(grid_size - 1, y + 1))
    elif direction == "LEFT":
        return (max(0, x - 1), y)
    elif direction == "RIGHT":
        return (min(grid_size - 1, x + 1), y)
    return pos

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)