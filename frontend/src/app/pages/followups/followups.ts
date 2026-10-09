import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { PageHeader } from '../../shared/page-header/page-header';
import { Person } from '../../shared/person/person';
import { Workspace } from '../../services/workspace';
import { Dialog } from '../../services/dialog';
import { Notification } from '../../services/notification';
import { Followups as FollowupsService } from '../../services/followups';
@Component({
  selector: 'app-followups',
  standalone: true,
  imports: [RouterLink, PageHeader, Person],
  templateUrl: './followups.html',
  styleUrl: './followups.css',
})
export class Followups {
  store = inject(Workspace);
  dialog = inject(Dialog);
  notify = inject(Notification);
  followups = inject(FollowupsService);
  async cancel(id: string): Promise<void> {
    try { await this.followups.cancel(id); this.notify.show('Follow-up cancelled.'); }
    catch(e) { this.notify.show((e as Error).message); }
  }
}
