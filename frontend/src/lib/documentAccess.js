/**
 * Secure document access helper.
 *
 * Cloudinary blocks public delivery of PDFs/ZIPs by default → the raw `file_url`
 * returns 401 in the browser. The backend `GET /api/documents/secure-url`
 * endpoint generates a short-lived (15 min) signed Cloudinary Admin-API URL
 * that bypasses this restriction. This helper centralises that call and the
 * window.open()/download flow so View and Download icons across the app stay
 * in sync.
 */
import axios from 'axios';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Fetch a signed Cloudinary URL for an onboarding document.
 *
 * @param {Object}  args
 * @param {string}  args.employeeId    - Owning employee UUID.
 * @param {string}  args.documentType  - e.g. "aadhaar_card", "pan_card".
 * @param {string} [args.disposition]  - "inline" (default) or "attachment".
 * @returns {Promise<string|null>}     - Signed URL, or null on failure.
 */
export async function fetchSignedDocumentUrl({ employeeId, documentType, disposition = 'inline', source = 'onboarding' }) {
  if (!employeeId || !documentType) return null;
  try {
    const token = localStorage.getItem('token');
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
 */
export async function viewSecureDocument({ employeeId, documentType, fallbackUrl, source = 'onboarding' }) {
  const url = await fetchSignedDocumentUrl({ employeeId, documentType, disposition: 'inline', source });
  const target = url || fallbackUrl;
  if (!target) return;
  window.open(target, '_blank', 'noopener,noreferrer');
}

/**
 * Trigger a browser download for a document using a signed URL (Download action).
 * Falls back to the raw URL if signing fails (legacy records).
 */
export async function downloadSecureDocument({ employeeId, documentType, fileName, fallbackUrl, source = 'onboarding' }) {
  const url = await fetchSignedDocumentUrl({ employeeId, documentType, disposition: 'attachment', source });
  const target = url || fallbackUrl;
  if (!target) return;
  // Anchor-based download lets the browser handle the filename + Content-Disposition.
  const a = document.createElement('a');
  a.href = target;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  if (fileName) a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
}
