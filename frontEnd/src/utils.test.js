import { describe, expect, it } from 'vitest';
import { humanDate, localDateString, membershipDisplayStatus } from './utils.js';

describe('localDateString', () => {
  it('formats a local calendar date as YYYY-MM-DD', () => {
    expect(localDateString(new Date(2026, 0, 9))).toBe('2026-01-09');
  });
});

describe('humanDate', () => {
  it('returns a placeholder for an empty date', () => {
    expect(humanDate('')).toBe('—');
  });

  it('formats a valid date without shifting the calendar day', () => {
    expect(humanDate('2026-02-14')).toContain('2026');
  });
});

describe('membershipDisplayStatus', () => {
  const today = '2026-06-15';

  it('marks an ended active membership as expired', () => {
    expect(membershipDisplayStatus({
      status: 'active',
      start_date: '2026-01-01',
      expiry_date: '2026-06-14',
    }, today)).toBe('Expired');
  });

  it('marks a future active membership as scheduled', () => {
    expect(membershipDisplayStatus({
      status: 'active',
      start_date: '2026-06-16',
      expiry_date: '2027-06-15',
    }, today)).toBe('Scheduled');
  });

  it('capitalizes other membership statuses', () => {
    expect(membershipDisplayStatus({
      status: 'cancelled',
      start_date: '2026-01-01',
      expiry_date: '2027-01-01',
    }, today)).toBe('Cancelled');
  });
});
