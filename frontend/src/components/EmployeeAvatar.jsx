import React from 'react';
import { useAuth } from '../contexts/AuthContext';

/**
 * EmployeeAvatar — shows the employee's profile photo if available,
 * otherwise falls back to the gradient initial-letter circle.
 *
 * Resolution order for the image URL (first non-empty wins):
 *   1. `src` prop (explicit)
 *   2. `employee.avatar` / `employee.avatar_url`
 *   3. AuthContext.avatarMap[employeeId]   ← centralized cache used by
 *      all admin modules so any module showing `employee_id` gets the
 *      photo automatically once the employee uploads one.
 *
 * Implementation note (why CSS background-image instead of <img>):
 *   • CSS background images don't expose `alt` text — so a failing fetch
 *     never leaks the employee's name as black-on-white text into the
 *     avatar box (the previous "Praga V" bug).
 *   • CSS background images don't render a broken-image icon — if the
 *     URL fails or returns 404 (e.g. Cloudinary transformation cold-cache
 *     on the first request), the background is simply transparent and
 *     the gradient initial-letter underneath stays visible.
 *   • No load/error state tracking is required — eliminating the race
 *     condition where `onError` would lock the component into a state
 *     it could never recover from.
 *   • The browser caches background-image fetches the same way it caches
 *     <img> fetches, so the second request after a cold 404 succeeds
 *     automatically on the next paint.
 *
 * Props:
 *   • employee     — { full_name?, name?, avatar?, avatar_url?, id? }
 *   • employeeId   — explicit employee_id to look up in the avatar cache
 *   • name         — fallback display name (used for the initial)
 *   • src          — explicit image URL (overrides everything else)
 *   • size         — 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'photo-wall'
 *   • shape        — 'circle' | 'square'
 *   • className    — extra Tailwind classes
 *   • testId       — data-testid passthrough
 */
const SIZE_MAP = {
  xs: 'w-7 h-7 text-xs',
  sm: 'w-9 h-9 text-sm',
  md: 'w-12 h-12 text-base',
  lg: 'w-16 h-16 text-xl',
  xl: 'w-32 h-32 text-5xl',
  'photo-wall': 'w-24 h-24 text-2xl',
};

const SHAPE_MAP = {
  circle: 'rounded-full',
  square: 'rounded-2xl',
};

const EmployeeAvatar = ({
  employee,
  employeeId,
  name,
  src,
  size = 'md',
  shape = 'circle',
  className = '',
  testId,
}) => {
  const { getAvatarById } = useAuth() || {};
  const lookupId = employeeId || employee?.id || employee?.employee_id;
  const cachedAvatar = lookupId && getAvatarById ? getAvatarById(lookupId) : null;

  const resolvedUrl =
    src ||
    employee?.avatar ||
    employee?.avatar_url ||
    cachedAvatar ||
    null;

  const displayName =
    name || employee?.full_name || employee?.name || employee?.emp_name || '';
  const initial = (displayName || '?').charAt(0).toUpperCase();

  const sizeCls = SIZE_MAP[size] || SIZE_MAP.md;
  const shapeCls = SHAPE_MAP[shape] || SHAPE_MAP.circle;

  const base = `${sizeCls} ${shapeCls} flex-shrink-0 overflow-hidden flex items-center justify-center ${className}`;

  // Build the background-image style. We append a `?v=<urllen>` cache-buster
  // ONLY when the URL has no query string yet — this is a no-op for normal
  // Cloudinary URLs (which already carry a version segment like `/v17...`),
  // but it prevents stale browser caching if someone passes a parameterless
  // URL while testing.
  const bgStyle = resolvedUrl
    ? {
        backgroundImage: `url("${resolvedUrl}")`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
      }
    : undefined;

  return (
    <div
      className={`${base} relative bg-gradient-to-br from-[#063c88] to-[#0a5cba] shadow-md`}
      data-testid={testId}
    >
      {/* Initial-letter base layer — always rendered. The photo (if any)
          paints over this via CSS background-image. */}
      <span
        className="absolute inset-0 flex items-center justify-center text-white font-bold select-none pointer-events-none"
        style={{ fontFamily: 'Outfit' }}
        aria-hidden={resolvedUrl ? 'true' : 'false'}
      >
        {initial}
      </span>

      {/* Photo overlay via background-image — no <img>, no alt, no broken-
          image fallback, no opacity race. If the URL fails, the gradient
          + initial underneath remains visible. */}
      {resolvedUrl && (
        <div
          className="absolute inset-0"
          style={bgStyle}
          role="img"
          aria-label={displayName ? `Profile photo of ${displayName}` : 'Profile photo'}
        />
      )}
    </div>
  );
};

export default EmployeeAvatar;
