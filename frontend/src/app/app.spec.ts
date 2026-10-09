import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { Workspace } from './services/workspace';
import { Leads } from './services/leads';
import { Api } from './services/api';
const uuid = '5e90a4db-4816-4da9-b1cb-69e6096cb176';
const prefs = {
  company: 'Codelps',
  sender: 'Team',
  offer: 'Mobile apps',
  timezone: 'Asia/Karachi',
  daily_limit: 10,
};
const record = {
  id: uuid,
  email: 'hello@real.example.com',
  first_name: 'Real',
  last_name: 'Business',
  company_name: 'Real Business',
  title: 'Owner',
  industry: 'Car wash',
  status: 'new',
  confidence: 0.8,
  research: { summary: 'Website evidence', source: 'Public website' },
};
describe('Real backend integration', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    http.verify();
    TestBed.resetTestingModule();
  });
  function flushWorkspace() {
    for (const r of http.match((req) => req.method === 'GET')) {
      if (r.request.url.endsWith('/settings')) r.flush(prefs);
      else if (r.request.url.endsWith('/integrations'))
        r.flush({ live_delivery_enabled: false, email: { provider: 'smtp' } });
      else
        r.flush({
          items: r.request.url.includes('/leads?') ? [record] : [],
          total: r.request.url.includes('/leads?') ? 1 : 0,
          page: 1,
          page_size: 100,
          pages: 1,
        });
    }
  }
  it('loads persisted UUID records and never seeds demo leads', async () => {
    const store = TestBed.inject(Workspace);
    expect(store.state().leads).toEqual([]);
    flushWorkspace();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(store.ready()).toBe(true);
    expect(store.state().leads[0].id).toBe(uuid);
    expect(store.state().leads[0].confidence).toBe(80);
    expect(store.state().settings.company).toBe('Codelps');
  });
  it('saves edits to the UUID endpoint and refreshes persisted records', async () => {
    const leads = TestBed.inject(Leads);
    flushWorkspace();
    await new Promise((resolve) => setTimeout(resolve, 0));
    const task = leads.save(
      {
        name: 'Updated Owner',
        email: 'hello@real.example.com',
        company: 'Real Business',
        title: 'Owner',
        industry: 'Car wash',
      },
      uuid,
    );
    const update = http.expectOne(
      (req) => req.method === 'PUT' && req.url.endsWith('/leads/' + uuid),
    );
    expect(update.request.body.first_name).toBe('Updated');
    update.flush(record);
    await new Promise((resolve) => setTimeout(resolve, 0));
    flushWorkspace();
    await task;
    expect(leads.items()).toHaveLength(1);
  });
  it('surfaces backend conflict errors instead of claiming a local save', async () => {
    const api = TestBed.inject(Api);
    const result = api.post('campaigns', {});
    const assertion = expect(result).rejects.toThrow('Lead is not assigned');
    http
      .expectOne((req) => req.method === 'POST')
      .flush(
        { error: { message: 'Lead is not assigned' } },
        { status: 409, statusText: 'Conflict' },
      );
    await assertion;
  });
});
