import { useState } from 'react';
import AskPanel from './components/AskPanel';
import MemoryPanel from './components/MemoryPanel';

function App() {
  return (
    <div className="min-h-screen p-6">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-semibold mb-6 text-white">Personal AI (Local)</h1>
        
        <div className="space-y-4">
          <AskPanel />
          <MemoryPanel />
        </div>

        <footer className="mt-8 text-sm text-gray-400 text-center">
          <small>Served locally. Model runs on your machine.</small>
        </footer>
      </div>
    </div>
  );
}

export default App;

