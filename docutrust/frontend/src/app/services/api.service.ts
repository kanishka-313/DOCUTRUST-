import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, Subject } from 'rxjs';

export interface DocumentOut {
  id: string;
  filename: string;
  pages: number;
  chunk_count: number;
  bytes: number;
  uploaded_at: string;
}

export interface Citation {
  source: string;
  snippet: string;
  score: number | null;
}

export interface TraceLog {
  agent: string;
  status: string;
  message: string;
  payload?: any;
  created_at: string;
}

export interface QuerySummary {
  id: string;
  question: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  decision?: string | null;
  created_at: string;
  completed_at?: string | null;
}

export interface QueryDetail extends QuerySummary {
  answer?: string | null;
  error?: string | null;
  citations?: Citation[] | null;
  logs: TraceLog[];
}

export interface StreamEvent {
  type: 'trace' | 'completed' | 'failed' | 'end';
  agent?: string;
  status?: string;
  message?: string;
  payload?: any;
  answer?: string;
  decision?: string;
  citations?: Citation[];
  error?: string;
  ts?: string;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly API = 'http://localhost:8000/api';

  constructor(private http: HttpClient) {}

  // Documents
  uploadDocument(file: File): Observable<DocumentOut> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<DocumentOut>(`${this.API}/documents`, form);
  }
  listDocuments(): Observable<DocumentOut[]> {
    return this.http.get<DocumentOut[]>(`${this.API}/documents`);
  }
  deleteDocument(id: string): Observable<void> {
    return this.http.delete<void>(`${this.API}/documents/${id}`);
  }

  // Queries
  ask(question: string): Observable<QuerySummary> {
    return this.http.post<QuerySummary>(`${this.API}/queries`, { question });
  }
  listQueries(): Observable<QuerySummary[]> {
    return this.http.get<QuerySummary[]>(`${this.API}/queries`);
  }
  getQuery(id: string): Observable<QueryDetail> {
    return this.http.get<QueryDetail>(`${this.API}/queries/${id}`);
  }

  streamQuery(id: string): Observable<StreamEvent> {
    const subject = new Subject<StreamEvent>();
    const es = new EventSource(`${this.API}/queries/${id}/stream`);

    const handle = (type: StreamEvent['type']) => (ev: MessageEvent) => {
      try { subject.next({ ...JSON.parse(ev.data), type }); }
      catch { subject.next({ type }); }
    };

    es.addEventListener('trace', handle('trace') as EventListener);
    es.addEventListener('completed', handle('completed') as EventListener);
    es.addEventListener('failed', handle('failed') as EventListener);
    es.addEventListener('end', () => { subject.next({ type: 'end' }); es.close(); subject.complete(); });
    es.addEventListener('ping', () => {});
    es.onerror = () => { es.close(); subject.complete(); };

    return subject.asObservable();
  }
}
