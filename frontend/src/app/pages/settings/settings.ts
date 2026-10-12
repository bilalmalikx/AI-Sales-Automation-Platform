import { Component, inject, signal, effect } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { PageHeader } from '../../shared/page-header/page-header';
import { Workspace } from '../../services/workspace';
import { Dialog } from '../../services/dialog';
import { Notification } from '../../services/notification';
import { Api } from '../../services/api';
interface IntegrationStatus {
  ai: { provider: string; configured: boolean };
  email: { provider: string; configured: boolean; delivery_enabled: boolean };
  calendar: { provider: string; configured: boolean };
  inbox: { provider: string; configured: boolean; automatic_sync: boolean; status: string; last_checked_at: string | null; error: string | null };
}
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
  private api = inject(Api);
  integrations = signal<IntegrationStatus | null>(null);
  integrationError = signal('');
  checking = signal(false);
  syncing = signal(false);
  smtpResult = signal('');
  constructor() {
    effect(() => { if(this.store.ready() && !this.hydrated) { this.form=structuredClone(this.store.state().settings); this.hydrated=true; } });
    void this.loadIntegrations();
  }
  private hydrated = false;
  async loadIntegrations(): Promise<void> {
    try { this.integrations.set(await this.api.get<IntegrationStatus>('integrations')); this.integrationError.set(''); }
    catch(e) { this.integrationError.set((e as Error).message); }
  }
  async checkSmtp(): Promise<void> {
    if(this.checking()) return;
    this.checking.set(true);
    this.smtpResult.set('');
    try { const result = await this.api.post<{message: string}>('integrations/email/check'); this.smtpResult.set(result.message); }
    catch(e) { this.smtpResult.set((e as Error).message); }
    finally { this.checking.set(false); }
  }
  async syncInbox(): Promise<void> {
    if(this.syncing()) return;
    this.syncing.set(true);
    try {
      const result = await this.api.post<{status: string; processed: number; message?: string}>('integrations/inbox/sync');
      if(result.status === 'failed') this.integrationError.set(result.message || 'Inbox sync failed.');
      else { await this.loadIntegrations(); await this.store.refresh(); this.notify.show(`${result.processed} replies imported.`); }
    } catch(e) { this.integrationError.set((e as Error).message); }
    finally { this.syncing.set(false); }
  }
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
