import { Component, EventEmitter, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-query-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './query-panel.component.html',
  styleUrls: ['./query-panel.component.scss'],
})
export class QueryPanelComponent {
  @Output() queryStarted = new EventEmitter<string>();

  question = '';
  submitting = signal(false);
  error = signal<string | null>(null);

  constructor(private api: ApiService) {}

  submit() {
    const q = this.question.trim();
    if (q.length < 3) {
      this.error.set('Type a question first.');
      return;
    }
    this.error.set(null);
    this.submitting.set(true);
    this.api.ask(q).subscribe({
      next: (res) => {
        this.submitting.set(false);
        this.queryStarted.emit(res.id);
        this.question = '';
      },
      error: (err) => {
        this.submitting.set(false);
        this.error.set(err?.error?.detail || 'Query failed to start');
      },
    });
  }

  onKey(e: KeyboardEvent) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) this.submit();
  }
}
