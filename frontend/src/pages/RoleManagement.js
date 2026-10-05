import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Shield, Users, UserCog, Eye, Search, ChevronDown } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/dialog';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const roleConfig = {
  hr: { label: 'HR Team', color: 'bg-emerald-100 text-emerald-700 border-emerald-200', description: 'Full control over all HR modules' },
  system_admin: { label: 'System Admin', color: 'bg-blue-100 text-blue-700 border-blue-200', description: 'System control + limited HRMS view access' },
  office_admin: { label: 'Office Admin', color: 'bg-amber-100 text-amber-700 border-amber-200', description: 'View employee data + limited operational access' },
  employee: { label: 'Employee', color: 'bg-slate-100 text-slate-700 border-slate-200', description: 'Self-service employee portal' },
};

export default function RoleManagement() {
  const { token, user } = useAuth();
  const [users, setUsers] = useState([]);
  const [permissions, setPermissions] = useState({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterRole, setFilterRole] = useState('all');
  const [editDialog, setEditDialog] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [newRole, setNewRole] = useState('');

  const headers = { Authorization: `Bearer ${token}` };

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [usersRes, permRes] = await Promise.all([
        axios.get(`${API}/roles/users`, { headers }),
        axios.get(`${API}/roles/permissions`, { headers }),
      ]);
      setUsers(usersRes.data);
      setPermissions(permRes.data);
    } catch (err) {
      toast.error('Failed to load role data');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filteredUsers = users.filter(u => {
    const matchSearch = !search || u.name?.toLowerCase().includes(search.toLowerCase()) || u.username?.toLowerCase().includes(search.toLowerCase());
    const matchRole = filterRole === 'all' || u.role === filterRole;
    return matchSearch && matchRole;
  });

  const handleEditRole = (u) => {
    setSelectedUser(u);
    setNewRole(u.role);
    setEditDialog(true);
  };

  const handleSaveRole = async () => {
    if (!selectedUser || !newRole || newRole === selectedUser.role) return;
    try {
      await axios.put(`${API}/roles/users/${selectedUser.id}/role`, { role: newRole }, { headers });
      toast.success(`Role updated to ${roleConfig[newRole]?.label || newRole}`);
      setEditDialog(false);
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update role');
    }
  };

  const roleCounts = users.reduce((acc, u) => {
    acc[u.role] = (acc[u.role] || 0) + 1;
    return acc;
  }, {});

  const isHR = user?.role === 'hr';

  return (
    <div className="space-y-6" data-testid="role-management-page">
      {/* Role Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.entries(roleConfig).map(([role, config]) => (
          <div key={role} className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm" data-testid={`role-card-${role}`}>
            <div className="flex items-center gap-3 mb-3">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${config.color}`}>
                <Shield className="w-5 h-5" />
              </div>
              <div>
                <p className="text-sm font-bold text-slate-900">{config.label}</p>
                <p className="text-xs text-slate-500">{roleCounts[role] || 0} users</p>
              </div>
            </div>
            <p className="text-xs text-slate-500">{config.description}</p>
          </div>
        ))}
      </div>

      {/* Permission Matrix */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        <div className="p-5 border-b border-slate-100">
          <h3 className="text-base font-bold text-slate-900">Permission Matrix</h3>
          <p className="text-xs text-slate-500 mt-1">Access levels for each role across modules</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50">
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">Role</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">Permissions</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(permissions).map(([role, data]) => (
                <tr key={role} className="border-t border-slate-50 hover:bg-slate-50/50">
                  <td className="px-5 py-4">
                    <Badge className={`${roleConfig[role]?.color || 'bg-slate-100'} border text-xs`}>
                      {data.label}
                    </Badge>
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex flex-wrap gap-1.5">
                      {data.permissions?.map((perm) => (
                        <span key={perm} className="text-[11px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">
                          {perm}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-bold text-slate-900">User Roles</h3>
            <p className="text-xs text-slate-500 mt-1">{filteredUsers.length} users</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search users..."
                className="pl-10 h-9 w-56 bg-slate-50 border-slate-200 rounded-xl text-sm"
                data-testid="role-search-input"
              />
            </div>
            <Select value={filterRole} onValueChange={setFilterRole}>
              <SelectTrigger className="w-40 h-9 bg-slate-50 border-slate-200 rounded-xl text-sm" data-testid="role-filter-select">
                <SelectValue placeholder="Filter by role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Roles</SelectItem>
                <SelectItem value="hr">HR Team</SelectItem>
                <SelectItem value="system_admin">System Admin</SelectItem>
                <SelectItem value="office_admin">Office Admin</SelectItem>
                <SelectItem value="employee">Employee</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {loading ? (
          <div className="p-12 flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#0b1f3b]" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">User</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">Username</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">Email</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">Role</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">Department</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">Status</th>
                  {isHR && <th className="text-left px-5 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((u) => (
                  <tr key={u.id} className="border-t border-slate-50 hover:bg-slate-50/50" data-testid={`user-row-${u.username}`}>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#063c88] to-[#0a5cba] flex items-center justify-center">
                          <span className="text-white text-xs font-semibold">{u.name?.charAt(0)?.toUpperCase()}</span>
                        </div>
                        <span className="font-medium text-slate-900">{u.name}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-slate-600">{u.username}</td>
                    <td className="px-5 py-3.5 text-slate-600">{u.email}</td>
                    <td className="px-5 py-3.5">
                      <Badge className={`${roleConfig[u.role]?.color || 'bg-slate-100'} border text-xs`}>
                        {roleConfig[u.role]?.label || u.role}
                      </Badge>
                    </td>
                    <td className="px-5 py-3.5 text-slate-600">{u.department || '-'}</td>
                    <td className="px-5 py-3.5">
                      <Badge className={u.is_active !== false ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-red-50 text-red-700 border-red-200'}>
                        {u.is_active !== false ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                    {isHR && (
                      <td className="px-5 py-3.5">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEditRole(u)}
                          className="text-xs h-7"
                          data-testid={`edit-role-${u.username}`}
                        >
                          <UserCog className="w-3.5 h-3.5 mr-1" />
                          Edit Role
                        </Button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Edit Role Dialog */}
      <Dialog open={editDialog} onOpenChange={setEditDialog}>
        <DialogContent className="sm:max-w-md" data-testid="edit-role-dialog">
          <DialogHeader>
            <DialogTitle>Change User Role</DialogTitle>
          </DialogHeader>
          {selectedUser && (
            <div className="space-y-4 py-4">
              <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-xl">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#063c88] to-[#0a5cba] flex items-center justify-center">
                  <span className="text-white font-semibold">{selectedUser.name?.charAt(0)?.toUpperCase()}</span>
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">{selectedUser.name}</p>
                  <p className="text-xs text-slate-500">{selectedUser.email}</p>
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1.5 block">Current Role</label>
                <Badge className={`${roleConfig[selectedUser.role]?.color} border text-xs`}>
                  {roleConfig[selectedUser.role]?.label || selectedUser.role}
                </Badge>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700 mb-1.5 block">New Role</label>
                <Select value={newRole} onValueChange={setNewRole}>
                  <SelectTrigger className="w-full" data-testid="new-role-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="hr">HR Team</SelectItem>
                    <SelectItem value="system_admin">System Admin</SelectItem>
                    <SelectItem value="office_admin">Office Admin</SelectItem>
                    <SelectItem value="employee">Employee</SelectItem>
                  </SelectContent>
                </Select>
                {newRole && permissions[newRole] && (
                  <p className="text-xs text-slate-500 mt-2">{permissions[newRole]?.description}</p>
                )}
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialog(false)} data-testid="cancel-role-edit">Cancel</Button>
            <Button
              onClick={handleSaveRole}
              disabled={!newRole || newRole === selectedUser?.role}
              className="bg-[#0b1f3b] hover:bg-[#0b1f3b]/90"
              data-testid="save-role-btn"
            >
              Update Role
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
