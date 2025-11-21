import axios, { CancelTokenSource } from 'axios';
import type { AskRequest, AskResponse, MemoryAddRequest, MemoryListResponse, PersonalitiesResponse } from '../types';

const api = axios.create({
  baseURL: import.meta.env.DEV ? '' : '',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Store cancel token source for the current ask request
let currentAskCancelToken: CancelTokenSource | null = null;

export const askQuestion = async (data: AskRequest, cancelToken?: CancelTokenSource): Promise<AskResponse> => {
  // If a cancel token is provided, use it; otherwise create a new one
  const tokenSource = cancelToken || axios.CancelToken.source();
  currentAskCancelToken = tokenSource;
  
  try {
    const response = await api.post<AskResponse>('/ask', data, {
      cancelToken: tokenSource.token
    });
    currentAskCancelToken = null;
    return response.data;
  } catch (error) {
    if (axios.isCancel(error)) {
      currentAskCancelToken = null;
      throw new Error('Request cancelled');
    }
    currentAskCancelToken = null;
    throw error;
  }
};

export const cancelAskRequest = () => {
  if (currentAskCancelToken) {
    currentAskCancelToken.cancel('Request cancelled by user');
    currentAskCancelToken = null;
  }
};

export const addMemory = async (data: MemoryAddRequest): Promise<{ status: string }> => {
  const response = await api.post<{ status: string }>('/memory/add', data);
  return response.data;
};

export const listMemories = async (): Promise<MemoryListResponse> => {
  const response = await api.get<MemoryListResponse>('/memory/list');
  return response.data;
};

export const deleteMemory = async (key: string): Promise<{ deleted: string }> => {
  const response = await api.post<{ deleted: string }>('/memory/delete', { key });
  return response.data;
};

export const debugPrompt = async (data: AskRequest): Promise<{ prompt: string; memory_texts: string[]; search_texts: string[] }> => {
  const response = await api.post('/debug-prompt', data);
  return response.data;
};

export const listPersonalities = async (): Promise<PersonalitiesResponse> => {
  const response = await api.get<PersonalitiesResponse>('/personalities');
  return response.data;
};

export interface ChatMessage {
  id: string;
  timestamp: string;
  display_timestamp: string;
  question: string;
  answer: string;
  images?: string[];
  files?: string[];
  personality?: string;
  used_memory: boolean;
  used_search: boolean;
  status?: 'pending' | 'sent' | 'error';
  is_local?: boolean;
}

export interface ChatHistoryResponse {
  interactions: ChatMessage[];
  total: number;
}

export const getChatHistory = async (limit: number = 100): Promise<ChatHistoryResponse> => {
  const response = await api.get<ChatHistoryResponse>(`/chat/history?limit=${limit}`);
  return response.data;
};

