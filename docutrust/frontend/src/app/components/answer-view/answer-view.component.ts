import { Component, Input, OnChanges, SimpleChanges, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { marked } from 'marked';
import { ApiService, QueryDetail } from '../../services/api.service';

@Component({
  selector: 'app-answer-view',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './answer-view.component.html',
  styleUrls: ['./answer-view.component.scss'],
})
export class AnswerViewComponent implements OnChanges {
  @Input() queryId: string | null = null;
  @Input() refreshToken = 0;

  query = signal<QueryDetail | null>(null);
  answerHtml = signal<string>('');

  constructor(private api: ApiService) {}

  ngOnChanges(changes: SimpleChanges) {
    if ((changes['queryId'] || changes['refreshToken']) && this.queryId) {
      this.load(this.queryId);
    } else if (!this.queryId) {
      this.query.set(null);
      this.answerHtml.set('');
    }
  }

  private load(id: string) {
    this.api.getQuery(id).subscribe({
      next: data => {
        this.query.set(data);
        this.answerHtml.set(data.answer ? (marked.parse(data.answer) as string) : '');
      },
    });
  }

  decisionLabel(d: string | null | undefined): string {
    switch (d) {
      case 'use_local':    return 'Local corpus';
      case 'partial':      return 'Local + web';
      case 'web_fallback': return 'Web fallback';
      default:             return d || '';
    }
  }

  citationLabel(src: string): string {
    if (src.startsWith('doc:')) {
      const parts = src.split(':');
      return `${parts[1]} · ${parts[2]}`;
    }
    if (src.startsWith('web:')) {
      const url = src.slice(4);
      try {
        return new URL(url).hostname;
      } catch { return url; }
    }
    return src;
  }

  isWeb(src: string): boolean { return src.startsWith('web:'); }

  href(src: string): string | null {
    if (src.startsWith('web:')) return src.slice(4);
    return null;
  }
}
