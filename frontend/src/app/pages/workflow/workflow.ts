import { Component, inject, signal, computed, effect } from '@angular/core';
import { RouterLink } from '@angular/router';
import { PageHeader } from '../../shared/page-header/page-header';
import { Dropdown } from '../../shared/dropdown/dropdown';
import { Workspace } from '../../services/workspace';
import { Dialog } from '../../services/dialog';
import { Notification } from '../../services/notification';
import { Workflow as WorkflowService } from '../../services/workflow';
@Component({
  selector: 'app-workflow',
  standalone: true,
  imports: [RouterLink, PageHeader, Dropdown],
  templateUrl: './workflow.html',
  styleUrl: './workflow.css',
})
export class Workflow {
  store = inject(Workspace);
  dialog = inject(Dialog);
  notify = inject(Notification);
  workflow = inject(WorkflowService);
  leadId = signal(
    String(
      this.store.state().leads.find((l) => !['Unsubscribed', 'Lost'].includes(l.status))?.id || '',
    ),
  );
  campaignId = signal(String(this.store.state().campaigns[0]?.id || ''));
  leadOptions = computed(() =>
    this.store
      .state()
      .leads.filter((l) => !['Unsubscribed', 'Lost'].includes(l.status))
      .map((l) => ({ value: String(l.id), label: l.name + ' · ' + l.company })),
  );
  campaignOptions = computed(() =>
    this.store.state().campaigns.map((c) => ({ value: String(c.id), label: c.name })),
  );
  constructor() {
    effect(() => {
      if (!this.leadId() && this.leadOptions().length) this.leadId.set(this.leadOptions()[0].value);
      if (!this.campaignId() && this.campaignOptions().length)
        this.campaignId.set(this.campaignOptions()[0].value);
    });
  }
  steps = ['Enrich contact', 'Research company', 'Write email', 'Human review'];
  async run(): Promise<void> {
    try {
      await this.workflow.run(this.leadId(), this.campaignId());
      this.notify.show('Draft created. Review it in Email review.');
    } catch (e) {
      this.notify.show((e as Error).message);
    }
  }
}
