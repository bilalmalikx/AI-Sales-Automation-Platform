import { Injectable, inject, computed } from '@angular/core';
import { Workspace } from './workspace';
@Injectable({ providedIn: 'root' })
export class Email {
  private store = inject(Workspace);
  readonly drafts = computed(() => this.store.state().drafts);
  async edit(id: string, subject: string, body: string): Promise<void> {
    const d = this.drafts().find((x) => x.id === id)!;
    await this.store.api.put(`emails/${id}`, { subject, body, expected_revision: d.revision });
    await this.store.refresh();
  }
  async approve(id: string): Promise<void> {
    const d = this.drafts().find((x) => x.id === id)!;
    if (
      d.requiresReview &&
      !confirm(
        'This draft uses research that requires review. Confirm that you checked the contact, website/app evidence and email claims before approving.',
      )
    )
      return;
    await this.store.api.post(`emails/${id}/approve`, {
      expected_revision: d.revision,
      acknowledge_low_confidence: true,
    });
    await this.store.refresh();
  }
  async send(id: string): Promise<void> {
    await this.store.api.post(`emails/${id}/send`);
    await this.store.refresh();
  }
}
