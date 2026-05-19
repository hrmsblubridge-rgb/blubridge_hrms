import { useState, useEffect, useMemo, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { ImageIcon, Search, Filter, Users as UsersIcon } from 'lucide-react';
import EmployeeAvatar from '../components/EmployeeAvatar';
import { Input } from '../components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EmployeePhotoWall = () => {
  const { getAuthHeaders } = useAuth();
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [deptFilter, setDeptFilter] = useState('all');
  const [photoFilter, setPhotoFilter] = useState('all'); // all | with | without

  const fetchEmployees = useCallback(async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API}/employees/all`, { headers: getAuthHeaders() });
      const list = Array.isArray(res.data) ? res.data : res.data?.items || [];
      setEmployees(list.filter((e) => !e.is_deleted));
    } catch (err) {
      toast.error('Failed to load employees');
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders]);

  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  const departments = useMemo(() => {
    const set = new Set();
    employees.forEach((e) => e.department && set.add(e.department));
    return Array.from(set).sort();
  }, [employees]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return employees
      .filter((e) => (deptFilter === 'all' ? true : e.department === deptFilter))
      .filter((e) => {
        if (photoFilter === 'with') return !!e.avatar;
        if (photoFilter === 'without') return !e.avatar;
        return true;
      })
      .filter((e) => {
        if (!q) return true;
        return (
          (e.full_name || '').toLowerCase().includes(q) ||
          (e.emp_id || '').toLowerCase().includes(q) ||
          (e.custom_employee_id || '').toLowerCase().includes(q) ||
          (e.designation || '').toLowerCase().includes(q) ||
          (e.team || '').toLowerCase().includes(q)
        );
      })
      .sort((a, b) => (a.full_name || '').localeCompare(b.full_name || ''));
  }, [employees, search, deptFilter, photoFilter]);

  // Group by department for visual structure
  const grouped = useMemo(() => {
    const groups = {};
    filtered.forEach((e) => {
      const d = e.department || 'Unassigned';
      if (!groups[d]) groups[d] = [];
      groups[d].push(e);
    });
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [filtered]);

  const withPhotoCount = useMemo(
    () => employees.filter((e) => e.avatar).length,
    [employees]
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="w-12 h-12 border-3 border-[#063c88] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="employee-photo-wall-page">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
            <ImageIcon className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>
              Photo Wall
            </h1>
            <p className="text-sm text-slate-500">
              {withPhotoCount} of {employees.length} employees have uploaded a profile photo
            </p>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="card-flat p-4 flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input
            placeholder="Search by name, ID, team or designation…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
            data-testid="photo-wall-search"
          />
        </div>
        <Select value={deptFilter} onValueChange={setDeptFilter}>
          <SelectTrigger className="w-full sm:w-56" data-testid="photo-wall-dept-filter">
            <SelectValue placeholder="All departments" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All departments</SelectItem>
            {departments.map((d) => (
              <SelectItem key={d} value={d}>
                {d}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={photoFilter} onValueChange={setPhotoFilter}>
          <SelectTrigger className="w-full sm:w-48" data-testid="photo-wall-photo-filter">
            <Filter className="w-4 h-4 mr-2" />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All employees</SelectItem>
            <SelectItem value="with">With photo</SelectItem>
            <SelectItem value="without">Without photo</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Grouped grid */}
      {grouped.length === 0 ? (
        <div className="card-flat p-12 text-center text-slate-500">
          <UsersIcon className="w-12 h-12 mx-auto mb-3 text-slate-300" />
          No employees match the current filters.
        </div>
      ) : (
        grouped.map(([dept, list]) => (
          <section key={dept} className="space-y-3" data-testid={`photo-wall-dept-${dept}`}>
            <div className="flex items-baseline justify-between border-b border-slate-100 pb-2">
              <h2 className="text-lg font-semibold text-slate-900" style={{ fontFamily: 'Outfit' }}>
                {dept}
              </h2>
              <span className="text-xs text-slate-500">{list.length} members</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4">
              {list.map((emp) => (
                <div
                  key={emp.id}
                  className="card-flat p-4 flex flex-col items-center text-center hover:shadow-lg transition cursor-default"
                  data-testid={`photo-wall-card-${emp.id}`}
                  title={`${emp.full_name} • ${emp.designation || ''}`}
                >
                  <EmployeeAvatar
                    employee={emp}
                    size="photo-wall"
                    shape="circle"
                    className="mb-3 shadow-sm"
                  />
                  <p className="text-sm font-semibold text-slate-900 truncate w-full" title={emp.full_name}>
                    {emp.full_name}
                  </p>
                  <p className="text-[11px] text-slate-500 truncate w-full" title={emp.designation}>
                    {emp.designation || '—'}
                  </p>
                  <p className="text-[10px] text-[#063c88] font-medium mt-1 truncate w-full">
                    {emp.custom_employee_id || emp.emp_id}
                  </p>
                  {!emp.avatar && (
                    <span className="mt-2 text-[10px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-100">
                      No photo
                    </span>
                  )}
                </div>
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
};

export default EmployeePhotoWall;
