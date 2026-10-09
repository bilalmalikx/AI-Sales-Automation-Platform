import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { PageHeader } from '../../shared/page-header/page-header';
import { Badge } from '../../shared/badge/badge';
import { Tilt } from '../../utils/tilt';
import { Workspace } from '../../services/workspace';
import { Dialog } from '../../services/dialog';
import { Notification } from '../../services/notification';
import { Campaigns as CampaignsService } from '../../services/campaigns';
@Component({
  selector: 'app-campaigns',
  standalone: true,
  imports: [RouterLink, PageHeader, Badge, Tilt],
  templateUrl: './campaigns.html',
  styleUrl: './campaigns.css',
})
export class Campaigns {
  store = inject(Workspace);
  dialog = inject(Dialog);
  notify = inject(Notification);
  campaigns = inject(CampaignsService);
  progress(sent: number, count: number): number {
    return count ? Math.min(100, (sent / count) * 100) : 0;
  }
  async toggle(id: string): Promise<void> {
    try { await this.campaigns.toggle(id); this.notify.show('Campaign status updated.'); }
    catch(e) { this.notify.show((e as Error).message); }
  }
}
