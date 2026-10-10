import { Injectable, inject, signal } from '@angular/core';
import { Workspace } from './workspace';
import { WorkflowRecord } from '../models/backend';
@Injectable({ providedIn: 'root' })
export class Workflow {
  private store = inject(Workspace);
  readonly processing = signal(false);
  readonly stage = signal(-1);
  readonly completed = signal(false);
  async run(
    leadId: string,
    campaignId: string,
    reviewedContact = false,
  ): Promise<string | undefined> {
    if (this.processing()) return;
    this.processing.set(true);
    this.completed.set(false);
    try {
      const r = await this.store.api.post<WorkflowRecord>(
        leadId.startsWith('prospect:')
          ? `discovery/prospects/${leadId.slice(9)}/prepare-outreach`
          : 'workflows',
        leadId.startsWith('prospect:')
          ? { campaign_id: campaignId, reviewed_contact: reviewedContact }
          : { lead_id: leadId, campaign_id: campaignId },
        { 'Idempotency-Key': crypto.randomUUID() },
      );
      const deadline = Date.now() + 10 * 60 * 1000;
      while (Date.now() < deadline) {
        const run = await this.store.api.get<WorkflowRecord>(`workflows/${r.id}`);
        this.stage.set(
          Math.max(
            0,
            ['queued', 'enrichment', 'research', 'draft', 'human_review'].indexOf(run.stage) - 1,
          ),
        );
        if (run.status === 'failed' || run.status === 'cancelled')
          throw new Error(run.error || 'Workflow stopped.');
        if (run.status === 'needs_review') {
          await this.store.refresh();
          this.completed.set(true);
          return run.lead_id;
        }
        await new Promise((resolve) => setTimeout(resolve, 2000));
      }
      throw new Error('Workflow is still running. Check backend activity and refresh.');
    } finally {
      this.processing.set(false);
      this.stage.set(-1);
    }
  }
}
