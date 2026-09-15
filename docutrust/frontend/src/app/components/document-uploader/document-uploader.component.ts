import { Component, EventEmitter, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-document-uploader',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './document-uploader.component.html',
  styleUrls: ['./document-uploader.component.scss'],
})
export class DocumentUploaderComponent {
  @Output() uploaded = new EventEmitter<void>();

  uploading = signal(false);
  progress = signal<string>('');
  error = signal<string | null>(null);
  dragOver = signal(false);

  constructor(private api: ApiService) {}

  onDragOver(e: DragEvent) {
    e.preventDefault();
    this.dragOver.set(true);
  }
  onDragLeave() { this.dragOver.set(false); }

  onDrop(e: DragEvent) {
    e.preventDefault();
    this.dragOver.set(false);
    const files = e.dataTransfer?.files;
    if (files && files.length) this.uploadAll(Array.from(files));
  }

  onPick(e: Event) {
    const input = e.target as HTMLInputElement;
    if (input.files) this.uploadAll(Array.from(input.files));
    input.value = '';
  }

  private uploadAll(files: File[]) {
    const pdfs = files.filter(f => f.name.toLowerCase().endsWith('.pdf'));
    if (!pdfs.length) {
      this.error.set('Only PDF files are supported.');
      return;
    }
    this.uploadNext(pdfs, 0);
  }

  private uploadNext(files: File[], i: number) {
    if (i >= files.length) {
      this.uploading.set(false);
      this.progress.set('');
      this.uploaded.emit();
      return;
    }
    this.uploading.set(true);
    this.error.set(null);
    this.progress.set(`Embedding ${files[i].name} (${i + 1}/${files.length})…`);
    this.api.uploadDocument(files[i]).subscribe({
      next: () => this.uploadNext(files, i + 1),
      error: err => {
        this.uploading.set(false);
        this.error.set(err?.error?.detail || 'Upload failed');
      },
    });
  }
}
