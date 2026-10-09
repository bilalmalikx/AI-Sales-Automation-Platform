import { Injectable, inject, computed } from '@angular/core';
import { Workspace } from './workspace';
import { Campaign } from '../models/workspace';
@Injectable({ providedIn: 'root' })
export class Campaigns {
  private store = inject(Workspace);
  readonly items = computed(() => this.store.state().campaigns);
  async save(
    value: Pick<Campaign, 'name' | 'audience' | 'offer' | 'tone' | 'ids'>,
    id?: string,
  ): Promise<void> {
    const payload = {
      name: value.name,
      audience: value.audience,
      offer: value.offer,
      tone: value.tone.toLowerCase(),
      lead_ids: value.ids,
    };
    if (id) await this.store.api.put(`campaigns/${id}`, payload);
    else await this.store.api.post('campaigns', payload);
    await this.store.refresh();
  }
  async toggle(id: string): Promise<void> {
    const c = this.items().find((c) => c.id === id)!;
    await this.store.api.patch(`campaigns/${id}/status`, {
      status: c.status === 'Active' ? 'paused' : 'active',
    });
    await this.store.refresh();
  }
}
