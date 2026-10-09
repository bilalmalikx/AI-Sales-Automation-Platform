import { Injectable, inject, computed } from '@angular/core';
import { Workspace } from './workspace';
import { Meeting } from '../models/workspace';
import { zonedTimestamp } from '../utils/date';
@Injectable({ providedIn: 'root' })
export class Meetings {
  private store = inject(Workspace);
  readonly items = computed(() => this.store.state().meetings);
  async save(value: Omit<Meeting, 'id' | 'status'>, id?: string): Promise<void> {
    const timezone = this.store.state().settings.timezone;
    const payload = {
      lead_id: value.lead,
      start_at: zonedTimestamp(value.date, value.time, timezone),
      duration_minutes: Number(value.duration),
      timezone,
    };
    if (id) await this.store.api.put(`meetings/${id}`, payload);
    else await this.store.api.post('meetings', payload);
    await this.store.refresh();
  }
  async cancel(id: string): Promise<void> {
    await this.store.api.post(`meetings/${id}/cancel`);
    await this.store.refresh();
  }
}
