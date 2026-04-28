import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { CalendarDays, Plus, Clock, CheckCircle2, XCircle, Edit2, Paperclip, Upload, Eye } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EmployeeLeave = () => {
  const { getAuthHeaders } = useAuth();
  const [leaves, setLeaves] = useState([]);
  const [leaveBalance, setLeaveBalance] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showApplyDialog, setShowApplyDialog] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [docFile, setDocFile] = useState(null);
  const [docUploading, setDocUploading] = useState(false);
  const [form, setForm] = useState({ leave_type: 'Sick', leave_split: 'Full Day', start_date: '', end_date: '', reason: '', supporting_document_url: '', supporting_document_name: '' });
  const [viewReason, setViewReason] = useState(null); // { reason, leave_type, start_date, end_date }

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const leavesRes = await axios.get(`${API}/employee/leaves`, { headers: getAuthHeaders() });
      const data = leavesRes.data;
      // Backend returns {requests: [], history: []} - merge into flat array
      const allLeaves = [...(data.requests || []), ...(data.history || [])];
      setLeaves(Array.isArray(data) ? data : allLeaves);
      try {
        const balanceRes = await axios.get(`${API}/employee/leave-balance`, { headers: getAuthHeaders() });
        setLeaveBalance(balanceRes.data);
      } catch {
        setLeaveBalance(null);
      }
    } catch (error) {
      toast.error('Failed to load leave data');
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleDocUpload = async (file) => {
    if (!file) return;
    setDocUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await axios.post(`${API}/upload`, fd, { headers: { ...getAuthHeaders(), 'Content-Type': 'multipart/form-data' } });
      setForm(prev => ({ ...prev, supporting_document_url: res.data.url || res.data.secure_url, supporting_document_name: file.name }));
      toast.success('Document uploaded');
    } catch { toast.error('Upload failed'); }
    finally { setDocUploading(false); }
  };

  const handleApplyLeave = async () => {
    if (!form.leave_type || !form.start_date || !form.reason) {
      toast.error('Please fill all fields');
      return;
    }
    if (form.reason.trim().length < 10) {
      toast.error('Reason must be at least 10 characters');
      return;
    }
    try {
      setFormLoading(true);
      // Single-day leave: silently mirror end_date = start_date so the
      // existing backend contract keeps working unchanged.
      const payload = { ...form, end_date: form.start_date };
      if (editingId) {
        await axios.put(`${API}/employee/leaves/${editingId}`, payload, { headers: getAuthHeaders() });
        toast.success('Leave updated');
      } else {
        await axios.post(`${API}/employee/leaves/apply`, payload, { headers: getAuthHeaders() });
        toast.success('Leave application submitted');
      }
      setShowApplyDialog(false);
      setEditingId(null);
      setDocFile(null);
      setForm({ leave_type: 'Sick', leave_split: 'Full Day', start_date: '', end_date: '', reason: '', supporting_document_url: '', supporting_document_name: '' });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to apply leave');
    } finally {
      setFormLoading(false);
    }
  };

  const handleEdit = (leave) => {
    setEditingId(leave.id);
    setForm({ leave_type: leave.leave_type, leave_split: leave.leave_split || 'Full Day', start_date: leave.start_date, end_date: leave.end_date, reason: leave.reason, supporting_document_url: leave.supporting_document_url || '', supporting_document_name: leave.supporting_document_name || '' });
    setShowApplyDialog(true);
  };

  const getStatusBadge = (status) => ({ 'pending': 'badge-warning', 'approved': 'badge-success', 'rejected': 'badge-error' }[status] || 'badge-neutral');

  const stats = {
    pending: leaves.filter(l => l.status === 'pending').length,
    approved: leaves.filter(l => l.status === 'approved').length,
    rejected: leaves.filter(l => l.status === 'rejected').length,
  };

  return (
    <div className="space-y-6 animate-fade-in" data-testid="employee-leave-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
            <CalendarDays className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Leave Management</h1>
            <p className="text-sm text-slate-500">Apply for leave and track requests</p>
          </div>
        </div>
        <Button onClick={() => { setEditingId(null); setDocFile(null); setForm({ leave_type: 'Sick', leave_split: 'Full Day', start_date: '', end_date: '', reason: '', supporting_document_url: '', supporting_document_name: '' }); setShowApplyDialog(true); }} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-xl shadow-lg shadow-[#063c88]/20" data-testid="apply-leave-btn">
          <Plus className="w-4 h-4 mr-2" /> Apply Leave
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Pending', value: stats.pending, icon: Clock, color: 'amber' },
          { label: 'Approved', value: stats.approved, icon: CheckCircle2, color: 'blue' },
          { label: 'Rejected', value: stats.rejected, icon: XCircle, color: 'red' },
        ].map((stat, i) => (
          <div key={i} className="stat-card">
            <div className="flex items-center gap-4">
              <div className={`w-10 h-10 rounded-xl bg-${stat.color}-100 flex items-center justify-center`}>
                <stat.icon className={`w-5 h-5 text-${stat.color}-600`} />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900 number-display">{stat.value}</p>
                <p className="text-xs text-slate-500">{stat.label}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Leave Balance */}
      {leaveBalance && (
        <div className="card-premium p-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4" style={{ fontFamily: 'Outfit' }}>Leave Balance</h3>
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'Sick', remaining: leaveBalance.sick_remaining, total: leaveBalance.sick_total },
              { label: 'Casual', remaining: leaveBalance.casual_remaining, total: leaveBalance.casual_total },
              { label: 'Annual', remaining: leaveBalance.annual_remaining, total: leaveBalance.annual_total },
            ].map((leave, i) => (
              <div key={i} className="p-4 rounded-xl bg-slate-50">
                <p className="text-sm text-slate-500 mb-2">{leave.label} Leave</p>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-bold text-slate-900">{leave.remaining}</span>
                  <span className="text-sm text-slate-500">/ {leave.total}</span>
                </div>
                <div className="h-2 bg-slate-200 rounded-full mt-2 overflow-hidden">
                  <div className="h-full bg-[#063c88] rounded-full transition-all" style={{ width: `${(leave.remaining / leave.total) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Leave History */}
      <div className="card-premium overflow-hidden">
        <div className="p-6 border-b border-slate-100">
          <h3 className="text-lg font-semibold text-slate-900" style={{ fontFamily: 'Outfit' }}>Leave History</h3>
        </div>
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-10 h-10 border-2 border-[#063c88] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="table-premium">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Split</th>
                  <th>Start Date</th>
                  <th>End Date</th>
                  <th>Duration</th>
                  <th>Reason</th>
                  <th>Document</th>
                  <th>Status</th>
                  <th>LOP</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {leaves.length === 0 ? (
                  <tr><td colSpan="10" className="text-center py-12 text-slate-500">No leave records found</td></tr>
                ) : (
                  leaves.map((leave, index) => (
                    <tr key={index}>
                      <td className="font-medium text-slate-900">{leave.leave_type}</td>
                      <td className="text-slate-600">{leave.leave_split || 'Full Day'}</td>
                      <td className="text-slate-600">{leave.start_date}</td>
                      <td className="text-slate-600">{leave.end_date}</td>
                      <td className="text-slate-600">{leave.duration}</td>
                      <td className="text-slate-600">
                        {leave.reason ? (
                          <div className="flex items-center gap-2 max-w-[240px]">
                            <span className="truncate" title={leave.reason}>{leave.reason}</span>
                            <button
                              type="button"
                              onClick={() => setViewReason({ reason: leave.reason, leave_type: leave.leave_type, start_date: leave.start_date, end_date: leave.end_date })}
                              className="shrink-0 text-slate-500 hover:text-[#063c88] transition-colors"
                              title="View full reason"
                              data-testid={`view-reason-${leave.id || index}`}
                            >
                              <Eye className="w-4 h-4" />
                            </button>
                          </div>
                        ) : '-'}
                      </td>
                      <td>{leave.supporting_document_url ? <a href={leave.supporting_document_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline text-xs flex items-center gap-1"><Paperclip className="w-3 h-3" />{leave.supporting_document_name || 'View'}</a> : '-'}</td>
                      <td><Badge className={getStatusBadge(leave.status)}>{leave.status}</Badge></td>
                      <td>{leave.is_lop === true ? <Badge className="badge-error">LOP</Badge> : leave.is_lop === false ? <Badge className="badge-success">No LOP</Badge> : '-'}</td>
                      <td>{leave.status === 'pending' && <Button size="sm" variant="outline" onClick={() => handleEdit(leave)} className="rounded-lg" data-testid={`edit-leave-${leave.id}`}><Edit2 className="w-3 h-3" /></Button>}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Apply Leave Dialog */}
      <Dialog open={showApplyDialog} onOpenChange={setShowApplyDialog}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl sm:max-w-lg">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Outfit' }}>{editingId ? 'Edit' : 'Apply for'} Leave</DialogTitle>
            <DialogDescription>Submit a new leave request</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-sm font-medium text-slate-700">Leave Type</Label>
                <Select value={form.leave_type} onValueChange={(v) => setForm({ ...form, leave_type: v, start_date: '', end_date: '' })}>
                  <SelectTrigger className="mt-1.5 rounded-lg" data-testid="leave-type-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Sick">Sick Leave</SelectItem>
                    <SelectItem value="Emergency">Emergency</SelectItem>
                    <SelectItem value="Preplanned">Preplanned</SelectItem>
                  </SelectContent>
                </Select>
                {/* Leave rule hints */}
                {form.leave_type === 'Sick' && <p className="text-[11px] text-amber-600 mt-1">Sick leave: past & current dates only</p>}
                {form.leave_type === 'Casual' && <p className="text-[11px] text-blue-600 mt-1">Casual leave: min 4 working days in advance (excl. Sundays)</p>}
                {form.leave_type === 'Emergency' && <p className="text-[11px] text-emerald-600 mt-1">Emergency leave: no date restrictions</p>}
              </div>
              <div>
                <Label className="text-sm font-medium text-slate-700">Leave Split</Label>
                <Select value={form.leave_split} onValueChange={(v) => setForm({ ...form, leave_split: v })}>
                  <SelectTrigger className="mt-1.5 rounded-lg" data-testid="leave-split-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Full Day">Full Day</SelectItem>
                    <SelectItem value="First Half">First Half</SelectItem>
                    <SelectItem value="Second Half">Second Half</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label className="text-sm font-medium text-slate-700">Leave Date</Label>
              <Input
                type="date"
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                max={form.leave_type === 'Sick' ? new Date().toISOString().split('T')[0] : undefined}
                min={form.leave_type === 'Casual' ? (() => { let d = new Date(); let days = 0; while (days < 4) { d.setDate(d.getDate() + 1); if (d.getDay() !== 0) days++; } return d.toISOString().split('T')[0]; })() : undefined}
                className="mt-1.5 rounded-lg"
                data-testid="leave-date-input"
              />
            </div>
            <div>
              <Label className="text-sm font-medium text-slate-700">Reason (min 10 characters)</Label>
              <Textarea value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="mt-1.5 rounded-lg min-h-[80px]" placeholder="Enter reason for leave..." data-testid="reason-textarea" />
            </div>
            <div>
              <Label className="text-sm font-medium text-slate-700">Supporting Document (optional)</Label>
              <div className="mt-1.5 flex items-center gap-3">
                <label className="flex items-center gap-2 px-4 py-2 rounded-lg border border-dashed border-slate-300 cursor-pointer hover:bg-slate-50 transition-colors">
                  <Upload className="w-4 h-4 text-slate-500" />
                  <span className="text-sm text-slate-600">{docUploading ? 'Uploading...' : form.supporting_document_name || 'Choose file'}</span>
                  <input type="file" className="hidden" accept=".pdf,.jpg,.jpeg,.png,.doc,.docx" onChange={(e) => { const f = e.target.files?.[0]; if (f) { setDocFile(f); handleDocUpload(f); } }} disabled={docUploading} />
                </label>
                {form.supporting_document_name && <span className="text-xs text-emerald-600 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" />Uploaded</span>}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowApplyDialog(false)} className="rounded-lg">Cancel</Button>
            <Button onClick={handleApplyLeave} disabled={formLoading} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg" data-testid="submit-leave-btn">
              {formLoading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : 'Submit'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Full Reason Dialog */}
      <Dialog open={!!viewReason} onOpenChange={(open) => !open && setViewReason(null)}>
        <DialogContent className="bg-[#fffdf7] rounded-2xl sm:max-w-lg" data-testid="view-reason-dialog">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Outfit' }}>Leave Reason</DialogTitle>
            {viewReason && (
              <DialogDescription>
                {viewReason.leave_type} · {viewReason.start_date}
                {viewReason.end_date && viewReason.end_date !== viewReason.start_date ? ` to ${viewReason.end_date}` : ''}
              </DialogDescription>
            )}
          </DialogHeader>
          <div className="mt-2 p-4 rounded-xl bg-slate-50 border border-slate-200 max-h-[50vh] overflow-y-auto">
            <p className="text-sm text-slate-800 whitespace-pre-wrap break-words" data-testid="view-reason-text">
              {viewReason?.reason || '-'}
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewReason(null)} className="rounded-lg" data-testid="close-reason-dialog">Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EmployeeLeave;
