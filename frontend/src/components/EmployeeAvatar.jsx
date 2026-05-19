import React, { useState, useEffect } from 'react';
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
 * If the resolved image FAILS to load in the browser (broken URL, CORS,
 * network error, etc.) we automatically fall back to the gradient
 * initial-letter circle — never an empty container.
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

  // Track whether the <img> failed to load. If it did, we render the
  // gradient initial-letter fallback instead of leaving an empty circle.
  const [hasError, setHasError] = useState(false);
  useEffect(() => {
    // Reset the error flag if the URL itself changes — e.g. when the user
    // uploads a new photo and the cache refreshes.
    setHasError(false);
  }, [resolvedUrl]);

  const displayName =
    name || employee?.full_name || employee?.name || employee?.emp_name || '';
  const initial = (displayName || '?').charAt(0).toUpperCase();

  const sizeCls = SIZE_MAP[size] || SIZE_MAP.md;
  const shapeCls = SHAPE_MAP[shape] || SHAPE_MAP.circle;

  const base = `${sizeCls} ${shapeCls} flex-shrink-0 overflow-hidden flex items-center justify-center ${className}`;

  const showPhoto = !!resolvedUrl && !hasError;

  // Render strategy: ALWAYS draw the gradient initial-letter as the base
  // layer, then overlay the <img> on top once we have a URL. This way:
  //   • If the photo is still loading, the user sees the initial — not
  //     an empty grey circle.
  //   • If the photo's background is white/transparent (common for ID
  //     headshots), the surrounding initial layer is hidden by the
  //     image but the photo content is unaffected.
  //   • If the photo URL is broken, `onError` sets hasError → the img is
  //     removed and the initial layer remains visible.
  return (
    <div
      className={`${base} relative bg-gradient-to-br from-[#063c88] to-[#0a5cba] shadow-md`}
      data-testid={testId}
    >
      {/* Initial-letter base layer — always rendered */}
      <span
        className="absolute inset-0 flex items-center justify-center text-white font-bold select-none pointer-events-none"
        style={{ fontFamily: 'Outfit' }}
        aria-hidden={showPhoto ? 'true' : 'false'}
      >
        {initial}
      </span>

      {/* Photo overlay — covers the initial when loaded */}
      {showPhoto && (
        <img
          src={resolvedUrl}
          alt={displayName || 'Profile photo'}
          className="absolute inset-0 w-full h-full object-cover"
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setHasError(true)}
        />
      )}
    </div>
  );
};

export default EmployeeAvatar;
