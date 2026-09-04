// Star Reward display formats: dates DD-MM-YYYY, times hh:mm AM/PM.
export const fmtDate = (iso) => {
  if (!iso) return '--';
  const s = String(iso).slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return String(iso);
  const [y, m, d] = s.split('-');
  return `${d}-${m}-${y}`;
};

export const fmtTime = (value) => {
  if (!value) return '--';
  const raw = String(value);
  const m = raw.match(/(\d{1,2}):(\d{2})/);
  if (!m) return raw;
  let h = parseInt(m[1], 10);
  const suffix = h >= 12 ? 'PM' : 'AM';
  h = h % 12 || 12;
  return `${String(h).padStart(2, '0')}:${m[2]} ${suffix}`;
};

export const fmtDateTime = (iso) => (iso ? `${fmtDate(iso)} ${fmtTime(String(iso).slice(11))}` : '--');
