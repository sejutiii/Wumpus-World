import React, { useState, useEffect, useRef } from 'react';
import { Play, Pause, RotateCcw, Zap, Brain, Target, MapPin, Activity } from 'lucide-react';

interface GameState {
  grid: string[][];
  agent_pos: [number, number];
  agent_alive: boolean;
  game_over: boolean;
  score: number;
  arrows_left: number;
  has_gold: boolean;
  knowledge_base: Array<{
    type: string;
    content: string;
    confidence: number;
  }>;
  last_inference: string;
  percepts: string[];
}

interface AgentAction {
  action: string;
  position: [number, number];
  reasoning: string;
}

function App() {
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [lastAction, setLastAction] = useState<AgentAction | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const connectWebSocket = () => {
    setConnectionStatus('connecting');
    wsRef.current = new WebSocket(`ws://${window.location.hostname}:8000/ws`);
    
    wsRef.current.onopen = () => {
      setConnectionStatus('connected');
      console.log('WebSocket connected');
    };
    
    wsRef.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      if (message.type === 'game_state') {
        setGameState(message.data);
      } else if (message.type === 'agent_action') {
        setLastAction(message.data);
      }
    };
    
    wsRef.current.onclose = () => {
      setConnectionStatus('disconnected');
      console.log('WebSocket disconnected');
    };
    
    wsRef.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('disconnected');
    };
  };

  const handleReset = async () => {
    setIsRunning(false);
    try {
      await fetch(`http://${window.location.hostname}:8000/api/reset`, { method: 'POST' });
    } catch (error) {
      console.error('Failed to reset game:', error);
    }
  };

  const handleStart = async () => {
    setIsRunning(true);
    try {
      await fetch(`http://${window.location.hostname}:8000/api/start`, { method: 'POST' });
    } catch (error) {
      console.error('Failed to start game:', error);
      setIsRunning(false);
    }
  };

  const handleStep = async () => {
    try {
      await fetch(`http://${window.location.hostname}:8000/api/step`, { method: 'POST' });
    } catch (error) {
      console.error('Failed to execute step:', error);
    }
  };

  const getCellDisplay = (cell: string, x: number, y: number) => {
    const isAgent = gameState && gameState.agent_pos[0] === x && gameState.agent_pos[1] === y;
    
    let content = '';
    let bgColor = 'bg-slate-50';
    let textColor = 'text-slate-600';
    let borderColor = 'border-slate-200';
    
    if (isAgent) {
      content = '🤖';
      bgColor = 'bg-blue-100';
      borderColor = 'border-blue-300';
    } else if (cell.includes('W')) {
      content = '👹';
      bgColor = 'bg-red-100';
      borderColor = 'border-red-300';
    } else if (cell.includes('P')) {
      content = '🕳️';
      bgColor = 'bg-gray-800';
      textColor = 'text-white';
      borderColor = 'border-gray-600';
    } else if (cell.includes('G')) {
      content = '🏆';
      bgColor = 'bg-yellow-100';
      borderColor = 'border-yellow-300';
    }
    
    return { content, bgColor, textColor, borderColor };
  };

  const getPerceptsDisplay = () => {
    if (!gameState?.percepts || gameState.percepts.length === 0) {
      return '👁️ No percepts';
    }
    
    const perceptIcons: { [key: string]: string } = {
      'Breeze': '💨',
      'Stench': '💀',
      'Glitter': '✨',
      'Bump': '🚫',
      'Scream': '😱'
    };
    
    return gameState.percepts.map(percept => 
      `${perceptIcons[percept] || '❓'} ${percept}`
    ).join(' | ');
  };

  if (!gameState) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-indigo-900 flex items-center justify-center">
        <div className="text-center text-white">
          <div className="animate-spin w-12 h-12 border-4 border-blue-400 border-t-transparent rounded-full mx-auto mb-4"></div>
          <h2 className="text-xl font-semibold mb-2">Initializing Wumpus AI Agent</h2>
          <p className="text-blue-200">
            Status: {connectionStatus === 'connecting' ? 'Connecting to server...' : 
                     connectionStatus === 'connected' ? 'Connected' : 'Disconnected'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-indigo-900 text-white">
      {/* Header */}
      <header className="border-b border-blue-800 bg-black/20 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Brain className="w-8 h-8 text-blue-400" />
              <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                Wumpus AI Agent
              </h1>
            </div>
            
            <div className="flex items-center space-x-4">
              <div className={`px-3 py-1 rounded-full text-sm font-medium ${
                connectionStatus === 'connected' ? 'bg-green-500/20 text-green-400' :
                connectionStatus === 'connecting' ? 'bg-yellow-500/20 text-yellow-400' :
                'bg-red-500/20 text-red-400'
              }`}>
                {connectionStatus}
              </div>
              
              <button
                onClick={handleReset}
                className="flex items-center space-x-2 px-4 py-2 bg-slate-600 hover:bg-slate-500 rounded-lg transition-colors"
              >
                <RotateCcw className="w-4 h-4" />
                <span>Reset</span>
              </button>
              
              <button
                onClick={isRunning ? () => setIsRunning(false) : handleStart}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                  isRunning 
                    ? 'bg-red-600 hover:bg-red-500' 
                    : 'bg-green-600 hover:bg-green-500'
                }`}
              >
                {isRunning ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                <span>{isRunning ? 'Pause' : 'Start AI'}</span>
              </button>
              
              <button
                onClick={handleStep}
                disabled={gameState.game_over}
                className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg transition-colors"
              >
                <Zap className="w-4 h-4" />
                <span>Step</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Game Grid */}
          <div className="lg:col-span-2">
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20">
              <h2 className="text-xl font-semibold mb-4 flex items-center">
                <Target className="w-5 h-5 mr-2 text-blue-400" />
                Wumpus World (10×10)
              </h2>
              
              <div className="grid grid-cols-10 gap-1 max-w-md mx-auto">
                {gameState.grid.map((row, y) =>
                  row.map((cell, x) => {
                    const { content, bgColor, textColor, borderColor } = getCellDisplay(cell, x, y);
                    return (
                      <div
                        key={`${x}-${y}`}
                        className={`w-8 h-8 border-2 ${bgColor} ${borderColor} flex items-center justify-center text-sm font-medium rounded transition-all hover:scale-110 cursor-pointer`}
                        title={`(${x},${y}) ${cell === '.' ? 'Empty' : cell}`}
                      >
                        {content}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>

          {/* Agent Status & Knowledge */}
          <div className="space-y-6">
            {/* Agent Status */}
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20">
              <h3 className="text-lg font-semibold mb-4 flex items-center">
                <Activity className="w-5 h-5 mr-2 text-green-400" />
                Agent Status
              </h3>
              
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-blue-200">Position:</span>
                  <span className="font-mono">({gameState.agent_pos[0]}, {gameState.agent_pos[1]})</span>
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="text-blue-200">Score:</span>
                  <span className={`font-bold ${gameState.score >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {gameState.score}
                  </span>
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="text-blue-200">Arrows:</span>
                  <span className="font-mono">{gameState.arrows_left}</span>
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="text-blue-200">Status:</span>
                  <span className={`font-medium ${
                    gameState.game_over 
                      ? (gameState.agent_alive ? 'text-yellow-400' : 'text-red-400')
                      : 'text-green-400'
                  }`}>
                    {gameState.game_over 
                      ? (gameState.agent_alive ? 'Victory!' : 'Defeated') 
                      : 'Active'
                    }
                  </span>
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="text-blue-200">Has Gold:</span>
                  <span className={gameState.has_gold ? 'text-yellow-400' : 'text-gray-400'}>
                    {gameState.has_gold ? '✅ Yes' : '❌ No'}
                  </span>
                </div>
              </div>
            </div>

            {/* Current Percepts */}
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20">
              <h3 className="text-lg font-semibold mb-3 flex items-center">
                <MapPin className="w-5 h-5 mr-2 text-purple-400" />
                Current Percepts
              </h3>
              <div className="text-sm bg-black/20 rounded-lg p-3 font-mono">
                {getPerceptsDisplay()}
              </div>
            </div>

            {/* Last Action */}
            {lastAction && (
              <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20">
                <h3 className="text-lg font-semibold mb-3 text-cyan-400">Last Action</h3>
                <div className="space-y-2">
                  <div className="text-sm">
                    <span className="text-blue-200">Action:</span>
                    <span className="ml-2 font-mono bg-black/20 px-2 py-1 rounded">
                      {lastAction.action}
                    </span>
                  </div>
                  <div className="text-sm">
                    <span className="text-blue-200">Reasoning:</span>
                    <p className="text-gray-300 mt-1 text-xs leading-relaxed">
                      {lastAction.reasoning}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Knowledge Base Summary */}
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20">
              <h3 className="text-lg font-semibold mb-3 flex items-center">
                <Brain className="w-5 h-5 mr-2 text-indigo-400" />
                Knowledge Base ({gameState.knowledge_base.length} items)
              </h3>
              
              <div className="max-h-48 overflow-y-auto space-y-2">
                {gameState.knowledge_base.slice(-10).map((item, index) => (
                  <div key={index} className="text-xs">
                    <div className="flex items-center justify-between mb-1">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        item.type === 'fact' ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'
                      }`}>
                        {item.type}
                      </span>
                      <span className="text-gray-400">{Math.round(item.confidence * 100)}%</span>
                    </div>
                    <div className="text-gray-300 font-mono bg-black/20 rounded p-2">
                      {item.content}
                    </div>
                  </div>
                ))}
                
                {gameState.knowledge_base.length === 0 && (
                  <div className="text-gray-400 text-center py-4">
                    No knowledge acquired yet
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;