export type LeadStatus =
  | 'New'
  | 'Contacted'
  | 'Replied'
  | 'Qualified'
  | 'Meeting booked'
  | 'Won'
  | 'Lost'
  | 'Unsubscribed'
  | 'Unresponsive'
  | 'Proposal sent'
  | 'Negotiating';
export interface Lead {
  id: string;
  name: string;
  email: string;
  company: string;
  title: string;
  status: LeadStatus;
  industry: string;
  confidence: number;
  followup?: string;
  research?: {
    summary: string;
    opportunity: string;
    source: string;
  };
}
export interface Campaign {
  id: string;
  name: string;
  audience: string;
  status: 'Active' | 'Paused' | 'Draft';
  tone: string;
  offer: string;
  ids: string[];
  sent: number;
  replies: number;
}
export interface EmailDraft {
  id: string;
  lead: string;
  campaign: string;
  status: 'Needs review' | 'Approved' | 'Sent' | 'Queued' | 'Sending' | 'Failed' | 'Cancelled' | 'Delivery unknown';
  revision?: number;
  requiresReview?: boolean;
  failure?: string | null;
  subject: string;
  body: string;
  sentDate?: string;
}
export interface Meeting {
  id: string;
  lead: string;
  date: string;
  time: string;
  duration: string;
  status: 'Scheduled' | 'Cancelled';
  syncStatus?: string;
  joinUrl?: string | null;
  error?: string | null;
}
export interface Conversation {
  lead: string;
  type: string;
  text: string;
  replies: string[];
}
export interface WorkspaceSettings {
  company: string;
  sender: string;
  offer: string;
  timezone: string;
  limit: number;
}
export interface Activity {
  text: string;
  time: string;
}
export interface WorkspaceState {
  leads: Lead[];
  campaigns: Campaign[];
  drafts: EmailDraft[];
  meetings: Meeting[];
  messages: Conversation[];
  settings: WorkspaceSettings;
  activity: Activity[];
}
export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}
export interface Metric {
  label: string;
  value: number | string;
  note: string;
  icon: string;
}
export const LEAD_STATUSES: LeadStatus[] = [
  'New',
  'Contacted',
  'Replied',
  'Qualified',
  'Meeting booked',
  'Won',
  'Lost',
  'Unsubscribed',
];
export const NAVIGATION = [
  { id: 'overview', label: 'Overview' },
  { id: 'discovery', label: 'Business discovery' },
  { id: 'leads', label: 'Leads' },
  { id: 'campaigns', label: 'Campaigns' },
  { id: 'workflow', label: 'AI workflow' },
  { id: 'emails', label: 'Email review' },
  { id: 'inbox', label: 'Inbox' },
  { id: 'meetings', label: 'Meetings' },
  { id: 'followups', label: 'Follow-ups' },
  { id: 'pipeline', label: 'CRM pipeline' },
  { id: 'analytics', label: 'Analytics' },
  { id: 'settings', label: 'Settings' },
];
