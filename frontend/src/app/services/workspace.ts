import { Injectable, inject, signal, DestroyRef } from '@angular/core';
import { Api } from './api';
import { WorkspaceState, LeadStatus, EmailDraft } from '../models/workspace';
import {
  ActivityRecord,
  CampaignRecord,
  DraftRecord,
  FollowupRecord,
  LeadRecord,
  MeetingRecord,
  MessageRecord,
  PreferencesRecord,
} from '../models/backend';
export const label = (value: string): string =>
  value.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
@Injectable({ providedIn: 'root' })
export class Workspace {
  readonly api = inject(Api);
  readonly ready = signal(false);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly storageOK = signal(true);
  readonly state = signal<WorkspaceState>({
    leads: [],
    campaigns: [],
    drafts: [],
    meetings: [],
    messages: [],
    activity: [],
    settings: {
      company: 'Codelps',
      sender: 'Codelps team',
      offer:
        'Mobile application development for businesses: booking, ordering, membership and customer loyalty.',
      timezone: 'Asia/Karachi',
      limit: 10,
    },
  });
  readonly followupRecords = signal<FollowupRecord[]>([]);
  readonly deliveryEnabled = signal(false);
  readonly emailProvider = signal('');
  constructor() {
    void this.refresh();
    const timer = setInterval(() => void this.refresh(), 5000);
    inject(DestroyRef).onDestroy(() => clearInterval(timer));
  }
  async refresh(): Promise<void> {
    if (this.loading()) return;
    this.loading.set(true);
    try {
      const [
        leads,
        campaigns,
        drafts,
        meetings,
        messages,
        activity,
        prefs,
        followups,
        integrations,
      ] = await Promise.all([
        this.api.all<LeadRecord>('leads'),
        this.api.all<CampaignRecord>('campaigns'),
        this.api.all<DraftRecord>('emails'),
        this.api.all<MeetingRecord>('meetings'),
        this.api.all<MessageRecord>('inbox'),
        this.api.all<ActivityRecord>('activity'),
        this.api.get<PreferencesRecord>('settings'),
        this.api.all<FollowupRecord>('followups'),
        this.api.get<{ live_delivery_enabled: boolean; email: { provider: string } }>(
          'integrations',
        ),
      ]);
      this.followupRecords.set(followups);
      this.deliveryEnabled.set(integrations.live_delivery_enabled);
      this.emailProvider.set(integrations.email.provider);
      const timezone = prefs.timezone;
      const localParts = (iso: string) =>
        Object.fromEntries(
          new Intl.DateTimeFormat('en-CA', {
            timeZone: timezone,
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            hourCycle: 'h23',
          })
            .formatToParts(new Date(iso))
            .map((x) => [x.type, x.value]),
        );
      this.state.set({
        leads: leads.map((l) => ({
          id: l.id,
          name: [l.first_name, l.last_name].filter(Boolean).join(' ') || l.company_name || l.email,
          email: l.email,
          company: l.company_name || '',
          title: l.title || 'Business contact',
          industry: l.industry || 'Not provided',
          status: label(l.status) as LeadStatus,
          confidence: Math.round(l.confidence * 100),
          research: l.research
            ? {
                summary: String(l.research['summary'] || l.research['company_description'] || ''),
                opportunity: String(l.research['opportunity'] || ''),
                source: String(l.research['source'] || ''),
              }
            : undefined,
          followup: followups
            .find((f) => f.lead_id === l.id && f.status === 'scheduled')
            ?.due_at.slice(0, 10),
        })),
        campaigns: campaigns.map((c) => ({
          id: c.id,
          name: c.name,
          audience: c.audience,
          status: label(c.status) as 'Active' | 'Paused' | 'Draft',
          tone: label(c.tone),
          offer: c.offer,
          ids: c.lead_ids,
          sent: c.sent,
          replies: c.replies,
        })),
        drafts: drafts.map((d) => ({
          id: d.id,
          lead: d.lead_id,
          campaign: d.campaign_id,
          status: label(d.status) as EmailDraft['status'],
          subject: d.subject,
          body: d.body,
          revision: d.revision,
          requiresReview: d.requires_review,
          failure: d.failure,
          sentDate: d.sent_at?.slice(0, 10),
        })),
        meetings: meetings.map((m) => {
          const p = localParts(m.start_at);
          return {
            id: m.id,
            lead: m.lead_id,
            date: `${p['year']}-${p['month']}-${p['day']}`,
            time: `${p['hour']}:${p['minute']}`,
            duration: String((Date.parse(m.end_at) - Date.parse(m.start_at)) / 60000),
            status: label(m.status) as 'Scheduled' | 'Cancelled',
            syncStatus: m.sync_status,
            joinUrl: m.join_url,
            error: m.error,
          };
        }),
        messages: messages
          .filter((m) => m.direction === 'incoming')
          .map((m) => ({
            lead: m.lead_id,
            type: label(m.intent),
            text: m.body,
            replies: messages
              .filter(
                (r) =>
                  r.direction === 'outgoing' &&
                  r.lead_id === m.lead_id &&
                  r.created_at > m.created_at,
              )
              .map((r) => r.body),
          })),
        activity: activity.map((a) => ({
          text: a.description,
          time: new Date(
            a.created_at.endsWith('Z') ? a.created_at : a.created_at + 'Z',
          ).toLocaleString(),
        })),
        settings: {
          company: prefs.company,
          sender: prefs.sender,
          offer: prefs.offer,
          timezone,
          limit: prefs.daily_limit,
        },
      });
      this.ready.set(true);
      this.error.set('');
    } catch (e) {
      this.error.set((e as Error).message);
    } finally {
      this.loading.set(false);
    }
  }
  async reset(): Promise<void> {
    await this.refresh();
  }
}
