import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DocumentUploaderComponent } from './components/document-uploader/document-uploader.component';
import { DocumentListComponent } from './components/document-list/document-list.component';
import { QueryPanelComponent } from './components/query-panel/query-panel.component';
import { AnswerViewComponent } from './components/answer-view/answer-view.component';
import { AgentTraceComponent } from './components/agent-trace/agent-trace.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    DocumentUploaderComponent,
    DocumentListComponent,
    QueryPanelComponent,
    AnswerViewComponent,
    AgentTraceComponent,
  ],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
})
export class AppComponent {
  activeQueryId = signal<string | null>(null);
  docsRefresh = signal(0);
  answerRefresh = signal(0);

  onUploaded() { this.docsRefresh.update(v => v + 1); }
  onQueryStarted(id: string) { this.activeQueryId.set(id); this.answerRefresh.update(v => v + 1); }
  onStreamEnded() { this.answerRefresh.update(v => v + 1); }
}
