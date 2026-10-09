import { Injectable, inject, computed } from '@angular/core';
import { Workspace } from './workspace';
@Injectable({ providedIn: 'root' })
export class Inbox {
  private store = inject(Workspace);
  readonly messages = computed(() => this.store.state().messages);
  async suggest(lead: string): Promise<string> {
    return (await this.store.api.post<{ body: string }>(`inbox/${lead}/suggest`)).body;
  }
  async reply(lead: string, body: string): Promise<void> {
    await this.store.api.post(`inbox/${lead}/reply`, { body });
    await this.store.refresh();
  }
  async stop(lead: string): Promise<void> {
    await this.store.api.post(`leads/${lead}/unsubscribe`);
    await this.store.refresh();
  }
}
