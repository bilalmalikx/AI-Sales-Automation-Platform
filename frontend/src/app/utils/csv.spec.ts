import { describe, it, expect } from 'vitest';
import { parseCsv, csvCell } from './csv';
import { meetingsOverlap } from './date';
describe('CSV imports', () => {
  it('preserves quoted commas, escaped quotes and multiline cells', () => {
    expect(
      parseCsv(
        'name,email\r\n"Alex, Morgan",alex@example.com\r\n"A ""quoted""\nname",test@example.com',
      ),
    ).toEqual([
      ['name', 'email'],
      ['Alex, Morgan', 'alex@example.com'],
      ['A "quoted"\nname', 'test@example.com'],
    ]);
  });
  it('rejects incomplete quoted data', () => {
    expect(() => parseCsv('email\n"broken')).toThrow('Unclosed quotation');
  });
  it('neutralizes spreadsheet formulas in exported cells', () => {
    expect(csvCell('=HYPERLINK("bad")')).toContain("'=HYPERLINK");
  });
});
describe('Booking conflicts', () => {
  it('allows adjacent appointments and rejects genuine overlap', () => {
    const a = { date: '2026-10-15', time: '10:00', duration: '30' };
    expect(meetingsOverlap(a, { ...a, time: '10:30' })).toBe(false);
    expect(meetingsOverlap(a, { ...a, time: '10:15' })).toBe(true);
    expect(meetingsOverlap(a, { ...a, time: '09:45', duration: '20' })).toBe(true);
    expect(meetingsOverlap(a, { ...a, date: '2026-10-16' })).toBe(false);
  });
});
