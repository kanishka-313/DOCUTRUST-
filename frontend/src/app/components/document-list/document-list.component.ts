import { Component, Input, OnChanges, SimpleChanges, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService, DocumentOut } from '../../services/api.service';

@Component({
  selector: 'app-document-list',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './document-list.component.html',
  styleUrls: ['./document-list.component.scss'],
})
export class DocumentListComponent implements OnChanges {
  @Input() refreshToken = 0;

  docs = signal<DocumentOut[]>([]);

  constructor(private api: ApiService) { this.load(); }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['refreshToken']) this.load();
  }

  load() {
    this.api.listDocuments().subscribe(d => this.docs.set(d));
  }

  remove(id: string, ev: Event) {
    ev.stopPropagation();
    this.api.deleteDocument(id).subscribe({ next: () => this.load() });
  }

  fmtBytes(n: number): string {
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
    return `${(n / 1024 / 1024).toFixed(1)} MB`;
  }
}
