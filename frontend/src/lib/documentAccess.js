/**
 * Secure document access helper.
 *
 * Cloudinary blocks public delivery of PDFs / ZIPs / DOCX by default → the raw
 * `file_url` returns 401 in the browser. The backend
 * `GET /api/documents/secure-url` endpoint generates a short-lived (15 min)
 * signed Cloudinary Admin-API URL that bypasses this restriction.
 *
 * Single source of truth for both **View** and **Download** actions across
 * Verification, Employees, EmployeeDocuments, and EmployeeOnboarding.
 *
 * Design choices encoded here (intentional, not arbitrary):
 *
 *   1. **Auth token** comes from `AuthContext`'s localStorage key
 *      (`blubridge_token`). Reading the wrong key was the long-standing
 *      cause of the "401 Unauthorized" bug: a wrong key → null Bearer →
 *      backend 401 → silent fallback to the raw URL → Cloudinary 401.
 *
 *   2. **No silent fallback to a known-broken URL.** If the signed URL
 *      fetch fails, we surface the error to the user and STOP. Opening the
 *      raw `res.cloudinary.com/...pdf` URL is *guaranteed* to 401 for PDFs
 *      / DOCX (Cloudinary security default) — falling back to it just hides
 *      the real failure and shows a blank browser tab.
 *
 *   3. **Popup-blocker-safe view.** We open the new tab *synchronously* on
 *      the original click (browser allows it as a user-gesture window), then
 *      redirect it after the async signed-URL fetch resolves. Without this,
 *      Safari/Firefox suppress `window.open()` calls that happen after an
 *      `await`.
 */
import axios from 'axios';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Auth token lives under this single key (AuthContext.js owns this name).
// If you ever rename it, change it in ONE place — both AuthContext and here.
const AUTH_TOKEN_KEY = 'blubridge_token';

function _authToken() {
  try {
    return localStorage.getItem(AUTH_TOKEN_KEY);
  } catch {
    return null;
  }
}

/**
 * Fetch a signed Cloudinary URL for a document.
 *
 * @param {Object}  args
 * @param {string}  args.employeeId    - Owning employee UUID.
 * @param {string}  args.documentType  - e.g. "aadhaar_card", "pan_card".
 * @param {string} [args.disposition]  - "inline" (default) or "attachment".
 * @param {string} [args.source]       - "onboarding" (default) | "employee".
 * @returns {Promise<string|null>}     - Signed URL, or null on failure.
 */
export async function fetchSignedDocumentUrl({
  employeeId, documentType, disposition = 'inline', source = 'onboarding',
}) {
  if (!employeeId || !documentType) return null;
  const token = _authToken();
  if (!token) {
    toast.error('Session expired — please log in again');
    return null;
  }
  try {
    const res = await axios.get(`${API}/documents/secure-url`, {
      params: { employee_id: employeeId, document_type: documentType, disposition, source },
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.data?.url || null;
  } catch (err) {
    const detail = err?.response?.data?.detail || err?.message || 'Failed to load document';
    toast.error(detail);
    return null;
  }
}

/**
 * Open a document in a new tab using a signed URL (View action).
 *
 * Popup-blocker-safe: opens a placeholder tab synchronously on the user
 * gesture, then redirects it once the signed URL resolves. We NEVER
 * navigate the current tab — that would yank the admin out of the
 * Verification / Employees screen they were working on, losing context.
 *
 * IMPORTANT — do NOT add `noopener,noreferrer` to the FIRST window.open()
 * below. Per spec, when those flags are present `window.open()` returns
 * `null` even though it DOES open a tab — Chrome/Edge/Firefox all behave
 * this way. The `null` return then trips the `if (!newTab)` guard, so
 * `newTab.location.href = url` never runs and the user is left staring at
 * the placeholder `about:blank` tab forever — the exact "View renders
 * blank" P0 we keep hitting. The tab is same-origin (we navigate it to a
 * URL on our own backend) so we don't need `noopener` for security; we
 * explicitly set `opener = null` after the navigation as a defence-in-depth
 * measure (functionally equivalent to `noopener` minus the null-return
 * footgun).
 */
export async function viewSecureDocument({
  employeeId, documentType, source = 'onboarding',
}) {
  // 1) Open the placeholder tab on the user gesture so popup blockers allow it.
  //    DO NOT pass `noopener,noreferrer` here — see comment above.
  const newTab = window.open('about:blank', '_blank');
  if (!newTab) {
    // A real popup blocker (no tab opened at all).
    toast.error('Popup blocked — please allow popups for this site to view documents');
    return;
  }
  // Optional: show a tiny "Loading…" message so the user sees something
  // instead of a stark white tab while the signed URL fetch is in flight.
  try {
    newTab.document.write(
      '<!doctype html><html><head><title>Loading document…</title>' +
      '<style>body{font-family:system-ui,sans-serif;display:flex;align-items:center;' +
      'justify-content:center;height:100vh;margin:0;color:#475569;background:#f8fafc}' +
      '</style></head><body>Loading document…</body></html>'
    );
    newTab.document.close();
  } catch (_) { /* best-effort */ }

  const url = await fetchSignedDocumentUrl({ employeeId, documentType, disposition: 'inline', source });
  if (!url) {
    // No silent fallback to the raw URL (guaranteed 401 for PDFs). Close
    // the placeholder tab; fetchSignedDocumentUrl already toasted the error.
    try { newTab.close(); } catch (_) { /* ignore */ }
    return;
  }
  // Navigate the tab to the inline-stream URL. Using `location.replace` so
  // the about:blank entry does not pollute the back-button history.
  try {
    newTab.location.replace(url);
  } catch (_) {
    // Fallback — assigning location is sometimes blocked when the tab is
    // marked cross-origin by an extension. Last-resort: navigate via href.
    newTab.location.href = url;
  }
  // Defence in depth: sever opener so the loaded document can't navigate us.
  try { newTab.opener = null; } catch (_) { /* ignore */ }
}

/**
 * Trigger a browser download for a document using a signed URL (Download action).
 *
 * Uses an anchor with `download` attribute so the browser preserves the
 * original filename (Cloudinary Content-Disposition supplies it too).
 */
export async function downloadSecureDocument({
  employeeId, documentType, fileName, source = 'onboarding',
}) {
  const url = await fetchSignedDocumentUrl({ employeeId, documentType, disposition: 'attachment', source });
  if (!url) {
    // Same as view: no broken fallback.
    return;
  }
  const a = document.createElement('a');
  a.href = url;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  if (fileName) a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
}
