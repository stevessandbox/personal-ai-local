import { useState } from 'react';
import AskPanel from './components/AskPanel';
import MemoryPanel from './components/MemoryPanel';
import ChatHistory from './components/ChatHistory';

function App() {
  const [activeTab, setActiveTab] = useState<'chat' | 'ask' | 'memory'>('ask');

  // Error boundary fallback
  try {
    return (
      <div className="min-h-screen p-6 bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-semibold mb-6 text-white">Personal AI (Local)</h1>
        
        {/* Tab Navigation */}
        <div className="flex space-x-2 mb-4 border-b border-white/10">
          <button
            onClick={() => setActiveTab('chat')}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'chat'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Chat
          </button>
          <button
            onClick={() => setActiveTab('ask')}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'ask'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Ask
          </button>
          <button
            onClick={() => setActiveTab('memory')}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'memory'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Memory
          </button>
        </div>
        
        <div className="space-y-4">
          {activeTab === 'chat' && <ChatHistory />}
          {activeTab === 'ask' && <AskPanel />}
          {activeTab === 'memory' && <MemoryPanel />}
        </div>

        <footer className="mt-8 text-sm text-gray-400 text-center">
          <small>Served locally. Model runs on your machine.</small>
        </footer>
      </div>
    </div>
    );
  } catch (error) {
    console.error('App render error:', error);
    return (
      <div className="min-h-screen p-6 bg-gray-900 text-white">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-2xl font-semibold mb-4 text-red-400">Error Loading App</h1>
          <p className="text-gray-300">{(error as Error).message}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Reload Page
          </button>
        </div>
      </div>
    );
  }
}

export default App;

