import { useState, useEffect, useMemo, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { ImageIcon, Search, Filter, Users as UsersIcon, Mail, Send, Loader2, ShieldAlert, Camera } from 'lucide-react';
import EmployeeAvatar from '../components/EmployeeAvatar';
import AvatarUploadDialog from '../components/AvatarUploadDialog';
import { Input } from '../components/ui/input';
import { Switch } from '../components/ui/switch';
import { Button } from '../components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EmployeePhotoWall = () => {
  const { getAuthHeaders, getAvatarById, token } = useAuth();
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [deptFilter, setDeptFilter] = useState('all');
  const [photoFilter, setPhotoFilter] = useState('all'); // all | with | without

  // Avatar upload dialog state
  const [activeEmployee, setActiveEmployee] = useState(null);

  // Email-tools state
  const [pilotEmail, setPilotEmail] = useState('rishi.nayak@blubridge.com');
  const [sendingTo, setSendingTo] = useState(null); // email currently being dispatched
  const [bulkEnabled, setBulkEnabled] = useState(false);
  const [bulkBusy, setBulkBusy] = useState(false);

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

  const fetchBulkFlag = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/admin/profile-upload-email/settings`, { headers: getAuthHeaders() });
      setBulkEnabled(!!res.data?.enable_bulk);
    } catch (e) {
      /* non-fatal */
    }
  }, [getAuthHeaders]);

  useEffect(() => {
    fetchEmployees();
    fetchBulkFlag();
  }, [fetchEmployees, fetchBulkFlag]);

  // ---- Email dispatch helpers ----
  const sendInvite = async ({ employee_id, email }) => {
    const key = email || employee_id;
    setSendingTo(key);
    try {
      const res = await axios.post(
        `${API}/admin/profile-upload-email/send`,
        { target: 'single', employee_id, email },
        { headers: getAuthHeaders() }
      );
      const sent = res.data?.sent?.[0];
      if (sent) {
        toast.success(`Email sent to ${sent.email}`);
      } else {
        toast.error(res.data?.failed?.[0]?.reason || 'Send failed');
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to send invite');
    } finally {
      setSendingTo(null);
    }
  };

  const sendPilot = async () => {
    const v = (pilotEmail || '').trim();
    if (!v) return toast.error('Enter an email');
    await sendInvite({ email: v });
  };

  const toggleBulkFlag = async (next) => {
    try {
      await axios.put(
        `${API}/admin/profile-upload-email/settings`,
        { enable_bulk: next },
        { headers: getAuthHeaders() }
      );
      setBulkEnabled(next);
      toast.success(`Bulk dispatch ${next ? 'enabled' : 'disabled'}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update flag');
    }
  };

  const sendBulk = async () => {
    if (!bulkEnabled) {
      toast.error('Enable bulk dispatch first (only after a successful pilot).');
      return;
    }
    const count = employees.filter((e) => !e.avatar && e.official_email).length;
    if (!window.confirm(`Send the upload email to ${count} employees who don't yet have a profile photo?`)) return;
    setBulkBusy(true);
    try {
      const res = await axios.post(
        `${API}/admin/profile-upload-email/send`,
        { target: 'all' },
        { headers: getAuthHeaders() }
      );
      toast.success(`Sent ${res.data?.count || 0} emails (${res.data?.failed?.length || 0} failed)`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Bulk send failed');
    } finally {
      setBulkBusy(false);
    }
  };

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
        if (photoFilter === 'with') return !!(e.avatar || getAvatarById?.(e.id));
        if (photoFilter === 'without') return !(e.avatar || getAvatarById?.(e.id));
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
    () => employees.filter((e) => e.avatar || getAvatarById?.(e.id)).length,
    [employees, getAvatarById]
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

      {/* Email Tools — Pilot dispatch panel */}
      <div className="card-flat p-5 border border-[#0a5cba]/15 bg-gradient-to-r from-[#063c88]/5 to-white" data-testid="profile-upload-email-tools">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-9 h-9 rounded-lg bg-[#063c88] flex items-center justify-center flex-shrink-0">
            <Mail className="w-4 h-4 text-white" />
          </div>
          <div className="flex-1">
            <h2 className="font-semibold text-slate-900" style={{ fontFamily: 'Outfit' }}>
              Profile picture invite email
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Send a secure, single-use link inviting an employee to upload their photo. Currently in <span className="font-medium text-[#063c88]">pilot mode</span> — send to one address at a time. Enable bulk dispatch only after the pilot is confirmed working.
            </p>
          </div>
        </div>

        <div className="flex flex-col md:flex-row gap-3 md:items-center">
          <Input
            type="email"
            placeholder="employee@blubridge.com"
            value={pilotEmail}
            onChange={(e) => setPilotEmail(e.target.value)}
            className="md:max-w-sm"
            data-testid="pilot-email-input"
          />
          <Button
            onClick={sendPilot}
            disabled={!!sendingTo}
            data-testid="send-pilot-email-btn"
            className="bg-[#063c88] hover:bg-[#0a5cba] text-white"
          >
            {sendingTo ? (
              <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Sending…</>
            ) : (
              <><Send className="w-4 h-4 mr-2" /> Send pilot email</>
            )}
          </Button>

          <div className="md:ml-auto flex items-center gap-3 bg-white border border-slate-200 rounded-xl px-4 py-2">
            <Switch
              checked={bulkEnabled}
              onCheckedChange={toggleBulkFlag}
              data-testid="bulk-flag-switch"
            />
            <div className="text-xs">
              <div className="font-semibold text-slate-900 flex items-center gap-1">
                {bulkEnabled ? 'Bulk dispatch ON' : 'Bulk dispatch OFF'}
                {bulkEnabled && <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />}
              </div>
              <div className="text-slate-500">enable_profile_upload_mail</div>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={sendBulk}
              disabled={!bulkEnabled || bulkBusy}
              data-testid="send-bulk-email-btn"
            >
              {bulkBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Send to all'}
            </Button>
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
              {list.map((emp) => {
                const hasPhoto = !!(emp.avatar || getAvatarById?.(emp.id));
                return (
                <div
                  key={emp.id}
                  className="card-flat p-4 flex flex-col items-center text-center hover:shadow-lg transition cursor-pointer group relative"
                  data-testid={`photo-wall-card-${emp.id}`}
                  title={`Click to ${hasPhoto ? 'replace' : 'upload'} photo`}
                  onClick={() => setActiveEmployee(emp)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setActiveEmployee(emp);
                    }
                  }}
                >
                  <div className="relative mb-3">
                    <EmployeeAvatar
                      employee={emp}
                      size="photo-wall"
                      shape="circle"
                      className="shadow-sm"
                    />
                    {/* Hover overlay — camera icon */}
                    <div className="absolute inset-0 rounded-full bg-slate-900/50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                      <Camera className="w-6 h-6 text-white" />
                    </div>
                  </div>
                  <p className="text-sm font-semibold text-slate-900 truncate w-full" title={emp.full_name}>
                    {emp.full_name}
                  </p>
                  <p className="text-[11px] text-slate-500 truncate w-full" title={emp.designation}>
                    {emp.designation || '—'}
                  </p>
                  <p className="text-[10px] text-[#063c88] font-medium mt-1 truncate w-full">
                    {emp.custom_employee_id || emp.emp_id}
                  </p>
                  {!hasPhoto && (
                    <>
                      <span className="mt-2 text-[10px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-100">
                        Pending Photo
                      </span>
                      {emp.official_email && (
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); sendInvite({ employee_id: emp.id }); }}
                          disabled={sendingTo === emp.id}
                          data-testid={`invite-${emp.id}`}
                          className="mt-2 inline-flex items-center justify-center gap-1 text-[10px] px-2 py-1 rounded-md bg-[#063c88]/5 text-[#063c88] hover:bg-[#063c88] hover:text-white transition disabled:opacity-60"
                          title="Send the upload-photo email to this employee"
                        >
                          {sendingTo === emp.id ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Send className="w-3 h-3" />
                          )}
                          Invite
                        </button>
                      )}
                    </>
                  )}
                  {hasPhoto && (
                    <span className="mt-2 text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100">
                      ✓ Photo uploaded
                    </span>
                  )}
                </div>
                );
              })}
            </div>
          </section>
        ))
      )}

      {/* Admin avatar upload dialog */}
      <AvatarUploadDialog
        open={!!activeEmployee}
        employee={activeEmployee}
        token={token}
        onClose={() => setActiveEmployee(null)}
        onUpdated={(updated) => {
          // Patch local list so the card flips to "Photo uploaded" instantly,
          // without waiting for the centralized refreshAvatars round-trip.
          if (updated?.id) {
            setEmployees((prev) =>
              prev.map((e) => (e.id === updated.id ? { ...e, ...updated } : e))
            );
          } else {
            fetchEmployees();
          }
        }}
      />
    </div>
  );
};

export default EmployeePhotoWall;
