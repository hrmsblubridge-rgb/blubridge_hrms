import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { LogOut, Plus, Edit2, AlertCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { useTableSort, SortableTh } from '../components/useTableSort';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EmployeeEarlyOut = () => {
  const { getAuthHeaders } = useAuth();
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [formLoading, setFormLoading] = useState(false);
  const [form, setForm] = useState({ date: '', expected_time: '', actual_time: '', reason: '' });
  const { sortedRows: sortedRequests, sortField, sortDir, toggleSort } = useTableSort(requests);

  const fetchData = useCallback(async () => {
    try { setLoading(true); const res = await axios.get(`${API}/early-out-requests`, { headers: getAuthHeaders() }); setRequests(res.data); }
    catch { toast.error('Failed to load early out requests'); }
    finally { setLoading(false); }
  }, [getAuthHeaders]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSubmit = async () => {
    if (!form.date || !form.reason || form.reason.trim().length < 5) { toast.error('Please fill date and reason (min 5 chars)'); return; }
    try {
      setFormLoading(true);
      if (editingId) { await axios.put(`${API}/early-out-requests/${editingId}`, form, { headers: getAuthHeaders() }); toast.success('Updated'); }
      else { await axios.post(`${API}/early-out-requests`, form, { headers: getAuthHeaders() }); toast.success('Submitted'); }
      setShowDialog(false); setEditingId(null); setForm({ date: '', expected_time: '', actual_time: '', reason: '' }); fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setFormLoading(false); }
  };

  const handleEdit = (r) => { setEditingId(r.id); setForm({ date: r.date, expected_time: r.expected_time || '', actual_time: r.actual_time || '', reason: r.reason }); setShowDialog(true); };
  const getStatusBadge = (s) => ({ pending: 'badge-warning', approved: 'badge-success', rejected: 'badge-error' }[s] || 'badge-neutral');
  const stats = { pending: requests.filter(r => r.status === 'pending').length, approved: requests.filter(r => r.status === 'approved').length, rejected: requests.filter(r => r.status === 'rejected').length };

  return (
    <div className="space-y-6 animate-fade-in" data-testid="employee-early-out-page">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center"><LogOut className="w-5 h-5 text-white" /></div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Early Out Requests</h1>
            <p className="text-sm text-slate-500">Apply and track early out requests</p>
          </div>
        </div>
        <Button onClick={() => { setEditingId(null); setForm({ date: '', expected_time: '', actual_time: '', reason: '' }); setShowDialog(true); }} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-xl" data-testid="apply-early-out-btn">
          <Plus className="w-4 h-4 mr-2" /> Apply Early Out
        </Button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[{ label: 'Pending', value: stats.pending, color: 'amber' }, { label: 'Approved', value: stats.approved, color: 'emerald' }, { label: 'Rejected', value: stats.rejected, color: 'red' }].map((s, i) => (
          <div key={i} className="stat-card"><div className="flex items-center gap-4"><div className={`w-10 h-10 rounded-xl bg-${s.color}-100 flex items-center justify-center`}><AlertCircle className={`w-5 h-5 text-${s.color}-600`} /></div><div><p className="text-2xl font-bold text-slate-900">{s.value}</p><p className="text-xs text-slate-500">{s.label}</p></div></div></div>
        ))}
      </div>

      <div className="card-premium overflow-hidden">
        {loading ? <div className="flex items-center justify-center h-48"><div className="w-10 h-10 border-2 border-[#063c88] border-t-transparent rounded-full animate-spin" /></div> : (
          <div className="overflow-x-auto">
            <table className="table-premium">
              <thead><tr>
                <SortableTh field="date" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Date</SortableTh>
                <SortableTh field="expected_time" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Expected Time</SortableTh>
                <SortableTh field="actual_time" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Actual Time</SortableTh>
                <SortableTh field="reason" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Reason</SortableTh>
                <SortableTh field="status" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Status</SortableTh>
                <SortableTh field="is_lop" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>LOP</SortableTh>
                <th>Actions</th>
              </tr></thead>
              <tbody>
                {sortedRequests.length === 0 ? <tr><td colSpan="7" className="text-center py-12 text-slate-500">No early out requests found</td></tr> : sortedRequests.map((r) => (
                  <tr key={r.id}>
                    <td className="font-medium text-slate-900">{r.date}</td>
                    <td className="text-slate-600">{r.expected_time || '-'}</td>
                    <td className="text-slate-600">{r.actual_time || '-'}</td>
                    <td className="text-slate-600 max-w-[200px] truncate">{r.reason}</td>
                    <td><Badge className={getStatusBadge(r.status)}>{r.status}</Badge></td>
                    <td>{r.is_lop === true ? <Badge className="badge-error">LOP</Badge> : r.is_lop === false ? <Badge className="badge-success">No LOP</Badge> : '-'}</td>
                    <td>{r.status === 'pending' && <Button size="sm" variant="outline" onClick={() => handleEdit(r)} className="rounded-lg"><Edit2 className="w-3 h-3" /></Button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Outfit' }}>{editingId ? 'Edit' : 'Apply'} Early Out Request</DialogTitle><DialogDescription>Submit your early out request</DialogDescription></DialogHeader>
          <div className="space-y-4 py-4">
            <div><Label>Date</Label><Input type="date" value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} className="mt-1.5 rounded-lg" /></div>
            <div className="grid grid-cols-2 gap-4">
              <div><Label>Expected Logout Time</Label><Input type="time" value={form.expected_time} onChange={e => setForm({ ...form, expected_time: e.target.value })} className="mt-1.5 rounded-lg" /></div>
              <div><Label>Actual Logout Time</Label><Input type="time" value={form.actual_time} onChange={e => setForm({ ...form, actual_time: e.target.value })} className="mt-1.5 rounded-lg" /></div>
            </div>
            <div><Label>Reason</Label><Textarea value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} className="mt-1.5 rounded-lg min-h-[80px]" placeholder="Reason for early out..." /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)} className="rounded-lg">Cancel</Button>
            <Button onClick={handleSubmit} disabled={formLoading} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg">{formLoading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : 'Submit'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EmployeeEarlyOut;
