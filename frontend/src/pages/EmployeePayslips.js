import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Receipt, Download, Eye, Loader2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const inr = (n) => '₹' + Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const monthLabel = (m) => new Date(`${m}-01T00:00:00`).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });

export default function EmployeePayslips() {
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();
  const [slips, setSlips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewSlip, setViewSlip] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await axios.get(`${API}/payslips/my`, { headers });
        setSlips(res.data);
      } catch { toast.error('Failed to load payslips'); }
      finally { setLoading(false); }
    })();
  }, []); // eslint-disable-line

  const downloadPdf = async (s) => {
    try {
      const res = await axios.get(`${API}/payslips/${s.id}/pdf`, { headers, responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url; a.download = `Payslip_${s.month}.pdf`;
      a.click(); URL.revokeObjectURL(url);
    } catch { toast.error('PDF download failed'); }
  };

  return (
    <div className="space-y-6" data-testid="my-payslips-page">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-emerald-100 text-emerald-700"><Receipt className="w-6 h-6" /></div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">My Payslips</h1>
          <p className="text-sm text-slate-500">Payslips are published on the 5th of the following month</p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-slate-400"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>
      ) : slips.length === 0 ? (
        <div className="bg-white rounded-xl border p-10 text-center text-slate-400" data-testid="no-payslips-msg">
          No payslips available yet. Your payslip for a month becomes available on the 5th of the following month once confirmed by HR.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {slips.map((s) => (
            <div key={s.id} className="bg-white rounded-xl border p-5 space-y-3 hover:shadow-md transition-shadow" data-testid={`payslip-card-${s.month}`}>
              <div className="flex items-center justify-between">
                <div className="font-semibold text-slate-800">{monthLabel(s.month)}</div>
                <Badge className="bg-emerald-100 text-emerald-700">Confirmed</Badge>
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div><div className="text-xs text-slate-400">Payable Days</div><div className="font-medium">{s.calc?.payable_days}</div></div>
                <div><div className="text-xs text-slate-400">Gross</div><div className="font-medium">{inr(s.calc?.gross_earnings)}</div></div>
                <div><div className="text-xs text-slate-400">Deductions</div><div className="font-medium text-red-600">−{inr(s.calc?.total_deductions)}</div></div>
                <div><div className="text-xs text-slate-400">Net Pay</div><div className="font-bold text-emerald-700" data-testid={`net-pay-${s.month}`}>{inr(s.calc?.net_pay)}</div></div>
              </div>
              <div className="flex gap-2 pt-1">
                <Button data-testid={`view-payslip-${s.month}`} size="sm" variant="outline" className="flex-1" onClick={() => setViewSlip(s)}>
                  <Eye className="w-4 h-4 mr-1" /> View
                </Button>
                <Button data-testid={`download-payslip-${s.month}`} size="sm" className="flex-1" onClick={() => downloadPdf(s)}>
                  <Download className="w-4 h-4 mr-1" /> PDF
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={!!viewSlip} onOpenChange={(o) => !o && setViewSlip(null)}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Payslip — {viewSlip && monthLabel(viewSlip.month)}</DialogTitle></DialogHeader>
          {viewSlip && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
                {[['Calendar Days', viewSlip.calc?.calendar_days], ['Payable Days', viewSlip.calc?.payable_days], ['Extra Pay Days', viewSlip.calc?.extra_pay_days], ['Per-Day', inr(viewSlip.calc?.per_day_salary)]].map(([l, v]) => (
                  <div key={l} className="bg-slate-50 rounded-lg p-2">
                    <div className="text-xs text-slate-400">{l}</div>
                    <div className="font-semibold text-sm">{v}</div>
                  </div>
                ))}
              </div>
              <table className="w-full text-sm">
                <thead className="text-xs text-slate-500 uppercase border-b">
                  <tr><th className="text-left py-2">Component</th><th className="text-right py-2">Amount</th></tr>
                </thead>
                <tbody>
                  {viewSlip.calc?.components.map((c, i) => (
                    <tr key={i} className="border-b border-slate-100">
                      <td className="py-2">
                        {c.name}
                        {c.operation === 'deduct' && (
                          <span className="ml-1 text-[10px] uppercase tracking-wide text-slate-400">
                            {c.include_in_gross ? '(CTC · deducted)' : '(deduction)'}
                          </span>
                        )}
                      </td>
                      <td className="py-2 text-right font-medium">{inr(c.amount)}</td>
                    </tr>
                  ))}
                  {viewSlip.calc?.other_allowance > 0 && (
                    <tr className="border-b border-slate-100"><td className="py-2">Other Allowance (Extra Pay)</td><td className="py-2 text-right font-medium">{inr(viewSlip.calc.other_allowance)}</td></tr>
                  )}
                </tbody>
                <tfoot>
                  <tr><td className="py-2 text-right text-slate-500">Gross</td><td className="py-2 text-right font-semibold">{inr(viewSlip.calc?.gross_earnings)}</td></tr>
                  <tr><td className="py-2 text-right text-slate-500">Deductions</td><td className="py-2 text-right font-semibold text-red-600">−{inr(viewSlip.calc?.total_deductions)}</td></tr>
                  <tr className="border-t"><td className="py-2 text-right font-semibold">NET PAY</td><td className="py-2 text-right font-bold text-emerald-700">{inr(viewSlip.calc?.net_pay)}</td></tr>
                </tfoot>
              </table>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
