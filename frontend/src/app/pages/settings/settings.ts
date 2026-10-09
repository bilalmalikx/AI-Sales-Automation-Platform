import { Component, inject, signal, effect } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { PageHeader } from '../../shared/page-header/page-header';
import { Workspace } from '../../services/workspace';
import { Dialog } from '../../services/dialog';
import { Notification } from '../../services/notification';
@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [FormsModule, PageHeader],
  templateUrl: './settings.html',
  styleUrl: './settings.css',
})
export class Settings {
  store = inject(Workspace);
  dialog = inject(Dialog);
  notify = inject(Notification);
  form = structuredClone(this.store.state().settings);
  error = signal('');
  private hydrated = false;
  constructor() { effect(() => { if(this.store.ready() && !this.hydrated) { this.form=structuredClone(this.store.state().settings); this.hydrated=true; } }); }
  async save(): Promise<void> {
    if (
      !this.form.company.trim() ||
      !this.form.sender.trim() ||
      !this.form.offer.trim() ||
      this.form.limit < 1 ||
      this.form.limit > 500
    ) {
      this.error.set('Complete the fields and choose a daily limit between 1 and 500.');
      return;
    }
    try {
      new Intl.DateTimeFormat('en', { timeZone: this.form.timezone });
    } catch {
      this.error.set('Enter a valid timezone such as Asia/Karachi.');
      return;
    }
    try {
      const {limit,...prefs}=this.form;
      await this.store.api.put('settings',{...prefs,daily_limit:Number(limit)});
      await this.store.refresh();
    } catch(e) { this.error.set((e as Error).message); return; }
    this.error.set('');
    this.notify.show('Workspace preferences saved to backend.');
  }
}
