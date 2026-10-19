import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Discovery } from './discovery';
import { Discovery as DiscoveryService } from '../../services/discovery';

describe('Daily discovery safety', () => {
  let save: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    save = vi.fn().mockResolvedValue(true);
    TestBed.configureTestingModule({providers:[{provide:DiscoveryService,useValue:{
      saveSchedule:save, runs:signal([]), prospects:signal([]), selected:signal(''),
    }}]});
  });
  it('creates a paused schedule using the visible search settings', async () => {
    const page = TestBed.runInInjectionContext(() => new Discovery());
    page.scheduleName='Skilledhat daily';
    page.scheduleDate=new Date(Date.now()+86400000).toISOString();
    page.form.location='Manchester';
    await page.createSchedule();
    expect(save).toHaveBeenCalledOnce();
    const value = save.mock.calls[0][0];
    expect(value.enabled).toBe(false);
    expect(value.parameters.location).toBe('Manchester');
    expect(value.parameters.limit).toBe(50);
    expect(value.due_at.endsWith('Z')).toBe(true);
    expect(page.scheduleNotice()).toContain('paused');
  });
  it('does not save an invalid or expired first-run time', async () => {
    const page = TestBed.runInInjectionContext(() => new Discovery());
    page.scheduleName='Daily';
    page.scheduleDate='2000-01-01T10:00';
    await page.createSchedule();
    expect(save).not.toHaveBeenCalled();
    expect(page.scheduleNotice()).toContain('future');
  });
});
