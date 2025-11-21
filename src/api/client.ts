import axios from 'axios';
import type { AskRequest, AskResponse, MemoryAddRequest, MemoryListResponse } from '../types';

const api = axios.create({
  baseURL: import.meta.env.DEV ? '' : '',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const askQuestion = async (data: AskRequest): Promise<AskResponse> => {
  const response = await api.post<AskResponse>('/ask', data);
  return response.data;
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

