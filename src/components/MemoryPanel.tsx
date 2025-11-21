import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from 'react-query';
import { addMemory, listMemories, deleteMemory } from '../api/client';

export default function MemoryPanel() {
  const [memKey, setMemKey] = useState('');
  const [memText, setMemText] = useState('');
  const queryClient = useQueryClient();

  const { data: memories, isLoading } = useQuery('memories', listMemories);

  const addMutation = useMutation(addMemory, {
    onSuccess: () => {
      queryClient.invalidateQueries('memories');
      setMemKey('');
      setMemText('');
    },
  });

  const deleteMutation = useMutation(deleteMemory, {
    onSuccess: () => {
      queryClient.invalidateQueries('memories');
    },
  });

  const handleAdd = () => {
    if (!memKey.trim() || !memText.trim()) {
      alert('Provide both key and memory text.');
      return;
    }
    addMutation.mutate({
      key: memKey.trim(),
      text: memText.trim(),
      metadata: { source: 'ui' },
    });
  };

  const handleList = () => {
    queryClient.invalidateQueries('memories');
  };

  const handleDelete = (key: string) => {
    if (confirm(`Delete memory "${key}"?`)) {
      deleteMutation.mutate(key);
    }
  };

  return (
    <div className="bg-white/5 rounded-lg p-4 shadow-lg border border-white/10">
      <h2 className="text-xl font-semibold mb-4 text-white">Memory</h2>
      
      <div className="space-y-3 mb-4">
        <input
          type="text"
          value={memKey}
          onChange={(e) => setMemKey(e.target.value)}
          placeholder="Key (e.g. note-1)"
          className="w-full p-2 rounded-md border border-white/10 bg-white/5 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <input
          type="text"
          value={memText}
          onChange={(e) => setMemText(e.target.value)}
          placeholder="Memory text (short)"
          className="w-full p-2 rounded-md border border-white/10 bg-white/5 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div className="flex gap-2 mb-4">
        <button
          onClick={handleAdd}
          disabled={addMutation.isLoading}
          className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {addMutation.isLoading ? 'Adding...' : 'Add Memory'}
        </button>
        <button
          onClick={handleList}
          disabled={isLoading}
          className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? 'Loading...' : 'List Memories'}
        </button>
      </div>

      <div className="bg-white/5 rounded-md p-4 min-h-[48px]">
        {isLoading ? (
          <div className="text-gray-400">Loading...</div>
        ) : memories && memories.ids && memories.ids.length > 0 ? (
          <div className="space-y-2">
            {memories.ids.map((id, idx) => (
              <div key={id} className="bg-black/20 rounded p-3 flex justify-between items-start">
                <div className="flex-1">
                  <strong className="text-white">{id}</strong>
                  <div className="text-gray-300 text-sm mt-1">
                    {memories.documents[idx] || ''}
                  </div>
                  <em className="text-gray-400 text-xs">
                    {JSON.stringify(memories.metadatas[idx] || {})}
                  </em>
                </div>
                <button
                  onClick={() => handleDelete(id)}
                  className="ml-2 px-2 py-1 bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 transition-colors text-xs"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-gray-400">No memories listed yet</div>
        )}
      </div>
    </div>
  );
}

