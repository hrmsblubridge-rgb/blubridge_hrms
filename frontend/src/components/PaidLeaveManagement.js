import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Wallet, Sparkles, Download, Upload, History, Lock, CheckCircle2, AlertTriangle } from 'lucide-react';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Badge } from './ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from './ui/dialog';
import { Input } from './ui/input';
import { formatDate } from '../lib/dateFormat';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

export const PaidLeaveManagement = () => {
  const { getAuthHeaders } = useAuth();
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showGenerate, setShowGenerate] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [history, setHistory] = useState([]);
  const years = [now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1];

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/admin/paid-leave/status`, { headers: getAuthHeaders(), params: { year, month } });
      setStatus(r.data);
    } catch { setStatus(null); }
    finally { setLoading(false); }
  }, [getAuthHeaders, year, month]);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const handleGenerate = async () => {
    setActionLoading(true);
    try {
      const r = await axios.post(`${API}/admin/paid-leave/generate`, { year, month }, { headers: getAuthHeaders() });
      toast.success(r.data.message);
      setShowGenerate(false); fetchStatus();
    } catch (e) { toast.error(e.response?.data?.detail || 'Generate failed'); }
    finally { setActionLoading(false); }
  };

  const handleExport = async (fmt) => {
    try {
      const resp = await axios.get(`${API}/admin/paid-leave/export`, { headers: getAuthHeaders(), params: { year, month, format: fmt }, responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([resp.data]));
      const a = document.createElement('a');
      a.href = url; a.download = `paid_leave_${year}_${String(month).padStart(2, '0')}.${fmt === 'csv' ? 'csv' : 'xlsx'}`;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      toast.success('Export downloaded');
    } catch (e) { toast.error(e.response?.data?.detail || 'Export failed'); }
  };

  const handleImport = async () => {
    if (!importFile) { toast.error('Please select a .xlsx or .csv file'); return; }
    setActionLoading(true); setImportResult(null);
    try {
      const fd = new FormData();
      fd.append('file', importFile);
      const r = await axios.post(`${API}/admin/paid-leave/import?year=${year}&month=${month}`, fd, { headers: { ...getAuthHeaders(), 'Content-Type': 'multipart/form-data' } });
      setImportResult(r.data);
      if (r.data.success) { toast.success(r.data.message); fetchStatus(); }
      else toast.error(r.data.message || 'Import had validation errors');
    } catch (e) { toast.error(e.response?.data?.detail || 'Import failed'); }
    finally { setActionLoading(false); }
  };

  const openHistory = async () => {
    setShowHistory(true);
    try {
      const r = await axios.get(`${API}/admin/paid-leave/history`, { headers: getAuthHeaders(), params: { year, month } });
      setHistory(r.data);
    } catch { setHistory([]); }
  };

  const finalized = status?.finalized;

  return (
    <div className="p-6 space-y-6" data-testid="paid-leave-management">
      <div className="flex flex-col lg:flex-row lg:items-end gap-4">
        <div className="flex items-end gap-3">
          <div>
            <Label className="text-sm text-slate-600 mb-1.5 block font-medium">Month</Label>
            <Select value={String(month)} onValueChange={(v) => setMonth(Number(v))}>
              <SelectTrigger className="rounded-lg w-40" data-testid="pl-month-select"><SelectValue /></SelectTrigger>
              <SelectContent>{MONTHS.map((mn, i) => <SelectItem key={i} value={String(i + 1)}>{mn}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-sm text-slate-600 mb-1.5 block font-medium">Year</Label>
            <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
              <SelectTrigger className="rounded-lg w-28" data-testid="pl-year-select"><SelectValue /></SelectTrigger>
              <SelectContent>{years.map(y => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 lg:ml-auto">
          <Button onClick={() => setShowGenerate(true)} disabled={loading || finalized} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg" data-testid="pl-generate-btn">
            <Sparkles className="w-4 h-4 mr-2" /> Generate Paid Leave
          </Button>
          <Button variant="outline" onClick={() => handleExport('xlsx')} className="rounded-lg" data-testid="pl-export-xlsx-btn"><Download className="w-4 h-4 mr-2" /> Export</Button>
          <Button variant="outline" onClick={() => handleExport('csv')} className="rounded-lg" data-testid="pl-export-csv-btn"><Download className="w-4 h-4 mr-2" /> CSV</Button>
          <Button variant="outline" onClick={() => { setImportFile(null); setImportResult(null); setShowImport(true); }} disabled={finalized} className="rounded-lg" data-testid="pl-import-btn"><Upload className="w-4 h-4 mr-2" /> Import</Button>
          <Button variant="outline" onClick={openHistory} className="rounded-lg" data-testid="pl-history-btn"><History className="w-4 h-4 mr-2" /> History</Button>
        </div>
      </div>

      {/* Status banner */}
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 flex items-center gap-3" data-testid="pl-status-banner">
        {finalized ? (
          <>
            <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center"><Lock className="w-5 h-5 text-amber-600" /></div>
            <div>
              <p className="text-sm font-semibold text-slate-900">{MONTHS[month - 1]} {year} — Finalized via {status.method === 'generate' ? 'Generate' : 'Import'}</p>
              <p className="text-xs text-slate-500">Processed for {status.record?.count} employee(s) by {status.record?.performed_by_name || 'Admin'}. Generate & Import are locked for this month.</p>
            </div>
          </>
        ) : (
          <>
            <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center"><Wallet className="w-5 h-5 text-emerald-600" /></div>
            <div>
              <p className="text-sm font-semibold text-slate-900">{MONTHS[month - 1]} {year} — Not yet processed</p>
              <p className="text-xs text-slate-500">{status?.eligible_count ?? 0} confirmed Full-Time employee(s) are eligible. Use Generate (adds 1 each) or Import to set balances.</p>
            </div>
          </>
        )}
      </div>

      {/* Generate confirm */}
      <Dialog open={showGenerate} onOpenChange={setShowGenerate}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl" data-testid="pl-generate-dialog">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Sparkles className="w-5 h-5 text-[#063c88]" /> Generate Paid Leave</DialogTitle>
            <DialogDescription>Generate 1 paid leave for all confirmed Full-Time employees for {MONTHS[month - 1]} {year}?</DialogDescription></DialogHeader>
          <p className="text-sm text-slate-600 py-2">This adds <strong>1 paid leave</strong> to each of the <strong>{status?.eligible_count ?? 0}</strong> eligible employees. This action can only be performed once for this month.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowGenerate(false)} disabled={actionLoading} className="rounded-lg">Cancel</Button>
            <Button onClick={handleGenerate} disabled={actionLoading} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg" data-testid="pl-generate-confirm">{actionLoading ? 'Generating…' : 'Generate'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Import */}
      <Dialog open={showImport} onOpenChange={(o) => { if (!actionLoading) setShowImport(o); }}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl max-w-2xl" data-testid="pl-import-dialog">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Upload className="w-5 h-5 text-[#063c88]" /> Import Paid Leave — {MONTHS[month - 1]} {year}</DialogTitle>
            <DialogDescription>Export the eligible list first, edit only the "Existing Available Paid Leave" column, then upload it here. Existing balances for the employees in the file will be replaced.</DialogDescription></DialogHeader>
          <div className="space-y-3 py-2">
            <Input type="file" accept=".xlsx,.csv" onChange={(e) => { setImportFile(e.target.files?.[0] || null); setImportResult(null); }} className="rounded-lg cursor-pointer" data-testid="pl-import-file" />
            {importFile && <p className="text-xs text-slate-500">Selected: <span className="font-medium">{importFile.name}</span></p>}
            {importResult && (
              <div className={`rounded-lg p-3 text-sm ${importResult.success ? 'bg-emerald-50 border border-emerald-200' : 'bg-red-50 border border-red-200'}`} data-testid="pl-import-result">
                <p className="flex items-center gap-2 font-medium">
                  {importResult.success ? <CheckCircle2 className="w-4 h-4 text-emerald-600" /> : <AlertTriangle className="w-4 h-4 text-red-600" />}
                  {importResult.message}
                </p>
                {importResult.errors && importResult.errors.length > 0 && (
                  <div className="mt-2 max-h-48 overflow-auto space-y-1">
                    {importResult.errors.map((er, i) => (
                      <div key={i} className="text-xs text-red-700"><span className="font-mono">Row {er.row}</span> · {er.employee_id || '—'} · {er.reason}</div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowImport(false)} disabled={actionLoading} className="rounded-lg">Close</Button>
            <Button onClick={handleImport} disabled={!importFile || actionLoading} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg" data-testid="pl-import-submit">{actionLoading ? 'Importing…' : 'Upload & Import'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* History */}
      <Dialog open={showHistory} onOpenChange={setShowHistory}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl max-w-3xl" data-testid="pl-history-dialog">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><History className="w-5 h-5 text-[#063c88]" /> Paid Leave History — {MONTHS[month - 1]} {year}</DialogTitle>
            <DialogDescription>Balance changes recorded for the selected month.</DialogDescription></DialogHeader>
          <div className="max-h-[60vh] overflow-auto">
            <table className="table-premium w-full text-sm">
              <thead><tr>
                <th className="text-left">Employee</th><th>Action</th><th>Prev</th><th>New</th><th>Change</th><th>By</th><th>When</th>
              </tr></thead>
              <tbody>
                {history.length === 0 ? <tr><td colSpan="7" className="text-center py-8 text-slate-500">No history for this month</td></tr> :
                  history.map((h) => (
                    <tr key={h.id}>
                      <td className="text-left font-medium text-slate-800">{h.emp_name}</td>
                      <td><Badge className="bg-slate-100 text-slate-700 border-slate-200 text-[10px]">{h.action_type}</Badge></td>
                      <td className="text-center">{h.previous_balance}</td>
                      <td className="text-center font-semibold">{h.new_balance}</td>
                      <td className={`text-center ${h.change_amount >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{h.change_amount >= 0 ? '+' : ''}{h.change_amount}</td>
                      <td className="text-center text-slate-500">{h.changed_by_name || '—'}</td>
                      <td className="text-center text-slate-500 whitespace-nowrap">{h.changed_at ? formatDate(h.changed_at.split('T')[0]) : '—'}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setShowHistory(false)} className="rounded-lg">Close</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PaidLeaveManagement;
