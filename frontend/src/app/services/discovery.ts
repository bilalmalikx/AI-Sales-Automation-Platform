import { Injectable, inject, signal, DestroyRef } from '@angular/core';
import { Api } from './api';
import { DiscoveryInput, DiscoveryRun, Prospect, DiscoveryConfiguration, DiscoverySchedule } from '../models/backend';
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
  readonly schedules = signal<DiscoverySchedule[]>([]);
  readonly scheduleBusy = signal(false);
  readonly scheduleError = signal('');
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
      const [runs, config, contacts, schedules] = await Promise.all([
        this.api.all<DiscoveryRun>('discovery/runs'),
        this.api.get<DiscoveryConfiguration>('discovery/configuration'),
        this.api.all<Prospect>('discovery/prospects?contact_only=true'),
        this.api.all<DiscoverySchedule>('discovery/schedules'),
      ]);
      this.runs.set(runs);
      this.config.set(config);
      this.contacts.set(contacts);
      this.schedules.set(schedules);
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
  async saveSchedule(value: {name: string; parameters: DiscoveryInput; due_at: string; enabled: boolean}, id?: string): Promise<boolean> {
    if(this.scheduleBusy()) return false;
    this.scheduleBusy.set(true);
    this.scheduleError.set('');
    try {
      if(id) await this.api.put(`discovery/schedules/${id}`,value);
      else await this.api.post('discovery/schedules',value);
      await this.refresh();
      return true;
    } catch(e) { this.scheduleError.set((e as Error).message); return false; }
    finally { this.scheduleBusy.set(false); }
  }
  async toggleSchedule(schedule: DiscoverySchedule): Promise<void> {
    // Pausing changes future slots only. In-flight runs keep their own Stop control.
    const due = !schedule.enabled && Date.parse(schedule.due_at) < Date.now()
      ? new Date(Date.now()+60000).toISOString() : schedule.due_at;
    await this.saveSchedule({name:schedule.name, parameters:schedule.parameters,
      due_at:due, enabled:!schedule.enabled},schedule.id);
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
  private outreachKeys = new Map<string, string>();
  async prepareOutreach(id: string, campaignId: string): Promise<boolean> {
    const slot = id + ':' + campaignId;
    const key = this.outreachKeys.get(slot) || crypto.randomUUID();
    this.outreachKeys.set(slot, key);
    try {
      await this.api.post(`discovery/prospects/${id}/prepare-outreach`,
        {campaign_id: campaignId, reviewed_contact: true}, {'Idempotency-Key': key});
      await this.refresh();
      return true;
    } catch (e) { this.error.set((e as Error).message); return false; }
  }
  async recheckApp(id: string): Promise<void> {
    try {
      await this.api.post(`discovery/prospects/${id}/recheck-app`);
      await this.refresh();
    } catch (e) { this.error.set((e as Error).message); }
  }
  select(id: string): void {
    this.selected.set(id);
    void this.refresh();
  }
}
