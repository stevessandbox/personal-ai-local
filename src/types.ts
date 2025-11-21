export interface AskRequest {
  question: string;
  use_memory?: boolean;
  use_search?: boolean;
}

export interface TavilyInfo {
  called: boolean;
  status: string;
  success: boolean;
  params?: {
    query: string;
    search_depth: string;
    max_results: number;
    api_key: string;
  };
  http_status?: number;
  results_count?: number;
  error?: string;
}

export interface AskResponse {
  answer: string;
  tavily_info: TavilyInfo;
  search_texts: string[];
  memory_texts: string[];
  timings?: Record<string, number>;
}

export interface MemoryAddRequest {
  key: string;
  text: string;
  metadata?: Record<string, any>;
}

export interface MemoryListResponse {
  ids: string[];
  documents: string[];
  metadatas: Record<string, any>[];
}

