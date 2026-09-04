import React, { useState } from 'react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Pencil, Trash2, Eye, RotateCcw, MessageSquare } from 'lucide-react';
import { fmtDate, fmtDateTime, fmtTime } from './format';

const VALIDITY_LABEL = { valid: 'Valid Leave', invalid: 'Invalid Leave' };

export const EXPANDABLE = new Set(['P02', 'P04', 'P05', 'P06', 'N01', 'N02', 'N03', 'N04', 'N05', 'N06', 'N07', 'N08']);
// criteria whose parent value is the aggregate of individually editable children
export const CHILD_EDITABLE = new Set(['P05', 'P06', 'N01', 'N02', 'N04', 'N05']);

const star = (v) => (v > 0 ? `+${v}` : `${v ?? 0}`);
const dash = (v) => (v === null || v === undefined || v === '' ? '--' : v);
const stamp = (v) => fmtDateTime(v);

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

const INFO_HEADERS = {
  P02: ['Week', 'Date Range', 'Star'],
  P04: ['Week', 'Date Range', 'Star'],
  P05: ['Week', 'Date Range', 'Eligible Days', 'Total Research Hours', 'Average Research Hours'],
  N04: ['Week', 'Date Range', 'Eligible Days', 'Total Research Hours', 'Average Research Hours'],
  P06: ['Date', 'Holiday Type', 'Work'],
  N01: ['Leave Date', 'Leave Type', 'Duration', 'Applied Date', 'Applied Time', 'Leave Validity', 'Notes'],
  N02: ['Leave Date', 'Duration', 'Notified At', 'Violation'],
  N03: ['Emergency Leave Date', 'Duration', 'Equivalent'],
  N05: ['Sequence', 'Days', 'Leave Types', 'Proof Uploaded'],
  N06: ['Date', 'Source', 'Type', 'Duration', 'Equivalent'],
  N07: ['Date', 'Time', 'Remarks', 'Star', 'Added By', 'Actions'],
  N08: ['Date', 'Time', 'Remarks', 'Star', 'Added By', 'Actions'],
};

const EDIT_HEADERS = ['System Star', 'Override', 'Final Star', 'Status', 'Action'];

const infoCells = (code, r, onReason) => {
  switch (code) {
    case 'P02':
    case 'P04':
      return [`Week ${r.week}`, `${r.start} → ${r.end}`, star(r.value)];
    case 'P05':
    case 'N04':
      return [`Week ${r.week}`, `${fmtDate(r.start)} → ${fmtDate(r.end)}`, r.eligible_days,
        dash(r.total_hhmm), dash(r.avg_hhmm)];
    case 'P06':
      return [fmtDate(r.date), r.kind, r.work];
    case 'N01':
      return [fmtDate(r.date), dash(r.leave_type), dash(r.split),
        fmtDate(r.applied_at), fmtTime(String(r.applied_at || '').slice(11)),
        VALIDITY_LABEL[r.leave_validity] || 'Not Set',
        <NoteButtons key="n" row={r} onOpen={onReason} />];
    case 'N02':
      return [fmtDate(r.date), dash(r.split), stamp(r.applied_at), r.reason];
    case 'N03':
      return [fmtDate(r.date), dash(r.split), r.equivalent];
    case 'N05':
      return [`${fmtDate(r.start)} → ${fmtDate(r.end)}`, r.days, (r.leave_types || []).join(', ') || '--',
        r.proof_uploaded ? 'Yes' : 'No'];
    case 'N06':
      return [fmtDate(r.date), dash(r.source), dash(r.leave_type), dash(r.duration), r.equivalent];
    default:
      return [JSON.stringify(r)];
  }
};

const NoteButtons = ({ row, onOpen }) => {
  const hasReason = !!(row.leave_reason || '').trim();
  const hasRemark = !!(row.approval_remark || '').trim();
  return (
    <div className="flex gap-0.5">
      <Button size="sm" variant="ghost" disabled={!hasReason} className="h-7 px-2"
        title={hasReason ? 'View employee leave reason' : 'No leave reason provided'}
        onClick={() => hasReason && onOpen(row)} data-testid={`brsf-reason-${row.key}`}>
        <Eye className={`w-3.5 h-3.5 ${hasReason ? 'text-slate-600' : 'text-slate-300'}`} />
      </Button>
      {hasRemark && (
        <Button size="sm" variant="ghost" className="h-7 px-2" title={row.approval_remark}
          onClick={() => onOpen(row)} data-testid={`brsf-remark-${row.key}`}>
          <MessageSquare className="w-3.5 h-3.5 text-amber-600" />
        </Button>
      )}
    </div>
  );
};

const childStatus = (code, r) => {
  if (r.override !== null && r.override !== undefined) return 'Overridden';
  if (r.applicable === false) return 'Not Applicable';
  if ((code === 'P05' || code === 'N04') && r.eligible_days === 0) return 'No Data';
  return 'Auto';
};

const STATUS_STYLE = {
  Overridden: 'bg-amber-100 text-amber-700 border-amber-200',
  Auto: 'bg-blue-50 text-blue-700 border-blue-200',
  'No Data': 'bg-slate-100 text-slate-500 border-slate-200',
  'Not Applicable': 'bg-slate-100 text-slate-500 border-slate-200',
};

export const BrsfChildTable = ({ line, rows, canEdit, onEditChild, onResetChild,
                                 onEditInstance, onDeleteInstance }) => {
  const [reason, setReason] = useState(null);
  const editable = CHILD_EDITABLE.has(line.code);
  const headers = [...(INFO_HEADERS[line.code] || ['Detail']), ...(editable ? EDIT_HEADERS : [])];
  if (!rows.length) return <p className="text-sm text-slate-500">No records for this criteria in the selected month.</p>;

  return (
    <>
      <table className="w-full text-xs" data-testid={`brsf-child-table-${line.code}`}>
        <thead>
          <tr className="text-left text-slate-500 uppercase tracking-wide">
            {headers.map((h) => <th key={h} className="px-2 py-1.5 font-medium">{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            if (['N07', 'N08'].includes(line.code)) {
              return (
                <tr key={r.id || i} className="border-t border-slate-200/70 text-slate-700" data-testid={`brsf-child-${line.code}-${i}`}>
                  {[fmtDate(r.date), fmtTime(r.time), dash(r.remarks), star(r.value), dash(r.created_by)].map((c, j) => (
                    <td key={j} className="px-2 py-1.5 align-top">{c}</td>
                  ))}
                  <td className="px-2 py-1.5">
                    <div className="flex gap-1">
                      <Button size="sm" variant="ghost" className="h-7 px-2" disabled={!canEdit}
                        onClick={() => onEditInstance(r)} data-testid={`brsf-edit-instance-${line.code}-${i}`}>
                        <Pencil className="w-3 h-3" />
                      </Button>
                      <Button size="sm" variant="ghost" className="h-7 px-2 text-rose-600" disabled={!canEdit}
                        onClick={() => onDeleteInstance(r)} data-testid={`brsf-delete-instance-${line.code}-${i}`}>
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </div>
                  </td>
                </tr>
              );
            }
            const status = childStatus(line.code, r);
            return (
              <tr key={r.key || i} className="border-t border-slate-200/70 text-slate-700" data-testid={`brsf-child-${line.code}-${i}`}>
                {infoCells(line.code, r, setReason).map((c, j) => (
                  <td key={j} className="px-2 py-1.5 align-top">{c}</td>
                ))}
                {editable && (
                  <>
                    <td className="px-2 py-1.5 number-display">{star(r.system_value ?? r.value)}</td>
                    <td className="px-2 py-1.5 number-display">
                      {r.override === null || r.override === undefined ? '--' : star(r.override)}
                    </td>
                    <td className={`px-2 py-1.5 number-display font-semibold ${(r.final ?? r.value) > 0 ? 'text-emerald-600' : (r.final ?? r.value) < 0 ? 'text-rose-600' : 'text-slate-400'}`}
                      data-testid={`brsf-child-final-${line.code}-${i}`}>
                      {star(r.final ?? r.value)}
                    </td>
                    <td className="px-2 py-1.5">
                      <Badge variant="outline" className={`text-[10px] ${STATUS_STYLE[status]}`}
                        data-testid={`brsf-child-status-${line.code}-${i}`}>{status}</Badge>
                      {r.capped && <span className="block text-[10px] text-slate-400">monthly cap reached</span>}
                    </td>
                    <td className="px-2 py-1.5">
                      <div className="flex gap-1">
                        <Button size="sm" variant="ghost" className="h-7 px-2" title="Edit this record"
                          disabled={!canEdit || r.applicable === false}
                          onClick={() => onEditChild(r)} data-testid={`brsf-child-edit-${line.code}-${i}`}>
                          <Pencil className="w-3 h-3" />
                        </Button>
                        {r.override !== null && r.override !== undefined && (
                          <Button size="sm" variant="ghost" className="h-7 px-2" title="Reset to system value"
                            disabled={!canEdit} onClick={() => onResetChild(r)}
                            data-testid={`brsf-child-reset-${line.code}-${i}`}>
                            <RotateCcw className="w-3 h-3" />
                          </Button>
                        )}
                      </div>
                    </td>
                  </>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>

      <Dialog open={!!reason} onOpenChange={(v) => !v && setReason(null)}>
        <DialogContent className="max-w-md" data-testid="brsf-reason-dialog">
          <DialogHeader>
            <DialogTitle>Leave Details — {fmtDate(reason?.date)}</DialogTitle>
            <DialogDescription>
              {reason?.leave_type} · {reason?.split} · {VALIDITY_LABEL[reason?.leave_validity] || 'Validity Not Set'}
            </DialogDescription>
          </DialogHeader>
          {!!(reason?.leave_reason || '').trim() && (
            <div>
              <p className="text-xs font-semibold text-slate-500 mb-1">Employee leave reason</p>
              <p className="text-sm text-slate-700 whitespace-pre-wrap">{reason.leave_reason}</p>
            </div>
          )}
          {!!(reason?.approval_remark || '').trim() && (
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <p className="text-xs font-semibold text-slate-500 mb-1">Approval remark</p>
              <p className="text-sm text-slate-700 whitespace-pre-wrap">{reason.approval_remark}</p>
            </div>
          )}
          {reason?.reason && (
            <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
              <p className="text-xs font-semibold text-blue-700 mb-1">System decision</p>
              <p className="text-sm text-blue-900">{reason.reason}</p>
            </div>
          )}
          {reason?.override_note && (
            <div className="p-3 rounded-lg bg-amber-50 border border-amber-200">
              <p className="text-xs font-semibold text-amber-700 mb-1">Admin override note</p>
              <p className="text-sm text-amber-900">{reason.override_note}</p>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
};

export default BrsfChildTable;
