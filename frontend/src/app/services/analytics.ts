import { Injectable, inject, computed } from '@angular/core';
import { Workspace } from './workspace';
import { downloadFile } from '../utils/csv';
@Injectable({ providedIn: 'root' })
export class Analytics {
  private store = inject(Workspace);
  readonly sent = computed(() => this.store.state().campaigns.reduce((n, c) => n + c.sent, 0));
  async export(): Promise<void> {
    downloadFile(
      'codelps-report.json',
      JSON.stringify(await this.store.api.get('analytics'), null, 2),
      'application/json',
    );
  }
}
