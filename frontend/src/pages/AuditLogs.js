import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '../components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '../components/ui/table';
import {
  Search,
  Activity,
  User,
  FileText,
  Loader2,
  Clock,
  Shield,
  UserPlus,
  UserMinus,
  Edit,
  LogIn,
  LogOut as LogOutIcon,
  CheckCircle2,
  XCircle,
  Upload
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ACTION_ICONS = {
  login: LogIn,
  logout: LogOutIcon,
  create: UserPlus,
  update: Edit,
  delete: UserMinus,
  deactivate: UserMinus,
  restore: UserPlus,
  approve: CheckCircle2,
  reject: XCircle,
  upload: Upload,
  verify: CheckCircle2,
  submit: FileText
};

const ACTION_COLORS = {
  login: 'bg-blue-100 text-blue-700',
  logout: 'bg-slate-100 text-slate-600',
  create: 'bg-emerald-100 text-emerald-700',
  update: 'bg-amber-100 text-amber-700',
  delete: 'bg-red-100 text-red-700',
  deactivate: 'bg-red-100 text-red-700',
  restore: 'bg-emerald-100 text-emerald-700',
  approve: 'bg-emerald-100 text-emerald-700',
  reject: 'bg-red-100 text-red-700',
  upload: 'bg-blue-100 text-blue-700',
  verify: 'bg-emerald-100 text-emerald-700',
  submit: 'bg-blue-100 text-blue-700'
};

const RESOURCE_LABELS = {
  auth: 'Authentication',
  employee: 'Employee',
  attendance: 'Attendance',
  leave: 'Leave',
  onboarding: 'Onboarding',
  ticket: 'Ticket',
  star_reward: 'Star Reward',
  team: 'Team',
  department: 'Department'
};

const AuditLogs = () => {
  const { token } = useAuth();
  
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Filters
  const [resourceFilter, setResourceFilter] = useState('All');
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchLogs();
  }, [resourceFilter]);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      const params = {
        resource: resourceFilter !== 'All' ? resourceFilter : undefined,
        limit: 200
      };
      
      const response = await axios.get(`${API}/audit-logs`, {
        params,
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setLogs(response.data);
    } catch (error) {
      console.error('Error fetching audit logs:', error);
      toast.error('Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  };

  const getActionIcon = (action) => {
    const baseAction = action.split('_')[0];
    return ACTION_ICONS[baseAction] || Activity;
  };

  const getActionColor = (action) => {
    const baseAction = action.split('_')[0];
    return ACTION_COLORS[baseAction] || 'bg-slate-100 text-slate-600';
  };

  const formatAction = (action) => {
    return action
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const filteredLogs = logs.filter(log => {
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      return log.user_name?.toLowerCase().includes(search) ||
             log.action?.toLowerCase().includes(search) ||
             log.resource?.toLowerCase().includes(search) ||
             log.details?.toLowerCase().includes(search);
    }
    return true;
  });

  const formatDate = (dateStr) => {
    const date = new Date(dateStr);
    return {
      date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      time: date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    };
  };

  return (
    <div className="space-y-6" data-testid="audit-logs-page">
      {/* Header Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-[#fffdf7] border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-500">Total Logs</p>
                <p className="text-2xl font-bold text-slate-900">{logs.length}</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                <Activity className="w-5 h-5 text-blue-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#fffdf7] border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-500">Logins Today</p>
                <p className="text-2xl font-bold text-emerald-600">
                  {logs.filter(l => {
                    const today = new Date().toDateString();
                    return l.action === 'login' && new Date(l.timestamp).toDateString() === today;
                  }).length}
                </p>
              </div>
              <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center">
                <LogIn className="w-5 h-5 text-emerald-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#fffdf7] border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-500">Changes Today</p>
                <p className="text-2xl font-bold text-amber-600">
                  {logs.filter(l => {
                    const today = new Date().toDateString();
                    return ['create', 'update', 'delete'].includes(l.action.split('_')[0]) && 
                           new Date(l.timestamp).toDateString() === today;
                  }).length}
                </p>
              </div>
              <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
                <Edit className="w-5 h-5 text-amber-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#fffdf7] border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-500">Onboarding Actions</p>
                <p className="text-2xl font-bold text-purple-600">
                  {logs.filter(l => l.resource === 'onboarding').length}
                </p>
              </div>
              <div className="w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center">
                <Shield className="w-5 h-5 text-purple-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="bg-[#fffdf7] border-0 shadow-sm">
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                placeholder="Search logs..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
                data-testid="audit-search"
              />
            </div>
            <Select value={resourceFilter} onValueChange={setResourceFilter}>
              <SelectTrigger className="w-[180px]" data-testid="resource-filter">
                <SelectValue placeholder="Resource" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All Resources</SelectItem>
                <SelectItem value="auth">Authentication</SelectItem>
                <SelectItem value="employee">Employee</SelectItem>
                <SelectItem value="attendance">Attendance</SelectItem>
                <SelectItem value="leave">Leave</SelectItem>
                <SelectItem value="onboarding">Onboarding</SelectItem>
                <SelectItem value="ticket">Ticket</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Logs Table */}
      <Card className="bg-[#fffdf7] border-0 shadow-sm">
        <CardHeader>
          <CardTitle className="text-lg">Activity Log</CardTitle>
          <CardDescription>
            Track all system activities and changes
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
            </div>
          ) : filteredLogs.length === 0 ? (
            <div className="text-center py-12">
              <Activity className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500">No audit logs found</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Resource</TableHead>
                  <TableHead>Details</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredLogs.map((log) => {
                  const ActionIcon = getActionIcon(log.action);
                  const actionColor = getActionColor(log.action);
                  const { date, time } = formatDate(log.timestamp);
                  
                  return (
                    <TableRow key={log.id} data-testid={`log-row-${log.id}`}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Clock className="w-4 h-4 text-slate-400" />
                          <div>
                            <p className="text-sm font-medium text-slate-900">{date}</p>
                            <p className="text-xs text-slate-500">{time}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center">
                            <User className="w-4 h-4 text-slate-500" />
                          </div>
                          <span className="text-sm text-slate-700">{log.user_name || 'System'}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge className={actionColor}>
                          <ActionIcon className="w-3 h-3 mr-1" />
                          {formatAction(log.action)}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span className="text-sm text-slate-600">
                          {RESOURCE_LABELS[log.resource] || log.resource}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="text-sm text-slate-500 line-clamp-1 max-w-[200px]">
                          {log.details || '-'}
                        </span>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default AuditLogs;
