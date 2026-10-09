import {
  Component,
  inject,
  signal,
  computed,
  effect,
  ElementRef,
  DestroyRef,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { untracked } from '@angular/core';
import { Dialog } from '../../services/dialog';
import { Workspace } from '../../services/workspace';
import { Leads } from '../../services/leads';
import { Campaigns } from '../../services/campaigns';
import { Email } from '../../services/email';
import { Meetings } from '../../services/meetings';
import { Followups } from '../../services/followups';
import { Notification } from '../../services/notification';
import { Person } from '../../shared/person/person';
import { Badge } from '../../shared/badge/badge';
import { Icon } from '../../shared/icon/icon';
import { Dropdown } from '../../shared/dropdown/dropdown';
import { DatePicker } from '../../shared/date-picker/date-picker';
import { NAVIGATION } from '../../models/workspace';
import { today } from '../../utils/date';
@Component({
  selector: 'app-workspace-dialog',
  standalone: true,
  imports: [FormsModule, Person, Badge, Icon, Dropdown, DatePicker],
  templateUrl: './workspace-dialog.html',
  styleUrl: './workspace-dialog.css',
})
export class WorkspaceDialog {
  dialog = inject(Dialog);
  store = inject(Workspace);
  leads = inject(Leads);
  campaigns = inject(Campaigns);
  email = inject(Email);
  meetings = inject(Meetings);
  followups = inject(Followups);
  notify = inject(Notification);
  router = inject(Router);
  native = viewChild<ElementRef<HTMLDialogElement>>('native');
  error = signal('');
  busy = signal(false);
  closing = signal(false);
  search = signal('');
  file: File | null = null;
  private returnFocus: HTMLElement | null = null;
  private timer: ReturnType<typeof setTimeout> | undefined;
  f = {
    name: '',
    email: '',
    company: '',
    title: '',
    industry: '',
    audience: '',
    offer: '',
    tone: 'Friendly',
    subject: '',
    body: '',
    lead: '',
    date: '',
    time: '10:00',
    duration: '30',
    ids: [] as string[],
  };
  kind = computed(() => this.dialog.current()?.kind || '');
  id = computed(() => this.dialog.current()?.id);
  profile = computed(() => this.store.state().leads.find((l) => l.id === this.id()));
  minDate = computed(() => today(this.store.state().settings.timezone));
  tones = ['Friendly', 'Professional', 'Casual'].map((s) => ({ value: s, label: s }));
  durations = [15, 20, 30, 45, 60].map((n) => ({ value: String(n), label: n + ' minutes' }));
  contactOptions = computed(() =>
    this.store
      .state()
      .leads.map((l) => ({ value: String(l.id), label: l.name + ' · ' + l.company })),
  );
  campaignLeads = computed(() =>
    this.store.state().leads.filter((l) => l.status !== 'Unsubscribed'),
  );
  needsReview = computed(
    () => this.store.state().drafts.filter((d) => d.status === 'Needs review').length,
  );
  matches = computed(() => {
    const q = this.search().trim().toLowerCase();
    return {
      pages: q ? NAVIGATION.filter((p) => p.label.toLowerCase().includes(q)) : [],
      leads: q
        ? this.store
            .state()
            .leads.filter((l) => `${l.name} ${l.company} ${l.email}`.toLowerCase().includes(q))
        : [],
    };
  });
  title = computed(() => {
    const kind = this.kind(),
      edit = !!this.id();
    const titles: Record<string, string> = {
      lead: edit ? 'Edit contact' : 'A new connection',
      'lead-detail': 'Contact profile',
      delete: 'Delete this lead?',
      campaign: edit ? 'Edit campaign' : 'Give your campaign direction',
      draft: 'Make it sound like you',
      booking: edit ? 'Reschedule conversation' : 'Make room for a conversation',
      followup: 'Plan a thoughtful follow-up',
      import: 'Bring your leads with you',
      reset: 'Start fresh?',
      search: 'Find your next step',
      notifications: 'Your workspace, at a glance',
    };
    return titles[kind] || '';
  });
  constructor() {
    effect(() => {
      const current = this.dialog.current(),
        el = this.native()?.nativeElement;
      if (!el) return;
      untracked(() => {
        if (current) {
          this.initialize();
          if (!el.open) {
            this.returnFocus = document.activeElement as HTMLElement;
            el.showModal();
          }
        } else if (el.open) {
          el.close();
          this.returnFocus?.focus();
        }
      });
    });
    inject(DestroyRef).onDestroy(() => clearTimeout(this.timer));
  }
  initialize(): void {
    clearTimeout(this.timer);
    this.error.set('');
    this.busy.set(false);
    this.closing.set(false);
    this.file = null;
    this.search.set('');
    const current = this.dialog.current()!,
      s = this.store.state();
    this.f = {
      name: '',
      email: '',
      company: '',
      title: '',
      industry: '',
      audience: '',
      offer: s.settings.offer,
      tone: 'Friendly',
      subject: '',
      body: '',
      lead: String(current.lead || s.leads[0]?.id || ''),
      date: '',
      time: '10:00',
      duration: '30',
      ids: [],
    };
    if (current.kind === 'lead' && current.id) {
      const l = this.leads.get(current.id);
      Object.assign(this.f, {
        name: l.name,
        email: l.email,
        company: l.company,
        title: l.title,
        industry: l.industry,
      });
    }
    if (current.kind === 'campaign' && current.id) {
      const c = s.campaigns.find((c) => c.id === current.id)!;
      Object.assign(this.f, {
        name: c.name,
        audience: c.audience,
        offer: c.offer,
        tone: c.tone,
        ids: [...c.ids],
      });
    }
    if (current.kind === 'draft') {
      const d = s.drafts.find((d) => d.id === current.id)!;
      Object.assign(this.f, { subject: d.subject, body: d.body });
    }
    if (current.kind === 'booking' && current.id) {
      const m = s.meetings.find((m) => m.id === current.id)!;
      Object.assign(this.f, {
        lead: String(m.lead),
        date: m.date,
        time: m.time,
        duration: m.duration,
      });
    }
    if (current.kind === 'followup')
      this.f.date = s.leads.find((l) => l.id === current.id)?.followup || '';
  }
  checkLead(id: string, checked: boolean): void {
    this.f.ids = checked ? [...this.f.ids, id] : this.f.ids.filter((x) => x !== id);
  }
  fileChanged(e: Event): void {
    this.file = (e.target as HTMLInputElement).files?.[0] || null;
  }
  async submit(): Promise<void> {
    if (this.busy()) return;
    this.error.set('');
    this.busy.set(true);
    try {
      const id = this.id();
      switch (this.kind()) {
        case 'lead':
          await this.leads.save(
            {
              name: this.f.name,
              email: this.f.email,
              company: this.f.company,
              title: this.f.title,
              industry: this.f.industry,
            },
            id,
          );
          this.notify.show('Contact saved to backend.');
          break;
        case 'campaign':
          await this.campaigns.save(
            {
              name: this.f.name,
              audience: this.f.audience,
              offer: this.f.offer,
              tone: this.f.tone,
              ids: this.f.ids,
            },
            id,
          );
          this.notify.show('Campaign saved to backend.');
          break;
        case 'draft':
          await this.email.edit(id!, this.f.subject, this.f.body);
          this.notify.show('Draft updated. Review and approve again.');
          break;
        case 'booking':
          await this.meetings.save(
            {
              lead: this.f.lead,
              date: this.f.date,
              time: this.f.time,
              duration: this.f.duration,
            },
            id,
          );
          this.notify.show('Booking saved; calendar synchronization queued.');
          break;
        case 'followup':
          await this.followups.schedule(id!, this.f.date);
          this.notify.show('Follow-up scheduled; due draft will require review.');
          break;
        case 'import':
          if (!this.file) throw new Error('Choose a CSV file first.');
          this.busy.set(true);
          const stats = await this.leads.import(await this.file.text());
          this.notify.show(
            `Import complete: ${stats.created} added, ${stats.skipped} duplicates skipped, ${stats.invalid} invalid rows.`,
          );
          break;
        default:
          return;
      }
      this.dialog.close();
    } catch (e) {
      this.error.set((e as Error).message);
    } finally {
      this.busy.set(false);
    }
  }
  async remove(): Promise<void> {
    try { await this.leads.delete(this.id()!); } catch(e) { this.error.set((e as Error).message); return; }
    this.dialog.close();
    this.notify.show('Lead deleted.');
  }
  async reset(): Promise<void> {
    await this.store.reset();
    this.dialog.close();
    this.notify.show('Backend data refreshed.');
    void this.router.navigate(['/overview']);
  }
  close(): void {
    if (this.busy()) return;
    if (matchMedia('(prefers-reduced-motion:reduce)').matches) {
      this.dialog.close();
      return;
    }
    this.closing.set(true);
    this.timer = setTimeout(() => {
      this.closing.set(false);
      this.dialog.close();
    }, 240);
  }
  cancel(event: Event): void {
    event.preventDefault();
    this.close();
  }
  navigate(path: string): void {
    this.dialog.close();
    void this.router.navigate(['/' + path]);
  }
}
