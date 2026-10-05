/**
 * HRMS Feature Flags
 * ------------------
 * Reversible module enable/disable switches. Flipping a flag to `true`
 * re-enables the module everywhere (sidebar, routes, search) with NO code
 * changes required. No data, APIs, components or routes are deleted — only
 * their UI visibility/access is gated by these flags.
 */
export const FEATURE_FLAGS = {
  // Operational Setup (a.k.a. Operational Checklist) module.
  // Set to `true` to restore the sidebar item and route access.
  OPERATIONAL_SETUP_ENABLED: false,
};

export default FEATURE_FLAGS;
