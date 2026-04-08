import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import {
  CheckCircle2, Circle, Search, Monitor, CreditCard, Key,
  Briefcase, Users, ClipboardList, ChevronRight, X, StickyNote,
  Loader2, Package, UserCheck
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle
} from '../components/ui/sheet';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const statusConfig = {
  pending: { color: 'bg-amber-100 text-amber-700 border-amber-200', label: 'Pending' },
  in_progress: { color: 'bg-blue-100 text-blue-700 border-blue-200', label: 'In Progress' },
  completed: { color: 'bg-emerald-100 text-emerald-700 border-emerald-200', label: 'Completed' },
};

const categoryIcons = {
  Infrastructure: Monitor,
  Stationery: Package,
  Access: Key,
  IT: CreditCard,
  Coordination: Users,
};

export default function OperationalChecklist() {
  const { token, user } = useAuth();
  const [checklists, setChecklists] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [selected, setSelected] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [noteItem, setNoteItem] = useState(null);
  const [noteText, setNoteText] = useState('');

  const headers = { Authorization: `Bearer ${token}` };
  const isHROrOfficeAdmin = ['hr', 'office_admin'].includes(user?.role);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const params = {};
      if (filterStatus !== 'all') params.status = filterStatus;
      if (search) params.search = search;

      const [listRes, statsRes] = await Promise.all([
        axios.get(`${API}/operational-checklists`, { headers, params }),
        axios.get(`${API}/operational-checklists/stats`, { headers }),
      ]);
      setChecklists(listRes.data);
      setStats(statsRes.data);
    } catch {
      toast.error('Failed to load checklists');
    } finally {
      setLoading(false);
    }
  }, [token, filterStatus, search]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const openDetail = async (cl) => {
    setDetailLoading(true);
    try {
      const res = await axios.get(`${API}/operational-checklists/${cl.employee_id}`, { headers });
      setSelected(res.data);
    } catch {
      toast.error('Failed to load checklist details');
    } finally {
      setDetailLoading(false);
    }
  };

  const toggleItem = async (itemKey, currentCompleted) => {
    if (!selected) return;
    try {
      const res = await axios.put(
        `${API}/operational-checklists/${selected.employee_id}/item/${itemKey}`,
        { completed: !currentCompleted, notes: '' },
        { headers }
      );
      setSelected(res.data);
      // Refresh list to update status badges
      const listRes = await axios.get(`${API}/operational-checklists`, {
        headers,
        params: { status: filterStatus !== 'all' ? filterStatus : undefined, search: search || undefined }
      });
      setChecklists(listRes.data);
      const statsRes = await axios.get(`${API}/operational-checklists/stats`, { headers });
      setStats(statsRes.data);
      toast.success(!currentCompleted ? 'Item completed' : 'Item unchecked');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update item');
    }
  };

  const saveNote = async () => {
    if (!selected || !noteItem) return;
    try {
      const item = selected.items.find(i => i.key === noteItem);
      const res = await axios.put(
        `${API}/operational-checklists/${selected.employee_id}/item/${noteItem}`,
        { completed: item?.completed || false, notes: noteText },
        { headers }
      );
      setSelected(res.data);
      setNoteItem(null);
      setNoteText('');
      toast.success('Note saved');
    } catch {
      toast.error('Failed to save note');
    }
  };

  const getProgress = (items) => {
    if (!items || items.length === 0) return 0;
    return Math.round((items.filter(i => i.completed).length / items.length) * 100);
  };

  return (
    <div className="space-y-6" data-testid="operational-checklist-page">
      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm" data-testid="stat-total">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center">
                <ClipboardList className="w-5 h-5 text-slate-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">{stats.total}</p>
                <p className="text-xs text-slate-500">Total</p>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm" data-testid="stat-pending">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center">
                <Circle className="w-5 h-5 text-amber-500" />
              </div>
              <div>
                <p className="text-2xl font-bold text-amber-600">{stats.pending}</p>
                <p className="text-xs text-slate-500">Pending</p>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm" data-testid="stat-in-progress">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center">
                <Loader2 className="w-5 h-5 text-blue-500" />
              </div>
              <div>
                <p className="text-2xl font-bold text-blue-600">{stats.in_progress}</p>
                <p className="text-xs text-slate-500">In Progress</p>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm" data-testid="stat-completed">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5 text-emerald-500" />
              </div>
              <div>
                <p className="text-2xl font-bold text-emerald-600">{stats.completed}</p>
                <p className="text-xs text-slate-500">Completed</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by employee name or ID..."
              className="pl-10 bg-slate-50 border-slate-200 rounded-xl"
              data-testid="checklist-search"
            />
          </div>
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger className="w-44 bg-slate-50 border-slate-200 rounded-xl" data-testid="checklist-status-filter">
              <SelectValue placeholder="Filter status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="in_progress">In Progress</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Employee Checklist Table */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        <div className="p-5 border-b border-slate-100">
          <h3 className="text-base font-bold text-slate-900">Employee Operational Setup</h3>
          <p className="text-xs text-slate-500 mt-1">Track workplace readiness for each employee</p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-10 h-10 border-2 border-[#063c88] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : checklists.length === 0 ? (
          <div className="p-12 text-center">
            <ClipboardList className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p className="text-sm text-slate-500">No checklists found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">Employee</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">Department</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">Progress</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">Status</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">Action</th>
                </tr>
              </thead>
              <tbody>
                {checklists.map((cl) => {
                  const progress = getProgress(cl.items);
                  const completedCount = cl.items?.filter(i => i.completed).length || 0;
                  const totalCount = cl.items?.length || 0;
                  const sc = statusConfig[cl.status] || statusConfig.pending;
                  return (
                    <tr key={cl.id} className="border-t border-slate-50 hover:bg-slate-50/50 cursor-pointer" onClick={() => openDetail(cl)} data-testid={`checklist-row-${cl.employee_id}`}>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[#063c88] to-[#0a5cba] flex items-center justify-center">
                            <span className="text-white text-xs font-semibold">{cl.emp_name?.charAt(0)?.toUpperCase()}</span>
                          </div>
                          <div>
                            <p className="font-medium text-slate-900">{cl.emp_name}</p>
                            <p className="text-xs text-slate-400">{cl.employee_id}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <p className="text-slate-700">{cl.department || '-'}</p>
                        <p className="text-xs text-slate-400">{cl.designation || ''}</p>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <div className="w-24 h-2 bg-slate-100 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all ${progress === 100 ? 'bg-emerald-500' : progress > 0 ? 'bg-blue-500' : 'bg-slate-200'}`}
                              style={{ width: `${progress}%` }}
                            />
                          </div>
                          <span className="text-xs text-slate-500 whitespace-nowrap">{completedCount}/{totalCount}</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <Badge className={`${sc.color} border text-xs`}>{sc.label}</Badge>
                      </td>
                      <td className="px-5 py-3.5">
                        <Button variant="ghost" size="sm" className="text-xs h-7 text-blue-600 hover:text-blue-700" data-testid={`review-btn-${cl.employee_id}`}>
                          Review <ChevronRight className="w-3.5 h-3.5 ml-1" />
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail Sheet */}
      <Sheet open={!!selected} onOpenChange={(open) => { if (!open) setSelected(null); }}>
        <SheetContent className="sm:max-w-lg overflow-y-auto" data-testid="checklist-detail-sheet">
          {detailLoading ? (
            <div className="flex items-center justify-center h-full">
              <div className="w-10 h-10 border-2 border-[#063c88] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : selected && (
            <>
              <SheetHeader className="pb-4 border-b border-slate-100">
                <SheetTitle className="text-lg">Operational Setup</SheetTitle>
                <div className="flex items-center gap-3 mt-3">
                  <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[#063c88] to-[#0a5cba] flex items-center justify-center">
                    <span className="text-white text-lg font-semibold">{selected.emp_name?.charAt(0)?.toUpperCase()}</span>
                  </div>
                  <div>
                    <p className="text-base font-semibold text-slate-900">{selected.emp_name}</p>
                    <p className="text-xs text-slate-500">{selected.department} {selected.designation ? `- ${selected.designation}` : ''}</p>
                  </div>
                </div>
                {/* Progress bar */}
                <div className="mt-4">
                  <div className="flex items-center justify-between text-xs text-slate-500 mb-1.5">
                    <span>Completion</span>
                    <span className="font-semibold">{getProgress(selected.items)}%</span>
                  </div>
                  <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${getProgress(selected.items) === 100 ? 'bg-emerald-500' : 'bg-blue-500'}`}
                      style={{ width: `${getProgress(selected.items)}%` }}
                    />
                  </div>
                </div>
              </SheetHeader>

              {/* Checklist Items grouped by category */}
              <div className="mt-6 space-y-5">
                {['Infrastructure', 'Stationery', 'Access', 'IT', 'Coordination'].map(category => {
                  const items = selected.items?.filter(i => i.category === category) || [];
                  if (items.length === 0) return null;
                  const CatIcon = categoryIcons[category] || ClipboardList;
                  return (
                    <div key={category}>
                      <div className="flex items-center gap-2 mb-3">
                        <CatIcon className="w-4 h-4 text-slate-400" />
                        <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">{category}</h4>
                      </div>
                      <div className="space-y-1">
                        {items.map((item) => (
                          <div
                            key={item.key}
                            className={`flex items-start gap-3 p-3 rounded-xl border transition-colors ${item.completed ? 'bg-emerald-50/50 border-emerald-100' : 'bg-white border-slate-100 hover:border-slate-200'}`}
                            data-testid={`checklist-item-${item.key}`}
                          >
                            <button
                              onClick={() => toggleItem(item.key, item.completed)}
                              className="mt-0.5 flex-shrink-0"
                              data-testid={`toggle-${item.key}`}
                            >
                              {item.completed ? (
                                <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                              ) : (
                                <Circle className="w-5 h-5 text-slate-300 hover:text-blue-400 transition-colors" />
                              )}
                            </button>
                            <div className="flex-1 min-w-0">
                              <p className={`text-sm ${item.completed ? 'text-emerald-700 line-through' : 'text-slate-800'}`}>
                                {item.label}
                              </p>
                              {item.completed_by && (
                                <p className="text-[10px] text-slate-400 mt-0.5">
                                  by {item.completed_by} {item.completed_at ? `on ${new Date(item.completed_at).toLocaleDateString()}` : ''}
                                </p>
                              )}
                              {item.notes && (
                                <p className="text-xs text-slate-500 mt-1 bg-slate-50 rounded-lg px-2 py-1">{item.notes}</p>
                              )}
                            </div>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setNoteItem(item.key);
                                setNoteText(item.notes || '');
                              }}
                              className="p-1 hover:bg-slate-100 rounded-lg flex-shrink-0"
                              title="Add note"
                            >
                              <StickyNote className="w-3.5 h-3.5 text-slate-400" />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Note Input */}
              {noteItem && (
                <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-xl">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs font-semibold text-amber-700">Add Note</p>
                    <button onClick={() => setNoteItem(null)}><X className="w-3.5 h-3.5 text-amber-500" /></button>
                  </div>
                  <Textarea
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                    placeholder="Add a note for this item..."
                    className="text-sm min-h-[60px] bg-white"
                    data-testid="note-textarea"
                  />
                  <Button size="sm" onClick={saveNote} className="mt-2 h-7 text-xs bg-amber-600 hover:bg-amber-700 text-white" data-testid="save-note-btn">
                    Save Note
                  </Button>
                </div>
              )}
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
