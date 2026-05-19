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

  const photoUrl =
    src ||
    employee?.avatar ||
    employee?.avatar_url ||
    cachedAvatar ||
    null;

  const displayName = name || employee?.full_name || employee?.name || employee?.emp_name || '';
  const initial = (displayName || '?').charAt(0).toUpperCase();

  const sizeCls = SIZE_MAP[size] || SIZE_MAP.md;
  const shapeCls = SHAPE_MAP[shape] || SHAPE_MAP.circle;

  const base = `${sizeCls} ${shapeCls} flex-shrink-0 overflow-hidden flex items-center justify-center ${className}`;

  if (photoUrl) {
    return (
      <div
        className={`${base} bg-slate-100 ring-1 ring-slate-200`}
        data-testid={testId}
      >
        <img
          src={photoUrl}
          alt={displayName || 'Profile photo'}
          className="w-full h-full object-cover"
          loading="lazy"
          onError={(e) => {
            // Hide broken image — parent gradient fallback would require a re-render,
            // so we just swap to a neutral background.
            e.currentTarget.style.display = 'none';
          }}
        />
      </div>
    );
  }

  return (
    <div
      className={`${base} bg-gradient-to-br from-[#063c88] to-[#0a5cba] shadow-md`}
      data-testid={testId}
    >
      <span className="text-white font-bold select-none" style={{ fontFamily: 'Outfit' }}>
        {initial}
      </span>
    </div>
  );
};

export default EmployeeAvatar;
