import { Component, inject, computed } from '@angular/core';
import { RouterLink } from '@angular/router';
import { PageHeader } from '../../shared/page-header/page-header';
import { MetricGrid } from '../../shared/metric-grid/metric-grid';
import { LeadTable } from '../../shared/lead-table/lead-table';
import { ActivityChart } from '../../shared/activity-chart/activity-chart';
import { Icon } from '../../shared/icon/icon';
import { Workspace } from '../../services/workspace';
import { Dialog } from '../../services/dialog';
import { Notification } from '../../services/notification';
import { Metric } from '../../models/workspace';
@Component({
  selector: 'app-overview',
  standalone: true,
  imports: [RouterLink, PageHeader, MetricGrid, LeadTable, ActivityChart, Icon],
  templateUrl: './overview.html',
  styleUrl: './overview.css',
})
export class Overview {
  store = inject(Workspace);
  dialog = inject(Dialog);
  notify = inject(Notification);
  metrics = computed<Metric[]>(() => {
    const s = this.store.state();
    return [
      {
        label: 'Total leads',
        value: s.leads.length,
        note: 'Persisted CRM contacts',
        icon: 'leads',
      },
      {
        label: 'Active campaigns',
        value: s.campaigns.filter((c) => c.status === 'Active').length,
        note: 'Ready to build momentum',
        icon: 'campaigns',
      },
      {
        label: 'Conversations',
        value: s.messages.length,
        note: 'Replies worth your attention',
        icon: 'inbox',
      },
      {
        label: 'Meetings booked',
        value: s.meetings.filter((m) => m.status === 'Scheduled').length,
        note: 'Your next opportunities',
        icon: 'meetings',
      },
    ];
  });
  draftCount = computed(
    () => this.store.state().drafts.filter((d) => d.status === 'Needs review').length,
  );
  unresearched = computed(() => this.store.state().leads.filter((l) => !l.confidence).length);
}
