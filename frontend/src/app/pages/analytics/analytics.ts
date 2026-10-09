import { Component, inject, computed } from '@angular/core';
import { PageHeader } from '../../shared/page-header/page-header';
import { MetricGrid } from '../../shared/metric-grid/metric-grid';
import { ActivityChart } from '../../shared/activity-chart/activity-chart';
import { Badge } from '../../shared/badge/badge';
import { Workspace } from '../../services/workspace';
import { Dialog } from '../../services/dialog';
import { Notification } from '../../services/notification';
import { Metric } from '../../models/workspace';
import { Analytics as AnalyticsService } from '../../services/analytics';
@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [PageHeader, MetricGrid, ActivityChart, Badge],
  templateUrl: './analytics.html',
  styleUrl: './analytics.css',
})
export class Analytics {
  store = inject(Workspace);
  dialog = inject(Dialog);
  notify = inject(Notification);
  analytics = inject(AnalyticsService);
  metrics = computed<Metric[]>(() => {
    const s = this.store.state();
    return [
      {
        label: 'Emails sent',
        value: this.analytics.sent(),
        note: 'Accepted by the configured provider',
        icon: 'emails',
      },
      {
        label: 'Replies received',
        value: s.messages.length,
        note: 'Recorded inbound conversations',
        icon: 'inbox',
      },
      {
        label: 'Scheduled meetings',
        value: s.meetings.filter((m) => m.status === 'Scheduled').length,
        note: 'Saved in this workspace',
        icon: 'meetings',
      },
      {
        label: 'Drafts prepared',
        value: s.drafts.length,
        note: 'Prepared by backend workflows',
        icon: 'workflow',
      },
    ];
  });
}
