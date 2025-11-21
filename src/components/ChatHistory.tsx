import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import { getChatHistory, askQuestion, cancelAskRequest } from '../api/client';
import axios, { CancelTokenSource } from 'axios';

export default function ChatHistory() {
  // All hooks must be called before any conditional returns
  const queryClient = useQueryClient();
  const {
    data,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useQuery(
    'chatHistory',
    async () => {
      try {
        const result = await getChatHistory(100);
        console.log('getChatHistory result:', result);
        return result;
      } catch (err) {
        console.error('Chat history API error:', err);
        return { interactions: [], total: 0 };
      }
    },
    {
      retry: 1,
      refetchInterval: 5000,
      refetchIntervalInBackground: true,
    }
  );
  const [question, setQuestion] = useState('');
  const [useMemory, setUseMemory] = useState(true);
  const [useSearch, setUseSearch] = useState(true);
  const [personality, setPersonality] = useState('');
  const [images, setImages] = useState<string[]>([]);
  const [files, setFiles] = useState<Array<{ name: string; size: number; type: string }>>([]);
  const [fileContents, setFileContents] = useState<Map<string, string>>(new Map());
  const chatEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);

  // Cancel token for current request
  const cancelTokenRef = useRef<CancelTokenSource | null>(null);

  // Ask mutation - must be called before any conditional returns
  const askMutation = useMutation(
    async (data: Parameters<typeof askQuestion>[0]) => {
      // Create cancel token for this request
      cancelTokenRef.current = axios.CancelToken.source();
      return askQuestion(data, cancelTokenRef.current);
    },
    {
      onSuccess: () => {
        setQuestion('');
        setImages([]);
        setFiles([]);
        setFileContents(new Map());
        queryClient.invalidateQueries('chatHistory');
        refetch();
        cancelTokenRef.current = null;
      },
      onError: (error: any) => {
        cancelTokenRef.current = null;
        // Don't show alert for cancelled requests
        if (error?.message !== 'Request cancelled by user' && !axios.isCancel(error)) {
          alert(`Error: ${error?.message || 'Unknown error'}`);
        }
      },
    }
  );

  // Cancel handler
  const handleCancel = () => {
    if (cancelTokenRef.current) {
      cancelTokenRef.current.cancel('Request cancelled by user');
      cancelTokenRef.current = null;
      askMutation.reset();
    }
    cancelAskRequest();
  };

  // Scroll effect - must be called before any conditional returns
  useEffect(() => {
    if (chatEndRef.current && !isLoading) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [data?.interactions, isLoading]);

  // Debug logging - must be called before any conditional returns
  useEffect(() => {
    console.log('ChatHistory state:', { 
      isLoading,
      error: error instanceof Error ? error.message : String(error),
      hasData: !!data,
      total: data?.total,
      rawInteractions: data?.interactions,
      interactionsCount: (data?.interactions || []).length,
      filteredInteractions: (data?.interactions || []).filter((msg: any) => msg && msg.id),
    });
  }, [data, isLoading, error]);

  // Handle loading and error states in JSX, not with early returns
  if (isLoading) {
    return (
      <div className="bg-white/5 rounded-lg p-4 shadow-lg border border-white/10">
        <p className="text-white">Loading chat history...</p>
      </div>
    );
  }

  if (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return (
      <div className="bg-white/5 rounded-lg p-4 shadow-lg border border-white/10 space-y-3">
        <p className="text-red-400">Error loading chat history: {message}</p>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Retry
        </button>
      </div>
    );
  }

  // Handle image upload (same as AskPanel)
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const uploadedFiles = e.target.files;
    if (!uploadedFiles) return;

    const fileArray = Array.from(uploadedFiles);
    const MAX_IMAGES = 3;
    const MAX_SIZE_MB = 10;
    const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

    if (images.length + fileArray.length > MAX_IMAGES) {
      alert(`Maximum ${MAX_IMAGES} images allowed. You already have ${images.length} image(s).`);
      e.target.value = '';
      return;
    }

    const newImages: string[] = [];
    const errors: string[] = [];

    fileArray.forEach((file) => {
      if (!file.type.startsWith('image/')) {
        errors.push(`${file.name} is not an image file`);
        return;
      }

      if (file.size > MAX_SIZE_BYTES) {
        errors.push(`${file.name} exceeds ${MAX_SIZE_MB}MB limit (${(file.size / 1024 / 1024).toFixed(2)}MB)`);
        return;
      }

      const reader = new FileReader();
      reader.onload = (event) => {
        const result = event.target?.result as string;
        if (result) {
          newImages.push(result);
          if (newImages.length === fileArray.filter(f => f.type.startsWith('image/') && f.size <= MAX_SIZE_BYTES).length) {
            if (errors.length > 0) {
              alert(`Some files were skipped:\n${errors.join('\n')}`);
            }
            setImages((prev) => [...prev, ...newImages]);
          }
        }
      };
      reader.readAsDataURL(file);
    });

    e.target.value = '';
  };

  // Handle file upload (same as AskPanel)
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
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-excel',
    ];

    if (files.length + fileArray.length > MAX_FILES) {
      alert(`Maximum ${MAX_FILES} files allowed. You already have ${files.length} file(s).`);
      e.target.value = '';
      return;
    }

    const newFiles: Array<{name: string, size: number, type: string}> = [];
    const newFileContents = new Map<string, string>();
    const errors: string[] = [];

    fileArray.forEach((file) => {
      if (!ALLOWED_TYPES.includes(file.type) && !file.name.match(/\.(txt|pdf|docx|xlsx|xls)$/i)) {
        errors.push(`${file.name} is not a supported file type (txt, pdf, docx, xlsx, xls)`);
        return;
      }

      if (file.size > MAX_SIZE_BYTES) {
        errors.push(`${file.name} exceeds ${MAX_SIZE_MB}MB limit (${(file.size / 1024 / 1024).toFixed(2)}MB)`);
        return;
      }

      const reader = new FileReader();
      reader.onload = (event) => {
        const result = event.target?.result as string;
        if (result) {
          const base64Content = result.includes(',') ? result.split(',')[1] : result;
          newFileContents.set(file.name, base64Content);
          newFiles.push({
            name: file.name,
            size: file.size,
            type: file.type || 'application/octet-stream'
          });

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

    e.target.value = '';
  };

  const removeImage = (index: number) => {
    setImages((prev) => prev.filter((_, i) => i !== index));
  };

  const removeFile = (fileName: string) => {
    setFiles((prev) => prev.filter(f => f.name !== fileName));
    setFileContents((prev) => {
      const updated = new Map(prev);
      updated.delete(fileName);
      return updated;
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() && images.length === 0 && files.length === 0) {
      alert('Type a question, upload an image, or upload a file first.');
      return;
    }

    const filesForApi = files.length > 0 ? files.map(f => ({
      name: f.name,
      content: fileContents.get(f.name) || '',
      type: f.type
    })) : undefined;

    askMutation.mutate({
      question: question.trim() || (images.length > 0 ? 'What do you see in this image?' : 'Analyze this file.'),
      use_memory: useMemory,
      use_search: useSearch,
      personality: personality.trim() || undefined,
      images: images.length > 0 ? images : undefined,
      files: filesForApi,
    });
  };

  // Get interactions - API should already return valid interactions with ids
  const interactions = data?.interactions || [];
  
  // Debug: Log the actual interactions array
  if (data && data.interactions) {
    console.log('Raw interactions from API:', data.interactions);
    console.log('Interactions length:', data.interactions.length);
    if (data.interactions.length > 0) {
      console.log('First interaction:', data.interactions[0]);
    }
  }

  return (
    <div className="bg-white/5 rounded-lg p-4 shadow-lg border border-white/10 flex flex-col h-[85vh]">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-white">Chat</h2>
        <span className={`text-xs ${isFetching ? 'text-green-400' : 'text-gray-400'}`}>
          {isFetching ? 'Syncing…' : 'Up to date'}
        </span>
      </div>
      
      {/* Chat Messages Area */}
      <div className="flex-1 overflow-y-auto pr-2 mb-4">
        {interactions.length === 0 ? (
          <p className="text-gray-400 text-center py-8">
            {isLoading ? 'Loading chat history...' : 'No interactions yet. Start chatting below!'}
          </p>
        ) : (
          <div className="space-y-6">
          {interactions.map((msg: any, idx: number) => (
            <div key={msg.id || `msg-${idx}`} className="space-y-3">
              {/* User Message */}
              <div className="flex flex-col items-end">
                <div className="bg-blue-600 text-white rounded-lg px-4 py-2 max-w-[80%] rounded-br-none">
                  <p className="text-sm whitespace-pre-wrap">{msg.question}</p>
                  
                  {/* Display images if any */}
                  {msg.images && msg.images.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {msg.images.map((imgPath: string, idx: number) => {
                        // Ensure image path is absolute - prepend API base URL if needed
                        const imageUrl = imgPath.startsWith('http') 
                          ? imgPath 
                          : imgPath.startsWith('/') 
                            ? (import.meta.env.DEV ? `http://localhost:8000${imgPath}` : imgPath)
                            : `/images/${imgPath}`;
                        return (
                          <img
                            key={idx}
                            src={imageUrl}
                            alt={`Upload ${idx + 1}`}
                            className="max-w-[200px] max-h-[200px] object-cover rounded-md border border-white/20 cursor-pointer hover:opacity-80 transition-opacity"
                            onClick={() => window.open(imageUrl, '_blank')}
                            onError={(e) => {
                              console.error('Failed to load image:', imageUrl);
                              (e.target as HTMLImageElement).style.display = 'none';
                            }}
                          />
                        );
                      })}
                    </div>
                  )}
                  
                  {/* Display files if any */}
                  {msg.files && msg.files.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {msg.files.map((filePath: string, idx: number) => {
                        const isLocal = filePath.startsWith('local:');
                        const fileName = isLocal
                          ? filePath.replace('local:', '')
                          : filePath.split('/').pop() || `File ${idx + 1}`;
                        return (
                          isLocal ? (
                            <span
                              key={idx}
                              className="block text-xs bg-blue-700 px-2 py-1 rounded text-white"
                            >
                              📄 {fileName}
                            </span>
                          ) : (
                            <a
                              key={idx}
                              href={filePath}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="block text-xs bg-blue-700 hover:bg-blue-800 px-2 py-1 rounded text-white underline"
                            >
                              📄 {fileName}
                            </a>
                          )
                        );
                      })}
                    </div>
                  )}
                  
                  <p className="text-xs text-blue-100 mt-1 opacity-70">{msg.display_timestamp}</p>
                </div>
              </div>

              {/* AI Response */}
              <div className="flex flex-col items-start">
                <div className="bg-gray-700 text-white rounded-lg px-4 py-3 max-w-[80%] rounded-bl-none shadow-md">
                  <p className="text-sm whitespace-pre-wrap break-words">{msg.answer}</p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    {msg.used_memory && <span className="bg-gray-600 px-2 py-1 rounded text-gray-300">💾 Memory</span>}
                    {msg.used_search && <span className="bg-gray-600 px-2 py-1 rounded text-gray-300">🔍 Search</span>}
                    {msg.personality && <span className="bg-gray-600 px-2 py-1 rounded text-gray-300">🎭 {msg.personality}</span>}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
        <div ref={chatEndRef} />
      </div>

      {/* Input Area */}
      <form onSubmit={handleSubmit} className="border-t border-white/10 pt-4 space-y-3">
        {/* Question Input */}
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Type your message... (or upload images/files)"
          rows={2}
          className="w-full p-2 rounded-md border border-white/10 bg-white/5 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
        />

        {/* Image and File Uploads */}
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="block text-xs text-gray-300 mb-1">Images (max 3, 10MB each)</label>
            <input
              ref={imageInputRef}
              type="file"
              accept="image/*"
              multiple
              onChange={handleImageUpload}
              disabled={images.length >= 3 || askMutation.isLoading}
              className="w-full p-1.5 rounded-md border border-white/10 bg-white/5 text-white text-xs file:mr-2 file:py-1 file:px-2 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-blue-500 file:text-white hover:file:bg-blue-600 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            />
            {images.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1">
                {images.map((img, idx) => (
                  <div key={idx} className="relative">
                    <img src={img} alt={`${idx + 1}`} className="w-12 h-12 object-cover rounded border border-white/10" />
                    <button
                      type="button"
                      onClick={() => removeImage(idx)}
                      className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-4 h-4 flex items-center justify-center text-xs"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="flex-1">
            <label className="block text-xs text-gray-300 mb-1">Files (max 5, 10MB each)</label>
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.pdf,.docx,.xlsx,.xls"
              multiple
              onChange={handleFileUpload}
              disabled={files.length >= 5 || askMutation.isLoading}
              className="w-full p-1.5 rounded-md border border-white/10 bg-white/5 text-white text-xs file:mr-2 file:py-1 file:px-2 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-green-500 file:text-white hover:file:bg-green-600 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            />
            {files.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1">
                {files.map((f, idx) => (
                  <span key={idx} className="text-xs bg-green-600 px-2 py-0.5 rounded flex items-center gap-1">
                    {f.name}
                    <button
                      type="button"
                      onClick={() => removeFile(f.name)}
                      className="text-white hover:text-red-300"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Options and Submit */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-4 text-sm">
            <label className="flex items-center gap-2 text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={useMemory}
                onChange={(e) => setUseMemory(e.target.checked)}
                disabled={askMutation.isLoading}
                className="rounded disabled:opacity-50 disabled:cursor-not-allowed"
              />
              Memory
            </label>
            <label className="flex items-center gap-2 text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={useSearch}
                onChange={(e) => setUseSearch(e.target.checked)}
                disabled={askMutation.isLoading}
                className="rounded disabled:opacity-50 disabled:cursor-not-allowed"
              />
              Search
            </label>
            <input
              type="text"
              value={personality}
              onChange={(e) => setPersonality(e.target.value)}
              placeholder="Personality (optional)"
              disabled={askMutation.isLoading}
              className="px-2 py-1 rounded border border-white/10 bg-white/5 text-white text-sm placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            />
          </div>
          <div className="flex gap-2">
            {askMutation.isLoading && (
              <button
                type="button"
                onClick={handleCancel}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
              >
                Cancel
              </button>
            )}
            <button
              type="submit"
              disabled={askMutation.isLoading || (!question.trim() && images.length === 0 && files.length === 0)}
              className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {askMutation.isLoading ? 'Sending...' : 'Send'}
            </button>
          </div>
        </div>
      </form>
      
      {interactions.length > 0 && (
        <p className="text-xs text-gray-400 text-center mt-2">
          Showing {interactions.length} of {data?.total || 0} interactions
        </p>
      )}
    </div>
  );
}

