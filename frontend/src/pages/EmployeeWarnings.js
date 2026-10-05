import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { toast } from 'sonner';
import { AlertTriangle, ShieldAlert, XOctagon, CheckCircle2, FileText, Info } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const LEVEL_META = {
  first:       { label: 'Warning Notice 1',   icon: AlertTriangle, cls: 'bg-amber-50 text-amber-800 border-amber-200',   dot: 'bg-amber-500' },
  final:       { label: 'Final Warning',       icon: ShieldAlert,   cls: 'bg-orange-50 text-orange-800 border-orange-200', dot: 'bg-orange-500' },
  termination: { label: 'Termination Action',  icon: XOctagon,      cls: 'bg-red-50 text-red-800 border-red-200',           dot: 'bg-red-500' },
};
const STATUS_META = {
  sent: 'Sent', awaiting_ack: 'Awaiting Your Acknowledgement', acknowledged: 'Acknowledged',
  response_received: 'Response Submitted', under_review: 'Under Review', closed: 'Closed',
  revoked: 'Revoked', email_failed: 'Delivery Issue', issued: 'Issued',
};

const StatusPill = ({ status }) => {
  const cls = {
    sent: 'bg-indigo-100 text-indigo-800',
    awaiting_ack: 'bg-amber-100 text-amber-800',
    acknowledged: 'bg-emerald-100 text-emerald-800',
    response_received: 'bg-cyan-100 text-cyan-800',
    under_review: 'bg-blue-100 text-blue-800',
    closed: 'bg-slate-100 text-slate-700',
    revoked: 'bg-slate-200 text-slate-700 line-through',
    email_failed: 'bg-rose-100 text-rose-800',
    issued: 'bg-indigo-100 text-indigo-800',
  }[status] || 'bg-slate-100 text-slate-700';
  return <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${cls}`}>{STATUS_META[status] || status}</span>;
};

export default function EmployeeWarnings() {
  const { token } = useAuth();
  const H = { Authorization: `Bearer ${token}` };
  const [warnings, setWarnings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openId, setOpenId] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/employee/warnings/me`, { headers: H });
      setWarnings(r.data.warnings || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load warnings');
    } finally { setLoading(false); }
  }, [token]); // eslint-disable-line

  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6" data-testid="employee-warnings-page">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">My Warnings</h1>
        <p className="text-sm text-slate-500 mt-1">Warnings issued to you under the Leave and Attendance Policy Non-Compliance Framework.</p>
      </div>

      {/* Info banner */}
      <Card className="p-4 rounded-2xl border-blue-100 bg-blue-50/60">
        <div className="flex gap-3">
          <Info className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
          <div className="text-sm text-slate-700">
            If a warning is <b>awaiting acknowledgement</b>, please open it and click <b>Acknowledge</b> to confirm receipt. You may also submit a written response. All actions are logged.
          </div>
        </div>
      </Card>

      {loading ? (
        <Card className="p-10 rounded-2xl text-center text-slate-500">Loading…</Card>
      ) : warnings.length === 0 ? (
        <Card className="p-12 rounded-2xl text-center border-slate-200" data-testid="no-warnings-state">
          <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto" />
          <p className="mt-3 text-slate-800 font-semibold">You have no warning records.</p>
          <p className="text-sm text-slate-500 mt-1">Keep following the Leave and Attendance Policy to maintain a clean record.</p>
        </Card>
      ) : (
        <div className="space-y-3">
          {warnings.map(w => {
            const meta = LEVEL_META[w.warning_level] || {};
            const Icon = meta.icon || AlertTriangle;
            const requiresAck = ['sent', 'awaiting_ack', 'email_failed'].includes(w.status);
            return (
              <Card key={w.id} className={`p-4 rounded-2xl border ${requiresAck ? 'border-amber-300 shadow-sm' : 'border-slate-200'}`} data-testid={`warning-card-${w.id}`}>
                <div className="flex items-start gap-4 flex-wrap">
                  <div className={`p-2.5 rounded-xl ${meta.cls}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-[220px]">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${meta.cls}`}>{meta.label}</span>
                      <StatusPill status={w.status} />
                      {requiresAck && <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500 text-white animate-pulse">Action Required</span>}
                    </div>
                    <div className="mt-1.5 text-[13px] text-slate-700">
                      <span className="font-medium">Ref:</span> <span className="font-mono">{w.warning_reference || '—'}</span>
                      <span className="mx-2 text-slate-300">·</span>
                      <span className="font-medium">Incident:</span> {w.incident_date}
                      {w.acknowledgement_due_date && <>
                        <span className="mx-2 text-slate-300">·</span>
                        <span className="font-medium">Ack due:</span> {w.acknowledgement_due_date}
                      </>}
                    </div>
                    <p className="mt-2 text-sm text-slate-600 line-clamp-2">{w.incident_description}</p>
                  </div>
                  <Button variant="outline" className="rounded-lg" onClick={() => setOpenId(w.id)} data-testid={`view-my-warning-${w.id}`}>
                    <FileText className="w-4 h-4 mr-1.5" />View
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {openId && <MyWarningDetail id={openId} onClose={() => setOpenId(null)} onChanged={load} />}
    </div>
  );
}

function MyWarningDetail({ id, onClose, onChanged }) {
  const { token } = useAuth();
  const H = { Authorization: `Bearer ${token}` };
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showRespond, setShowRespond] = useState(false);
  const [responseText, setResponseText] = useState('');
  const [ackComment, setAckComment] = useState('');

  const load = useCallback(async () => {
    try { const r = await axios.get(`${API}/warnings/${id}`, { headers: H }); setData(r.data); }
    catch (e) { toast.error(e?.response?.data?.detail || 'Load failed'); onClose(); }
  }, [id]); // eslint-disable-line
  useEffect(() => { load(); }, [load]);

  const acknowledge = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/warnings/${id}/acknowledge`, { comment: ackComment || undefined }, { headers: H });
      toast.success('Warning acknowledged');
      await load(); onChanged();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); }
    finally { setBusy(false); }
  };

  const submitResponse = async () => {
    if (!responseText.trim()) return toast.error('Please write your response');
    setBusy(true);
    try {
      await axios.post(`${API}/warnings/${id}/respond`, { response_text: responseText }, { headers: H });
      toast.success('Response submitted');
      setShowRespond(false); setResponseText('');
      await load(); onChanged();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); }
    finally { setBusy(false); }
  };

  if (!data) return null;
  const meta = LEVEL_META[data.warning_level] || {};
  const canAck = ['sent', 'awaiting_ack', 'email_failed'].includes(data.status);
  const canRespond = ['sent', 'awaiting_ack', 'acknowledged', 'email_failed'].includes(data.status);

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="my-warning-detail">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 flex-wrap">
            Warning ·
            <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${meta.cls}`}>{meta.label}</span>
            <StatusPill status={data.status} />
          </DialogTitle>
        </DialogHeader>
        <div className="text-sm space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div><div className="text-xs text-slate-500">Reference</div><div className="font-mono font-medium">{data.warning_reference || '—'}</div></div>
            <div><div className="text-xs text-slate-500">Issue Date</div><div className="font-medium">{data.warning_issue_date || '—'}</div></div>
            <div><div className="text-xs text-slate-500">Incident Date</div><div className="font-medium">{data.incident_date}</div></div>
            <div><div className="text-xs text-slate-500">Category</div><div className="font-medium capitalize">{(data.incident_category || '').replace(/_/g, ' ')}</div></div>
            <div><div className="text-xs text-slate-500">Ack Due</div><div className="font-medium">{data.acknowledgement_due_date || '—'}</div></div>
            <div><div className="text-xs text-slate-500">Issued By</div><div className="font-medium">{data.approved_by_name || data.created_by_name || '—'}</div></div>
          </div>

          <div>
            <div className="text-xs text-slate-500">Details of Non-Compliance</div>
            <div className="mt-1 p-3 bg-slate-50 rounded-lg whitespace-pre-wrap">{data.incident_description}</div>
          </div>
          {data.corrective_action && (
            <div>
              <div className="text-xs text-slate-500">Required Corrective Action</div>
              <div className="mt-1 p-3 bg-amber-50 rounded-lg whitespace-pre-wrap">{data.corrective_action}</div>
            </div>
          )}
          {data.response_text && (
            <div>
              <div className="text-xs text-slate-500">Your Response</div>
              <div className="mt-1 p-3 bg-cyan-50 rounded-lg whitespace-pre-wrap">{data.response_text}</div>
              <div className="text-[11px] text-slate-500 mt-1">Submitted {data.response_submitted_at ? new Date(data.response_submitted_at).toLocaleString('en-IN') : ''}</div>
            </div>
          )}

          {/* Actions */}
          {canAck && (
            <div className="border-t pt-4">
              <div className="text-sm font-semibold text-slate-700 mb-2">Acknowledge Receipt</div>
              <textarea
                className="w-full rounded-lg border border-slate-300 p-2 text-sm"
                rows={2}
                placeholder="Optional comment (visible to HR)"
                value={ackComment}
                onChange={e => setAckComment(e.target.value)}
                data-testid="ack-comment-input"
              />
              <Button className="mt-2 rounded-lg bg-emerald-600 hover:bg-emerald-700" disabled={busy} onClick={acknowledge} data-testid="ack-btn">
                <CheckCircle2 className="w-4 h-4 mr-1.5" />I Acknowledge Receipt of this Warning
              </Button>
            </div>
          )}

          {canRespond && (
            <div className="border-t pt-4">
              {!showRespond ? (
                <Button variant="outline" className="rounded-lg" onClick={() => setShowRespond(true)} data-testid="show-respond-btn">
                  Submit a Written Response
                </Button>
              ) : (
                <div>
                  <div className="text-sm font-semibold text-slate-700 mb-2">Your Written Response</div>
                  <textarea
                    className="w-full rounded-lg border border-slate-300 p-2 text-sm"
                    rows={4}
                    placeholder="Explain the circumstances, present your side, or provide any relevant context…"
                    value={responseText}
                    onChange={e => setResponseText(e.target.value)}
                    data-testid="respond-text-input"
                  />
                  <div className="mt-2 flex gap-2">
                    <Button variant="outline" onClick={() => { setShowRespond(false); setResponseText(''); }}>Cancel</Button>
                    <Button className="bg-[#063c88] hover:bg-[#052e6b]" disabled={busy} onClick={submitResponse} data-testid="submit-response-btn">Submit Response</Button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Timeline */}
          <div className="border-t pt-4">
            <div className="text-sm font-semibold text-slate-700 mb-2">Timeline</div>
            <ol className="relative space-y-2 pl-5 border-l-2 border-slate-100">
              {(data.audit_log || []).slice().reverse().map(a => (
                <li key={a.id} className="relative">
                  <span className="absolute -left-[26px] top-1 w-3 h-3 rounded-full bg-[#063c88] ring-4 ring-white" />
                  <div className="text-xs text-slate-500">{new Date(a.created_at).toLocaleString('en-IN')}</div>
                  <div className="font-medium text-slate-800 capitalize">{(a.action || '').replace(/_/g, ' ')}</div>
                  {a.description && <div className="text-xs text-slate-600">{a.description}</div>}
                </li>
              ))}
            </ol>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
