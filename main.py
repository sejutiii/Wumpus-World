from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
from typing import List, Optional
from pydantic import BaseModel
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    
    logger.info(f"Game reset with environment: {env_data or 'default'}")
    await manager.broadcast({
        "type": "game_state",
        "data": get_game_state_data()
    })
    
    return {"status": "Game reset successfully"}

@app.post("/api/start")
async def start_game():
    if not game_state.environment:
        game_state.reset()
    
    logger.info("AI agent started")
    asyncio.create_task(run_ai_agent())
    
    return {"status": "AI agent started"}

@app.post("/api/step")
async def step_game():
    if not game_state.environment:
        raise HTTPException(status_code=400, detail="Game not initialized. Call /api/reset or /api/start first.")
    
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
        if not grid or any(len(row) != len(grid) for row in grid):
            raise ValueError("Grid must be square and non-empty")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid file format: {e}")
    game_state.reset(grid)
    logger.info(f"Environment uploaded: {grid}")
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
            "game_status": "playing",
            "has_arrow": True,  # NEW
            "arrow_used": False  # NEW
        }
    
    logger.debug(f"Game state data requested - Agent at {game_state.agent_pos}")
    print("Full environment grid:")
    for row in game_state.environment.grid:
        print(" ".join(row))
    print("-" * 40)
    return {
        "grid": game_state.environment.grid,
        "playing_grid": game_state.knowledge_base.get_playing_grid(),
        "agent_pos": list(game_state.agent_pos),
        "agent_alive": game_state.agent_alive,
        "game_over": game_state.game_over,
        "has_gold": game_state.has_gold,
        "knowledge_base": game_state.knowledge_base.get_knowledge_summary(),
        "last_inference": game_state.inference_engine.get_last_inference(),
        "percepts": game_state.environment.get_percepts(game_state.agent_pos),
        "game_status": game_state.game_status,
        "has_arrow": game_state.knowledge_base.has_arrow,  # NEW
        "arrow_used": game_state.knowledge_base.arrow_used  # NEW
    }
async def run_ai_agent():
    while not game_state.game_over and game_state.agent_alive:
        logger.info(f"Running AI agent step at position {game_state.agent_pos}")
        await execute_agent_step()
        await asyncio.sleep(1.0)

async def execute_agent_step():
    if game_state.game_over or not game_state.agent_alive:
        logger.warning("Attempted step in game over or agent dead state")
        return
    
    # Update knowledge base with current position and percepts first
    percepts = game_state.environment.get_percepts(game_state.agent_pos)
    logger.debug(f"Percepts at {game_state.agent_pos}: {percepts}")
    game_state.knowledge_base.update_knowledge_base(game_state.agent_pos, percepts)
    
    # Determine action after the knowledge base is updated
    action = game_state.inference_engine.determine_next_action(
        game_state.agent_pos, 
        percepts,
        game_state.environment.grid_size
    )
    logger.info(f"Action chosen: {action} at {game_state.agent_pos} with percepts {percepts}")
    
    if not game_state.has_gold:
        if action == "GRAB" and "Glitter" in percepts:
            game_state.has_gold = True
            game_state.knowledge_base.set_gold_found(game_state.agent_pos)
            game_state.game_over = True
            game_state.game_status = "won"
            logger.info("Gold grabbed, game won")
    
    # NEW: Handle arrow shooting
    if action.startswith("SHOOT_"):
        direction = action.split("_")[1]
        heard_scream = game_state.environment.shoot_arrow(game_state.agent_pos, direction)
        if heard_scream:
            # Add scream to percepts for next step
            percepts.append("Scream")
        logger.info(f"Arrow shot {direction}, scream heard: {heard_scream}")
    
    # Only allow movement after gold is found
    elif action.startswith("MOVE_"):
        direction = action.split("_")[1]
        new_pos = get_new_position(game_state.agent_pos, direction)
        if game_state.environment.is_valid_position(new_pos):
            game_state.agent_pos = new_pos
            game_state.visited_cells.add(new_pos)
            cell_contents = game_state.environment.get_cell_contents(new_pos)
            logger.debug(f"Moved to {new_pos}, contents: {cell_contents}")
            if "P" in cell_contents or "W" in cell_contents:
                game_state.agent_alive = False
                game_state.game_over = True
                game_state.game_status = "lost"
                logger.error(f"Agent defeated at {new_pos} by {cell_contents}")
    
    # Check stopping conditions
    if game_state.has_gold and game_state.agent_pos == (0, 0):
        game_state.game_over = True
        if game_state.game_status != "won":
            game_state.game_status = "won"
            logger.info("Returned to (0,0) with gold, game won")
    elif len(game_state.visited_cells) == game_state.environment.grid_size * game_state.environment.grid_size:
        game_state.game_over = True
        if game_state.game_status == "playing":
            game_state.game_status = "lost"
            logger.info("All cells visited, game lost")
    
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