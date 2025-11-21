import { useState, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from 'react-query';
import { askQuestion, debugPrompt, listPersonalities, cancelAskRequest } from '../api/client';
import TavilyStatus from './TavilyStatus';
import type { AskResponse } from '../types';
import axios, { CancelTokenSource } from 'axios';

export default function AskPanel() {
  const [question, setQuestion] = useState('');
  const [useMemory, setUseMemory] = useState(true);  // Enable memory by default to remember interactions
  const [useSearch, setUseSearch] = useState(true);
  const [personality, setPersonality] = useState('');
  const [selectedPersonalityId, setSelectedPersonalityId] = useState<string | null>(null);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [images, setImages] = useState<string[]>([]);  // Base64-encoded images
  const [files, setFiles] = useState<Array<{name: string, size: number, type: string}>>([]);  // File metadata
  const [fileContents, setFileContents] = useState<Map<string, string>>(new Map());  // Base64 file contents

  const queryClient = useQueryClient();

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

  // Cancel token for current request
  const cancelTokenRef = useRef<CancelTokenSource | null>(null);

  const askMutation = useMutation(
    async (data: Parameters<typeof askQuestion>[0]) => {
      // Create cancel token for this request
      cancelTokenRef.current = axios.CancelToken.source();
      return askQuestion(data, cancelTokenRef.current);
    },
    {
      onSuccess: (data) => {
        setResponse(data);
        // Refetch personalities after successful interaction (new personality may have been stored)
        refetchPersonalities();
        // Invalidate chat history query to refresh the chat view
        queryClient.invalidateQueries('chatHistory');
        // Clear images and files after successful submission
        setImages([]);
        setFiles([]);
        setFileContents(new Map());
        cancelTokenRef.current = null;
      },
      onError: (error: any) => {
        cancelTokenRef.current = null;
        // Don't show error for cancelled requests
        if (error?.message !== 'Request cancelled by user' && !axios.isCancel(error)) {
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
        }
      },
    }
  );

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

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    const fileArray = Array.from(files);
    const MAX_IMAGES = 3;
    const MAX_SIZE_MB = 10;
    const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

    // Check total image count
    if (images.length + fileArray.length > MAX_IMAGES) {
      alert(`Maximum ${MAX_IMAGES} images allowed. You already have ${images.length} image(s).`);
      e.target.value = ''; // Reset input
      return;
    }

    const newImages: string[] = [];
    const errors: string[] = [];

    fileArray.forEach((file) => {
      // Check file type
      if (!file.type.startsWith('image/')) {
        errors.push(`${file.name} is not an image file`);
        return;
      }

      // Check file size (10MB limit)
      if (file.size > MAX_SIZE_BYTES) {
        errors.push(`${file.name} exceeds ${MAX_SIZE_MB}MB limit (${(file.size / 1024 / 1024).toFixed(2)}MB)`);
        return;
      }

      const reader = new FileReader();
      reader.onload = (event) => {
        const result = event.target?.result as string;
        if (result) {
          newImages.push(result);
          // When all valid files are processed
          if (newImages.length + images.length === fileArray.filter(f => f.type.startsWith('image/') && f.size <= MAX_SIZE_BYTES).length) {
            if (errors.length > 0) {
              alert(`Some files were skipped:\n${errors.join('\n')}`);
            }
            setImages((prev) => [...prev, ...newImages]);
          }
        }
      };
      reader.readAsDataURL(file);
    });

    e.target.value = ''; // Reset input after processing
  };

  const removeImage = (index: number) => {
    setImages((prev) => prev.filter((_, i) => i !== index));
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const uploadedFiles = e.target.files;
    if (!uploadedFiles) return;

    const fileArray = Array.from(uploadedFiles);
    const MAX_FILES = 5;
    const MAX_SIZE_MB = 10;
    const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;
    const ALLOWED_TYPES = [
      'text/plain',
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // .docx
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', // .xlsx
      'application/vnd.ms-excel', // .xls
    ];

    // Check total file count
    if (files.length + fileArray.length > MAX_FILES) {
      alert(`Maximum ${MAX_FILES} files allowed. You already have ${files.length} file(s).`);
      e.target.value = '';
      return;
    }

    const newFiles: Array<{name: string, size: number, type: string}> = [];
    const newFileContents = new Map<string, string>();
    const errors: string[] = [];

    fileArray.forEach((file) => {
      // Check file type
      if (!ALLOWED_TYPES.includes(file.type) && !file.name.match(/\.(txt|pdf|docx|xlsx|xls)$/i)) {
        errors.push(`${file.name} is not a supported file type (txt, pdf, docx, xlsx, xls)`);
        return;
      }

      // Check file size (10MB limit)
      if (file.size > MAX_SIZE_BYTES) {
        errors.push(`${file.name} exceeds ${MAX_SIZE_MB}MB limit (${(file.size / 1024 / 1024).toFixed(2)}MB)`);
        return;
      }

      const reader = new FileReader();
      reader.onload = (event) => {
        const result = event.target?.result as string;
        if (result) {
          // Extract base64 data (remove data URL prefix if present)
          const base64Content = result.includes(',') ? result.split(',')[1] : result;
          newFileContents.set(file.name, base64Content);
          newFiles.push({
            name: file.name,
            size: file.size,
            type: file.type || 'application/octet-stream'
          });

          // When all valid files are processed
          if (newFiles.length === fileArray.filter(f => 
            (ALLOWED_TYPES.includes(f.type) || f.name.match(/\.(txt|pdf|docx|xlsx|xls)$/i)) && 
            f.size <= MAX_SIZE_BYTES
          ).length) {
            if (errors.length > 0) {
              alert(`Some files were skipped:\n${errors.join('\n')}`);
            }
            setFiles((prev) => [...prev, ...newFiles]);
            setFileContents((prev) => {
              const updated = new Map(prev);
              newFileContents.forEach((content, name) => updated.set(name, content));
              return updated;
            });
          }
        }
      };
      reader.readAsDataURL(file);
    });

    e.target.value = ''; // Reset input after processing
  };

  const removeFile = (fileName: string) => {
    setFiles((prev) => prev.filter(f => f.name !== fileName));
    setFileContents((prev) => {
      const updated = new Map(prev);
      updated.delete(fileName);
      return updated;
    });
  };

  const handleAsk = () => {
    if (!question.trim() && images.length === 0 && files.length === 0) {
      alert('Type a question, upload an image, or upload a file first.');
      return;
    }
    
    // Prepare files for API
    const filesForApi = files.length > 0 ? files.map(f => ({
      name: f.name,
      content: fileContents.get(f.name) || '',
      type: f.type
    })) : undefined;

    askMutation.mutate({
      question: question.trim() || (images.length > 0 ? 'What do you see in this image?' : 'Analyze this file.'),
      use_memory: useMemory,
      use_search: useSearch,
      personality: getPersonalityValue(),
      images: images.length > 0 ? images : undefined,
      files: filesForApi,
    });
  };

  // Cancel handler
  const handleCancel = () => {
    if (cancelTokenRef.current) {
      cancelTokenRef.current.cancel('Request cancelled by user');
      cancelTokenRef.current = null;
      askMutation.reset();
    }
    cancelAskRequest();
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
        placeholder="Ask anything... (or upload an image to analyze)"
        rows={3}
        disabled={askMutation.isLoading}
        className="w-full p-2 rounded-md border border-white/10 bg-white/5 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 mb-3 disabled:opacity-50 disabled:cursor-not-allowed"
      />

      {/* Image Upload Section */}
      <div className="mb-3">
        <label className="block text-sm text-gray-300 mb-2">
          Images (optional) - Max 3 images, 10MB each
        </label>
        <input
          type="file"
          accept="image/*"
          multiple
          onChange={handleImageUpload}
          disabled={images.length >= 3 || askMutation.isLoading}
          className="w-full p-2 rounded-md border border-white/10 bg-white/5 text-white text-sm file:mr-4 file:py-1 file:px-3 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-500 file:text-white hover:file:bg-blue-600 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        />
        {images.length >= 3 && (
          <p className="text-xs text-yellow-400 mt-1">Maximum 3 images reached</p>
        )}
        
        {/* Image Previews */}
        {images.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {images.map((img, index) => (
              <div key={index} className="relative inline-block">
                <img
                  src={img}
                  alt={`Upload ${index + 1}`}
                  className="w-24 h-24 object-cover rounded-md border border-white/10"
                />
                <button
                  onClick={() => removeImage(index)}
                  className="absolute top-0 right-0 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs hover:bg-red-600"
                  title="Remove image"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* File Upload Section */}
      <div className="mb-3">
        <label className="block text-sm text-gray-300 mb-2">
          Files (optional) - Max 5 files, 10MB each (txt, pdf, docx, xlsx, xls)
        </label>
        <input
          type="file"
          accept=".txt,.pdf,.docx,.xlsx,.xls,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
          multiple
          onChange={handleFileUpload}
          disabled={files.length >= 5 || askMutation.isLoading}
          className="w-full p-2 rounded-md border border-white/10 bg-white/5 text-white text-sm file:mr-4 file:py-1 file:px-3 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-green-500 file:text-white hover:file:bg-green-600 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        />
        {files.length >= 5 && (
          <p className="text-xs text-yellow-400 mt-1">Maximum 5 files reached</p>
        )}
        
        {/* File List */}
        {files.length > 0 && (
          <div className="mt-3 space-y-2">
            {files.map((file, index) => (
              <div key={index} className="flex items-center justify-between p-2 bg-white/5 rounded-md border border-white/10">
                <div className="flex-1">
                  <p className="text-sm text-white">{file.name}</p>
                  <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(2)} KB</p>
                </div>
                <button
                  onClick={() => removeFile(file.name)}
                  className="ml-2 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs hover:bg-red-600"
                  title="Remove file"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mb-3 space-y-2">
        <label className="block text-sm text-gray-300 mb-1">Personality (optional)</label>
        
        {/* Dropdown for stored personalities */}
        {personalitiesData && personalitiesData.personalities && personalitiesData.personalities.length > 0 && (
          <select
            value={selectedPersonalityId || ''}
            onChange={(e) => handlePersonalitySelect(e.target.value || null)}
            className="w-full p-2 rounded-md border border-white/10 bg-white/5 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm mb-2"
            disabled={!!personality.trim() || askMutation.isLoading}
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
          disabled={!!selectedPersonalityId || askMutation.isLoading}
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
        <div className="flex gap-2">
          {askMutation.isLoading && (
            <button
              onClick={handleCancel}
              className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
            >
              Cancel
            </button>
          )}
          <button
            onClick={handleAsk}
            disabled={askMutation.isLoading}
            className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {askMutation.isLoading ? 'Thinking...' : 'Ask'}
          </button>
        </div>
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

