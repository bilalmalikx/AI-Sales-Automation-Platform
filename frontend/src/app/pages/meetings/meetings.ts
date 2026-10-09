import { Component, inject } from '@angular/core';
import { PageHeader } from '../../shared/page-header/page-header';
import { Badge } from '../../shared/badge/badge';
import { Workspace } from '../../services/workspace';
import { Dialog } from '../../services/dialog';
import { Notification } from '../../services/notification';
import { Meetings as MeetingsService } from '../../services/meetings';
import { Leads } from '../../services/leads';
@Component({
  selector: 'app-meetings',
  standalone: true,
  imports: [PageHeader, Badge],
  templateUrl: './meetings.html',
  styleUrl: './meetings.css',
})
export class Meetings {
  store = inject(Workspace);
  dialog = inject(Dialog);
  notify = inject(Notification);
  meetings = inject(MeetingsService);
  leads = inject(Leads);
  month(date: string): string {
    return new Date(date + 'T12:00:00').toLocaleDateString('en', { month: 'short' });
  }
  day(date: string): number {
    return Number(date.slice(-2));
  }
  async cancel(id: string): Promise<void> {
    try { await this.meetings.cancel(id); this.notify.show('Meeting cancelled; calendar synchronization queued.'); }
    catch(e) { this.notify.show((e as Error).message); }
  }
}
