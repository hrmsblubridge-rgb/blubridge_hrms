import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { EmployeeAutocomplete } from '../components/EmployeeAutocomplete';
import { formatDate } from '../lib/dateFormat';
import EmployeeAvatar from '../components/EmployeeAvatar';
import { useTableSort, SortableTh } from '../components/useTableSort';
import { 
  CalendarCheck, 
  Search, 
  Filter,
  ChevronLeft,
  ChevronRight,
  Clock,
  LogIn,
  LogOut as LogOutIcon,
  AlertCircle,
  Eye,
  BarChart3
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { DatePicker } from '../components/ui/date-picker';
import EmployeeLeaveDetail from '../components/EmployeeLeaveDetail';
import { PageSizeSelector } from '../components/PageSizeSelector';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Attendance = () => {
  const { getAuthHeaders } = useAuth();
  const [attendance, setAttendance] = useState([]);
  const [teams, setTeams] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [designations, setDesignations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [showLeaveDetail, setShowLeaveDetail] = useState(false);
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  // Vigilance integration (admin only) — dynamic Research/Break columns per uploader
  const [vigMap, setVigMap] = useState({});
  const [vigUploaders, setVigUploaders] = useState([]);

  // Default: today's date (original behavior)
  const [filters, setFilters] = useState({
    empName: '',
    team: 'All',
    department: 'All',
    designation: 'All',
    fromDate: new Date().toISOString().split('T')[0],
    toDate: new Date().toISOString().split('T')[0],
    status: 'All'
  });

  useEffect(() => { fetchData(); }, []);

  const formatDateForApi = (date) => {
    if (!date) return '';
    const d = new Date(date);
    return `${String(d.getDate()).padStart(2, '0')}-${String(d.getMonth() + 1).padStart(2, '0')}-${d.getFullYear()}`;
  };

  const fetchData = async () => {
    try {
      setLoading(true);
      const [attendanceRes, teamsRes, deptsRes, desigRes] = await Promise.all([
        axios.get(`${API}/attendance`, {
          headers: getAuthHeaders(),
          params: { 
            from_date: formatDateForApi(filters.fromDate), 
            to_date: formatDateForApi(filters.toDate) 
          }
        }),
        axios.get(`${API}/teams`, { headers: getAuthHeaders() }),
        axios.get(`${API}/departments`, { headers: getAuthHeaders() }),
        axios.get(`${API}/settings/designations`, { headers: getAuthHeaders() }).catch(() => ({ data: [] }))
      ]);
      setAttendance(attendanceRes.data);
      setTeams(teamsRes.data);
      setDepartments(deptsRes.data);
      setDesignations(desigRes.data || []);
    } catch (error) {
      console.error('Attendance fetch error:', error);
      toast.error('Failed to load attendance data');
    } finally {
      setLoading(false);
    }
  };

  const vigToIso = (d) => {
    if (!d) return '';
    const m = String(d).match(/^(\d{2})-(\d{2})-(\d{4})$/);
    return m ? `${m[3]}-${m[2]}-${m[1]}` : String(d).slice(0, 10);
  };

  // Fetch vigilance Research/Break data for the currently loaded attendance range.
  useEffect(() => {
    if (!filters.fromDate || !filters.toDate) return;
    axios.get(`${API}/vigilance/attendance-integration`, {
      headers: getAuthHeaders(),
      params: { from_date: formatDateForApi(filters.fromDate), to_date: formatDateForApi(filters.toDate) },
    }).then(res => {
      const map = res.data?.map || {};
      setVigMap(map);
      const names = [];
      Object.values(map).forEach(list => list.forEach(x => {
        if (x.uploaded_by_name && !names.includes(x.uploaded_by_name)) names.push(x.uploaded_by_name);
      }));
      names.sort();
      setVigUploaders(names);
    }).catch(() => { setVigMap({}); setVigUploaders([]); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attendance]);

  const handleReset = async () => {
    const today = new Date().toISOString().split('T')[0];
    const resetFilters = { 
      empName: '', 
      team: 'All', 
      department: 'All', 
      designation: 'All',
      fromDate: today, 
      toDate: today, 
      status: 'All' 
    };
    setFilters(resetFilters);
    
    // Fetch with reset filter values directly
    try {
      setLoading(true);
      const response = await axios.get(`${API}/attendance`, {
        headers: getAuthHeaders(),
        params: { 
          from_date: formatDateForApi(today), 
          to_date: formatDateForApi(today) 
        }
      });
      setAttendance(response.data);
      setCurrentPage(1);
      toast.info('Filters reset');
    } catch (error) {
      toast.error('Failed to reset');
    } finally {
      setLoading(false);
    }
  };

  const handleFilter = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/attendance`, {
        headers: getAuthHeaders(),
        params: {
          employee_name: filters.empName || undefined,
          team: filters.team !== 'All' ? filters.team : undefined,
          department: filters.department !== 'All' ? filters.department : undefined,
          designation: filters.designation !== 'All' ? filters.designation : undefined,
          from_date: formatDateForApi(filters.fromDate),
          to_date: formatDateForApi(filters.toDate),
          status: filters.status !== 'All' ? filters.status : undefined
        }
      });
      setAttendance(response.data);
      setCurrentPage(1);
      toast.success('Filter applied');
    } catch (error) {
      toast.error('Failed to filter');
    } finally {
      setLoading(false);
    }
  };

  const { sortedRows: sortedAttendance, sortField, sortDir: sortOrder, toggleSort: handleSort } = useTableSort(attendance);

  // Pagination computed values
  const totalRecords = sortedAttendance.length;
  const totalPages = Math.max(1, Math.ceil(totalRecords / rowsPerPage));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const startIndex = (safeCurrentPage - 1) * rowsPerPage;
  const endIndex = Math.min(startIndex + rowsPerPage, totalRecords);
  const paginatedAttendance = sortedAttendance.slice(startIndex, endIndex);

  const getStatusBadge = (status, isLop) => {
    if (isLop || status === 'Loss of Pay') return 'badge-error font-bold';
    const styles = {
      'Login': 'badge-success', 'Completed': 'badge-info', 'Present': 'badge-success',
      'Not Logged': 'badge-neutral', 'Early Out': 'badge-error', 'Late Login': 'badge-warning'
    };
    return styles[status] || 'badge-neutral';
  };

  const getStatusIcon = (status) => {
    if (status === 'Login') return <LogIn className="w-3 h-3" />;
    if (status === 'Completed') return <LogOutIcon className="w-3 h-3" />;
    if (status === 'Late Login') return <Clock className="w-3 h-3" />;
    return null;
  };

  // Stats — categorization rules (kept in lock-step with the row badge logic):
  //   • PRESENT     – clocked-in, completed shift, NOT late, NOT early out, NOT LOP
  //   • LOGGED IN   – currently inside their shift (Login state)
  //   • LATE LOGIN  – arrived late; includes late-login LOPs from the engine
  //   • ABSENT      – truly non-working day: Absent / Not Logged / On Leave
  //
  // NOTE: late-login LOPs do NOT fall into Absent — they belong in Late Login.
  // Same applies for early-out LOPs (kept out of Absent; surfaced by the
  // row badge separately). This keeps the four counters mutually exclusive
  // and aligned with the row-level status the admin actually sees.
  const isLateLoginLop = (a) => a.is_lop && (a.lop_reason || '').toLowerCase().includes('late login');
  const stats = {
    present: sortedAttendance.filter(a =>
      (a.status === 'Present' || a.status === 'Completed') && !a.is_lop
    ).length,
    login: sortedAttendance.filter(a => a.status === 'Login').length,
    late: sortedAttendance.filter(a => a.status === 'Late Login' || isLateLoginLop(a)).length,
    absent: sortedAttendance.filter(a => {
      // Late-login LOPs belong in Late Login, NOT Absent
      if (isLateLoginLop(a)) return false;
      const s = a.status || '';
      return s === 'Absent' || s === 'Not Logged' || s.includes('Leave');
    }).length,
  };

  // Handle employee click to show leave detail
  const handleEmployeeClick = (record) => {
    setSelectedEmployee({
      emp_name: record.emp_name,
      employee_id: record.employee_id,
      team: record.team,
      department: record.department,
      emp_id: record.emp_id
    });
    setShowLeaveDetail(true);
  };

  return (
    <div className="space-y-6 animate-fade-in" data-testid="attendance-page">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
          <CalendarCheck className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>Attendance</h1>
          <p className="text-sm text-slate-500">Track employee attendance records</p>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Present', value: stats.present, icon: LogOutIcon, color: 'emerald' },
          { label: 'Logged In', value: stats.login, icon: LogIn, color: 'blue' },
          { label: 'Late Login', value: stats.late, icon: Clock, color: 'amber' },
          { label: 'Absent', value: stats.absent, icon: AlertCircle, color: 'red' },
        ].map((stat, i) => (
          <div key={i} className="card-flat p-4 flex items-center gap-4">
            <div className={`w-10 h-10 rounded-xl bg-${stat.color}-100 flex items-center justify-center`}>
              <stat.icon className={`w-5 h-5 text-${stat.color}-600`} />
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900 number-display">{stat.value}</p>
              <p className="text-xs text-slate-500">{stat.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="card-flat p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
          <div>
            <label className="text-sm text-slate-600 mb-1.5 block font-medium">Employee Name</label>
            <EmployeeAutocomplete
              value={filters.empName}
              onChange={(val) => setFilters({ ...filters, empName: val })}
              onSelect={(emp) => setFilters({ ...filters, empName: emp.full_name })}
              placeholder="Search employee..."
              data-testid="search-emp-name"
            />
          </div>
          <div>
            <label className="text-sm text-slate-600 mb-1.5 block font-medium">Department</label>
            <Select value={filters.department} onValueChange={(v) => setFilters({ ...filters, department: v })}>
              <SelectTrigger className="rounded-lg" data-testid="filter-department"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All Departments</SelectItem>
                {departments.map((dept) => <SelectItem key={dept.id} value={dept.name}>{dept.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-sm text-slate-600 mb-1.5 block font-medium">Team</label>
            <Select value={filters.team} onValueChange={(v) => setFilters({ ...filters, team: v })}>
              <SelectTrigger className="rounded-lg" data-testid="filter-team"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All Teams</SelectItem>
                {teams.map((team) => <SelectItem key={team.id} value={team.name}>{team.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-sm text-slate-600 mb-1.5 block font-medium">Designation</label>
            <Select value={filters.designation} onValueChange={(v) => setFilters({ ...filters, designation: v })}>
              <SelectTrigger className="rounded-lg" data-testid="filter-designation"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All Designations</SelectItem>
                {Array.from(new Set((designations || []).map(d => d.name).filter(Boolean))).sort().map((name) => <SelectItem key={name} value={name}>{name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-sm text-slate-600 mb-1.5 block font-medium">Status</label>
            <Select value={filters.status} onValueChange={(v) => setFilters({ ...filters, status: v })}>
              <SelectTrigger className="rounded-lg" data-testid="filter-status"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All Status</SelectItem>
                <SelectItem value="Login">Login</SelectItem>
                <SelectItem value="Completed">Completed</SelectItem>
                <SelectItem value="Present">Present</SelectItem>
                <SelectItem value="Loss of Pay">Loss of Pay</SelectItem>
                <SelectItem value="Early Out">Early Out</SelectItem>
                <SelectItem value="Late Login">Late Login</SelectItem>
                <SelectItem value="Not Logged">Not Logged</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="text-sm text-slate-600 mb-1.5 block font-medium">From Date</label>
            <DatePicker value={filters.fromDate} onChange={(val) => setFilters({ ...filters, fromDate: val })} placeholder="Select date" data-testid="filter-from" />
          </div>
          <div>
            <label className="text-sm text-slate-600 mb-1.5 block font-medium">To Date</label>
            <DatePicker value={filters.toDate} onChange={(val) => setFilters({ ...filters, toDate: val })} placeholder="Select date" data-testid="filter-to" />
          </div>
          <div className="flex items-end gap-2 lg:col-span-2">
            <Button onClick={handleFilter} className="bg-[#063c88] hover:bg-[#052d66] text-white rounded-lg" data-testid="apply-filter-btn">
              <Filter className="w-4 h-4 mr-2" /> Apply Filter
            </Button>
            <Button variant="outline" onClick={handleReset} className="rounded-lg" data-testid="reset-filter-btn">
              Reset
            </Button>
          </div>
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
                  <th className="w-12"></th>
                  <SortableTh field="emp_name" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>Employee</SortableTh>
                  <SortableTh field="team" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>Team</SortableTh>
                  <SortableTh field="date" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>Date</SortableTh>
                  <SortableTh field="check_in" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>In</SortableTh>
                  <SortableTh field="check_out" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>Out</SortableTh>
                  <SortableTh field="total_hours" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>Total Hours</SortableTh>
                  {vigUploaders.flatMap(name => ([
                    <th key={name + '-r'} className="px-4 py-3 text-left text-xs font-semibold text-emerald-700 whitespace-nowrap bg-emerald-50/60" data-testid="vig-att-research-col">Total Research Hrs<br /><span className="font-normal text-emerald-600">({name})</span></th>,
                    <th key={name + '-b'} className="px-4 py-3 text-left text-xs font-semibold text-emerald-700 whitespace-nowrap bg-emerald-50/60">Total Break Hrs<br /><span className="font-normal text-emerald-600">({name})</span></th>,
                  ]))}
                  <SortableTh field="status" sortField={sortField} sortDir={sortOrder} onSort={handleSort}>Status</SortableTh>
                </tr>
              </thead>
              <tbody>
                {paginatedAttendance.length === 0 ? (
                  <tr>
                    <td colSpan={8 + vigUploaders.length * 2} className="text-center py-12 text-slate-500">
                      <CalendarCheck className="w-10 h-10 mx-auto mb-2 text-slate-300" />
                      <p>No attendance records found</p>
                    </td>
                  </tr>
                ) : (
                  paginatedAttendance.map((record, index) => (
                    <tr key={record.id || index} className={`${record.is_lop ? 'bg-red-50/50' : ''} group`}>
                      <td>
                        <button 
                          className="p-2 hover:bg-[#063c88]/10 rounded-lg transition-colors opacity-60 group-hover:opacity-100"
                          onClick={() => handleEmployeeClick(record)}
                          data-testid={`view-leave-btn-${index}`}
                          title="View Leave & Attendance Details"
                        >
                          <BarChart3 className="w-4 h-4 text-[#063c88]" />
                        </button>
                      </td>
                      <td>
                        <div 
                          className="flex items-center gap-3 cursor-pointer hover:opacity-80 transition-opacity"
                          onClick={() => handleEmployeeClick(record)}
                          data-testid={`employee-row-${index}`}
                        >
                          <EmployeeAvatar employeeId={record.employee_id} name={record.emp_name} size="sm" shape="circle" />
                          <span className="font-medium text-slate-900 hover:text-[#063c88] transition-colors">{record.emp_name}</span>
                        </div>
                      </td>
                      <td className="text-slate-600">{record.team}</td>
                      <td className="text-slate-600 whitespace-nowrap">{formatDate(record.date)}</td>
                      <td>
                        <div className="text-slate-900 font-medium">{record.check_in || '-'}</div>
                      </td>
                      <td>
                        <div className="text-slate-900 font-medium">{record.check_out || '-'}</div>
                      </td>
                      <td className="text-slate-600 font-medium">{record.total_hours || '-'}</td>
                      {vigUploaders.flatMap(name => {
                        const list = vigMap[`${record.employee_id}__${vigToIso(record.date)}`] || [];
                        const sub = list.find(x => x.uploaded_by_name === name);
                        return [
                          <td key={name + '-r'} className="text-emerald-700 font-medium whitespace-nowrap bg-emerald-50/30">{sub?.total_research_hours || '-'}</td>,
                          <td key={name + '-b'} className="text-emerald-700 font-medium whitespace-nowrap bg-emerald-50/30">{sub?.total_break_hours || '-'}</td>,
                        ];
                      })}
                      <td>
                        <Badge className={`${getStatusBadge(record.status, record.is_lop)} flex items-center gap-1 w-fit`}>
                          {getStatusIcon(record.is_lop ? 'Loss of Pay' : record.status)}
                          {record.is_lop ? 'Loss of Pay' : record.status}
                        </Badge>
                        {record.is_lop && record.lop_reason && (
                          <div className="text-xs text-red-600 mt-1 max-w-[200px] truncate" title={record.lop_reason}>
                            {record.lop_reason}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          {/* Pagination Controls */}
          {totalRecords > 0 && (
            <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/50" data-testid="attendance-pagination">
              <div className="flex items-center gap-4">
                <p className="text-sm text-slate-500" data-testid="pagination-info">
                  Showing {startIndex + 1}–{endIndex} of {totalRecords} records
                </p>
                <PageSizeSelector
                  value={rowsPerPage}
                  onChange={(v) => { setRowsPerPage(v); setCurrentPage(1); }}
                  testId="rows-per-page-select"
                />
              </div>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="outline" disabled={safeCurrentPage <= 1} onClick={() => setCurrentPage(prev => prev - 1)} className="rounded-lg" data-testid="attendance-prev-page">
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <span className="text-sm text-slate-600 px-3" data-testid="pagination-page-info">Page {safeCurrentPage} of {totalPages}</span>
                <Button size="sm" variant="outline" disabled={safeCurrentPage >= totalPages} onClick={() => setCurrentPage(prev => prev + 1)} className="rounded-lg" data-testid="attendance-next-page">
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}
          </>
        )}
      </div>

      {/* Employee Leave Detail Modal */}
      {showLeaveDetail && selectedEmployee && (
        <EmployeeLeaveDetail 
          employee={selectedEmployee}
          onClose={() => {
            setShowLeaveDetail(false);
            setSelectedEmployee(null);
          }}
        />
      )}
    </div>
  );
};

export default Attendance;
