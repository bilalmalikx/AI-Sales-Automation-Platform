import { Injectable, inject, computed } from '@angular/core';
import { Workspace } from './workspace';
import { zonedTimestamp } from '../utils/date';
@Injectable({ providedIn: 'root' })
export class Followups {
  private store = inject(Workspace);
  readonly items = computed(() => this.store.state().leads.filter((l) => l.followup));
  async schedule(id: string, date: string): Promise<void> {
    const s = this.store.state();
    const c = s.campaigns.find((c) => c.ids.includes(id));
    if (!c) throw new Error('Assign the contact to a campaign first.');
    await this.store.api.post('followups', {
      lead_id: id,
      campaign_id: c.id,
      due_at: zonedTimestamp(date, '10:00', s.settings.timezone),
    });
    await this.store.refresh();
  }
  async cancel(id: string): Promise<void> {
    const f = this.store
      .followupRecords()
      .find((f) => f.lead_id === id && f.status === 'scheduled');
    if (f) await this.store.api.post(`followups/${f.id}/cancel`);
    await this.store.refresh();
  }
}
