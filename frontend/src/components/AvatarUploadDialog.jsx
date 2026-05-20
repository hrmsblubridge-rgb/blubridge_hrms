/**
 * AvatarUploadDialog — admin-side profile photo upload modal.
 *
 * Supports four input methods:
 *   • Click to open file picker
 *   • Drag-and-drop image file onto the dropzone
 *   • CTRL+V to paste image from clipboard (screenshots, copied images)
 *   • Mobile camera capture (via accept="image/*" + capture attribute)
 *
 * Features:
 *   • Live preview before save
 *   • 5 MB size cap, format validation (JPG/JPEG/PNG/WebP)
 *   • Upload progress indicator
 *   • Replace / Remove / Cancel
 *   • Centralized refreshAvatars() on success so every HRMS module
 *     (Attendance, Leave, Payroll, Dashboard, ID-card, etc.) picks up
 *     the new photo without a page reload.
 *   • Audit log written by the backend on every PUT/DELETE
 */
import { useRef, useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Camera,
  Loader2,
  Upload as UploadIcon,
  ClipboardPaste,
  Trash2,
  X,
  ImagePlus,
} from 'lucide-react';
import EmployeeAvatar from './EmployeeAvatar';
import { Button } from './ui/button';
import { useAuth } from '../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ACCEPTED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
const MAX_SIZE_BYTES = 5 * 1024 * 1024;

const formatBytes = (n) => {
  if (!n && n !== 0) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
};

const AvatarUploadDialog = ({ employee, open, onClose, onUpdated, token }) => {
  const { refreshAvatars } = useAuth() || {};
  const fileRef = useRef(null);
  const dropRef = useRef(null);

  const [previewUrl, setPreviewUrl] = useState(null); // local blob URL
  const [pendingFile, setPendingFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  const authHeader = { Authorization: `Bearer ${token}` };

  // Reset state whenever the dialog re-opens
  useEffect(() => {
    if (open) {
      setPreviewUrl(null);
      setPendingFile(null);
      setProgress(0);
      setBusy(false);
      setIsDragging(false);
    }
  }, [open, employee?.id]);

  // Cleanup blob URLs on unmount
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const validateAndStage = useCallback((file) => {
    if (!file) return false;
    if (!ACCEPTED_TYPES.includes(file.type)) {
      toast.error('Unsupported format. Please use JPG, PNG, or WebP.');
      return false;
    }
    if (file.size > MAX_SIZE_BYTES) {
      toast.error('File too large. Maximum size is 5 MB.');
      return false;
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    setPendingFile(file);
    return true;
  }, [previewUrl]);

  // ---- Clipboard paste (CTRL+V) ----
  useEffect(() => {
    if (!open) return undefined;
    const handler = (e) => {
      if (busy) return;
      const items = e.clipboardData?.items || [];
      for (let i = 0; i < items.length; i += 1) {
        const item = items[i];
        if (item.kind === 'file' && item.type?.startsWith('image/')) {
          const file = item.getAsFile();
          if (file) {
            // Rename pasted blob with a sensible filename + correct extension
            const ext = (file.type.split('/')[1] || 'png').replace('jpeg', 'jpg');
            const named = new File([file], `pasted-${Date.now()}.${ext}`, { type: file.type });
            if (validateAndStage(named)) {
              toast.success('Image pasted from clipboard');
              e.preventDefault();
            }
            return;
          }
        }
      }
    };
    window.addEventListener('paste', handler);
    return () => window.removeEventListener('paste', handler);
  }, [open, busy, validateAndStage]);

  // ---- Drag and drop ----
  const onDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!busy) setIsDragging(true);
  };
  const onDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };
  const onDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (busy) return;
    const file = e.dataTransfer?.files?.[0];
    if (file) validateAndStage(file);
  };

  // ---- File picker ----
  const onFileChange = (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (file) validateAndStage(file);
  };

  // ---- Upload to Cloudinary then persist on backend ----
  const handleSave = async () => {
    if (!pendingFile || !employee?.id) return;
    setBusy(true);
    setProgress(5);
    try {
      // 1) Cloudinary signature
      const sigResp = await axios.get(`${API}/cloudinary/signature?folder=avatars`, { headers: authHeader });
      const { signature, timestamp, cloud_name, api_key, folder, type } = sigResp.data;
      setProgress(15);

      // 2) Upload to Cloudinary with progress
      const fd = new FormData();
      fd.append('file', pendingFile);
      fd.append('signature', signature);
      fd.append('timestamp', timestamp);
      fd.append('api_key', api_key);
      fd.append('folder', folder);
      if (type) fd.append('type', type);

      const cloudResp = await axios.post(
        `https://api.cloudinary.com/v1_1/${cloud_name}/auto/upload`,
        fd,
        {
          onUploadProgress: (evt) => {
            if (evt.total) {
              const pct = Math.round((evt.loaded / evt.total) * 75) + 15;
              setProgress(Math.min(pct, 90));
            }
          },
        }
      );
      const fullUrl = cloudResp.data.secure_url;
      const publicId = cloudResp.data.public_id;
      const transformed = fullUrl.includes('/upload/')
        ? fullUrl.replace('/upload/', '/upload/c_fill,g_face,w_512,h_512,q_auto,f_auto/')
        : fullUrl;
      setProgress(95);

      // 3) Persist on backend (admin endpoint — writes audit log + handles old asset cleanup)
      const saveResp = await axios.put(
        `${API}/employees/${employee.id}/avatar`,
        { avatar_url: transformed, avatar_public_id: publicId },
        { headers: authHeader }
      );
      setProgress(100);
      toast.success(`Profile photo updated for ${employee.full_name}`);
      onUpdated?.(saveResp.data);
      refreshAvatars?.();
      onClose?.();
    } catch (err) {
      console.error('Admin avatar upload error:', err);
      toast.error(err.response?.data?.detail || 'Failed to upload photo');
    } finally {
      setBusy(false);
      setProgress(0);
    }
  };

  const handleRemove = async () => {
    if (!employee?.avatar) return;
    if (!window.confirm(`Remove the profile photo for ${employee.full_name}?`)) return;
    setBusy(true);
    try {
      const resp = await axios.put(
        `${API}/employees/${employee.id}/avatar`,
        { avatar_url: '', avatar_public_id: null },
        { headers: authHeader }
      );
      toast.success('Profile photo removed');
      onUpdated?.(resp.data);
      refreshAvatars?.();
      onClose?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to remove photo');
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  const hasExistingPhoto = !!employee?.avatar;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in"
      onClick={busy ? undefined : onClose}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      data-testid="avatar-upload-dialog"
    >
      <div
        className={`w-full max-w-lg bg-white rounded-2xl shadow-2xl overflow-hidden transition ${
          isDragging ? 'ring-4 ring-[#063c88]/50' : ''
        }`}
        onClick={(e) => e.stopPropagation()}
        ref={dropRef}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <div>
            <h3 className="text-base font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>
              Update profile photo
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              {employee?.full_name} · {employee?.designation || employee?.department || ''}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="p-1.5 rounded-lg hover:bg-slate-100 disabled:opacity-40"
            aria-label="Close"
            data-testid="avatar-dialog-close"
          >
            <X className="w-4 h-4 text-slate-500" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4">
          {/* Preview row */}
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0">
              <EmployeeAvatar
                employee={previewUrl ? { ...employee, avatar: previewUrl } : employee}
                size="xl"
                shape="circle"
                testId="avatar-dialog-preview"
              />
            </div>
            <div className="flex-1 text-xs text-slate-500 space-y-1">
              <div>JPG, PNG, or WebP · up to 5 MB</div>
              <div>Auto-resized to 512×512 with face-aware cropping</div>
              {pendingFile && (
                <div className="text-emerald-700 font-medium pt-1">
                  ✓ {pendingFile.name} ({formatBytes(pendingFile.size)})
                </div>
              )}
            </div>
          </div>

          {/* Dropzone */}
          <button
            type="button"
            onClick={() => !busy && fileRef.current?.click()}
            disabled={busy}
            className={`w-full rounded-xl border-2 border-dashed transition-all p-6 text-center ${
              isDragging
                ? 'border-[#063c88] bg-[#063c88]/5'
                : 'border-slate-200 hover:border-[#063c88]/40 hover:bg-slate-50'
            } ${busy ? 'opacity-60 cursor-wait' : 'cursor-pointer'}`}
            data-testid="avatar-dialog-dropzone"
          >
            <ImagePlus className="w-8 h-8 mx-auto mb-2 text-[#063c88]" />
            <div className="text-sm font-medium text-slate-700">
              {isDragging ? 'Release to drop' : 'Click to upload, drag &amp; drop, or paste'}
            </div>
            <div className="text-[11px] text-slate-500 mt-1.5 flex items-center justify-center gap-3 flex-wrap">
              <span className="inline-flex items-center gap-1">
                <UploadIcon className="w-3 h-3" /> Browse
              </span>
              <span>·</span>
              <span className="inline-flex items-center gap-1">
                <ClipboardPaste className="w-3 h-3" /> Ctrl+V to paste
              </span>
              <span>·</span>
              <span className="inline-flex items-center gap-1">
                <Camera className="w-3 h-3" /> Camera
              </span>
            </div>
          </button>

          {/* Progress */}
          {busy && progress > 0 && (
            <div data-testid="avatar-dialog-progress">
              <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className="h-1.5 bg-[#063c88] transition-all rounded-full"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="text-[11px] text-slate-500 mt-1.5 flex items-center justify-between">
                <span>Uploading…</span><span>{progress}%</span>
              </div>
            </div>
          )}

          <input
            ref={fileRef}
            type="file"
            accept={ACCEPTED_TYPES.join(',')}
            capture="environment"
            onChange={onFileChange}
            className="hidden"
            data-testid="avatar-dialog-file-input"
          />
        </div>

        {/* Footer actions */}
        <div className="px-5 py-4 border-t border-slate-100 bg-slate-50 flex flex-wrap items-center justify-between gap-2">
          <div>
            {hasExistingPhoto && (
              <Button
                type="button"
                variant="outline"
                onClick={handleRemove}
                disabled={busy}
                className="text-rose-600 border-rose-200 hover:bg-rose-50"
                data-testid="avatar-dialog-remove-btn"
              >
                <Trash2 className="w-3.5 h-3.5 mr-1.5" /> Remove
              </Button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              disabled={busy}
              data-testid="avatar-dialog-cancel-btn"
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleSave}
              disabled={!pendingFile || busy}
              className="bg-[#063c88] hover:bg-[#04306d]"
              data-testid="avatar-dialog-save-btn"
            >
              {busy ? (
                <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Uploading…</>
              ) : (
                <><UploadIcon className="w-3.5 h-3.5 mr-1.5" /> {hasExistingPhoto ? 'Replace' : 'Upload'}</>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AvatarUploadDialog;
