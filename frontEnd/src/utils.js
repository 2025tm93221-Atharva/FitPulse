export function localDateString(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function humanDate(value) {
  if (!value) return '—';
  const parsed = new Date(`${value.slice(0, 10)}T12:00:00`);
  return parsed.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

export function formatTimestamp(value) {
  if (!value) return 'No visits recorded yet';
  return new Date(value).toLocaleString(undefined, {
    day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
  });
}

export function membershipDisplayStatus(membership, today) {
  if (membership.status === 'active' && membership.expiry_date < today) return 'Expired';
  if (membership.status === 'active' && membership.start_date > today) return 'Scheduled';
  return membership.status.charAt(0).toUpperCase() + membership.status.slice(1);
}
