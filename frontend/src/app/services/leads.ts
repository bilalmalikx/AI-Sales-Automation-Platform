import { Injectable, inject, computed } from '@angular/core';
import { Workspace } from './workspace';
import { Lead, LeadStatus } from '../models/workspace';
import { csvCell, downloadFile } from '../utils/csv';
@Injectable({ providedIn: 'root' })
export class Leads {
  private store = inject(Workspace);
  readonly items = computed(() => this.store.state().leads);
  get(id: string): Lead {
    const l = this.items().find((l) => l.id === id);
    if (!l) throw new Error('Contact not found.');
    return l;
  }
  async save(value: Omit<Lead, 'id' | 'status' | 'confidence'>, id?: string): Promise<void> {
    const [first_name, ...last] = value.name.trim().split(' ');
    const payload = {
      email: value.email.trim(),
      first_name,
      last_name: last.join(' ') || null,
      company_name: value.company,
      title: value.title,
      industry: value.industry,
    };
    if (id) await this.store.api.put(`leads/${id}`, payload);
    else await this.store.api.post('leads', payload);
    await this.store.refresh();
  }
  async delete(id: string): Promise<void> {
    await this.store.api.delete(`leads/${id}`);
    await this.store.refresh();
  }
  async move(id: string, status: LeadStatus): Promise<void> {
    if (status === 'Unsubscribed') await this.store.api.post(`leads/${id}/unsubscribe`);
    else
      await this.store.api.put(`leads/${id}`, { status: status.toLowerCase().replace(/ /g, '_') });
    await this.store.refresh();
  }
  async import(text: string): Promise<{ created: number; skipped: number; invalid: number }> {
    const file = new FormData();
    file.append('file', new Blob([text], { type: 'text/csv' }), 'leads.csv');
    const r = await this.store.api.post<{
      statistics: { created: number; skipped: number; failed: number };
    }>('leads/import/csv', file);
    await this.store.refresh();
    return {
      created: r.statistics.created,
      skipped: r.statistics.skipped,
      invalid: r.statistics.failed,
    };
  }
  export(): void {
    downloadFile(
      'codelps-leads.csv',
      'name,email,company,title,industry,status\n' +
        this.items()
          .map((l) =>
            [l.name, l.email, l.company, l.title, l.industry, l.status].map(csvCell).join(','),
          )
          .join('\n'),
    );
  }
  sample(): void {
    downloadFile(
      'salesway-sample.csv',
      'name,email,company,title,industry\nAlex Morgan,alex@sample.example,Sample Studio,Founder,Design\n',
    );
  }
}
