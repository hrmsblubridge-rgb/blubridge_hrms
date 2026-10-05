import React, { useRef, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../ui/dialog';
import { FileSpreadsheet, Download, Upload, Loader2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const monthLabel = (m) => new Date(`${m}-01T00:00:00`).toLocaleString('en-US', { month: 'long', year: 'numeric' });

export const BrsfExportImport = ({ month, headers, onImported, importDisabled }) => {
  const fileRef = useRef(null);
  const [busy, setBusy] = useState('');
  const [preview, setPreview] = useState(null);
  const [confirming, setConfirming] = useState(false);

  const download = async (format) => {
    setBusy(format);
    try {
      const res = await axios.get(`${API}/brsf/export`, {
        params: { month, format }, headers, responseType: 'blob',
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `BRSF_Star_Reward_${monthLabel(month).replace(' ', '_')}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`${format.toUpperCase()} exported for ${monthLabel(month)}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Export failed');
    } finally {
      setBusy('');
    }
  };

  const upload = async (file) => {
    if (!file) return;
    setBusy('import');
    try {
      const form = new FormData();
      form.append('month', month);
      form.append('file', file);
      const res = await axios.post(`${API}/brsf/import/preview`, form, { headers });
      setPreview(res.data);
      if (!res.data.changes.length && !res.data.errors.length) {
        toast.info('No changed star values found in this file');
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not read this file');
    } finally {
      setBusy('');
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const confirmImport = async () => {
    setConfirming(true);
    try {
      const res = await axios.post(`${API}/brsf/import/confirm`, { batch_id: preview.batch_id }, { headers });
      toast.success(res.data.message);
      if (res.data.failed?.length) toast.error(`${res.data.failed.length} value(s) could not be applied`);
      setPreview(null);
      onImported();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Import failed');
    } finally {
      setConfirming(false);
    }
  };

  const s = preview?.summary;

  return (
    <>
      <Button variant="outline" onClick={() => download('xlsx')} disabled={!!busy} className="rounded-lg" data-testid="brsf-export-xlsx">
        {busy === 'xlsx' ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <FileSpreadsheet className="w-4 h-4 mr-2" />}
        Export Excel
      </Button>
      <Button variant="outline" onClick={() => download('csv')} disabled={!!busy} className="rounded-lg" data-testid="brsf-export-csv">
        {busy === 'csv' ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
        Export CSV
      </Button>
      <Button variant="outline" onClick={() => fileRef.current?.click()} disabled={!!busy || importDisabled}
        title={importDisabled ? 'Import is available only for completed months' : 'Import an edited BRSF sheet'}
        className="rounded-lg" data-testid="brsf-import-btn">
        {busy === 'import' ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Upload className="w-4 h-4 mr-2" />}
        Import Excel/CSV
      </Button>
      <input ref={fileRef} type="file" accept=".xlsx,.xlsm,.csv" className="hidden"
        onChange={(e) => upload(e.target.files?.[0])} data-testid="brsf-import-input" />

      <Dialog open={!!preview} onOpenChange={(v) => !v && setPreview(null)}>
        <DialogContent className="max-w-5xl" data-testid="brsf-import-preview-dialog">
          <DialogHeader>
            <DialogTitle>Import Preview — {monthLabel(month)}</DialogTitle>
            <DialogDescription>
              Nothing is saved until you confirm. Blank cells are left untouched; total columns are always recalculated by the HRMS.
            </DialogDescription>
          </DialogHeader>

          {s && (
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2" data-testid="brsf-import-summary">
              {[['Employees in File', s.employees_in_file], ['Valid Employees', s.valid_employees],
                ['Changed Values', s.changed_values], ['No Change', s.no_change],
                ['Errors', s.errors], ['Skipped', s.skipped]].map(([label, value]) => (
                <div key={label} className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-center">
                  <p className="text-lg font-bold text-slate-900 number-display">{value}</p>
                  <p className="text-[11px] text-slate-500">{label}</p>
                </div>
              ))}
            </div>
          )}

          <div className="max-h-[45vh] overflow-auto mt-2">
            <table className="w-full text-sm" data-testid="brsf-import-preview-table">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500 sticky top-0">
                <tr className="text-left">
                  <th className="px-3 py-2">Row</th>
                  <th className="px-3 py-2">Employee</th>
                  <th className="px-3 py-2">Criterion</th>
                  <th className="px-3 py-2 text-right">Existing Final</th>
                  <th className="px-3 py-2 text-right">Imported</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {(preview?.changes || []).map((c, i) => (
                  <tr key={`c${i}`} className="border-b border-slate-100" data-testid={`brsf-import-change-${i}`}>
                    <td className="px-3 py-2 text-slate-500">{c.row}</td>
                    <td className="px-3 py-2">{c.employee}</td>
                    <td className="px-3 py-2">{c.code} · {c.criteria}</td>
                    <td className="px-3 py-2 text-right number-display">{c.existing}</td>
                    <td className="px-3 py-2 text-right number-display font-semibold">{c.imported}</td>
                    <td className="px-3 py-2">
                      <Badge variant="outline" className="text-xs bg-emerald-50 text-emerald-700 border-emerald-200">Valid</Badge>
                    </td>
                  </tr>
                ))}
                {(preview?.errors || []).map((c, i) => (
                  <tr key={`e${i}`} className="border-b border-slate-100 bg-rose-50/40" data-testid={`brsf-import-error-${i}`}>
                    <td className="px-3 py-2 text-slate-500">{c.row}</td>
                    <td className="px-3 py-2">{c.employee}</td>
                    <td className="px-3 py-2">{c.code} · {c.criteria}</td>
                    <td className="px-3 py-2 text-right number-display">{c.existing}</td>
                    <td className="px-3 py-2 text-right number-display font-semibold">{String(c.imported)}</td>
                    <td className="px-3 py-2 text-rose-700 text-xs">Invalid — {c.message}</td>
                  </tr>
                ))}
                {(preview?.skipped || []).map((c, i) => (
                  <tr key={`s${i}`} className="border-b border-slate-100" data-testid={`brsf-import-skipped-${i}`}>
                    <td className="px-3 py-2 text-slate-500">{c.row}</td>
                    <td className="px-3 py-2">{c.employee}</td>
                    <td className="px-3 py-2 text-slate-400" colSpan={3}>—</td>
                    <td className="px-3 py-2 text-slate-500 text-xs">Skipped — {c.reason}</td>
                  </tr>
                ))}
                {preview && !preview.changes.length && !preview.errors.length && !preview.skipped.length && (
                  <tr><td colSpan={6} className="px-3 py-8 text-center text-slate-500">
                    Every value in this file already matches the HRMS — nothing to import.
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setPreview(null)} data-testid="brsf-import-cancel">Cancel</Button>
            <Button onClick={confirmImport} disabled={confirming || !preview?.changes?.length}
              className="bg-[#063c88] text-white" data-testid="brsf-import-confirm">
              {confirming && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Confirm Import{preview?.changes?.length ? ` (${preview.changes.length})` : ''}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default BrsfExportImport;
