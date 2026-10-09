import { Component, inject, signal, computed } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { PageHeader } from '../../shared/page-header/page-header';
import { Person } from '../../shared/person/person';
import { Badge } from '../../shared/badge/badge';
import { Workspace } from '../../services/workspace';
import { Dialog } from '../../services/dialog';
import { Notification } from '../../services/notification';
import { Inbox as ConversationService } from '../../services/inbox';
import { Leads } from '../../services/leads';
@Component({
  selector: 'app-inbox',
  standalone: true,
  imports: [FormsModule, PageHeader, Person, Badge],
  templateUrl: './inbox.html',
  styleUrl: './inbox.css',
})
export class Inbox {
  store = inject(Workspace);
  dialog = inject(Dialog);
  notify = inject(Notification);
  inbox = inject(ConversationService);
  leads = inject(Leads);
  selected = signal(0);
  reply = signal('');
  message = computed(() => this.inbox.messages()[this.selected()] || this.inbox.messages()[0]);
  select(index: number): void {
    this.selected.set(index);
    this.reply.set('');
  }
  async suggest(): Promise<void> {
    const m = this.message();
    if (m) { try { this.reply.set(await this.inbox.suggest(m.lead)); } catch(e) { this.notify.show((e as Error).message); } }
  }
  async save(): Promise<void> {
    try {
      await this.inbox.reply(this.message()!.lead, this.reply());
      this.reply.set('');
      this.notify.show('Reply draft saved. Send it from Email review.');
    } catch (e) {
      this.notify.show((e as Error).message);
    }
  }
  async stop(): Promise<void> {
    try { await this.inbox.stop(this.message()!.lead); this.notify.show('Outreach stopped for this contact.'); } catch(e) { this.notify.show((e as Error).message); }
  }
}
