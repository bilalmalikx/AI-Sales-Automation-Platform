import { Component, inject, signal, computed } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { PageHeader } from '../../shared/page-header/page-header';
import { LeadTable } from '../../shared/lead-table/lead-table';
import { Dropdown } from '../../shared/dropdown/dropdown';
import { Workspace } from '../../services/workspace';
import { Dialog } from '../../services/dialog';
import { Notification } from '../../services/notification';
import { LEAD_STATUSES } from '../../models/workspace';
import { Leads as LeadsService } from '../../services/leads';
@Component({
  selector: 'app-leads',
  standalone: true,
  imports: [FormsModule, PageHeader, LeadTable, Dropdown],
  templateUrl: './leads.html',
  styleUrl: './leads.css',
})
export class Leads {
  store = inject(Workspace);
  dialog = inject(Dialog);
  notify = inject(Notification);
  leads = inject(LeadsService);
  search = signal('');
  filter = signal('All');
  options = [{ value: 'All', label: 'All' }, ...LEAD_STATUSES.map((s) => ({ value: s, label: s }))];
  filtered = computed(() =>
    this.leads
      .items()
      .filter(
        (l) =>
          (this.filter() === 'All' || l.status === this.filter()) &&
          `${l.name} ${l.company} ${l.email}`.toLowerCase().includes(this.search().toLowerCase()),
      ),
  );
  export(): void {
    this.leads.export();
    this.notify.show('Lead export downloaded.');
  }
}
