from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import json
import asyncio
from typing import List, Optional
from pydantic import BaseModel

from environment import WumpusEnvironment
from knowledgeBase import KnowledgeBase
from inferenceEngine import InferenceEngine

app = FastAPI(title="Wumpus AI Agent", version="1.0.0")

# Enable CORS for React frontend
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
        self.score = 0
        self.arrows_left = 1
        self.has_gold = False
        
    def reset(self, environment_data=None):
        self.environment = WumpusEnvironment()
        if environment_data:
            self.environment.load_environment(environment_data)
        else:
            self.environment.generate_random_environment()
        
        self.knowledge_base = KnowledgeBase()
        self.inference_engine = InferenceEngine(self.knowledge_base)
        self.agent_pos = (0, 0)
        self.agent_alive = True
        self.game_over = False
        self.score = 0
        self.arrows_left = 1
        self.has_gold = False

game_state = GameState()

class EnvironmentRequest(BaseModel):
    grid: List[List[str]]

@app.post("/api/reset")
async def reset_game(env_request: Optional[EnvironmentRequest] = None):
    env_data = env_request.dict() if env_request else None
    game_state.reset(env_data)
    
    # Send initial state
    await manager.broadcast({
        "type": "game_state",
        "data": get_game_state_data()
    })
    
    return {"status": "Game reset successfully"}

@app.post("/api/start")
async def start_game():
    if not game_state.environment:
        game_state.reset()
    
    # Start the AI agent
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
        # Send initial state
        await websocket.send_text(json.dumps({
            "type": "game_state",
            "data": get_game_state_data()
        }))
        
        while True:
            # Keep connection alive and handle any incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def get_game_state_data():
    if not game_state.environment:
        return {
            "grid": [["." for _ in range(10)] for _ in range(10)],
            "agent_pos": [0, 0],
            "agent_alive": True,
            "game_over": False,
            "score": 0,
            "arrows_left": 1,
            "has_gold": False,
            "knowledge_base": [],
            "last_inference": "",
            "percepts": []
        }
    
    return {
        "grid": game_state.environment.get_visible_grid(game_state.agent_pos),
        "agent_pos": list(game_state.agent_pos),
        "agent_alive": game_state.agent_alive,
        "game_over": game_state.game_over,
        "score": game_state.score,
        "arrows_left": game_state.arrows_left,
        "has_gold": game_state.has_gold,
        "knowledge_base": game_state.knowledge_base.get_knowledge_summary() if game_state.knowledge_base else [],
        "last_inference": game_state.inference_engine.get_last_inference() if game_state.inference_engine else "",
        "percepts": game_state.environment.get_percepts(game_state.agent_pos) if game_state.environment else []
    }

async def run_ai_agent():
    """Run the AI agent autonomously with delays for visualization"""
    while not game_state.game_over and game_state.agent_alive:
        await execute_agent_step()
        await asyncio.sleep(1.5)  # Delay for visualization

async def execute_agent_step():
    """Execute one step of the AI agent"""
    if game_state.game_over or not game_state.agent_alive:
        return
    
    # Get current percepts
    percepts = game_state.environment.get_percepts(game_state.agent_pos)
    
    # Update knowledge base with percepts
    game_state.knowledge_base.add_percepts(game_state.agent_pos, percepts)
    
    # Use inference engine to determine next action
    action = game_state.inference_engine.determine_next_action(
        game_state.agent_pos, 
        percepts,
        game_state.environment.grid_size
    )
    
    # Execute action
    if action == "GRAB" and "Glitter" in percepts:
        game_state.has_gold = True
        game_state.score += 1000
        
    elif action.startswith("MOVE_"):
        direction = action.split("_")[1]
        new_pos = get_new_position(game_state.agent_pos, direction)
        
        if game_state.environment.is_valid_position(new_pos):
            game_state.agent_pos = new_pos
            
            # Check for death conditions
            cell_contents = game_state.environment.get_cell_contents(new_pos)
            if "P" in cell_contents or "W" in cell_contents:
                game_state.agent_alive = False
                game_state.score -= 1000
                game_state.game_over = True
    
    elif action.startswith("SHOOT_"):
        direction = action.split("_")[1]
        if game_state.arrows_left > 0:
            game_state.arrows_left -= 1
            hit_wumpus = game_state.environment.shoot_arrow(game_state.agent_pos, direction)
            if hit_wumpus:
                game_state.score += 500
                game_state.knowledge_base.add_fact(f"WumpusKilled")
    
    # Check win condition
    if game_state.has_gold and game_state.agent_pos == (0, 0):
        game_state.game_over = True
        game_state.score += 100
    
    # Broadcast updated state
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
    if direction == "UP":
        return (x, max(0, y - 1))
    elif direction == "DOWN":
        return (x, min(9, y + 1))
    elif direction == "LEFT":
        return (max(0, x - 1), y)
    elif direction == "RIGHT":
        return (min(9, x + 1), y)
    return pos

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)