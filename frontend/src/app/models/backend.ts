export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}
export interface LeadRecord {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  company_name: string | null;
  title: string | null;
  industry: string | null;
  status: string;
  confidence: number;
  research: Record<string, unknown> | null;
}
export interface CampaignRecord {
  id: string;
  name: string;
  audience: string;
  status: string;
  tone: string;
  offer: string;
  lead_ids: string[];
  sent: number;
  replies: number;
}
export interface DraftRecord {
  id: string;
  lead_id: string;
  campaign_id: string;
  status: string;
  subject: string;
  body: string;
  revision: number;
  requires_review: boolean;
  sent_at: string | null;
  failure: string | null;
}
export interface MeetingRecord {
  id: string;
  lead_id: string;
  start_at: string;
  end_at: string;
  status: string;
  sync_status: string;
  join_url: string | null;
  error: string | null;
}
export interface MessageRecord {
  id: string;
  lead_id: string;
  direction: string;
  intent: string;
  body: string;
  created_at: string;
}
export interface FollowupRecord {
  id: string;
  lead_id: string;
  campaign_id: string;
  due_at: string;
  status: string;
}
export interface PreferencesRecord {
  company: string;
  sender: string;
  offer: string;
  timezone: string;
  daily_limit: number;
}
export interface ActivityRecord {
  description: string;
  created_at: string;
}
export interface WorkflowRecord {
  id: string;
  status: string;
  stage: string;
  error: string | null;
  output: Record<string, unknown>;
}
export interface DiscoveryInput {
  industry: string;
  location: string;
  country: 'GB' | 'US';
  limit: number;
  mode: 'fresh' | 'dataset';
  generate_drafts: boolean;
}
export interface DiscoveryRun {
  id: string;
  parameters: DiscoveryInput;
  status: string;
  stage: string;
  total: number;
  processed: number;
  ai_calls: number;
  provider_cost: number;
  provider_run_id: string | null;
  dataset_id: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}
export interface Prospect {
  id: string;
  run_id: string;
  company: string;
  website: string | null;
  country: string;
  city: string;
  phone: string;
  status: string;
  stage: string;
  contact_available: boolean;
  emails: { email: string; source_url: string }[];
  app_status: string;
  score: number;
  reason: string | null;
  analysis: {
    summary?: string;
    opportunity?: string;
    provider?: string;
    score?: number;
    suitable?: boolean;
    reasons?: string[];
    tokens?: number;
  };
  evidence: Record<string, unknown>;
  lead_id: string | null;
  campaign_id: string | null;
}
export interface DiscoveryConfiguration {
  apify_configured: boolean;
  dataset_configured: boolean;
  daily_limit: number;
  run_budget_usd: number;
  ai_provider: string;
  ai_configured: boolean;
  ai_endpoint: string;
  ai_model: string;
  ai_calls_per_run: number;
}
