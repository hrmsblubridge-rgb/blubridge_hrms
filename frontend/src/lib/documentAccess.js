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
 */
export async function viewSecureDocument({
  employeeId, documentType, source = 'onboarding',
}) {
  // 1) Open the placeholder tab on the user gesture so popup blockers allow it.
  const newTab = window.open('about:blank', '_blank', 'noopener,noreferrer');
  if (!newTab) {
    // Popup was blocked BEFORE we could even fetch the signed URL.
    // Tell the user how to fix it — do NOT hijack the current tab.
    toast.error('Popup blocked — please allow popups for this site to view documents');
    return;
  }
  const url = await fetchSignedDocumentUrl({ employeeId, documentType, disposition: 'inline', source });
  if (!url) {
    // No silent fallback to the raw URL (guaranteed 401 for PDFs). Close
    // the placeholder tab; fetchSignedDocumentUrl already toasted the error.
    newTab.close();
    return;
  }
  newTab.location.href = url;
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
