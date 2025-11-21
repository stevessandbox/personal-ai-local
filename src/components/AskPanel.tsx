import { useState } from 'react';
import { useMutation, useQuery } from 'react-query';
import { askQuestion, debugPrompt, listPersonalities } from '../api/client';
import TavilyStatus from './TavilyStatus';
import type { AskResponse } from '../types';

export default function AskPanel() {
  const [question, setQuestion] = useState('');
  const [useMemory, setUseMemory] = useState(true);  // Enable memory by default to remember interactions
  const [useSearch, setUseSearch] = useState(true);
  const [personality, setPersonality] = useState('');
  const [selectedPersonalityId, setSelectedPersonalityId] = useState<string | null>(null);
  const [response, setResponse] = useState<AskResponse | null>(null);

  // Fetch available personalities (with error handling to prevent crashes)
  const { data: personalitiesData, refetch: refetchPersonalities } = useQuery(
    'personalities',
    listPersonalities,
    {
      refetchOnWindowFocus: false,
      retry: 1,
      onError: (error) => {
        // Silently handle errors - personalities are optional
        console.warn('Failed to load personalities:', error);
      },
    }
  );

  const askMutation = useMutation(askQuestion, {
    onSuccess: (data) => {
      setResponse(data);
      // Refetch personalities after successful interaction (new personality may have been stored)
      refetchPersonalities();
    },
    onError: (error: any) => {
      setResponse({
        answer: `Error: ${error.message || 'Unknown error'}`,
        tavily_info: {
          called: false,
          status: 'error',
          success: false,
        },
        search_texts: [],
        memory_texts: [],
      });
    },
  });

  const debugMutation = useMutation(debugPrompt, {
    onSuccess: (data) => {
      setResponse({
        answer: data.prompt,
        tavily_info: {
          called: false,
          status: 'not called',
          success: false,
        },
        search_texts: data.search_texts,
        memory_texts: data.memory_texts,
      });
    },
  });

  // Get the actual personality value (from dropdown or text input)
  const getPersonalityValue = (): string | undefined => {
    if (selectedPersonalityId && personalitiesData?.personalities) {
      const selected = personalitiesData.personalities.find(p => p.id === selectedPersonalityId);
      return selected?.text;
    }
    return personality.trim() || undefined;
  };

  const handlePersonalitySelect = (personalityId: string | null) => {
    setSelectedPersonalityId(personalityId);
    if (personalityId) {
      // Clear text input when dropdown is selected
      setPersonality('');
    }
  };

  const handlePersonalityTextChange = (value: string) => {
    setPersonality(value);
    // Clear dropdown selection when typing
    if (selectedPersonalityId) {
      setSelectedPersonalityId(null);
    }
  };

  const handleAsk = () => {
    if (!question.trim()) {
      alert('Type a question first.');
      return;
    }
    askMutation.mutate({
      question: question.trim(),
      use_memory: useMemory,
      use_search: useSearch,
      personality: getPersonalityValue(),
    });
  };

  const handleDebug = () => {
    if (!question.trim()) {
      alert('Type a question first.');
      return;
    }
    debugMutation.mutate({
      question: question.trim(),
      use_memory: useMemory,
      use_search: useSearch,
      personality: getPersonalityValue(),
    });
  };

  return (
    <div className="bg-white/5 rounded-lg p-4 shadow-lg border border-white/10">
      <h2 className="text-xl font-semibold mb-4 text-white">Ask</h2>
      
      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask anything..."
        rows={3}
        className="w-full p-2 rounded-md border border-white/10 bg-white/5 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 mb-3"
      />

      <div className="mb-3 space-y-2">
        <label className="block text-sm text-gray-300 mb-1">Personality (optional)</label>
        
        {/* Dropdown for stored personalities */}
        {personalitiesData && personalitiesData.personalities && personalitiesData.personalities.length > 0 && (
          <select
            value={selectedPersonalityId || ''}
            onChange={(e) => handlePersonalitySelect(e.target.value || null)}
            className="w-full p-2 rounded-md border border-white/10 bg-white/5 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm mb-2"
            disabled={!!personality.trim()}
          >
            <option value="">Select a saved personality...</option>
            {personalitiesData.personalities.map((p) => (
              <option key={p.id} value={p.id} className="bg-gray-800">
                {p.text}
              </option>
            ))}
          </select>
        )}
        
        {/* Text input for custom personality */}
        <input
          type="text"
          value={personality}
          onChange={(e) => handlePersonalityTextChange(e.target.value)}
          placeholder={selectedPersonalityId ? "Using saved personality above" : "Or type a custom personality (e.g., goth, friendly, professional)"}
          disabled={!!selectedPersonalityId}
          className="w-full p-2 rounded-md border border-white/10 bg-white/5 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        />
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
          <input
            type="checkbox"
            checked={useMemory}
            onChange={(e) => setUseMemory(e.target.checked)}
            className="w-4 h-4 rounded border-white/20 bg-white/5 text-blue-500 focus:ring-2 focus:ring-blue-500"
          />
          Use memory
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
          <input
            type="checkbox"
            checked={useSearch}
            onChange={(e) => setUseSearch(e.target.checked)}
            className="w-4 h-4 rounded border-white/20 bg-white/5 text-blue-500 focus:ring-2 focus:ring-blue-500"
          />
          Use web search
        </label>
        <button
          onClick={handleAsk}
          disabled={askMutation.isLoading}
          className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {askMutation.isLoading ? 'Thinking...' : 'Ask'}
        </button>
        <button
          onClick={handleDebug}
          disabled={debugMutation.isLoading}
          className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {debugMutation.isLoading ? 'Building...' : 'Show Debug Prompt'}
        </button>
      </div>

      {response && (
        <div className="mt-4 space-y-4">
          <div className="bg-white/5 rounded-md p-4 border-b border-white/10">
            <strong className="text-white">Answer:</strong>
            <div className="mt-2 text-gray-300 whitespace-pre-wrap">
              {response.answer || '(no answer)'}
            </div>
          </div>

          {response.tavily_info && (
            <TavilyStatus info={response.tavily_info} />
          )}
          
          {/* Debug: Show raw tavily_info if it exists */}
          {import.meta.env.DEV && response.tavily_info && (
            <details className="bg-gray-800/50 rounded p-2 text-xs">
              <summary className="cursor-pointer text-gray-400">Debug: Raw tavily_info</summary>
              <pre className="mt-2 text-gray-300 overflow-auto">
                {JSON.stringify(response.tavily_info, null, 2)}
              </pre>
            </details>
          )}

          {response.search_texts && response.search_texts.length > 0 && (
            <div className="bg-white/5 rounded-md p-4">
              <strong className="text-white">Search Results:</strong>
              <ul className="mt-2 space-y-2 list-disc list-inside text-sm text-gray-400">
                {response.search_texts.map((text, idx) => (
                  <li key={idx} className="text-gray-300">
                    {text.substring(0, 200)}{text.length > 200 ? '...' : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

