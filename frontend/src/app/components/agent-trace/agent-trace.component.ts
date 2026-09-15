import { Component, EventEmitter, Input, OnChanges, OnDestroy, Output, SimpleChanges, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription } from 'rxjs';
import { ApiService, StreamEvent } from '../../services/api.service';

interface TraceEntry {
  agent: string;
  status: string;
  message: string;
  payload?: any;
  ts: string;
}

@Component({
  selector: 'app-agent-trace',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './agent-trace.component.html',
  styleUrls: ['./agent-trace.component.scss'],
})
export class AgentTraceComponent implements OnChanges, OnDestroy {
  @Input() queryId: string | null = null;
  @Output() streamEnded = new EventEmitter<void>();

  entries = signal<TraceEntry[]>([]);
  streaming = signal(false);
  decision = signal<string | null>(null);
  private sub?: Subscription;

  // Static pipeline stages displayed in the rail
  stages = [
    { key: 'Retriever',      label: 'Retrieve' },
    { key: 'Grader',         label: 'Grade' },
    { key: 'Decision',       label: 'Decide' },
    { key: 'Query Rewriter', label: 'Rewrite' },
    { key: 'Web Fallback',   label: 'Web search' },
    { key: 'Generator',      label: 'Generate' },
  ];

  stageState = signal<Record<string, 'idle' | 'running' | 'done' | 'failed'>>({});

  constructor(private api: ApiService) {}

  ngOnChanges(changes: SimpleChanges) {
    if (changes['queryId']) {
      this.reset();
      if (this.queryId) this.connect(this.queryId);
    }
  }

  private reset() {
    this.sub?.unsubscribe();
    this.entries.set([]);
    this.streaming.set(false);
    this.decision.set(null);
    const fresh: Record<string, 'idle'> = {};
    this.stages.forEach(s => fresh[s.key] = 'idle');
    this.stageState.set(fresh);
  }

  private connect(id: string) {
    this.streaming.set(true);
    this.sub = this.api.streamQuery(id).subscribe({
      next: (ev: StreamEvent) => this.handle(ev),
      complete: () => { this.streaming.set(false); this.streamEnded.emit(); },
      error: () => { this.streaming.set(false); this.streamEnded.emit(); },
    });
  }

  private handle(ev: StreamEvent) {
    if (ev.type === 'trace' && ev.agent) {
      this.entries.update(arr => [...arr, {
        agent: ev.agent!, status: ev.status || '', message: ev.message || '',
        payload: ev.payload, ts: ev.ts || '',
      }]);
      const next = { ...this.stageState() };
      if (ev.status === 'started') next[ev.agent] = 'running';
      else if (ev.status === 'completed') next[ev.agent] = 'done';
      else if (ev.status === 'failed') next[ev.agent] = 'failed';
      this.stageState.set(next);

      // capture decision strategy
      if (ev.agent === 'Decision' && ev.payload?.strategy) {
        this.decision.set(ev.payload.strategy);
      }
    } else if (ev.type === 'completed') {
      this.decision.set(ev.decision || this.decision());
    } else if (ev.type === 'end') {
      this.streaming.set(false);
    }
  }

  ngOnDestroy() { this.sub?.unsubscribe(); }

  formatTime(iso: string): string {
    if (!iso) return '';
    return new Date(iso).toLocaleTimeString('en-GB', { hour12: false });
  }

  decisionLabel(d: string | null): string {
    switch (d) {
      case 'use_local':    return 'Local corpus sufficient';
      case 'partial':      return 'Partial · web augmented';
      case 'web_fallback': return 'Local insufficient · web fallback';
      default:             return '';
    }
  }
}
