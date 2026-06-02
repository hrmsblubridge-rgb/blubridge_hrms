/**
 * Central HRMS date formatter — the SINGLE source of truth for any date
 * displayed in the UI (tables, modals, cards, exports preview, widgets).
 *
 * Output format: 01-May-2026  (DD-Mon-YYYY)
 *   - day:  always 2-digit
 *   - month: 3-letter English abbreviation (Jan, Feb, Mar, ...)
 *   - year: 4-digit
 *
 * Accepts: Date | ISO string ("2026-05-01") | DD-MM-YYYY string ("01-05-2026")
 *         | DD/MM/YYYY | timestamp (number).
 * Returns `fallback` (default "-") for null / undefined / invalid input.
 *
 * IMPORTANT: This helper changes ONLY the displayed string. All API
 * contracts and DB storage formats remain unchanged.
 */

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function parseToDate(input) {
  if (input === null || input === undefined || input === '') return null;
  if (input instanceof Date) return isNaN(input.getTime()) ? null : input;
  if (typeof input === 'number') {
    const d = new Date(input);
    return isNaN(d.getTime()) ? null : d;
  }
  if (typeof input !== 'string') return null;
  const s = input.trim();
  if (!s) return null;

  // DD-MM-YYYY or DD/MM/YYYY
  const ddmm = s.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/);
  if (ddmm) {
    const [, dd, mm, yyyy] = ddmm;
    const d = new Date(Number(yyyy), Number(mm) - 1, Number(dd));
    return isNaN(d.getTime()) ? null : d;
  }

  // YYYY-MM-DD (ISO date) — keep raw to avoid TZ off-by-one
  const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (iso) {
    const [, yyyy, mm, dd] = iso;
    const d = new Date(Number(yyyy), Number(mm) - 1, Number(dd));
    return isNaN(d.getTime()) ? null : d;
  }

  // Full ISO datetime / RFC-2822 — let JS parse
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

/**
 * Primary formatter.
 * @param {*} input  Anything parseable.
 * @param {string} [fallback="-"]  Returned when input is empty / invalid.
 * @returns {string}  e.g. "01-May-2026"
 */
export function formatDate(input, fallback = '-') {
  const d = parseToDate(input);
  if (!d) return fallback;
  const dd = String(d.getDate()).padStart(2, '0');
  const mon = MONTHS[d.getMonth()];
  const yyyy = d.getFullYear();
  return `${dd}-${mon}-${yyyy}`;
}

/**
 * "01-May-2026, 09:45 AM" — for timestamps where time also matters.
 */
export function formatDateTime(input, fallback = '-') {
  const d = parseToDate(input);
  if (!d) return fallback;
  const base = formatDate(d);
  let h = d.getHours();
  const m = String(d.getMinutes()).padStart(2, '0');
  const ampm = h >= 12 ? 'PM' : 'AM';
  h = h % 12 || 12;
  return `${base}, ${String(h).padStart(2, '0')}:${m} ${ampm}`;
}

/**
 * "Mon, 01-May-2026" — for dashboard cards / time tracker headers.
 */
const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
export function formatDateWithDay(input, fallback = '-') {
  const d = parseToDate(input);
  if (!d) return fallback;
  return `${WEEKDAYS[d.getDay()]}, ${formatDate(d)}`;
}

/**
 * "DD-MM-YYYY" — backend API date format used by `/api/attendance`,
 * `/api/dashboard/stats`, etc. Centralised here so frontend display and
 * API params share ONE source of truth (no more query-drift regressions).
 */
export function formatDateForAPI(input) {
  const d = parseToDate(input);
  if (!d) return null;
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  return `${dd}-${mm}-${yyyy}`;
}

export default formatDate;
