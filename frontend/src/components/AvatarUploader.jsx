import React, { useRef, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Camera, Loader2, X } from 'lucide-react';
import EmployeeAvatar from './EmployeeAvatar';
import { useAuth } from '../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ACCEPTED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
const MAX_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB

/**
 * AvatarUploader — wraps EmployeeAvatar and adds:
 *   • camera-icon overlay (click to open file picker)
 *   • upload progress spinner
 *   • optional "remove photo" affordance
 *
 * Props:
 *   • employee       — current employee object { id, full_name, avatar, avatar_public_id, ... }
 *   • mode           — 'self' (uses /employee/me/avatar) | 'admin' (uses /employees/{id}/avatar)
 *   • onUpdated      — callback(updatedEmployee) after successful save
 *   • token          — JWT
 *   • size           — passed to EmployeeAvatar
 *   • shape          — 'circle' | 'square'
 *   • canRemove      — show 'X' to clear photo (only meaningful in 'self' mode for now)
 *   • testIdPrefix   — namespace for data-testids
 */
const AvatarUploader = ({
  employee,
  mode = 'self',
  onUpdated,
  token,
  size = 'xl',
  shape = 'square',
  canRemove = true,
  testIdPrefix = 'avatar',
}) => {
  const fileRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(null);
  const { refreshAvatars } = useAuth() || {};

  const authHeader = { Authorization: `Bearer ${token}` };

  const openPicker = () => {
    if (busy) return;
    fileRef.current?.click();
  };

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;

    if (!ACCEPTED_TYPES.includes(file.type)) {
      toast.error('Unsupported format. Please use JPG, PNG, or WebP.');
      return;
    }
    if (file.size > MAX_SIZE_BYTES) {
      toast.error('File too large. Maximum size is 5 MB.');
      return;
    }

    // Local preview while uploading
    const localUrl = URL.createObjectURL(file);
    setPreview(localUrl);
    setBusy(true);
    try {
      // 1) Cloudinary signature
      const sigResp = await axios.get(`${API}/cloudinary/signature?folder=avatars`, { headers: authHeader });
      const { signature, timestamp, cloud_name, api_key, folder, type } = sigResp.data;

      // 2) Upload to Cloudinary
      const fd = new FormData();
      fd.append('file', file);
      fd.append('signature', signature);
      fd.append('timestamp', timestamp);
      fd.append('api_key', api_key);
      fd.append('folder', folder);
      if (type) fd.append('type', type);

      const cloudResp = await axios.post(
        `https://api.cloudinary.com/v1_1/${cloud_name}/auto/upload`,
        fd
      );
      const fullUrl = cloudResp.data.secure_url;
      const publicId = cloudResp.data.public_id;

      // Auto-resize via Cloudinary URL transformation (512x512, smart-crop on faces, web-optimized).
      // Insert transformation segment right after `/upload/`.
      const transformed = fullUrl.includes('/upload/')
        ? fullUrl.replace('/upload/', '/upload/c_fill,g_face,w_512,h_512,q_auto,f_auto/')
        : fullUrl;

      // 3) Persist on backend
      const endpoint =
        mode === 'self'
          ? `${API}/employee/me/avatar`
          : `${API}/employees/${employee?.id}/avatar`;

      const saveResp = await axios.put(
        endpoint,
        { avatar_url: transformed, avatar_public_id: publicId },
        { headers: authHeader }
      );

      toast.success('Profile photo updated');
      setPreview(null);
      onUpdated?.(saveResp.data);
      // Refresh the centralized avatar cache so EVERY admin module
      // (Attendance, Leave, Verification, Reports, etc.) reflects the
      // change without a page reload.
      refreshAvatars?.();
    } catch (err) {
      console.error('Avatar upload error:', err);
      toast.error(err.response?.data?.detail || 'Failed to upload photo');
      setPreview(null);
    } finally {
      setBusy(false);
      URL.revokeObjectURL(localUrl);
    }
  };

  const handleRemove = async () => {
    if (busy) return;
    if (!employee?.avatar) return;
    if (!window.confirm('Remove your profile photo?')) return;
    setBusy(true);
    try {
      const endpoint =
        mode === 'self'
          ? `${API}/employee/me/avatar`
          : `${API}/employees/${employee?.id}/avatar`;

      if (mode === 'self') {
        const resp = await axios.delete(endpoint, { headers: authHeader });
        if (resp.data?.success) {
          // Fetch fresh profile to propagate
          const me = await axios.get(`${API}/employee/profile`, { headers: authHeader });
          onUpdated?.(me.data);
        }
      } else {
        // Admin mode: send empty avatar via PUT
        const resp = await axios.put(
          endpoint,
          { avatar_url: '', avatar_public_id: null },
          { headers: authHeader }
        );
        onUpdated?.(resp.data);
      }
      toast.success('Profile photo removed');
      refreshAvatars?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to remove photo');
    } finally {
      setBusy(false);
    }
  };

  // Build a transient "preview" employee so EmployeeAvatar can show local file
  // immediately while the upload is in flight.
  const previewEmployee = preview
    ? { ...(employee || {}), avatar: preview }
    : employee;

  return (
    <div className="relative inline-block group" data-testid={`${testIdPrefix}-wrapper`}>
      <EmployeeAvatar
        employee={previewEmployee}
        size={size}
        shape={shape}
        className={busy ? 'opacity-70' : ''}
        testId={`${testIdPrefix}-image`}
      />

      {/* Camera overlay button */}
      <button
        type="button"
        onClick={openPicker}
        disabled={busy}
        data-testid={`${testIdPrefix}-upload-btn`}
        className="absolute bottom-1 right-1 w-9 h-9 rounded-full bg-white shadow-lg ring-1 ring-slate-200 flex items-center justify-center hover:bg-[#063c88] hover:text-white transition disabled:opacity-50 disabled:cursor-not-allowed"
        title="Change photo"
        aria-label="Change photo"
      >
        {busy ? (
          <Loader2 className="w-4 h-4 animate-spin text-[#063c88] group-hover:text-white" />
        ) : (
          <Camera className="w-4 h-4 text-[#063c88] group-hover:text-white" />
        )}
      </button>

      {/* Remove button (only when avatar present and allowed) */}
      {canRemove && employee?.avatar && !busy && (
        <button
          type="button"
          onClick={handleRemove}
          data-testid={`${testIdPrefix}-remove-btn`}
          className="absolute top-1 right-1 w-7 h-7 rounded-full bg-white shadow ring-1 ring-slate-200 flex items-center justify-center hover:bg-red-50 hover:text-red-600 transition opacity-0 group-hover:opacity-100"
          title="Remove photo"
          aria-label="Remove photo"
        >
          <X className="w-3.5 h-3.5 text-slate-500 hover:text-red-600" />
        </button>
      )}

      <input
        ref={fileRef}
        type="file"
        accept={ACCEPTED_TYPES.join(',')}
        onChange={handleFile}
        className="hidden"
        data-testid={`${testIdPrefix}-file-input`}
      />
    </div>
  );
};

export default AvatarUploader;
