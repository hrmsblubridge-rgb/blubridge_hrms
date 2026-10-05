/**
 * whitenBackground — client-side pipeline that guarantees every uploaded
 * profile photo has a strict #FFFFFF background before it ever leaves the
 * browser.
 *
 * Pipeline:
 *   1. Run @imgly/background-removal on the raw File → PNG blob with
 *      transparent background around the subject.
 *   2. Draw the cut-out onto a solid #FFFFFF canvas at the original photo's
 *      pixel dimensions.
 *   3. Return a JPEG File (smaller + no alpha) so Cloudinary storage and
 *      subsequent transformations stay predictable.
 *
 * If anything in the ML step fails (unsupported browser, model download
 * blocked, etc.) the helper THROWS — the caller should surface a toast so
 * the user knows the photo was rejected and can retry, rather than silently
 * uploading a photo with a non-white background.
 */
import { removeBackground } from '@imgly/background-removal';

const WHITE = '#FFFFFF';

const _fileFromBlob = (blob, name) =>
  new File([blob], name, { type: blob.type || 'image/jpeg', lastModified: Date.now() });

const _blobToImageBitmap = async (blob) => {
  if (typeof createImageBitmap === 'function') {
    try {
      return await createImageBitmap(blob);
    } catch {
      /* fall through */
    }
  }
  // Fallback for older browsers
  const url = URL.createObjectURL(blob);
  try {
    const img = await new Promise((resolve, reject) => {
      const el = new Image();
      el.onload = () => resolve(el);
      el.onerror = reject;
      el.src = url;
    });
    return img;
  } finally {
    URL.revokeObjectURL(url);
  }
};

export async function whitenBackground(file, { onProgress } = {}) {
  if (!file) throw new Error('No file provided');

  // 1. Remove background using in-browser WASM model (first call downloads
  // and caches the model, subsequent calls are fast).
  const cutout = await removeBackground(file, {
    output: { format: 'image/png', quality: 1 },
    progress: (key, current, total) => {
      if (onProgress && total) onProgress(key, current, total);
    },
  });

  // 2. Composite the transparent cut-out onto a solid white canvas.
  const bitmap = await _blobToImageBitmap(cutout);
  const w = bitmap.width;
  const h = bitmap.height;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = WHITE;
  ctx.fillRect(0, 0, w, h);
  ctx.drawImage(bitmap, 0, 0);
  if (bitmap.close) bitmap.close();

  // 3. Encode as JPEG (no alpha channel — impossible to reintroduce a
  // transparent/coloured background downstream).
  const jpegBlob = await new Promise((resolve, reject) => {
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Canvas encode failed'))), 'image/jpeg', 0.92);
  });

  const base = (file.name || 'photo').replace(/\.[^.]+$/, '');
  return _fileFromBlob(jpegBlob, `${base}_wbg.jpg`);
}
