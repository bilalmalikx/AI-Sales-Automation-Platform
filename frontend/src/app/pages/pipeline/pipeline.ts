import { Component, inject } from '@angular/core';
import { PageHeader } from '../../shared/page-header/page-header';
import { Badge } from '../../shared/badge/badge';
import { Dropdown } from '../../shared/dropdown/dropdown';
import { Workspace } from '../../services/workspace';
import { Dialog } from '../../services/dialog';
import { Notification } from '../../services/notification';
import { LEAD_STATUSES, LeadStatus } from '../../models/workspace';
import { Leads } from '../../services/leads';
@Component({
  selector: 'app-pipeline',
  standalone: true,
  imports: [PageHeader, Badge, Dropdown],
  templateUrl: './pipeline.html',
  styleUrl: './pipeline.css',
})
export class Pipeline {
  store = inject(Workspace);
  dialog = inject(Dialog);
  notify = inject(Notification);
  leads = inject(Leads);
  columns = [
    { name: 'New', statuses: ['New'] },
    { name: 'In conversation', statuses: ['Contacted', 'Replied'] },
    { name: 'Qualified', statuses: ['Qualified', 'Meeting booked'] },
    { name: 'Closed', statuses: ['Won', 'Lost', 'Unsubscribed'] },
  ];
  options = LEAD_STATUSES.map((s) => ({ value: s, label: s }));
  inColumn(statuses: string[]) {
    return this.leads.items().filter((l) => statuses.includes(l.status));
  }
  async move(id: string, status: string): Promise<void> {
    try { await this.leads.move(id, status as LeadStatus); } catch(e) { this.notify.show((e as Error).message); }
  }
}
