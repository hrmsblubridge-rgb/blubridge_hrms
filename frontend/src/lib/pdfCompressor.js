/**
 * Client-side PDF compressor for Offer Letters (and any large PDF upload).
 *
 * Cloudinary's Free plan caps assets at ~10 MB. Users routinely try to
 * upload scanned offer letters that are 12–20 MB. This module re-rasterises
 * each page via pdfjs-dist and re-builds the PDF with jsPDF at reduced
 * DPI + JPEG quality until the output fits under the target threshold.
 *
 * Behaviour:
 *   - Only PDFs are compressed. Non-PDF files are returned unchanged.
 *   - A monotonically-shrinking preset ladder is walked; the first output
 *     that meets `targetBytes` wins.
 *   - If no preset can hit `targetBytes`, the *smallest* output produced
 *     is returned so the caller can still surface a useful error alongside
 *     the (now smaller but not small enough) file size.
 *   - If compression makes the file BIGGER (rare — pure-text PDFs), the
 *     original is returned untouched.
 */

import { jsPDF } from 'jspdf';
import * as pdfjsLib from 'pdfjs-dist/build/pdf.mjs';
// CRA/webpack 5 asset URL — resolves at build time to a URL for the bundled
// worker file. Keeps the compressor fully offline (no CDN dependency).
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.mjs',
  import.meta.url
).toString();

// Ordered from "gentlest" → "most aggressive". Text-heavy documents typically
// only need the top of the ladder; image-heavy scans usually need step 2–4.
const PRESETS = [
  { scale: 1.75, quality: 0.85, label: 'high' },
  { scale: 1.50, quality: 0.75, label: 'medium' },
  { scale: 1.25, quality: 0.60, label: 'low' },
  { scale: 1.00, quality: 0.50, label: 'lowest' },
  { scale: 0.80, quality: 0.40, label: 'minimum' },
];

/** Read a File/Blob as ArrayBuffer. */
function readAsArrayBuffer(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = () => reject(r.error);
    r.readAsArrayBuffer(file);
  });
}

/** Render one PDF page → JPEG data-URL at the requested scale/quality. */
async function renderPageToJpeg(page, scale, quality) {
  const viewport = page.getViewport({ scale });
  const canvas = document.createElement('canvas');
  canvas.width = Math.ceil(viewport.width);
  canvas.height = Math.ceil(viewport.height);
  const ctx = canvas.getContext('2d', { willReadFrequently: false });
  // White background — JPEG has no alpha; blank canvas would render black.
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  await page.render({ canvasContext: ctx, viewport }).promise;
  const dataUrl = canvas.toDataURL('image/jpeg', quality);
  // Free the canvas memory immediately — large PDFs otherwise pin hundreds
  // of MB of bitmap memory in Chrome.
  canvas.width = 0;
  canvas.height = 0;
  return { dataUrl, w: viewport.width, h: viewport.height };
}

/**
 * Rebuild a compressed PDF at the given preset. Returns a Blob.
 */
async function buildCompressedPdf(pdfDoc, preset, onProgress) {
  const pageCount = pdfDoc.numPages;
  let out = null;

  for (let i = 1; i <= pageCount; i++) {
    const page = await pdfDoc.getPage(i);
    const { dataUrl, w, h } = await renderPageToJpeg(page, preset.scale, preset.quality);
    const orientation = w >= h ? 'landscape' : 'portrait';
    // jsPDF works in points (1pt = 1/72"). Our canvas is in pixels at 96 DPI
    // effective, so convert.
    const pageW = (w / 96) * 72;
    const pageH = (h / 96) * 72;
    if (!out) {
      out = new jsPDF({ orientation, unit: 'pt', format: [pageW, pageH], compress: true });
    } else {
      out.addPage([pageW, pageH], orientation);
    }
    out.addImage(dataUrl, 'JPEG', 0, 0, pageW, pageH, undefined, 'FAST');
    if (onProgress) onProgress(Math.round((i / pageCount) * 100));
    // Yield to the event loop so the UI stays responsive on 30+ page PDFs.
    await new Promise((r) => setTimeout(r, 0));
  }

  return out.output('blob');
}

/**
 * Public API — compress a PDF File down to `targetBytes` (best-effort).
 *
 * @param {File} file        The user-picked file.
 * @param {number} targetBytes Threshold to try to fit under (e.g. 9 MB).
 * @param {(pct: number, phase: string) => void} onProgress
 *   Called with (0..100, preset-label) during rendering.
 * @returns {Promise<{ file: File, compressed: boolean, originalBytes: number, finalBytes: number, preset: string | null }>}
 */
export async function compressPdfIfNeeded(file, targetBytes, onProgress) {
  const originalBytes = file.size;
  const isPdf = /\.pdf$/i.test(file.name) || file.type === 'application/pdf';
  if (!isPdf || originalBytes <= targetBytes) {
    return { file, compressed: false, originalBytes, finalBytes: originalBytes, preset: null };
  }

  const buf = await readAsArrayBuffer(file);
  const pdfDoc = await pdfjsLib.getDocument({ data: buf }).promise;

  let best = null; // { blob, preset }
  for (const preset of PRESETS) {
    const blob = await buildCompressedPdf(pdfDoc, preset, (p) => onProgress?.(p, preset.label));
    if (!best || blob.size < best.blob.size) best = { blob, preset };
    if (blob.size <= targetBytes) break; // Good enough — stop escalating.
  }

  // If even the best compressed output is bigger than the original, respect the
  // caller's file (rare with text-only PDFs).
  if (!best || best.blob.size >= originalBytes) {
    return { file, compressed: false, originalBytes, finalBytes: originalBytes, preset: null };
  }

  const outName = file.name.replace(/\.pdf$/i, '') + '_compressed.pdf';
  const outFile = new File([best.blob], outName, { type: 'application/pdf', lastModified: Date.now() });
  return {
    file: outFile,
    compressed: true,
    originalBytes,
    finalBytes: outFile.size,
    preset: best.preset.label,
  };
}
