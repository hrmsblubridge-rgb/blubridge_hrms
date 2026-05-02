import { useMemo, useState, useCallback } from 'react';
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';

/**
 * Centralized client-side sort utility for the HRMS premium tables.
 *
 * Usage:
 *   const { sortedRows, sortField, sortDir, toggleSort } = useTableSort(rows, 'emp_name');
 *
 *   <th><SortableTh field="emp_name" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Employee</SortableTh></th>
 *
 * Sort cycle on each column: asc → desc → none (default).
 *
 * Smart value coercion: numbers, dates (DD-MM-YYYY / YYYY-MM-DD / ISO), times
 * (HH:MM), and strings are all handled. Falsy/empty values always sort last.
 */

const DATE_DMY = /^\d{2}-\d{2}-\d{4}$/;
const DATE_YMD = /^\d{4}-\d{2}-\d{2}/;
const TIME_HM = /^\d{1,2}:\d{2}(:\d{2})?(\s?[AaPp][Mm])?$/;
const NUM = /^-?\d+(\.\d+)?$/;
const DUR = /^(\d+)h(?:\s*(\d+)m)?$/i;

const _coerce = (v) => {
  if (v === null || v === undefined || v === '' || v === '-') return null;
  if (typeof v === 'number') return v;
  if (v instanceof Date) return v.getTime();
  const s = String(v).trim();
  if (s === '' || s === '-') return null;
  if (NUM.test(s)) return parseFloat(s);
  if (DUR.test(s)) {
    const m = s.match(DUR);
    return parseInt(m[1], 10) * 60 + (m[2] ? parseInt(m[2], 10) : 0);
  }
  if (DATE_DMY.test(s)) {
    const [d, m, y] = s.split('-').map((x) => parseInt(x, 10));
    return new Date(y, m - 1, d).getTime();
  }
  if (DATE_YMD.test(s)) {
    const t = Date.parse(s);
    if (!Number.isNaN(t)) return t;
  }
  if (TIME_HM.test(s)) {
    let [hh, mm] = s.split(':');
    let h = parseInt(hh, 10);
    let m = parseInt(mm, 10);
    if (/pm/i.test(s) && h < 12) h += 12;
    if (/am/i.test(s) && h === 12) h = 0;
    return h * 60 + m;
  }
  return s.toLowerCase();
};

const _getField = (row, field) => {
  if (typeof field === 'function') return field(row);
  if (typeof field !== 'string') return undefined;
  if (field.indexOf('.') === -1) return row?.[field];
  return field.split('.').reduce((o, k) => (o == null ? undefined : o[k]), row);
};

const _compare = (a, b, dir) => {
  if (a === null && b === null) return 0;
  if (a === null) return 1; // empty always last
  if (b === null) return -1;
  if (typeof a === 'number' && typeof b === 'number') {
    return dir === 'asc' ? a - b : b - a;
  }
  const sa = String(a);
  const sb = String(b);
  return dir === 'asc' ? sa.localeCompare(sb) : sb.localeCompare(sa);
};

export function useTableSort(rows, defaultField = null, defaultDir = 'asc') {
  const [sortField, setSortField] = useState(defaultField);
  const [sortDir, setSortDir] = useState(defaultDir);

  // 3-state cycle per column:
  //   click 1 → ASC, click 2 → DESC, click 3 → reset (default order).
  // Switching to a different column always restarts the cycle at ASC.
  const toggleSort = useCallback((field) => {
    setSortField((prevField) => {
      if (prevField !== field) {
        setSortDir('asc');
        return field;
      }
      // Same column — advance the cycle synchronously
      let nextField = field;
      setSortDir((curDir) => {
        if (curDir === 'asc') return 'desc';
        // curDir === 'desc' → reset
        nextField = null;
        return 'asc';
      });
      return nextField;
    });
  }, []);

  const resetSort = useCallback(() => {
    setSortField(null);
    setSortDir('asc');
  }, []);

  // CRITICAL: when sortField is null we return the SAME `rows` reference (i.e.
  // the original order from the source dataset) — we never mutate `rows`.
  const sortedRows = useMemo(() => {
    if (!Array.isArray(rows) || !sortField) return rows;
    const copy = rows.slice();
    copy.sort((ra, rb) => _compare(_coerce(_getField(ra, sortField)), _coerce(_getField(rb, sortField)), sortDir));
    return copy;
  }, [rows, sortField, sortDir]);

  return { sortedRows, sortField, sortDir, toggleSort, resetSort, setSortField, setSortDir };
}

/**
 * Drop-in <th> with built-in sort indicators.
 * Use as:  <SortableTh field="emp_name" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Employee</SortableTh>
 */
export const SortableTh = ({ field, sortField, sortDir, onSort, className = '', children, testid, ...rest }) => {
  const active = sortField === field;
  const Icon = active ? (sortDir === 'asc' ? ChevronUp : ChevronDown) : ChevronsUpDown;
  return (
    <th
      {...rest}
      onClick={() => onSort && onSort(field)}
      data-testid={testid || `sortable-${field}`}
      className={`sortable ${active ? 'sort-active' : ''} ${className}`.trim()}
    >
      <span className="inline-flex items-center gap-1">
        {children}
        <Icon className={`w-3.5 h-3.5 ${active ? 'opacity-100' : 'opacity-40'}`} />
      </span>
    </th>
  );
};

export default useTableSort;
