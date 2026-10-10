import { Injectable, inject, signal, DestroyRef } from '@angular/core';
import { Api } from './api';
import { DiscoveryInput, DiscoveryRun, Prospect, DiscoveryConfiguration } from '../models/backend';
@Injectable({ providedIn: 'root' })
export class Discovery {
  private api = inject(Api);
  readonly runs = signal<DiscoveryRun[]>([]);
  readonly prospects = signal<Prospect[]>([]);
  readonly contacts = signal<Prospect[]>([]);
  readonly config = signal<DiscoveryConfiguration | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly selected = signal('');
  readonly submitting = signal(false);
  private requestKey: string | null = null;
  private requestPayload = '';
  constructor() {
    void this.refresh();
    const timer = setInterval(() => void this.refresh(), 2000);
    inject(DestroyRef).onDestroy(() => clearInterval(timer));
  }
  async refresh(): Promise<void> {
    if (this.loading()) return;
    this.loading.set(true);
    try {
      const [runs, config, contacts] = await Promise.all([
        this.api.all<DiscoveryRun>('discovery/runs'),
        this.api.get<DiscoveryConfiguration>('discovery/configuration'),
        this.api.all<Prospect>('discovery/prospects?contact_only=true'),
      ]);
      this.runs.set(runs);
      this.config.set(config);
      this.contacts.set(contacts);
      if (!this.selected() && runs.length) this.selected.set(runs[0].id);
      this.prospects.set(
        await this.api.all<Prospect>(
          'discovery/prospects' + (this.selected() !== 'all' ? '?run_id=' + this.selected() : ''),
        ),
      );
      this.error.set('');
    } catch (e) {
      this.error.set((e as Error).message);
    } finally {
      this.loading.set(false);
    }
  }
  async start(value: DiscoveryInput): Promise<void> {
    if (this.submitting()) return;
    this.submitting.set(true);
    this.error.set('');
    const payload = JSON.stringify(value);
    if (payload !== this.requestPayload) {
      this.requestKey = null;
      this.requestPayload = payload;
    }
    this.requestKey ||= crypto.randomUUID();
    try {
      const run = await this.api.post<DiscoveryRun>('discovery/runs', value, {
        'Idempotency-Key': this.requestKey,
      });
      this.requestKey = null;
      this.selected.set(run.id);
      await this.refresh();
    } catch (e) {
      this.error.set((e as Error).message);
    } finally {
      this.submitting.set(false);
    }
  }
  async cancel(id: string): Promise<void> {
    try {
      await this.api.post(`discovery/runs/${id}/cancel`);
      await this.refresh();
    } catch (e) {
      this.error.set((e as Error).message);
    }
  }
  async retry(id: string): Promise<void> {
    try {
      await this.api.post(`discovery/prospects/${id}/retry`);
      await this.refresh();
    } catch (e) {
      this.error.set((e as Error).message);
    }
  }
  select(id: string): void {
    this.selected.set(id);
    void this.refresh();
  }
}
