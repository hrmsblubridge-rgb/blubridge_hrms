import React from 'react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Pencil, Trash2 } from 'lucide-react';

export const EXPANDABLE = new Set(['P02', 'P04', 'P05', 'P06', 'N01', 'N02', 'N03', 'N04', 'N05', 'N06', 'N07', 'N08']);

const star = (v) => (v > 0 ? `+${v}` : `${v ?? 0}`);
const dash = (v) => (v === null || v === undefined || v === '' ? '--' : v);

// Child rows come from the automated calculation, the manual instances, or the
// weekly manual entry (P02 / P04 in weekly mode).
export const childRowsFor = (line, weeks) => {
  if (['N07', 'N08'].includes(line.code)) return line.instances || [];
  if (['P02', 'P04'].includes(line.code)) {
    if (line.entry_mode !== 'weekly') return [];
    return weeks.map((w) => {
      const e = (line.weekly || []).find((x) => x.week === w.week);
      return { ...w, value: e ? Number(e.value) || 0 : 0 };
    });
  }
  return line.system_children || [];
};

const HEADERS = {
  P02: ['Week', 'Date Range', 'Star'],
  P04: ['Week', 'Date Range', 'Star'],
  P05: ['Week', 'Date Range', 'Eligible Days', 'Total Research Hours', 'Average Research Hours', 'System Star'],
  N04: ['Week', 'Date Range', 'Eligible Days', 'Total Research Hours', 'Average Research Hours', 'System Star'],
  P06: ['Date', 'Holiday Type', 'Work', 'System Star'],
  N01: ['Leave Date', 'Leave Type', 'Split', 'Applied At', 'Violation', 'System Star'],
  N02: ['Leave Date', 'Split', 'Notified At', 'Violation', 'System Star'],
  N03: ['Emergency Leave Date', 'Split', 'Counted'],
  N05: ['Sequence', 'Days', 'Leave Types', 'Proof Uploaded', 'System Star'],
  N06: ['Date', 'Status', 'Absence Equivalent', 'Counted'],
  N07: ['Date', 'Time', 'Remarks', 'Star', 'Added By', 'Actions'],
  N08: ['Date', 'Time', 'Remarks', 'Star', 'Added By', 'Actions'],
};

const cells = (code, r, actions) => {
  switch (code) {
    case 'P02':
    case 'P04':
      return [`Week ${r.week}`, `${r.start} → ${r.end}`, star(r.value)];
    case 'P05':
    case 'N04':
      return [`Week ${r.week}`, `${r.start} → ${r.end}`, r.eligible_days,
        dash(r.total_hhmm), dash(r.avg_hhmm),
        <span key="s">{star(r.value)}{r.capped && <Badge variant="outline" className="ml-2 text-[10px] bg-slate-100">monthly cap reached</Badge>}</span>];
    case 'P06':
      return [r.date, r.kind, r.work, star(r.value)];
    case 'N01':
      return [r.date, dash(r.leave_type), dash(r.split), dash(String(r.applied_at || '').slice(0, 16).replace('T', ' ')), r.reason, star(r.value)];
    case 'N02':
      return [r.date, dash(r.split), dash(String(r.applied_at || '').slice(0, 16).replace('T', ' ')), r.reason, star(r.value)];
    case 'N03':
      return [r.date, dash(r.split), 'Yes'];
    case 'N05':
      return [`${r.start} → ${r.end}`, r.days, (r.leave_types || []).join(', ') || '--',
        r.proof_uploaded ? 'Yes' : 'No', star(r.value)];
    case 'N06':
      return [r.date, r.status, r.equivalent, 'Yes'];
    case 'N07':
    case 'N08':
      return [dash(r.date), dash(r.time), dash(r.remarks), star(r.value), dash(r.created_by), actions];
    default:
      return [JSON.stringify(r)];
  }
};

export const BrsfChildTable = ({ line, rows, onEditInstance, onDeleteInstance }) => {
  const headers = HEADERS[line.code] || ['Detail'];
  if (!rows.length) return <p className="text-sm text-slate-500">No records for this criteria in the selected month.</p>;
  return (
    <table className="w-full text-xs" data-testid={`brsf-child-table-${line.code}`}>
      <thead>
        <tr className="text-left text-slate-500 uppercase tracking-wide">
          {headers.map((h) => <th key={h} className="px-2 py-1.5 font-medium">{h}</th>)}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => {
          const actions = ['N07', 'N08'].includes(line.code) ? (
            <div key="a" className="flex gap-1">
              <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => onEditInstance(r)} data-testid={`brsf-edit-instance-${line.code}-${i}`}>
                <Pencil className="w-3 h-3" />
              </Button>
              <Button size="sm" variant="ghost" className="h-7 px-2 text-rose-600" onClick={() => onDeleteInstance(r)} data-testid={`brsf-delete-instance-${line.code}-${i}`}>
                <Trash2 className="w-3 h-3" />
              </Button>
            </div>
          ) : null;
          return (
            <tr key={r.id || i} className="border-t border-slate-200/70 text-slate-700" data-testid={`brsf-child-${line.code}-${i}`}>
              {cells(line.code, r, actions).map((c, j) => (
                <td key={j} className="px-2 py-1.5 align-top">{c}</td>
              ))}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
};

export default BrsfChildTable;
