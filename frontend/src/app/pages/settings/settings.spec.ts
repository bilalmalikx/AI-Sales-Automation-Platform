import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Settings } from './settings';
import { Workspace } from '../../services/workspace';
import { Api } from '../../services/api';
import { Auth } from '../../services/auth';
import { Dialog } from '../../services/dialog';
import { Notification } from '../../services/notification';

describe('Service connection controls', () => {
  const integrations = {
    ai: {provider: 'openai', configured: true},
    email: {provider: 'smtp', configured: true, delivery_enabled: true},
    calendar: {provider: 'local', configured: true},
    inbox: {provider: 'imap', configured: true, status: 'synced', automatic_sync: true, last_checked_at: null, error: null},
  };
  let api: { get: ReturnType<typeof vi.fn>; post: ReturnType<typeof vi.fn> };
  let refresh: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    api = {get: vi.fn().mockResolvedValue(integrations), post: vi.fn()};
    refresh = vi.fn().mockResolvedValue(undefined);
    TestBed.configureTestingModule({providers: [
      {provide: Api, useValue: api},
      {provide: Auth, useValue: {user: signal(null)}},
      {provide: Workspace, useValue: {ready: signal(true), state: signal({settings: {company: 'Skilledhat', sender: 'Team', offer: 'Mobile apps', timezone: 'Asia/Karachi', limit: 10}}), refresh}},
      {provide: Dialog, useValue: {}},
      {provide: Notification, useValue: {show: vi.fn()}},
    ]});
  });
  function create() { return TestBed.runInInjectionContext(() => new Settings()); }
  it('checks SMTP without requesting Send', async () => {
    const page = create();
    api.post.mockResolvedValue({status: 'connected', message: 'No email sent.'});
    await page.checkSmtp();
    expect(api.post).toHaveBeenCalledExactlyOnceWith('integrations/email/check');
    expect(page.smtpResult()).toBe('No email sent.');
    expect(page.checking()).toBe(false);
  });
  it('refreshes real inbox records after successful sync', async () => {
    const page = create();
    api.post.mockResolvedValue({status: 'synced', processed: 2});
    await page.syncInbox();
    expect(api.post).toHaveBeenCalledExactlyOnceWith('integrations/inbox/sync');
    expect(refresh).toHaveBeenCalledOnce();
    expect(page.syncing()).toBe(false);
  });
  it('keeps sync failure visible without claiming records were imported', async () => {
    const page = create();
    await page.loadIntegrations();
    api.post.mockResolvedValue({status: 'failed', processed: 0, message: 'Check IMAP credentials.'});
    await page.syncInbox();
    expect(page.integrationError()).toBe('Check IMAP credentials.');
    expect(refresh).not.toHaveBeenCalled();
  });
});
