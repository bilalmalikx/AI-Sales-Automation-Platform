import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { PageHeader } from '../../shared/page-header/page-header';
import { Person } from '../../shared/person/person';
import { Badge } from '../../shared/badge/badge';
import { Workspace } from '../../services/workspace';
import { Dialog } from '../../services/dialog';
import { Notification } from '../../services/notification';
import { Email } from '../../services/email';
import { Leads } from '../../services/leads';
@Component({
  selector: 'app-emails',
  standalone: true,
  imports: [RouterLink, PageHeader, Person, Badge],
  templateUrl: './emails.html',
  styleUrl: './emails.css',
})
export class Emails {
  store = inject(Workspace);
  dialog = inject(Dialog);
  notify = inject(Notification);
  email = inject(Email);
  leads = inject(Leads);
  async approve(id: string): Promise<void> {
    try { await this.email.approve(id); } catch(e) { this.notify.show((e as Error).message); }
  }
  async send(id: string): Promise<void> {
    try { await this.email.send(id); this.notify.show('Delivery queued. Provider status will update here.'); }
    catch(e) { this.notify.show((e as Error).message); }
  }
}
