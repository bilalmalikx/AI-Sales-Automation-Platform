import { Routes } from '@angular/router';
export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'overview' },
  {
    path: 'overview',
    loadComponent: () => import('./pages/overview/overview').then((m) => m.Overview),
  },
  { path: 'discovery', loadComponent: () => import('./pages/discovery/discovery').then(m => m.Discovery) },
  { path: 'leads', loadComponent: () => import('./pages/leads/leads').then((m) => m.Leads) },
  {
    path: 'campaigns',
    loadComponent: () => import('./pages/campaigns/campaigns').then((m) => m.Campaigns),
  },
  {
    path: 'workflow',
    loadComponent: () => import('./pages/workflow/workflow').then((m) => m.Workflow),
  },
  { path: 'emails', loadComponent: () => import('./pages/emails/emails').then((m) => m.Emails) },
  { path: 'inbox', loadComponent: () => import('./pages/inbox/inbox').then((m) => m.Inbox) },
  {
    path: 'meetings',
    loadComponent: () => import('./pages/meetings/meetings').then((m) => m.Meetings),
  },
  {
    path: 'followups',
    loadComponent: () => import('./pages/followups/followups').then((m) => m.Followups),
  },
  {
    path: 'pipeline',
    loadComponent: () => import('./pages/pipeline/pipeline').then((m) => m.Pipeline),
  },
  {
    path: 'analytics',
    loadComponent: () => import('./pages/analytics/analytics').then((m) => m.Analytics),
  },
  {
    path: 'settings',
    loadComponent: () => import('./pages/settings/settings').then((m) => m.Settings),
  },
  { path: '**', redirectTo: 'overview' },
];
