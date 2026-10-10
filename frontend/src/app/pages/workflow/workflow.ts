import { Component, inject, signal, computed, effect } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Discovery } from '../../services/discovery';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { PageHeader } from '../../shared/page-header/page-header';
import { Dropdown } from '../../shared/dropdown/dropdown';
import { Workspace } from '../../services/workspace';
import { Dialog } from '../../services/dialog';
import { Notification } from '../../services/notification';
import { Workflow as WorkflowService } from '../../services/workflow';
@Component({
  selector: 'app-workflow',
  standalone: true,
  imports: [FormsModule, RouterLink, PageHeader, Dropdown],
  templateUrl: './workflow.html',
  styleUrl: './workflow.css',
})
export class Workflow {
  store = inject(Workspace);
  dialog = inject(Dialog);
  notify = inject(Notification);
  workflow = inject(WorkflowService);
  discovery = inject(Discovery);
  route = inject(ActivatedRoute);
  reviewedContact = signal(false);
  discoverySelection = computed(() => this.leadId().startsWith('prospect:'));
  leadId = signal(
    String(
      this.store.state().leads.find((l) => !['Unsubscribed', 'Lost'].includes(l.status))?.id || '',
    ),
  );
  campaignId = signal(
    this.route.snapshot.queryParamMap.get('campaign') ||
      String(this.store.state().campaigns[0]?.id || ''),
  );
  selectedProspect = computed(() =>
    this.discovery.contacts().find((p) => 'prospect:' + p.id === this.leadId()),
  );
  leadOptions = computed(() => {
    const leads = this.store
      .state()
      .leads.filter((l) => !['Unsubscribed', 'Lost'].includes(l.status));
    const emails = new Set(this.store.state().leads.map((l) => l.email.toLowerCase()));
    const prospects = this.discovery.contacts().filter((p) => {
      if (
        !p.emails.length ||
        p.lead_id ||
        p.stage !== 'complete' ||
        ['excluded', 'cancelled'].includes(p.status) ||
        p.app_status === 'app_found'
      )
        return false;
      const email = p.emails[0].email.toLowerCase();
      if (emails.has(email)) return false;
      emails.add(email);
      return true;
    });
    return [
      ...leads.map((l) => ({ value: l.id, label: l.name + ' · ' + l.company })),
      ...prospects.map((p) => ({
        value: 'prospect:' + p.id,
        label:
          p.company + ' · ' + p.city + ' · ' + p.emails[0].email + ' · Discovery / review required',
      })),
    ];
  });
  campaignOptions = computed(() =>
    this.store.state().campaigns.map((c) => ({ value: String(c.id), label: c.name })),
  );
  constructor() {
    effect(() => {
      if (
        !this.workflow.processing() &&
        !this.leadOptions().some((option) => option.value === this.leadId())
      ) {
        this.leadId.set(this.leadOptions()[0]?.value || '');
        this.reviewedContact.set(false);
      }
      if (!this.campaignId() && this.campaignOptions().length)
        this.campaignId.set(this.campaignOptions()[0].value);
    });
  }
  steps = ['Enrich contact', 'Research company', 'Write email', 'Human review'];
  async run(): Promise<void> {
    try {
      const leadId = await this.workflow.run(
        this.leadId(),
        this.campaignId(),
        this.reviewedContact(),
      );
      if (leadId) this.leadId.set(leadId);
      await this.discovery.refresh();
      this.notify.show('Draft created. Review it in Email review.');
    } catch (e) {
      this.notify.show((e as Error).message);
    }
  }
}
