import React from 'react';

/**
 * EmployeeAvatar — shows the employee's profile photo if available,
 * otherwise falls back to the gradient initial-letter circle.
 *
 * Props:
 *   • employee     — { full_name?, name?, avatar?, avatar_url? }
 *   • name         — optional fallback name string
 *   • src          — optional explicit image URL (overrides employee.avatar)
 *   • size         — 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'photo-wall'
 *   • shape        — 'circle' | 'square' (default 'circle')
 *   • className    — extra Tailwind classes
 *   • testId       — data-testid forwarder
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
  name,
  src,
  size = 'md',
  shape = 'circle',
  className = '',
  testId,
}) => {
  const photoUrl = src || employee?.avatar || employee?.avatar_url || null;
  const displayName = name || employee?.full_name || employee?.name || '';
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
