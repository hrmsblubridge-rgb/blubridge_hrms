import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Fingerprint, Plus, Edit2, AlertCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { useTableSort, SortableTh } from '../components/useTableSort';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EmployeeMissedPunch = () => {
  const { getAuthHeaders } = useAuth();
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [formLoading, setFormLoading] = useState(false);
  const [form, setForm] = useState({ date: '', punch_type: 'Check-in', check_in_time: '', check_out_time: '', reason: '' });
  const { sortedRows: sortedRequests, sortField, sortDir, toggleSort } = useTableSort(requests);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API}/missed-punches`, { headers: getAuthHeaders() });
      // Handle both old (array) and new (paginated) response
      const items = Array.isArray(res.data) ? res.data : (res.data.data || []);
      setRequests(items);
    }
    catch { toast.error('Failed to load missed punch requests'); }
    finally { setLoading(false); }
  }, [getAuthHeaders]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSubmit = async () => {
    if (!form.date || !form.reason || form.reason.trim().length < 5) { toast.error('Fill date and reason (min 5 chars)'); return; }
    if (form.punch_type === 'Check-in' && !form.check_in_time) { toast.error('Select check-in time'); return; }
    if (form.punch_type === 'Check-out' && !form.check_out_time) { toast.error('Select check-out time'); return; }
    if (form.punch_type === 'Both' && (!form.check_in_time || !form.check_out_time)) { toast.error('Select both times'); return; }
    try {
      setFormLoading(true);
      if (editingId) { await axios.put(`${API}/missed-punches/${editingId}`, form, { headers: getAuthHeaders() }); toast.success('Updated'); }
      else { await axios.post(`${API}/missed-punches`, form, { headers: getAuthHeaders() }); toast.success('Submitted'); }
      setShowDialog(false); setEditingId(null); setForm({ date: '', punch_type: 'Check-in', check_in_time: '', check_out_time: '', reason: '' }); fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setFormLoading(false); }
  };

  const handleEdit = (r) => { setEditingId(r.id); setForm({ date: r.date, punch_type: r.punch_type, check_in_time: r.check_in_time || '', check_out_time: r.check_out_time || '', reason: r.reason }); setShowDialog(true); };
  const getStatusBadge = (s) => ({ pending: 'badge-warning', approved: 'badge-success', rejected: 'badge-error' }[s] || 'badge-neutral');

  return (
    <div className="space-y-6 animate-fade-in" data-testid="employee-missed-punch-page">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center"><Fingerprint className="w-5 h-5 text-white" /></div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Missed Punch</h1>
            <p className="text-sm text-slate-500">Apply for missed punch corrections</p>
          </div>
        </div>
        <Button onClick={() => { setEditingId(null); setForm({ date: '', punch_type: 'Check-in', check_in_time: '', check_out_time: '', reason: '' }); setShowDialog(true); }} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-xl" data-testid="apply-missed-punch-btn">
          <Plus className="w-4 h-4 mr-2" /> Apply Missed Punch
        </Button>
      </div>

      <div className="card-premium overflow-hidden">
        {loading ? <div className="flex items-center justify-center h-48"><div className="w-10 h-10 border-2 border-[#063c88] border-t-transparent rounded-full animate-spin" /></div> : (
          <div className="overflow-x-auto">
            <table className="table-premium">
              <thead><tr>
                <SortableTh field="date" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Date</SortableTh>
                <SortableTh field="punch_type" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Punch Type</SortableTh>
                <SortableTh field="check_in_time" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Check-In</SortableTh>
                <SortableTh field="check_out_time" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Check-Out</SortableTh>
                <SortableTh field="reason" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Reason</SortableTh>
                <SortableTh field="status" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Status</SortableTh>
                <th>Actions</th>
              </tr></thead>
              <tbody>
                {sortedRequests.length === 0 ? <tr><td colSpan="7" className="text-center py-12 text-slate-500">No missed punch requests found</td></tr> : sortedRequests.map((r) => (
                  <tr key={r.id}>
                    <td className="font-medium text-slate-900">{r.date}</td>
                    <td className="text-slate-600">{r.punch_type}</td>
                    <td className="text-slate-600">{r.check_in_time ? (r.check_in_time.includes('T') ? new Date(r.check_in_time).toLocaleString('en-IN', {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',hour12:true}) : r.check_in_time) : '-'}</td>
                    <td className="text-slate-600">{r.check_out_time ? (r.check_out_time.includes('T') ? new Date(r.check_out_time).toLocaleString('en-IN', {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',hour12:true}) : r.check_out_time) : '-'}</td>
                    <td className="text-slate-600 max-w-[200px] truncate">{r.reason}</td>
                    <td><Badge className={getStatusBadge(r.status)}>{r.status}</Badge></td>
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
          <DialogHeader><DialogTitle style={{ fontFamily: 'Outfit' }}>{editingId ? 'Edit' : 'Apply'} Missed Punch</DialogTitle><DialogDescription>Select punch type and provide details</DialogDescription></DialogHeader>
          <div className="space-y-4 py-4">
            <div><Label>Date</Label><Input type="date" value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} className="mt-1.5 rounded-lg" /></div>
            <div>
              <Label>Punch Type</Label>
              <Select value={form.punch_type} onValueChange={v => setForm({ ...form, punch_type: v, check_in_time: v === 'Check-out' ? '' : form.check_in_time, check_out_time: v === 'Check-in' ? '' : form.check_out_time })}>
                <SelectTrigger className="mt-1.5 rounded-lg" data-testid="punch-type-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Check-in">Check-in</SelectItem>
                  <SelectItem value="Check-out">Check-out</SelectItem>
                  <SelectItem value="Both">Both</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {(form.punch_type === 'Check-in' || form.punch_type === 'Both') && (
              <div><Label>Check-In Date & Time</Label><Input type="datetime-local" value={form.check_in_time} onChange={e => setForm({ ...form, check_in_time: e.target.value })} className="mt-1.5 rounded-lg" data-testid="check-in-datetime" /></div>
            )}
            {(form.punch_type === 'Check-out' || form.punch_type === 'Both') && (
              <div><Label>Check-Out Date & Time</Label><Input type="datetime-local" value={form.check_out_time} onChange={e => setForm({ ...form, check_out_time: e.target.value })} className="mt-1.5 rounded-lg" data-testid="check-out-datetime" /></div>
            )}
            <div><Label>Reason</Label><Textarea value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} className="mt-1.5 rounded-lg min-h-[80px]" placeholder="Reason for missed punch..." /></div>
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

export default EmployeeMissedPunch;
