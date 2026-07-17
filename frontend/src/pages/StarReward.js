import React, { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import EmployeeAvatar from '../components/EmployeeAvatar';
import { Download, Plus, Eye, ArrowLeft, Star, Users, Award, TrendingUp, Trophy, Sparkles, AlertTriangle, Zap, Loader2, CheckCircle2, Pencil, CalendarClock } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { DatePicker } from '../components/ui/date-picker';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { MonthPicker } from '../components/ui/month-picker';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { PageSizeSelector } from '../components/PageSizeSelector';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const getWeeksForMonth = (monthStr) => {
  const [year, month] = monthStr.split('-').map(Number);
  const firstDay = new Date(year, month - 1, 1);
  const lastDay = new Date(year, month, 0);
  const weeks = [];
  let weekStart = new Date(firstDay);
  let weekNum = 1;
  
  while (weekStart <= lastDay && weekNum <= 5) {
    let weekEnd = new Date(weekStart);
    weekEnd.setDate(weekEnd.getDate() + 6);
    if (weekEnd > lastDay) weekEnd = new Date(lastDay);
    weeks.push({
      week: weekNum,
      startDate: weekStart.toISOString().split('T')[0],
      endDate: weekEnd.toISOString().split('T')[0],
      fromDate: weekStart.toISOString().split('T')[0],
      toDate: weekEnd.toISOString().split('T')[0],
      value: '',
      reason: ''
    });
    weekStart = new Date(weekEnd);
    weekStart.setDate(weekStart.getDate() + 1);
    weekNum++;
  }
  while (weeks.length < 5) {
    const lastWeek = weeks[weeks.length - 1];
    const newStart = new Date(lastWeek.endDate);
    newStart.setDate(newStart.getDate() + 1);
    const newEnd = new Date(newStart);
    newEnd.setDate(newEnd.getDate() + 6);
    weeks.push({
      week: weeks.length + 1, startDate: newStart.toISOString().split('T')[0], endDate: newEnd.toISOString().split('T')[0],
      fromDate: newStart.toISOString().split('T')[0], toDate: newEnd.toISOString().split('T')[0], value: '', reason: ''
    });
  }
  return weeks;
};

const StarReward = () => {
  const { getAuthHeaders, user } = useAuth();
  const [employees, setEmployees] = useState([]);
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('employees');
  const [viewMode, setViewMode] = useState('table');
  const [showTeamDetails, setShowTeamDetails] = useState(false);
  const [selectedTeam, setSelectedTeam] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [addFormType, setAddFormType] = useState('performance');
  const [addFormMonth, setAddFormMonth] = useState(new Date().toISOString().slice(0, 7));
  const [weeklyData, setWeeklyData] = useState([]);
  const [simpleFormData, setSimpleFormData] = useState({ value: '', reason: '' });
  const [showViewModal, setShowViewModal] = useState(false);
  const [starHistory, setStarHistory] = useState([]);
  const [monthlyView, setMonthlyView] = useState(null);
  const [expandedViewMonth, setExpandedViewMonth] = useState(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [filters, setFilters] = useState({ team: 'All', month: new Date().toISOString().slice(0, 7), search: '' });
  const [tableFilters, setTableFilters] = useState({ fromMonth: new Date().toISOString().slice(0, 7), toMonth: new Date().toISOString().slice(0, 7), pageSize: 25 });
  const [currentPage, setCurrentPage] = useState(1);
  const [autoCalcEmp, setAutoCalcEmp] = useState(null);
  const [showBulkAuto, setShowBulkAuto] = useState(false);
  const [schedulerStatus, setSchedulerStatus] = useState(null);
  const [editEmp, setEditEmp] = useState(null);
  const [leaveEditEmp, setLeaveEditEmp] = useState(null);

  useEffect(() => { fetchData(); }, []);
  useEffect(() => { if (addFormType === 'performance' || addFormType === 'learning') setWeeklyData(getWeeksForMonth(addFormMonth)); }, [addFormMonth, addFormType]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [employeesRes, teamsRes] = await Promise.all([
        axios.get(`${API}/star-rewards`, { headers: getAuthHeaders(), params: { department: 'Research Unit', team: filters.team !== 'All' ? filters.team : undefined, month: filters.month } }),
        axios.get(`${API}/teams`, { headers: getAuthHeaders(), params: { department: 'Research Unit' } })
      ]);
      setEmployees(employeesRes.data);
      setTeams(teamsRes.data.filter(t => t.department === 'Research Unit'));
      // Non-blocking: fetch scheduler status for the header strip
      axios.get(`${API}/star-rewards/auto/scheduler-status`, { headers: getAuthHeaders() })
        .then(r => setSchedulerStatus(r.data))
        .catch(() => {});
    } catch (error) {
      toast.error('Failed to load star rewards data');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/star-rewards`, { headers: getAuthHeaders(), params: { department: 'Research Unit', team: filters.team !== 'All' ? filters.team : undefined, month: filters.month, search: filters.search || undefined } });
      setEmployees(response.data);
      setCurrentPage(1);
      toast.success('Filters applied');
    } catch (error) {
      toast.error('Failed to apply filters');
    } finally {
      setLoading(false);
    }
  };

  const handleExportCSV = () => {
    let data, headers, filename;
    if (activeTab === 'employees') {
      headers = ['Name', 'Email', 'Team', 'Stars', 'Unsafe'];
      data = filteredEmployees.map(e => [e.name, e.email, e.team, e.stars, e.unsafe_count]);
      filename = `employees-star-rating-${filters.month}.csv`;
    } else {
      headers = ['Team', 'Members', 'Team Stars', 'Avg'];
      data = teamStats.map(t => [t.name, t.members, t.totalStars.toFixed(2), t.avgStars.toFixed(2)]);
      filename = `teams-star-rating-${filters.month}.csv`;
    }
    const csv = [headers, ...data].map(row => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = window.URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    toast.success('CSV exported');
  };

  const handleViewEmployee = async (employee) => {
    setSelectedEmployee(employee);
    setStarHistory([]);
    setMonthlyView(null);
    setExpandedViewMonth(null);
    setLoadingHistory(true);
    setShowViewModal(true);
    try {
      // Fetch BOTH flat history AND month-wise breakdown in parallel.
      const [histRes, monthlyRes] = await Promise.all([
        axios.get(`${API}/star-rewards/history/${employee.id}`, { headers: getAuthHeaders() }),
        axios.get(`${API}/star-rewards/auto/monthly/${employee.id}`, { headers: getAuthHeaders() }).catch(() => null),
      ]);
      setStarHistory(histRes.data);
      if (monthlyRes && monthlyRes.data) {
        setMonthlyView(monthlyRes.data);
        // Auto-expand the most recent month so HR sees a clear per-month view
        const months = monthlyRes.data.months || [];
        if (months.length) setExpandedViewMonth(months[months.length - 1].month);
      }
    } catch (error) {
      setStarHistory([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleAddStars = (employee) => {
    setSelectedEmployee(employee);
    setAddFormType('performance');
    setAddFormMonth(filters.month);
    setWeeklyData(getWeeksForMonth(filters.month));
    setSimpleFormData({ value: '', reason: '' });
    setShowAddForm(true);
  };

  const updateWeekData = (weekIndex, field, value) => {
    setWeeklyData(prev => { const updated = [...prev]; updated[weekIndex] = { ...updated[weekIndex], [field]: value }; return updated; });
  };

  const submitStars = async () => {
    try {
      if (addFormType === 'performance' || addFormType === 'learning') {
        const validWeeks = weeklyData.filter(w => w.value && w.reason);
        if (validWeeks.length === 0) { toast.error('Please fill at least one week'); return; }
        for (const week of validWeeks) {
          await axios.post(`${API}/star-rewards`, { employee_id: selectedEmployee.id, stars: parseInt(week.value), reason: week.reason, type: addFormType, week_number: week.week, from_date: week.fromDate, to_date: week.toDate }, { headers: getAuthHeaders() });
        }
        toast.success(`Stars awarded for ${validWeeks.length} week(s)`);
      } else {
        if (!simpleFormData.value || !simpleFormData.reason) { toast.error('Please fill value and reason'); return; }
        const stars = addFormType === 'unsafe' ? -Math.abs(parseInt(simpleFormData.value)) : parseInt(simpleFormData.value);
        await axios.post(`${API}/star-rewards`, { employee_id: selectedEmployee.id, stars, reason: simpleFormData.reason, type: addFormType }, { headers: getAuthHeaders() });
        toast.success('Stars recorded');
      }
      setShowAddForm(false);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to award stars');
    }
  };

  const canAddStars = ['hr'].includes(user?.role);
  const filteredEmployees = useMemo(() => employees.filter(e => !filters.search || e.name.toLowerCase().includes(filters.search.toLowerCase()) || e.email.toLowerCase().includes(filters.search.toLowerCase())), [employees, filters.search]);
  const paginatedEmployees = useMemo(() => { const start = (currentPage - 1) * tableFilters.pageSize; return filteredEmployees.slice(start, start + tableFilters.pageSize); }, [filteredEmployees, currentPage, tableFilters.pageSize]);
  const totalPages = Math.ceil(filteredEmployees.length / tableFilters.pageSize);
  const teamStats = useMemo(() => teams.map(team => { const teamEmployees = filteredEmployees.filter(e => e.team === team.name); const totalStars = teamEmployees.reduce((sum, e) => sum + (e.stars || 0), 0); return { ...team, members: teamEmployees.length || team.member_count || 0, totalStars, avgStars: teamEmployees.length > 0 ? totalStars / teamEmployees.length : 0, employees: teamEmployees }; }), [teams, filteredEmployees]);
  const totalStars = useMemo(() => filteredEmployees.reduce((sum, e) => sum + (e.stars || 0), 0), [filteredEmployees]);
  const topPerformer = useMemo(() => filteredEmployees.reduce((top, e) => (!top || (e.stars || 0) > (top.stars || 0)) ? e : top, null), [filteredEmployees]);

  // View History Modal — now shows a proper MONTH-BY-MONTH breakdown so HR
  // can clearly see each month's stars separately (fixes the "all months look
  // the same" concern). Expanding a month reveals the individual reward lines.
  const ViewHistoryModal = () => {
    const months = monthlyView?.months || [];
    return (
    <Dialog open={showViewModal} onOpenChange={setShowViewModal}>
      <DialogContent className="bg-[#fffdf7] max-w-3xl rounded-2xl max-h-[85vh] overflow-y-auto" data-testid="view-history-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3" style={{ fontFamily: 'Outfit' }}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg">
              <Star className="w-5 h-5 text-white fill-white" />
            </div>
            Star History - {selectedEmployee?.name}
          </DialogTitle>
          <DialogDescription>
            Month-by-month rollup · {monthlyView?.employee?.date_of_joining && (<>Joined <b>{monthlyView.employee.date_of_joining}</b> · </>)}
            {months.length} month{months.length === 1 ? '' : 's'} of records
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          {/* Summary cards */}
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="p-3 rounded-xl bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-200/50">
              <p className="text-[11px] text-amber-700 uppercase tracking-wide font-semibold">Cumulative Stars</p>
              <p className={`text-2xl font-bold mt-0.5 ${(selectedEmployee?.stars || 0) >= 0 ? 'text-amber-600' : 'text-red-600'}`}>{selectedEmployee?.stars || 0}</p>
            </div>
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/50">
              <p className="text-[11px] text-slate-500 uppercase tracking-wide font-semibold">Unsafe Count</p>
              <p className="text-2xl font-bold text-red-500 mt-0.5">{selectedEmployee?.unsafe_count || 0}</p>
            </div>
            <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200/50">
              <p className="text-[11px] text-emerald-700 uppercase tracking-wide font-semibold">Months Recorded</p>
              <p className="text-2xl font-bold text-emerald-600 mt-0.5">{months.length}</p>
            </div>
          </div>

          {loadingHistory ? (
            <div className="flex items-center justify-center py-10">
              <div className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : months.length === 0 ? (
            <p className="text-center text-slate-500 py-10">No star history yet.</p>
          ) : (
            <div className="space-y-2">
              <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider px-1">Month-by-month breakdown</div>
              {months.map((m) => {
                const isOpen = expandedViewMonth === m.month;
                const isCurrent = m.month === monthlyView?.current_month;
                const [y, mm] = m.month.split('-');
                const mLabel = new Date(Number(y), Number(mm) - 1).toLocaleString('en-IN', { month: 'long', year: 'numeric' });
                return (
                  <div key={m.month} className={`rounded-xl border ${isCurrent ? 'border-amber-300 bg-amber-50/50' : 'border-slate-200 bg-white'}`} data-testid={`admin-month-${m.month}`}>
                    <button
                      type="button"
                      onClick={() => setExpandedViewMonth(isOpen ? null : m.month)}
                      className="w-full flex items-center gap-3 px-4 py-3 text-left"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-semibold text-slate-800">
                          {mLabel}
                          {isCurrent && <span className="ml-2 text-[10px] uppercase font-bold text-amber-700 tracking-wider">Current</span>}
                        </div>
                        <div className="text-[11px] text-slate-500 mt-0.5 flex gap-2 flex-wrap">
                          <span>{m.entries} entr{m.entries === 1 ? 'y' : 'ies'}</span>
                          {m.auto_stars !== 0 && <span>· Auto <b>{m.auto_stars > 0 ? `+${m.auto_stars}` : m.auto_stars}</b></span>}
                          {m.manual_stars !== 0 && <span>· Manual <b>{m.manual_stars > 0 ? `+${m.manual_stars}` : m.manual_stars}</b></span>}
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        {m.positive > 0 && <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-100 rounded px-2 py-0.5">+{m.positive}</span>}
                        {m.negative < 0 && <span className="text-[11px] font-semibold text-rose-700 bg-rose-100 rounded px-2 py-0.5">{m.negative}</span>}
                        <div className={`px-3 py-1 rounded-lg text-sm font-bold ${m.stars > 0 ? 'bg-emerald-50 text-emerald-700' : m.stars < 0 ? 'bg-rose-50 text-rose-700' : 'bg-slate-50 text-slate-700'}`}>
                          {m.stars > 0 ? '+' : ''}{m.stars} <Star className="inline w-3 h-3 fill-current -mt-0.5" />
                        </div>
                        <span className="text-slate-400 text-lg leading-none w-4 text-center">{isOpen ? '−' : '+'}</span>
                      </div>
                    </button>
                    {isOpen && m.items.length > 0 && (
                      <div className="border-t border-slate-200 divide-y divide-slate-100">
                        {m.items.map(it => (
                          <div key={it.id} className="px-4 py-2.5 flex items-start gap-3 text-sm">
                            <span className={`inline-block px-2 py-0.5 rounded font-bold text-[11px] shrink-0 ${it.stars > 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                              {it.stars > 0 ? '+' : ''}{it.stars}
                            </span>
                            <div className="flex-1 min-w-0">
                              <div className="text-[13px] font-medium text-slate-800">{it.category}</div>
                              <div className="text-[11px] text-slate-500 mt-0.5">{it.reason}</div>
                            </div>
                            <div className="text-[11px] text-slate-400 shrink-0 tabular-nums">{it.date}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setShowViewModal(false)} className="rounded-lg">Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-3 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-slate-500 text-sm">Loading star rewards...</p>
        </div>
      </div>
    );
  }

  // ADD FORM VIEW
  if (showAddForm && selectedEmployee) {
    return (
      <>
        <ViewHistoryModal />
        <div className="space-y-6 animate-fade-in" data-testid="star-add-form">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button variant="ghost" onClick={() => setShowAddForm(false)} className="rounded-xl p-2" data-testid="back-btn">
                <ArrowLeft className="w-5 h-5" />
              </Button>
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg">
                <Award className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Award Stars</h1>
                <p className="text-sm text-slate-500">{selectedEmployee.name} • {addFormMonth}</p>
              </div>
            </div>
          </div>

          <div className="card-premium p-6">
            <div className="mb-6">
              <Label className="text-sm font-medium text-slate-700 mb-2 block">Award Type</Label>
              <Select value={addFormType} onValueChange={setAddFormType}>
                <SelectTrigger className="w-64 rounded-lg" data-testid="form-type-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="performance">Performance</SelectItem>
                  <SelectItem value="learning">Learning</SelectItem>
                  <SelectItem value="innovation">Innovation</SelectItem>
                  <SelectItem value="unsafe">Unsafe Conduct</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {(addFormType === 'performance' || addFormType === 'learning') && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mb-6">
                {weeklyData.map((week, index) => (
                  <div key={index} className="p-5 rounded-2xl bg-[#f8f6f0] border border-[#e8e4d9]">
                    <div className="flex items-center justify-between mb-4">
                      <span className="font-semibold text-[#e67e22] text-lg">Week {week.week}</span>
                      <span className="text-xs text-slate-400">{week.startDate} → {week.endDate}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-3 mb-4">
                      <div>
                        <Label className="text-sm text-slate-600 font-medium">From</Label>
                        <DatePicker value={week.fromDate} onChange={(val) => updateWeekData(index, 'fromDate', val)} className="rounded-xl text-sm mt-1.5 bg-white border-slate-200" />
                      </div>
                      <div>
                        <Label className="text-sm text-slate-600 font-medium">To</Label>
                        <DatePicker value={week.toDate} onChange={(val) => updateWeekData(index, 'toDate', val)} className="rounded-xl text-sm mt-1.5 bg-white border-slate-200" />
                      </div>
                    </div>
                    <div className="mb-4">
                      <Label className="text-sm text-slate-600 font-medium">Stars</Label>
                      <Input type="number" value={week.value} onChange={(e) => updateWeekData(index, 'value', e.target.value)} className="rounded-xl mt-1.5 bg-white border-slate-200" placeholder="0" data-testid={`week-${index}-value`} />
                    </div>
                    <div>
                      <Label className="text-sm text-slate-600 font-medium">Reason</Label>
                      <Textarea value={week.reason} onChange={(e) => updateWeekData(index, 'reason', e.target.value)} className="rounded-xl mt-1.5 min-h-[80px] bg-white border-slate-200 resize-none" placeholder="Enter reason..." data-testid={`week-${index}-reason`} />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {(addFormType === 'innovation' || addFormType === 'unsafe') && (
              <div className="max-w-md space-y-4 mb-6">
                <div>
                  <Label className="text-sm font-medium text-slate-700">Month</Label>
                  <Input type="month" value={addFormMonth} onChange={(e) => setAddFormMonth(e.target.value)} className="rounded-lg mt-1.5" data-testid="simple-month" />
                </div>
                <div>
                  <Label className="text-sm font-medium text-slate-700">Stars {addFormType === 'unsafe' && '(will be negative)'}</Label>
                  <Input type="number" value={simpleFormData.value} onChange={(e) => setSimpleFormData(prev => ({ ...prev, value: e.target.value }))} className="rounded-lg mt-1.5" placeholder="Enter value" data-testid="simple-value" />
                </div>
                <div>
                  <Label className="text-sm font-medium text-slate-700">Reason</Label>
                  <Textarea value={simpleFormData.reason} onChange={(e) => setSimpleFormData(prev => ({ ...prev, reason: e.target.value }))} className="rounded-lg mt-1.5 min-h-[100px]" placeholder="Enter reason..." data-testid="simple-reason" />
                </div>
              </div>
            )}

            <div className="flex gap-3 pt-4 border-t border-slate-100">
              <Button onClick={submitStars} className="bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white rounded-lg shadow-lg shadow-amber-500/20" data-testid="save-btn">
                <Star className="w-4 h-4 mr-2 fill-white" /> Save Stars
              </Button>
              <Button variant="outline" onClick={() => setShowAddForm(false)} className="rounded-lg" data-testid="cancel-btn">Cancel</Button>
            </div>
          </div>
        </div>
      </>
    );
  }

  // TEAM DETAILS VIEW
  if (showTeamDetails && selectedTeam) {
    return (
      <>
        <ViewHistoryModal />
        <div className="space-y-6 animate-fade-in" data-testid="team-details-view">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button variant="ghost" onClick={() => { setShowTeamDetails(false); setSelectedTeam(null); }} className="rounded-xl p-2">
                <ArrowLeft className="w-5 h-5" />
              </Button>
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg">
                <Users className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>{selectedTeam.name}</h1>
                <p className="text-sm text-slate-500">{selectedTeam.members} members • {selectedTeam.totalStars} total stars</p>
              </div>
            </div>
          </div>

          <div className="card-premium overflow-hidden">
            <div className="overflow-x-auto">
              <table className="table-premium">
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Email</th>
                    <th className="text-center">Stars</th>
                    <th className="text-center">Unsafe</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedTeam.employees?.length === 0 ? (
                    <tr><td colSpan="5" className="text-center py-12 text-slate-500">No team members found</td></tr>
                  ) : (
                    selectedTeam.employees?.map((emp) => (
                      <tr key={emp.id}>
                        <td>
                          <div className="flex items-center gap-3">
                            <EmployeeAvatar employeeId={emp.id} name={emp.name} size="sm" shape="circle" />
                            <span className="font-medium text-slate-900">{emp.name}</span>
                          </div>
                        </td>
                        <td className="text-slate-600">{emp.email}</td>
                        <td className="text-center">
                          <Badge className={`${(emp.stars || 0) >= 0 ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
                            {emp.stars || 0} <Star className="w-3 h-3 ml-1 fill-current" />
                          </Badge>
                        </td>
                        <td className="text-center">{emp.unsafe_count > 0 ? <Badge className="badge-error">{emp.unsafe_count}</Badge> : <span className="text-slate-400">0</span>}</td>
                        <td>
                          <div className="flex gap-1">
                            <Button size="sm" variant="ghost" onClick={() => handleViewEmployee(emp)} className="h-8 w-8 p-0 rounded-lg" data-testid={`view-history-${emp.id}`}>
                              <Eye className="w-4 h-4 text-slate-500" />
                            </Button>
                            {canAddStars && emp.department === 'Research Unit' && (
                              <Button size="sm" variant="ghost" onClick={() => setAutoCalcEmp(emp)} className="h-8 w-8 p-0 rounded-lg" data-testid={`auto-calc-${emp.id}`} title="Auto-Calculate stars per policy">
                                <Zap className="w-4 h-4 text-amber-500" />
                              </Button>
                            )}
                            {canAddStars && (
                              <Button size="sm" variant="ghost" onClick={() => handleAddStars(emp)} className="h-8 w-8 p-0 rounded-lg" data-testid={`add-stars-${emp.id}`} title="Add manual reward">
                                <Plus className="w-4 h-4 text-amber-500" />
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </>
    );
  }

  // MAIN VIEW
  return (
    <>
      <ViewHistoryModal />
      <div className="space-y-6 animate-fade-in" data-testid="star-reward-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg shadow-amber-500/20">
              <Trophy className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Star Rewards</h1>
              <p className="text-sm text-slate-500">Research Unit • {filters.month}</p>
            </div>
          </div>
          <div className="flex gap-2">
            {canAddStars && (
              <Button onClick={() => setShowBulkAuto(true)} className="rounded-xl bg-amber-500 hover:bg-amber-600 text-white" data-testid="bulk-auto-btn" title="Auto-Calculate stars for ALL Research Unit employees using each one's joining date">
                <Zap className="w-4 h-4 mr-2" /> Auto-Calculate All
              </Button>
            )}
            <Button onClick={handleExportCSV} variant="outline" className="rounded-xl" data-testid="export-csv-btn">
              <Download className="w-4 h-4 mr-2" /> Export
            </Button>
          </div>
        </div>

        {/* Daily auto-recompute status strip */}
        {canAddStars && schedulerStatus && (
          <div className="rounded-xl border border-slate-200 bg-gradient-to-r from-amber-50 to-white px-4 py-2 flex items-center gap-3 text-xs flex-wrap" data-testid="scheduler-status-strip">
            <span className={`w-2 h-2 rounded-full ${schedulerStatus.last_run_result === 'success' ? 'bg-emerald-500' : schedulerStatus.last_run_at ? 'bg-amber-500' : 'bg-slate-400'} animate-pulse`}/>
            <span className="font-semibold text-slate-700">Auto-recompute:</span>
            {schedulerStatus.last_run_at ? (
              <>
                <span className="text-slate-600">Last ran {new Date(schedulerStatus.last_run_at).toLocaleString('en-IN')}</span>
                <span className="text-slate-400">·</span>
                <span className="text-slate-600">Through <b>{schedulerStatus.last_run_end_date}</b></span>
                <span className="text-slate-400">·</span>
                <span className="text-slate-600"><b>{schedulerStatus.last_run_processed}</b> employees · <b>{schedulerStatus.last_run_entries}</b> entries · <b className={schedulerStatus.last_run_result === 'success' ? 'text-emerald-700' : 'text-amber-700'}>{schedulerStatus.last_run_result}</b></span>
              </>
            ) : (
              <span className="text-slate-500">Not run yet — daily job runs at 02:00 IST. Click &ldquo;Auto-Calculate All&rdquo; for the first sync.</span>
            )}
            <span className="ml-auto text-[10px] text-slate-500 italic">Runs automatically every day at 02:00 IST · Manual awards never touched</span>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Total Stars', value: totalStars, icon: Star, gradient: 'from-amber-400 to-orange-500' },
            { label: 'Total Employees', value: filteredEmployees.length, icon: Users, gradient: 'from-blue-500 to-indigo-600' },
            { label: 'Teams', value: teams.length, icon: Users, gradient: 'from-emerald-500 to-teal-600' },
            { label: 'Top Performer', value: topPerformer?.name?.split(' ')[0] || '-', icon: Trophy, gradient: 'from-purple-500 to-pink-500', subValue: topPerformer ? `${topPerformer.stars} stars` : '' },
          ].map((stat, i) => (
            <div key={i} className="stat-card">
              <div className="flex items-center gap-4">
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${stat.gradient} flex items-center justify-center shadow-lg`}>
                  <stat.icon className="w-6 h-6 text-white" strokeWidth={1.5} />
                </div>
                <div>
                  <p className="text-2xl font-bold text-slate-900 number-display">{stat.value}</p>
                  <p className="text-xs text-slate-500">{stat.label}</p>
                  {stat.subValue && <p className="text-xs text-amber-600 font-medium">{stat.subValue}</p>}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="card-flat p-6">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <Label className="text-sm text-slate-600 mb-1.5 block">Team</Label>
              <Select value={filters.team} onValueChange={(v) => setFilters({ ...filters, team: v })}>
                <SelectTrigger className="w-40 rounded-lg" data-testid="filter-team"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="All">All Teams</SelectItem>
                  {teams.map((team) => <SelectItem key={team.id} value={team.name}>{team.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-sm text-slate-600 mb-1.5 block">Month</Label>
              <MonthPicker value={filters.month} onChange={(v) => setFilters({ ...filters, month: v })} className="w-36" data-testid="filter-month" />
            </div>
            <div>
              <Label className="text-sm text-slate-600 mb-1.5 block">Search</Label>
              <Input placeholder="Name or email..." value={filters.search} onChange={(e) => setFilters({ ...filters, search: e.target.value })} className="w-48 rounded-lg" data-testid="filter-search" />
            </div>
            <Button onClick={handleApply} className="bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white rounded-lg shadow-lg shadow-amber-500/20" data-testid="apply-btn">
              Apply
            </Button>
          </div>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="bg-slate-100 p-1 rounded-xl">
            <TabsTrigger value="employees" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm px-6" data-testid="tab-employees">
              <Users className="w-4 h-4 mr-2" /> Employees
            </TabsTrigger>
            <TabsTrigger value="teams" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm px-6" data-testid="tab-teams">
              <Award className="w-4 h-4 mr-2" /> Teams
            </TabsTrigger>
          </TabsList>

          <TabsContent value="employees" className="mt-4">
            {/* View Toggle */}
            <div className="flex justify-end mb-4">
              <div className="flex rounded-lg overflow-hidden border border-slate-200">
                <Button variant={viewMode === 'table' ? 'default' : 'ghost'} onClick={() => setViewMode('table')} className={`rounded-none px-4 ${viewMode === 'table' ? 'bg-[#063c88] text-white' : ''}`} size="sm">Table</Button>
                <Button variant={viewMode === 'grid' ? 'default' : 'ghost'} onClick={() => setViewMode('grid')} className={`rounded-none px-4 ${viewMode === 'grid' ? 'bg-[#063c88] text-white' : ''}`} size="sm">Grid</Button>
              </div>
            </div>

            {viewMode === 'table' ? (
              <div className="card-premium overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="table-premium">
                    <thead>
                      <tr>
                        <th>Employee</th>
                        <th>Email</th>
                        <th>Team</th>
                        <th className="text-center" title={filters.month ? `Stars earned in ${filters.month}` : 'Cumulative stars'}>
                          Stars {filters.month && <span className="text-[10px] font-normal text-slate-500 block leading-none">({filters.month})</span>}
                        </th>
                        <th className="text-center">Unsafe</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {paginatedEmployees.length === 0 ? (
                        <tr><td colSpan="6" className="text-center py-12 text-slate-500">No employees found</td></tr>
                      ) : (
                        paginatedEmployees.map((emp) => (
                          <tr key={emp.id}>
                            <td>
                              <div className="flex items-center gap-3">
                                <EmployeeAvatar employeeId={emp.id} name={emp.name} size="sm" shape="circle" />
                                <span className="font-medium text-slate-900">{emp.name}</span>
                              </div>
                            </td>
                            <td className="text-slate-600">{emp.email}</td>
                            <td className="text-slate-600">{emp.team}</td>
                            <td className="text-center">
                              <Badge className={`${(emp.stars || 0) >= 0 ? 'bg-amber-100 text-amber-700 border-amber-200' : 'bg-red-100 text-red-700 border-red-200'}`}>
                                {emp.stars || 0} <Star className="w-3 h-3 ml-1 fill-current" />
                              </Badge>
                            </td>
                            <td className="text-center">{emp.unsafe_count > 0 ? <Badge className="badge-error">{emp.unsafe_count}</Badge> : <span className="text-slate-400">0</span>}</td>
                            <td>
                              <div className="flex gap-1">
                                <Button size="sm" variant="ghost" onClick={() => handleViewEmployee(emp)} className="h-8 w-8 p-0 rounded-lg" data-testid={`view-history-${emp.id}`}>
                                  <Eye className="w-4 h-4 text-slate-500" />
                                </Button>
                                {canAddStars && emp.department === 'Research Unit' && (
                                  <Button size="sm" variant="ghost" onClick={() => setAutoCalcEmp(emp)} className="h-8 w-8 p-0 rounded-lg" data-testid={`auto-calc-${emp.id}`} title="Auto-Calculate stars per policy">
                                    <Zap className="w-4 h-4 text-amber-500" />
                                  </Button>
                                )}
                                {canAddStars && (
                                  <Button size="sm" variant="ghost" onClick={() => setEditEmp(emp)} className="h-8 w-8 p-0 rounded-lg" data-testid={`edit-stars-${emp.id}`} title="Edit stars / flags">
                                    <Pencil className="w-4 h-4 text-indigo-500" />
                                  </Button>
                                )}
                                {canAddStars && (
                                  <Button size="sm" variant="ghost" onClick={() => setLeaveEditEmp(emp)} className="h-8 w-8 p-0 rounded-lg" data-testid={`leave-adjust-${emp.id}`} title="Adjust stars for a leave instance">
                                    <CalendarClock className="w-4 h-4 text-blue-500" />
                                  </Button>
                                )}
                                {canAddStars && (
                                  <Button size="sm" variant="ghost" onClick={() => handleAddStars(emp)} className="h-8 w-8 p-0 rounded-lg" data-testid={`add-stars-${emp.id}`} title="Add manual reward">
                                    <Plus className="w-4 h-4 text-amber-500" />
                                  </Button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
                {filteredEmployees.length > 0 && (
                  <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/50">
                    <div className="flex items-center gap-4">
                      <p className="text-sm text-slate-500">
                        Showing {filteredEmployees.length === 0 ? 0 : ((currentPage - 1) * tableFilters.pageSize) + 1}–{Math.min(currentPage * tableFilters.pageSize, filteredEmployees.length)} of {filteredEmployees.length}
                      </p>
                      <PageSizeSelector
                        value={tableFilters.pageSize}
                        onChange={(v) => { setTableFilters(prev => ({ ...prev, pageSize: v })); setCurrentPage(1); }}
                        testId="star-reward-rows-per-page"
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <Button size="sm" variant="outline" disabled={currentPage <= 1} onClick={() => setCurrentPage(p => p - 1)} className="rounded-lg">Prev</Button>
                      <span className="text-sm text-slate-600 px-3">Page {currentPage} of {totalPages}</span>
                      <Button size="sm" variant="outline" disabled={currentPage >= totalPages} onClick={() => setCurrentPage(p => p + 1)} className="rounded-lg">Next</Button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {paginatedEmployees.map((emp, index) => (
                  <div key={emp.id} className="p-5 rounded-xl bg-gradient-to-br from-[#fffdf7] to-amber-50/30 border border-amber-200/30 hover:border-amber-300 hover:shadow-lg transition-all animate-slide-up" style={{ animationDelay: `${index * 0.03}s` }}>
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <EmployeeAvatar employeeId={emp.id} name={emp.name} size="md" shape="square" className="shadow-lg" />
                        <div>
                          <p className="font-semibold text-slate-900">{emp.name}</p>
                          <p className="text-xs text-slate-500">{emp.team}</p>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between pt-4 border-t border-amber-200/50">
                      <div className="flex items-center gap-2">
                        <Star className="w-5 h-5 text-amber-500 fill-amber-500" />
                        <span className={`text-xl font-bold ${(emp.stars || 0) >= 0 ? 'text-amber-600' : 'text-red-600'}`}>{emp.stars || 0}</span>
                      </div>
                      <div className="flex gap-1">
                        <Button size="sm" variant="ghost" onClick={() => handleViewEmployee(emp)} className="h-8 w-8 p-0 rounded-lg" data-testid={`grid-view-${emp.id}`}>
                          <Eye className="w-4 h-4 text-slate-500" />
                        </Button>
                        {canAddStars && emp.department === 'Research Unit' && (
                          <Button size="sm" variant="ghost" onClick={() => setAutoCalcEmp(emp)} className="h-8 w-8 p-0 rounded-lg" data-testid={`grid-auto-${emp.id}`} title="Auto-Calculate">
                            <Zap className="w-4 h-4 text-amber-500" />
                          </Button>
                        )}
                        {canAddStars && (
                          <Button size="sm" variant="ghost" onClick={() => handleAddStars(emp)} className="h-8 w-8 p-0 rounded-lg" data-testid={`grid-add-${emp.id}`}>
                            <Plus className="w-4 h-4 text-amber-500" />
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="teams" className="mt-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {teamStats.map((team, index) => (
                <div key={team.id} className="p-5 rounded-xl bg-gradient-to-br from-[#fffdf7] to-amber-50/30 border border-amber-200/30 hover:border-amber-300 hover:shadow-lg transition-all animate-slide-up" style={{ animationDelay: `${index * 0.05}s` }}>
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="font-semibold text-lg text-slate-900" style={{ fontFamily: 'Outfit' }}>{team.name}</h3>
                      <p className="text-xs text-slate-500">{team.members} members</p>
                    </div>
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg">
                      <Users className="w-5 h-5 text-white" />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div className="p-3 rounded-lg bg-white/70">
                      <p className="text-xs text-slate-500">Total Stars</p>
                      <p className="text-xl font-bold text-amber-600">{team.totalStars.toFixed(0)}</p>
                    </div>
                    <div className="p-3 rounded-lg bg-white/70">
                      <p className="text-xs text-slate-500">Avg / Member</p>
                      <p className="text-xl font-bold text-slate-900">{team.avgStars.toFixed(1)}</p>
                    </div>
                  </div>
                  <Button onClick={() => { setSelectedTeam(team); setShowTeamDetails(true); }} className="w-full bg-white/80 hover:bg-white text-slate-700 border border-amber-200 rounded-lg" data-testid={`view-team-${team.id}`}>
                    <Eye className="w-4 h-4 mr-2" /> View Members
                  </Button>
                </div>
              ))}
            </div>
          </TabsContent>
        </Tabs>
      </div>
      {autoCalcEmp && (
        <AutoStarDialog
          employee={autoCalcEmp}
          onClose={() => setAutoCalcEmp(null)}
          onApplied={() => { setAutoCalcEmp(null); fetchData(); }}
          getAuthHeaders={getAuthHeaders}
        />
      )}
      {showBulkAuto && (
        <BulkAutoStarDialog
          onClose={() => setShowBulkAuto(false)}
          onApplied={() => { setShowBulkAuto(false); fetchData(); }}
          getAuthHeaders={getAuthHeaders}
        />
      )}
      {editEmp && (
        <EditStarsDialog
          employee={editEmp}
          onClose={() => setEditEmp(null)}
          onApplied={() => { setEditEmp(null); fetchData(); }}
          getAuthHeaders={getAuthHeaders}
        />
      )}
      {leaveEditEmp && (
        <LeaveAdjustDialog
          employee={leaveEditEmp}
          onClose={() => setLeaveEditEmp(null)}
          onApplied={() => fetchData()}
          getAuthHeaders={getAuthHeaders}
        />
      )}
    </>
  );
};

// ---------------------------------------------------------------------------
// Auto-Calculate Stars Dialog — Research Unit only. Fetches a policy-driven
// breakdown of stars for [start_date, today], HR reviews, then Apply persists.
// ---------------------------------------------------------------------------
function AutoStarDialog({ employee, onClose, onApplied, getAuthHeaders }) {
  const today = new Date().toISOString().slice(0, 10);
  const defaultStart = employee.join_date || (() => {
    const d = new Date(); d.setMonth(d.getMonth() - 3); return d.toISOString().slice(0, 10);
  })();
  const [startDate, setStartDate] = React.useState(defaultStart);
  const [endDate, setEndDate] = React.useState(today);
  const [preview, setPreview] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [applying, setApplying] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.post(`${API}/star-rewards/auto/preview`,
        { employee_id: employee.id, start_date: startDate, end_date: endDate },
        { headers: getAuthHeaders() });
      setPreview(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Preview failed');
      setPreview(null);
    } finally { setLoading(false); }
  }, [employee.id, startDate, endDate, getAuthHeaders]);

  React.useEffect(() => { load(); }, [load]);

  const apply = async () => {
    if (!preview?.breakdown?.length) return toast.error('Nothing to apply');
    if (!window.confirm(`Apply ${preview.breakdown.length} auto-calculated entries (${preview.total_stars >= 0 ? '+' : ''}${preview.total_stars} stars) for ${employee.full_name}?\n\nThis will REPLACE any previous automatic entries for this date range but will NOT touch manual awards.`)) return;
    setApplying(true);
    try {
      const r = await axios.post(`${API}/star-rewards/auto/apply`,
        { employee_id: employee.id, start_date: startDate, end_date: endDate },
        { headers: getAuthHeaders() });
      toast.success(`Applied ${r.data.applied} entries · Total stars now ${r.data.total_stars}`);
      onApplied();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Apply failed');
    } finally { setApplying(false); }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="auto-star-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-amber-500" />
            Auto-Calculate Stars · {employee.full_name}
          </DialogTitle>
        </DialogHeader>

        {/* Range picker */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label className="text-xs font-semibold text-slate-600">Start Date</Label>
            <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} max={endDate} className="mt-1 rounded-lg" data-testid="auto-start-date" />
          </div>
          <div>
            <Label className="text-xs font-semibold text-slate-600">End Date</Label>
            <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} min={startDate} max={today} className="mt-1 rounded-lg" data-testid="auto-end-date" />
          </div>
        </div>

        {/* Policy summary strip */}
        <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 text-xs text-blue-900">
          <div className="font-semibold mb-1">Policy-driven — BluBridge Research Star Framework</div>
          <div className="text-blue-800">This computes stars from attendance and leave records per the policy: full monthly attendance (+2), 10+ hrs weekly avg (+1), uninformed absences (−2 each), &gt;4 monthly absences (−4), &gt;2 emergency leaves/month (−3), late sick notification (−1), and consecutive-day engagement/commitment shortfalls (§10). <b>Manual awards remain untouched.</b></div>
        </div>

        {loading ? (
          <div className="p-10 text-center text-slate-500"><Loader2 className="w-6 h-6 animate-spin inline mr-2" />Computing per policy…</div>
        ) : !preview ? (
          <div className="p-6 text-center text-rose-600">Failed to load preview.</div>
        ) : (
          <>
            {/* Summary cards */}
            <div className="grid grid-cols-4 gap-3">
              <div className="p-3 rounded-lg bg-white border border-slate-200 text-center">
                <div className="text-[11px] text-slate-500">Net Stars</div>
                <div className={`text-2xl font-bold ${preview.total_stars > 0 ? 'text-emerald-600' : preview.total_stars < 0 ? 'text-rose-600' : 'text-slate-700'}`} data-testid="auto-total-stars">
                  {preview.total_stars > 0 ? '+' : ''}{preview.total_stars}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-center">
                <div className="text-[11px] text-emerald-700">Positive</div>
                <div className="text-2xl font-bold text-emerald-600">+{preview.positive_stars}</div>
              </div>
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-center">
                <div className="text-[11px] text-rose-700">Deductions</div>
                <div className="text-2xl font-bold text-rose-600">{preview.negative_stars}</div>
              </div>
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-center">
                <div className="text-[11px] text-slate-500">Days Evaluated</div>
                <div className="text-2xl font-bold text-slate-700">{preview.meta?.attendance_days_evaluated ?? 0}</div>
              </div>
            </div>

            {/* Breakdown */}
            {preview.breakdown.length === 0 ? (
              <div className="p-8 text-center border border-dashed border-slate-300 rounded-xl">
                <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto" />
                <p className="mt-2 text-sm text-slate-700 font-medium">No policy triggers in this range.</p>
                <p className="text-xs text-slate-500 mt-1">The employee has no attendance/leave events matching any auto-computed rule between the selected dates.</p>
              </div>
            ) : (
              <div className="border border-slate-200 rounded-xl overflow-hidden max-h-[380px] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 sticky top-0 z-10">
                    <tr className="text-left text-[11px] uppercase tracking-wider text-slate-500">
                      <th className="px-3 py-2">Date</th>
                      <th className="px-3 py-2">Category</th>
                      <th className="px-3 py-2">Event</th>
                      <th className="px-3 py-2 text-center">Stars</th>
                      <th className="px-3 py-2">Remarks</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {preview.breakdown.map(x => (
                      <tr key={x.id} className={x.stars > 0 ? 'bg-emerald-50/30' : 'bg-rose-50/30'}>
                        <td className="px-3 py-2 whitespace-nowrap font-mono text-[12px]">{x.date}</td>
                        <td className="px-3 py-2 text-[12px]">{x.category}</td>
                        <td className="px-3 py-2 text-[12px]">{x.event}</td>
                        <td className="px-3 py-2 text-center">
                          <span className={`inline-block px-2 py-0.5 rounded font-bold ${x.stars > 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                            {x.stars > 0 ? '+' : ''}{x.stars}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-[11px] text-slate-500">{x.remarks}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        <div className="flex flex-wrap justify-end gap-2 pt-4 mt-4 -mx-6 -mb-6 px-6 py-4 border-t border-slate-200 sticky bottom-0 bg-white/95 backdrop-blur-sm rounded-b-lg shadow-[0_-4px_12px_-4px_rgba(15,23,42,0.08)]">
          <Button variant="outline" className="rounded-lg h-9 px-4" onClick={onClose} disabled={applying}>Close</Button>
          <Button variant="outline" className="rounded-lg h-9 px-4" onClick={load} disabled={loading || applying}>
            <Loader2 className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />Recompute
          </Button>
          <Button
            className="rounded-lg h-9 px-5 bg-amber-500 hover:bg-amber-600 shadow-sm"
            onClick={apply}
            disabled={applying || loading || !preview?.breakdown?.length}
            data-testid="auto-apply-btn"
          >
            <Zap className="w-4 h-4 mr-1.5"/>{applying ? 'Applying…' : 'Apply Auto-Awards'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default StarReward;

// ---------------------------------------------------------------------------
// Edit Stars & Flags Dialog — HR manual override. Recorded as a single audit
// row with `source: 'manual_adjustment'` so re-runs of the auto policy never
// touch it. Supports Increase / Decrease / Reset-to-zero for both stars and
// the flag (unsafe) counter. A note is mandatory for accountability.
// ---------------------------------------------------------------------------
function EditStarsDialog({ employee, onClose, onApplied, getAuthHeaders }) {
  const [starMode, setStarMode] = React.useState('increase');
  const [starValue, setStarValue] = React.useState('');
  const [flagMode, setFlagMode] = React.useState('none');
  const [flagValue, setFlagValue] = React.useState('');
  const [note, setNote] = React.useState('');
  const [saving, setSaving] = React.useState(false);

  const previewStar = React.useMemo(() => {
    const cur = Number(employee.stars || 0);
    const v = Number(starValue || 0);
    if (starMode === 'increase') return { delta: v, next: cur + v };
    if (starMode === 'decrease') return { delta: -v, next: cur - v };
    if (starMode === 'set_zero') return { delta: -cur, next: 0 };
    return { delta: 0, next: cur };
  }, [starMode, starValue, employee.stars]);
  const previewFlag = React.useMemo(() => {
    const cur = Number(employee.unsafe_count || 0);
    const v = Number(flagValue || 0);
    if (flagMode === 'increase') return { delta: v, next: cur + v };
    if (flagMode === 'decrease') return { delta: -v, next: Math.max(0, cur - v) };
    if (flagMode === 'set_zero') return { delta: -cur, next: 0 };
    return { delta: 0, next: cur };
  }, [flagMode, flagValue, employee.unsafe_count]);

  const submit = async () => {
    if (starMode === 'none' && flagMode === 'none') return toast.error('Pick an action for stars or flags');
    if ((starMode === 'increase' || starMode === 'decrease') && (!starValue || Number(starValue) <= 0)) return toast.error('Enter a positive star value');
    if ((flagMode === 'increase' || flagMode === 'decrease') && (!flagValue || Number(flagValue) <= 0)) return toast.error('Enter a positive flag value');
    if (!note.trim()) return toast.error('Please add a note explaining this adjustment');
    setSaving(true);
    try {
      const r = await axios.post(`${API}/star-rewards/adjust`, {
        employee_id: employee.id,
        star_mode: starMode, star_value: starMode === 'set_zero' || starMode === 'none' ? 0 : Number(starValue),
        flag_mode: flagMode, flag_value: flagMode === 'set_zero' || flagMode === 'none' ? 0 : Number(flagValue),
        note: note.trim(),
      }, { headers: getAuthHeaders() });
      toast.success(`Saved · Stars ${r.data.new_stars} · Flags ${r.data.new_unsafe}`);
      onApplied();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Adjustment failed');
    } finally { setSaving(false); }
  };

  const ModePills = ({ mode, setMode, testidPrefix }) => (
    <div className="flex gap-1.5 flex-wrap">
      {[
        { k: 'increase',  label: 'Increase',    cls: 'bg-emerald-500 hover:bg-emerald-600' },
        { k: 'decrease',  label: 'Decrease',    cls: 'bg-rose-500 hover:bg-rose-600' },
        { k: 'set_zero',  label: 'Set to 0',    cls: 'bg-slate-500 hover:bg-slate-600' },
        { k: 'none',      label: 'No change',   cls: 'bg-slate-300 hover:bg-slate-400 text-slate-700' },
      ].map(m => (
        <button key={m.k}
          onClick={() => setMode(m.k)}
          data-testid={`${testidPrefix}-${m.k}`}
          className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold transition ${mode === m.k ? `${m.cls} text-white shadow-sm` : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>
          {m.label}
        </button>
      ))}
    </div>
  );

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="edit-stars-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Pencil className="w-5 h-5 text-indigo-500" />
            Edit Stars &amp; Flags · {employee.full_name || employee.name}
          </DialogTitle>
        </DialogHeader>

        {/* Current state summary */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 rounded-xl bg-amber-50 border border-amber-200">
            <div className="text-[11px] text-amber-700 uppercase tracking-wide font-semibold">Current Stars</div>
            <div className="text-2xl font-bold text-amber-700 mt-0.5">{employee.stars ?? 0} <Star className="inline w-4 h-4 fill-current -mt-0.5"/></div>
          </div>
          <div className="p-3 rounded-xl bg-rose-50 border border-rose-200">
            <div className="text-[11px] text-rose-700 uppercase tracking-wide font-semibold">Current Flags</div>
            <div className="text-2xl font-bold text-rose-700 mt-0.5">{employee.unsafe_count ?? 0} <AlertTriangle className="inline w-4 h-4 -mt-0.5"/></div>
          </div>
        </div>

        {/* Star adjustment */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold text-slate-700">Star Value</div>
            {starMode !== 'none' && starMode !== 'set_zero' && (
              <div className="text-[11px] text-slate-500">New total: <b className={previewStar.next > (employee.stars || 0) ? 'text-emerald-600' : previewStar.next < (employee.stars || 0) ? 'text-rose-600' : 'text-slate-700'}>{previewStar.next}</b></div>
            )}
            {starMode === 'set_zero' && (<div className="text-[11px] text-slate-500">New total: <b className="text-slate-700">0</b></div>)}
          </div>
          <ModePills mode={starMode} setMode={setStarMode} testidPrefix="star-mode" />
          {(starMode === 'increase' || starMode === 'decrease') && (
            <Input type="number" min="1" placeholder="Value (e.g. 5)" value={starValue} onChange={e => setStarValue(e.target.value)} className="rounded-lg" data-testid="star-value-input"/>
          )}
        </div>

        {/* Flag adjustment */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold text-slate-700">Flag (Unsafe) Value</div>
            {flagMode !== 'none' && flagMode !== 'set_zero' && (
              <div className="text-[11px] text-slate-500">New total: <b>{previewFlag.next}</b></div>
            )}
            {flagMode === 'set_zero' && (<div className="text-[11px] text-slate-500">New total: <b>0</b></div>)}
          </div>
          <ModePills mode={flagMode} setMode={setFlagMode} testidPrefix="flag-mode" />
          {(flagMode === 'increase' || flagMode === 'decrease') && (
            <Input type="number" min="1" placeholder="Value (e.g. 1)" value={flagValue} onChange={e => setFlagValue(e.target.value)} className="rounded-lg" data-testid="flag-value-input"/>
          )}
        </div>

        {/* Note */}
        <div>
          <Label className="text-xs font-semibold text-slate-600">Note / Reason *</Label>
          <textarea
            className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm"
            rows={3}
            placeholder="Explain the reason for this adjustment. Visible in the audit trail."
            value={note}
            onChange={e => setNote(e.target.value)}
            data-testid="edit-note-input"
          />
        </div>

        <div className="text-[11px] text-slate-500 italic p-2 rounded bg-slate-50 border border-slate-200">
          Manual adjustments are stored as an audit row with <b>source: manual_adjustment</b> and are <b>never overwritten</b> by the daily auto-recompute.
        </div>

        <div className="flex flex-wrap justify-end gap-2 pt-4 mt-4 -mx-6 -mb-6 px-6 py-4 border-t border-slate-200 sticky bottom-0 bg-white/95 backdrop-blur-sm rounded-b-lg shadow-[0_-4px_12px_-4px_rgba(15,23,42,0.08)]">
          <Button variant="outline" className="rounded-lg h-9 px-4" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button
            className="rounded-lg h-9 px-5 bg-indigo-500 hover:bg-indigo-600"
            onClick={submit}
            disabled={saving}
            data-testid="edit-submit-btn"
          >
            {saving ? <><Loader2 className="w-4 h-4 mr-1.5 animate-spin"/>Saving…</> : 'Submit'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Bulk Auto-Calculate Dialog — runs the automation for EVERY active Research
// Unit employee, using each employee's own date_of_joining as the start.
// Idempotent per-employee: prior auto rows in the same range are replaced.
// Manual awards are never touched.
// ---------------------------------------------------------------------------
function BulkAutoStarDialog({ onClose, onApplied, getAuthHeaders }) {
  const today = new Date().toISOString().slice(0, 10);
  const [endDate, setEndDate] = React.useState(today);
  const [running, setRunning] = React.useState(false);
  const [result, setResult] = React.useState(null);

  const run = async () => {
    if (!window.confirm("This will auto-compute stars for ALL active Research Unit employees using each employee's joining date → the selected end date.\n\nManual awards will NOT be affected. Prior auto entries in the same range will be replaced.\n\nContinue?")) return;
    setRunning(true); setResult(null);
    try {
      const r = await axios.post(`${API}/star-rewards/auto/bulk-apply`,
        { end_date: endDate },
        { headers: getAuthHeaders(), timeout: 120000 });
      setResult(r.data);
      toast.success(`Processed ${r.data.processed} employees · ${r.data.total_entries_applied} entries applied`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Bulk apply failed');
    } finally { setRunning(false); }
  };

  const perEmployeeSorted = React.useMemo(() => {
    if (!result?.per_employee) return [];
    return [...result.per_employee].sort((a, b) => (b.total_stars ?? -999) - (a.total_stars ?? -999));
  }, [result]);

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto" data-testid="bulk-auto-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-amber-500" />
            Auto-Calculate Stars for All Research Unit Employees
          </DialogTitle>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
            <div className="text-[11px] font-semibold text-slate-600">Start Date (per employee)</div>
            <div className="text-sm font-medium text-slate-800 mt-0.5">Each employee&apos;s own <b>Date of Joining</b></div>
            <div className="text-[11px] text-slate-500 mt-0.5">Employees without a joining date fall back to <b>2026-01-01</b>.</div>
          </div>
          <div>
            <Label className="text-xs font-semibold text-slate-600">End Date (applied to all)</Label>
            <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} max={today} className="mt-1 rounded-lg" data-testid="bulk-end-date" />
          </div>
        </div>

        {/* Policy notice */}
        <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 text-xs text-blue-900">
          <div className="font-semibold mb-1">Policy — BluBridge Research Star Framework</div>
          <div>Uses each employee&apos;s <b>joining date → the end date</b>. Runs the same rules used per-employee: full monthly attendance (+2), 10+ hrs weekly avg (+1), uninformed absences (−2), &gt;4 monthly absences (−4), &gt;2 emergency leaves/month (−3), late sick notification (−1), and consecutive-day engagement/commitment shortfalls (§10). <b>Manual awards remain untouched.</b></div>
        </div>

        {!result ? (
          <div className="p-10 text-center text-slate-600">
            {running ? (
              <>
                <Loader2 className="w-8 h-8 animate-spin mx-auto text-amber-500" />
                <p className="mt-3 font-semibold">Running policy across every Research Unit employee…</p>
                <p className="text-xs text-slate-500 mt-1">This may take up to a minute for the whole department.</p>
              </>
            ) : (
              <>
                <Zap className="w-10 h-10 text-amber-500 mx-auto" />
                <p className="mt-3 font-semibold">Ready to run</p>
                <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">Click <b>Run for All Employees</b> below to compute + apply auto-stars for every active Research Unit employee using their joining date as the starting point.</p>
              </>
            )}
          </div>
        ) : (
          <>
            {/* Summary */}
            <div className="grid grid-cols-4 gap-3">
              <div className="p-3 rounded-lg bg-white border border-slate-200 text-center">
                <div className="text-[11px] text-slate-500">Employees Processed</div>
                <div className="text-2xl font-bold text-slate-800">{result.processed}</div>
              </div>
              <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-center">
                <div className="text-[11px] text-emerald-700">Positive Stars</div>
                <div className="text-2xl font-bold text-emerald-600">+{result.total_positive_stars}</div>
              </div>
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-center">
                <div className="text-[11px] text-rose-700">Deductions</div>
                <div className="text-2xl font-bold text-rose-600">{result.total_negative_stars}</div>
              </div>
              <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-center">
                <div className="text-[11px] text-amber-700">Total Entries Applied</div>
                <div className="text-2xl font-bold text-amber-600">{result.total_entries_applied}</div>
              </div>
            </div>

            {/* Per-employee table */}
            <div className="border border-slate-200 rounded-xl overflow-hidden max-h-[420px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 sticky top-0">
                  <tr className="text-left text-[11px] uppercase tracking-wider text-slate-500">
                    <th className="px-3 py-2">Employee</th>
                    <th className="px-3 py-2">Team</th>
                    <th className="px-3 py-2">Start</th>
                    <th className="px-3 py-2 text-center">Entries</th>
                    <th className="px-3 py-2 text-center">Positive</th>
                    <th className="px-3 py-2 text-center">Deductions</th>
                    <th className="px-3 py-2 text-center">Net Stars</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {perEmployeeSorted.map(e => (
                    <tr key={e.employee_id} className={e.error ? 'bg-rose-50/40' : ''}>
                      <td className="px-3 py-2">
                        <div className="font-medium text-slate-800 text-[12px]">{e.full_name}</div>
                        <div className="text-[10px] text-slate-500">{e.emp_id}</div>
                      </td>
                      <td className="px-3 py-2 text-[11px] text-slate-600">{e.team || '—'}</td>
                      <td className="px-3 py-2 font-mono text-[11px]">{e.start_date}</td>
                      <td className="px-3 py-2 text-center text-[12px]">{e.applied ?? 0}</td>
                      <td className="px-3 py-2 text-center text-[12px] text-emerald-600 font-semibold">+{e.positive ?? 0}</td>
                      <td className="px-3 py-2 text-center text-[12px] text-rose-600 font-semibold">{e.negative ?? 0}</td>
                      <td className="px-3 py-2 text-center">
                        {e.error ? (
                          <span className="text-[10px] text-rose-700" title={e.error}>error</span>
                        ) : (
                          <span className={`inline-block px-2 py-0.5 rounded font-bold text-[12px] ${(e.total_stars ?? 0) > 0 ? 'bg-emerald-100 text-emerald-700' : (e.total_stars ?? 0) < 0 ? 'bg-rose-100 text-rose-700' : 'bg-slate-100 text-slate-700'}`}>
                            {(e.total_stars ?? 0) > 0 ? '+' : ''}{e.total_stars ?? 0}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        <div className="flex flex-wrap justify-end gap-2 pt-4 mt-4 -mx-6 -mb-6 px-6 py-4 border-t border-slate-200 sticky bottom-0 bg-white/95 backdrop-blur-sm rounded-b-lg shadow-[0_-4px_12px_-4px_rgba(15,23,42,0.08)]">
          <Button variant="outline" className="rounded-lg h-9 px-4" onClick={onClose} disabled={running}>Close</Button>
          {result ? (
            <Button className="rounded-lg h-9 px-5 bg-[#063c88] hover:bg-[#052e6b]" onClick={onApplied} data-testid="bulk-done-btn">
              Done · Refresh Table
            </Button>
          ) : (
            <Button className="rounded-lg h-9 px-5 bg-amber-500 hover:bg-amber-600" onClick={run} disabled={running} data-testid="bulk-run-btn">
              <Zap className="w-4 h-4 mr-1.5"/>{running ? 'Running…' : 'Run for All Employees'}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Leave Adjust Dialog — HR picks a specific leave instance for the employee,
// marks it Valid / Invalid, then increases / decreases / zeros the star (and
// optionally flag) impact of that leave. Persisted as a `manual_adjustment`
// row linked via `related_leave_id`, protected from the daily auto-recompute.
// ---------------------------------------------------------------------------
function LeaveAdjustDialog({ employee, onClose, onApplied, getAuthHeaders }) {
  const [state, setState] = React.useState({ loading: true, leaves: [] });
  const [selected, setSelected] = React.useState(null); // leave doc
  const [validity, setValidity] = React.useState('valid');
  const [starMode, setStarMode] = React.useState('decrease');
  const [starValue, setStarValue] = React.useState('');
  const [flagMode, setFlagMode] = React.useState('none');
  const [flagValue, setFlagValue] = React.useState('');
  const [note, setNote] = React.useState('');
  const [saving, setSaving] = React.useState(false);

  const load = React.useCallback(async () => {
    setState({ loading: true, leaves: [] });
    try {
      const r = await axios.get(`${API}/star-rewards/leaves/${employee.id}`, { headers: getAuthHeaders() });
      setState({ loading: false, leaves: r.data.leaves || [] });
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load leaves');
      setState({ loading: false, leaves: [] });
    }
  }, [employee.id, getAuthHeaders]);
  React.useEffect(() => { load(); }, [load]);

  const pickLeave = (lv) => {
    setSelected(lv);
    setValidity(lv.current_validity || 'valid');
    setStarMode('decrease');
    setStarValue('');
    setFlagMode('none');
    setFlagValue('');
    setNote('');
  };

  const submit = async () => {
    if (!selected) return toast.error('Pick a leave first');
    if ((starMode === 'increase' || starMode === 'decrease') && (!starValue || Number(starValue) <= 0))
      return toast.error('Enter a positive star value');
    if ((flagMode === 'increase' || flagMode === 'decrease') && (!flagValue || Number(flagValue) <= 0))
      return toast.error('Enter a positive flag value');
    if (!note.trim()) return toast.error('Note is required');
    setSaving(true);
    try {
      const r = await axios.post(`${API}/star-rewards/leaves/adjust`, {
        employee_id: employee.id,
        leave_id: selected.id,
        validity,
        star_mode: starMode,
        star_value: (starMode === 'set_zero' || starMode === 'none') ? 0 : Number(starValue),
        flag_mode: flagMode,
        flag_value: (flagMode === 'none') ? 0 : Number(flagValue),
        note: note.trim(),
      }, { headers: getAuthHeaders() });
      toast.success(`Adjustment saved · Stars ${r.data.new_stars} · Flags ${r.data.new_unsafe}`);
      setSelected(null);
      await load();
      onApplied();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to save');
    } finally { setSaving(false); }
  };

  const ModePills = ({ mode, setMode, tPrefix, allowSetZero = true }) => (
    <div className="flex gap-1.5 flex-wrap">
      {[
        { k: 'increase', label: 'Increase', cls: 'bg-emerald-500 hover:bg-emerald-600' },
        { k: 'decrease', label: 'Decrease', cls: 'bg-rose-500 hover:bg-rose-600' },
        ...(allowSetZero ? [{ k: 'set_zero', label: 'Set to 0', cls: 'bg-slate-500 hover:bg-slate-600' }] : []),
        { k: 'none', label: 'No change', cls: 'bg-slate-300 hover:bg-slate-400 text-slate-700' },
      ].map(m => (
        <button key={m.k}
          onClick={() => setMode(m.k)}
          data-testid={`${tPrefix}-${m.k}`}
          className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold transition ${mode === m.k ? `${m.cls} text-white shadow-sm` : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>
          {m.label}
        </button>
      ))}
    </div>
  );

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="leave-adjust-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CalendarClock className="w-5 h-5 text-blue-500" />
            Leave-Based Star Adjustment · {employee.full_name || employee.name}
          </DialogTitle>
        </DialogHeader>

        {!selected ? (
          <div className="space-y-3">
            <div className="text-sm text-slate-600">
              Pick a leave instance to review. HR marks it as valid or invalid and adjusts the employee&apos;s stars accordingly.
            </div>
            {state.loading ? (
              <div className="p-10 text-center text-slate-500"><Loader2 className="w-6 h-6 animate-spin inline mr-2"/>Loading leaves…</div>
            ) : state.leaves.length === 0 ? (
              <div className="p-10 text-center text-slate-500">No leaves on record.</div>
            ) : (
              <div className="border border-slate-200 rounded-xl overflow-hidden max-h-[55vh] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 sticky top-0 z-10">
                    <tr className="text-left text-[11px] uppercase tracking-wider text-slate-500">
                      <th className="px-3 py-2">Start</th>
                      <th className="px-3 py-2">Type</th>
                      <th className="px-3 py-2">Split</th>
                      <th className="px-3 py-2">Duration</th>
                      <th className="px-3 py-2">Status</th>
                      <th className="px-3 py-2">Validity</th>
                      <th className="px-3 py-2 text-center">Prior ★ Adj</th>
                      <th className="px-3 py-2"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {state.leaves.map(lv => (
                      <tr key={lv.id} className="hover:bg-slate-50" data-testid={`leave-row-${lv.id}`}>
                        <td className="px-3 py-2 font-mono text-[12px]">{lv.start_date}</td>
                        <td className="px-3 py-2 text-[12px]">{lv.leave_type}</td>
                        <td className="px-3 py-2 text-[12px]">{lv.leave_split}</td>
                        <td className="px-3 py-2 text-[12px]">{lv.duration}</td>
                        <td className="px-3 py-2 text-[12px] capitalize">{lv.status}</td>
                        <td className="px-3 py-2 text-[12px]">
                          {lv.current_validity ? (
                            <span className={`px-2 py-0.5 rounded font-semibold text-[11px] ${lv.current_validity === 'valid' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>{lv.current_validity}</span>
                          ) : <span className="text-slate-400 text-[11px] italic">unset</span>}
                        </td>
                        <td className="px-3 py-2 text-center text-[12px]">
                          {lv.net_adjusted_stars !== 0 ? (
                            <span className={`font-bold ${lv.net_adjusted_stars > 0 ? 'text-emerald-600' : 'text-rose-600'}`}>{lv.net_adjusted_stars > 0 ? '+' : ''}{lv.net_adjusted_stars}</span>
                          ) : <span className="text-slate-300">—</span>}
                        </td>
                        <td className="px-3 py-2 text-right">
                          <Button size="sm" variant="outline" onClick={() => pickLeave(lv)} className="rounded-lg h-7 text-[11px]" data-testid={`pick-leave-${lv.id}`}>
                            Select
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {/* Selected leave summary */}
            <div className="p-3 rounded-xl bg-blue-50 border border-blue-200 text-sm">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <div className="font-semibold text-slate-800">{selected.leave_type} · {selected.start_date}</div>
                  <div className="text-[11px] text-slate-600 mt-0.5">{selected.leave_split} · {selected.duration} · Status: <b className="capitalize">{selected.status}</b></div>
                  {selected.reason && <div className="text-[11px] text-slate-500 mt-1 italic">Reason: {selected.reason}</div>}
                </div>
                <Button size="sm" variant="ghost" className="rounded-lg text-[11px]" onClick={() => setSelected(null)} data-testid="back-to-leaves">
                  <ArrowLeft className="w-3.5 h-3.5 mr-1"/>Back to list
                </Button>
              </div>
            </div>

            {/* Field 1: Validity */}
            <div>
              <Label className="text-xs font-semibold text-slate-600">1. Leave is</Label>
              <div className="mt-1.5 flex gap-2">
                <button
                  onClick={() => setValidity('valid')}
                  data-testid="validity-valid"
                  className={`flex-1 px-3 py-2 rounded-lg text-sm font-semibold border-2 transition ${validity === 'valid' ? 'border-emerald-500 bg-emerald-50 text-emerald-700' : 'border-slate-200 text-slate-500 hover:border-slate-300'}`}>
                  <CheckCircle2 className="w-4 h-4 inline mr-1.5"/>Valid
                </button>
                <button
                  onClick={() => setValidity('invalid')}
                  data-testid="validity-invalid"
                  className={`flex-1 px-3 py-2 rounded-lg text-sm font-semibold border-2 transition ${validity === 'invalid' ? 'border-rose-500 bg-rose-50 text-rose-700' : 'border-slate-200 text-slate-500 hover:border-slate-300'}`}>
                  <AlertTriangle className="w-4 h-4 inline mr-1.5"/>Invalid
                </button>
              </div>
            </div>

            {/* Field 2a: Star Value & mode */}
            <div>
              <Label className="text-xs font-semibold text-slate-600">2. Star Value</Label>
              <div className="mt-1.5">
                <ModePills mode={starMode} setMode={setStarMode} tPrefix="leave-star-mode" />
              </div>
              {(starMode === 'increase' || starMode === 'decrease') && (
                <Input type="number" min="1" placeholder="Value (e.g. 2)" value={starValue} onChange={e => setStarValue(e.target.value)} className="mt-2 rounded-lg" data-testid="leave-star-value"/>
              )}
              {starMode === 'set_zero' && (
                <div className="mt-1.5 text-[11px] text-slate-500 italic">Neutralizes prior star adjustments already applied to this specific leave ({selected.net_adjusted_stars > 0 ? '+' : ''}{selected.net_adjusted_stars || 0}).</div>
              )}
            </div>

            {/* Field 2b: Flag (optional) */}
            <div>
              <Label className="text-xs font-semibold text-slate-600">Flag (Unsafe) — optional</Label>
              <div className="mt-1.5">
                <ModePills mode={flagMode} setMode={setFlagMode} tPrefix="leave-flag-mode" allowSetZero={false}/>
              </div>
              {(flagMode === 'increase' || flagMode === 'decrease') && (
                <Input type="number" min="1" placeholder="Flag value" value={flagValue} onChange={e => setFlagValue(e.target.value)} className="mt-2 rounded-lg" data-testid="leave-flag-value"/>
              )}
            </div>

            {/* Note */}
            <div>
              <Label className="text-xs font-semibold text-slate-600">Note / Reason *</Label>
              <textarea
                className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm"
                rows={3}
                placeholder="Explain the validity decision and adjustment. Visible in the audit trail."
                value={note}
                onChange={e => setNote(e.target.value)}
                data-testid="leave-note"
              />
            </div>

            {selected.prior_adjustments?.length > 0 && (
              <div className="p-2 rounded-lg bg-slate-50 border border-slate-200 text-[11px] text-slate-600">
                <b>Prior adjustments on this leave:</b>
                <ul className="mt-1 space-y-0.5 list-disc list-inside">
                  {selected.prior_adjustments.map(a => (
                    <li key={a.id}>
                      {a.stars > 0 ? '+' : ''}{a.stars} ★ · marked <b>{a.validity}</b> · {new Date(a.created_at).toLocaleString('en-IN')}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <div className="flex flex-wrap justify-end gap-2 pt-4 mt-4 -mx-6 -mb-6 px-6 py-4 border-t border-slate-200 sticky bottom-0 bg-white/95 backdrop-blur-sm rounded-b-lg shadow-[0_-4px_12px_-4px_rgba(15,23,42,0.08)]">
          <Button variant="outline" className="rounded-lg h-9 px-4" onClick={onClose} disabled={saving}>Close</Button>
          {selected && (
            <Button
              className="rounded-lg h-9 px-5 bg-blue-500 hover:bg-blue-600"
              onClick={submit}
              disabled={saving}
              data-testid="leave-submit-btn"
            >
              {saving ? <><Loader2 className="w-4 h-4 mr-1.5 animate-spin"/>Saving…</> : '3. Submit'}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
