import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { CalendarCheck, Clock, LogIn, LogOut as LogOutIcon, AlertCircle, Filter, ChevronLeft, ChevronRight } from 'lucide-react';
import { Badge } from '../components/ui/badge';
import { DatePicker } from '../components/ui/date-picker';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { PageSizeSelector } from '../components/PageSizeSelector';
import { useTableSort, SortableTh } from '../components/useTableSort';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EmployeeAttendance = () => {
  const { getAuthHeaders } = useAuth();
  const [attendance, setAttendance] = useState([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('this_month');
  const [statusFilter, setStatusFilter] = useState('All');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const fetchAttendance = useCallback(async () => {
    try {
      setLoading(true);
      const params = { duration: period, status_filter: statusFilter };
      if (period === 'custom' && customFrom && customTo) {
        params.from_date = new Date(customFrom).toLocaleDateString('en-GB').split('/').join('-');
        params.to_date = new Date(customTo).toLocaleDateString('en-GB').split('/').join('-');
      }
      const response = await axios.get(`${API}/employee/attendance`, { headers: getAuthHeaders(), params });
      setAttendance(response.data);
      setCurrentPage(1);
    } catch (error) {
      toast.error('Failed to load attendance');
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders, period, statusFilter, customFrom, customTo]);

  useEffect(() => { fetchAttendance(); }, [fetchAttendance]);

  const getStatusBadge = (status, isLop) => {
    if (isLop || status === 'Loss of Pay') return 'badge-error font-bold';
    const styles = { 'Login': 'badge-success', 'Completed': 'badge-info', 'Present': 'badge-success', 'Not Logged': 'badge-neutral', 'Early Out': 'badge-error', 'Late Login': 'badge-warning', 'Late': 'badge-warning', 'Leave': 'bg-purple-50 text-purple-700 border border-purple-200/50', 'Absent': 'badge-error', 'Sunday': 'bg-slate-100 text-slate-500 border border-slate-200/50', 'NA': 'bg-slate-50 text-slate-400 border border-slate-200/50' };
    // Handle leave type variants like "Sick Leave", "Casual Leave"
    if (status && status.includes('Leave')) return 'bg-purple-50 text-purple-700 border border-purple-200/50';
    return styles[status] || 'badge-neutral';
  };

  const stats = {
    present: attendance.filter(a => ['Present', 'Completed', 'Login'].includes(a.status)).length,
    late: attendance.filter(a => a.status === 'Late Login' || a.status === 'Late').length,
    absent: attendance.filter(a => a.status === 'Absent' || a.status === 'Not Logged' || a.is_lop).length,
    leave: attendance.filter(a => a.status === 'Leave' || (a.status && a.status.includes('Leave'))).length,
  };

  // Sort + pagination — sort first, then slice
  const { sortedRows: sortedAttendance, sortField, sortDir, toggleSort } = useTableSort(attendance);
  const totalRecords = sortedAttendance.length;
  const totalPages = Math.max(1, Math.ceil(totalRecords / rowsPerPage));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const startIndex = (safeCurrentPage - 1) * rowsPerPage;
  const endIndex = Math.min(startIndex + rowsPerPage, totalRecords);
  const paginatedAttendance = sortedAttendance.slice(startIndex, endIndex);

  return (
    <div className="space-y-6 animate-fade-in" data-testid="employee-attendance-page">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
          <CalendarCheck className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>My Attendance</h1>
          <p className="text-sm text-slate-500">View your attendance history</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Present', value: stats.present, icon: LogOutIcon, color: 'blue' },
          { label: 'Late Login', value: stats.late, icon: Clock, color: 'amber' },
          { label: 'Absent/LOP', value: stats.absent, icon: AlertCircle, color: 'red' },
          { label: 'Leave', value: stats.leave, icon: CalendarCheck, color: 'purple' },
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

      {/* Filters */}
      <div className="card-flat p-6">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="text-sm text-slate-600 mb-1.5 block font-medium">Period</label>
            <Select value={period} onValueChange={(v) => setPeriod(v)}>
              <SelectTrigger className="w-[160px] rounded-lg" data-testid="filter-period"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="this_week">This Week</SelectItem>
                <SelectItem value="last_week">Last Week</SelectItem>
                <SelectItem value="this_month">This Month</SelectItem>
                <SelectItem value="last_month">Last Month</SelectItem>
                <SelectItem value="custom">Custom Range</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {period === 'custom' && (
            <>
              <div>
                <label className="text-sm text-slate-600 mb-1.5 block font-medium">From Date</label>
                <DatePicker value={customFrom} onChange={(val) => setCustomFrom(val)} placeholder="Select date" data-testid="filter-from" />
              </div>
              <div>
                <label className="text-sm text-slate-600 mb-1.5 block font-medium">To Date</label>
                <DatePicker value={customTo} onChange={(val) => setCustomTo(val)} placeholder="Select date" data-testid="filter-to" />
              </div>
            </>
          )}
          <div>
            <label className="text-sm text-slate-600 mb-1.5 block font-medium">Status</label>
            <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v)}>
              <SelectTrigger className="w-[140px] rounded-lg" data-testid="filter-status"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All Status</SelectItem>
                <SelectItem value="Present">Present</SelectItem>
                <SelectItem value="Late">Late</SelectItem>
                <SelectItem value="Early Out">Early Out</SelectItem>
                <SelectItem value="Absent">Absent</SelectItem>
                <SelectItem value="Sunday">Sunday</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button onClick={fetchAttendance} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg" data-testid="apply-filter-btn">
            <Filter className="w-4 h-4 mr-2" /> Apply
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="card-premium overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-10 h-10 border-2 border-[#063c88] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
          <div className="overflow-x-auto">
            <table className="table-premium">
              <thead>
                <tr>
                  <SortableTh field="date" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Date</SortableTh>
                  <SortableTh field="day" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Day</SortableTh>
                  <SortableTh field="check_in" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Check-In</SortableTh>
                  <SortableTh field="check_out" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Check-Out</SortableTh>
                  <SortableTh field="total_hours" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Total Hours</SortableTh>
                  <SortableTh field="status" sortField={sortField} sortDir={sortDir} onSort={toggleSort}>Status</SortableTh>
                </tr>
              </thead>
              <tbody>
                {paginatedAttendance.length === 0 ? (
                  <tr><td colSpan="6" className="text-center py-12 text-slate-500">No attendance records found</td></tr>
                ) : (
                  paginatedAttendance.map((record, index) => (
                    <tr key={index} className={record.is_lop ? 'bg-red-50/50' : ''}>
                      <td className="font-medium text-slate-900">{record.date}</td>
                      <td className="text-slate-600">{record.day}</td>
                      <td className="text-slate-600">{record.login || record.check_in || '-'}</td>
                      <td className="text-slate-600">{record.logout || record.check_out || '-'}</td>
                      <td className="text-slate-600">{record.total_hours || '-'}</td>
                      <td><Badge className={getStatusBadge(record.status, record.is_lop)}>{record.is_lop ? 'Loss of Pay' : record.status}</Badge></td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          {totalRecords > 0 && (
            <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/50" data-testid="emp-attendance-pagination">
              <div className="flex items-center gap-4">
                <p className="text-sm text-slate-500" data-testid="emp-pagination-info">
                  Showing {startIndex + 1}–{endIndex} of {totalRecords} records
                </p>
                <PageSizeSelector
                  value={rowsPerPage}
                  onChange={(v) => { setRowsPerPage(v); setCurrentPage(1); }}
                  testId="emp-rows-per-page-select"
                />
              </div>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="outline" disabled={safeCurrentPage <= 1} onClick={() => setCurrentPage(prev => prev - 1)} className="rounded-lg" data-testid="emp-attendance-prev-page">
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <span className="text-sm text-slate-600 px-3">Page {safeCurrentPage} of {totalPages}</span>
                <Button size="sm" variant="outline" disabled={safeCurrentPage >= totalPages} onClick={() => setCurrentPage(prev => prev + 1)} className="rounded-lg" data-testid="emp-attendance-next-page">
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}
          </>
        )}
      </div>
    </div>
  );
};

export default EmployeeAttendance;
