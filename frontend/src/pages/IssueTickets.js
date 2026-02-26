import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '../components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Search,
  Plus,
  Filter,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertCircle,
  Paperclip,
  Flag,
  Monitor,
  HeartHandshake,
  Banknote,
  Briefcase,
  Scale,
  Activity,
  ChevronRight,
  Star,
  MessageSquare,
  User,
  Calendar,
  ArrowUpRight,
  PauseCircle,
  RefreshCw
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Status configuration with premium design colors
const STATUS_CONFIG = {
  'Open': { color: 'bg-blue-50 text-blue-700 border-blue-200', icon: AlertCircle },
  'In Progress': { color: 'bg-purple-50 text-purple-700 border-purple-200', icon: RefreshCw },
  'Waiting for Approval': { color: 'bg-amber-50 text-amber-700 border-amber-200', icon: Clock },
  'On Hold': { color: 'bg-orange-50 text-orange-700 border-orange-200', icon: PauseCircle },
  'Resolved': { color: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: CheckCircle2 },
  'Closed': { color: 'bg-slate-100 text-slate-600 border-slate-200', icon: CheckCircle2 },
  'Rejected': { color: 'bg-red-50 text-red-700 border-red-200', icon: XCircle }
};

const PRIORITY_CONFIG = {
  'High': { color: 'bg-red-50 text-red-700 border-red-200', dotColor: 'bg-red-500' },
  'Medium': { color: 'bg-amber-50 text-amber-700 border-amber-200', dotColor: 'bg-amber-500' },
  'Low': { color: 'bg-slate-100 text-slate-600 border-slate-200', dotColor: 'bg-slate-400' }
};

const CATEGORY_ICONS = {
  'IT & System Support': Monitor,
  'HR Support': HeartHandshake,
  'Finance & Accounts': Banknote,
  'Admin & Stationery': Briefcase,
  'Compliance & Legal': Scale,
  'Operations': Activity
};

const CATEGORY_COLORS = {
  'IT & System Support': 'text-blue-600 bg-blue-50',
  'HR Support': 'text-rose-600 bg-rose-50',
  'Finance & Accounts': 'text-emerald-600 bg-emerald-50',
  'Admin & Stationery': 'text-orange-600 bg-orange-50',
  'Compliance & Legal': 'text-slate-600 bg-slate-100',
  'Operations': 'text-teal-600 bg-teal-50'
};

const IssueTickets = () => {
  const { token, user } = useAuth();
  
  const [tickets, setTickets] = useState([]);
  const [stats, setStats] = useState(null);
  const [categories, setCategories] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState('All');
  const [priorityFilter, setPriorityFilter] = useState('All');
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [searchTerm, setSearchTerm] = useState('');
  
  // Modal states
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [createModal, setCreateModal] = useState(false);
  const [newTicket, setNewTicket] = useState({
    category: '',
    subcategory: '',
    subject: '',
    description: '',
    priority: 'Medium',
    employee_id: ''
  });
  const [processing, setProcessing] = useState(false);
  const [statusUpdate, setStatusUpdate] = useState({ status: '', notes: '', resolution: '' });

  const isAdmin = ['super_admin', 'admin', 'hr_manager'].includes(user?.role);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const params = {
        status: statusFilter !== 'All' ? statusFilter : undefined,
        priority: priorityFilter !== 'All' ? priorityFilter : undefined,
        category: categoryFilter !== 'All' ? categoryFilter : undefined,
        search: searchTerm || undefined
      };
      
      const requests = [
        axios.get(`${API}/issue-tickets`, { params, headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/issue-tickets/stats`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/issue-tickets/categories`, { headers: { Authorization: `Bearer ${token}` } })
      ];
      
      if (isAdmin) {
        requests.push(axios.get(`${API}/employees/all`, { headers: { Authorization: `Bearer ${token}` } }));
      }
      
      const responses = await Promise.all(requests);
      setTickets(responses[0].data.tickets || []);
      setStats(responses[1].data);
      setCategories(responses[2].data);
      if (responses[3]) {
        setEmployees(responses[3].data);
      }
    } catch (error) {
      console.error('Error fetching tickets:', error);
      toast.error('Failed to load tickets');
    } finally {
      setLoading(false);
    }
  }, [token, statusFilter, priorityFilter, categoryFilter, searchTerm, isAdmin]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCreateTicket = async () => {
    if (!newTicket.category || !newTicket.subcategory || !newTicket.subject.trim() || !newTicket.description.trim()) {
      toast.error('Please fill in all required fields');
      return;
    }
    
    setProcessing(true);
    try {
      await axios.post(`${API}/issue-tickets`, newTicket, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Ticket created successfully');
      setCreateModal(false);
      setNewTicket({ category: '', subcategory: '', subject: '', description: '', priority: 'Medium', employee_id: '' });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create ticket');
    } finally {
      setProcessing(false);
    }
  };

  const handleStatusUpdate = async () => {
    if (!statusUpdate.status) {
      toast.error('Please select a status');
      return;
    }
    
    setProcessing(true);
    try {
      await axios.put(`${API}/issue-tickets/${selectedTicket.id}/status`, statusUpdate, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Ticket status updated');
      setSelectedTicket(null);
      setStatusUpdate({ status: '', notes: '', resolution: '' });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update ticket');
    } finally {
      setProcessing(false);
    }
  };

  const getSubcategories = () => {
    const cat = categories.find(c => c.category === newTicket.category);
    return cat?.subcategories || [];
  };

  const StatCard = ({ label, value, icon: Icon, color, trend }) => (
    <div className="stat-card group cursor-default">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">{label}</p>
          <p className="text-3xl font-bold text-[#0b1f3b] number-display">{value}</p>
          {trend && (
            <p className={`text-xs mt-1 ${trend > 0 ? 'text-emerald-600' : 'text-red-500'}`}>
              {trend > 0 ? '+' : ''}{trend}% from last week
            </p>
          )}
        </div>
        <div className={`w-12 h-12 rounded-xl ${color} flex items-center justify-center transition-transform group-hover:scale-110`}>
          <Icon className="w-6 h-6" strokeWidth={1.5} />
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-in" data-testid="issue-tickets-page">
      {/* Stats Section */}
      {stats && (
        <div className="bento-grid">
          <div className="bento-card span-3">
            <StatCard 
              label="Total Tickets" 
              value={stats.total} 
              icon={MessageSquare} 
              color="bg-blue-100 text-blue-600" 
            />
          </div>
          <div className="bento-card span-3">
            <StatCard 
              label="Open" 
              value={stats.by_status?.['Open'] || 0} 
              icon={AlertCircle} 
              color="bg-blue-100 text-blue-600" 
            />
          </div>
          <div className="bento-card span-3">
            <StatCard 
              label="In Progress" 
              value={stats.by_status?.['In Progress'] || 0} 
              icon={RefreshCw} 
              color="bg-purple-100 text-purple-600" 
            />
          </div>
          <div className="bento-card span-3">
            <StatCard 
              label="Resolved" 
              value={stats.by_status?.['Resolved'] || 0} 
              icon={CheckCircle2} 
              color="bg-emerald-100 text-emerald-600" 
            />
          </div>
        </div>
      )}

      {/* Priority Summary */}
      {stats && isAdmin && (
        <div className="grid grid-cols-3 gap-4">
          {['High', 'Medium', 'Low'].map(priority => (
            <div key={priority} className="card-flat p-4 flex items-center gap-4">
              <div className={`w-3 h-3 rounded-full ${PRIORITY_CONFIG[priority]?.dotColor}`} />
              <div>
                <p className="text-sm font-medium text-slate-700">{priority} Priority</p>
                <p className="text-2xl font-bold text-slate-900">{stats.by_priority?.[priority] || 0}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filters and Actions */}
      <Card className="card-premium">
        <CardContent className="p-6">
          <div className="flex flex-col lg:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <Input
                placeholder="Search tickets by number, subject, or employee..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-12 h-12 bg-slate-50 border-0 rounded-xl"
                data-testid="ticket-search-input"
              />
            </div>
            <div className="flex gap-3 flex-wrap">
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[160px] h-12 rounded-xl" data-testid="status-filter">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="All">All Status</SelectItem>
                  {Object.keys(STATUS_CONFIG).map(status => (
                    <SelectItem key={status} value={status}>{status}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={priorityFilter} onValueChange={setPriorityFilter}>
                <SelectTrigger className="w-[140px] h-12 rounded-xl" data-testid="priority-filter">
                  <SelectValue placeholder="Priority" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="All">All Priority</SelectItem>
                  <SelectItem value="High">High</SelectItem>
                  <SelectItem value="Medium">Medium</SelectItem>
                  <SelectItem value="Low">Low</SelectItem>
                </SelectContent>
              </Select>
              <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                <SelectTrigger className="w-[180px] h-12 rounded-xl" data-testid="category-filter">
                  <SelectValue placeholder="Category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="All">All Categories</SelectItem>
                  {categories.map(cat => (
                    <SelectItem key={cat.category} value={cat.category}>{cat.category}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button 
                onClick={() => setCreateModal(true)} 
                className="h-12 px-6 bg-[#063c88] hover:bg-[#052d66] rounded-xl shadow-lg shadow-blue-900/20"
                data-testid="create-ticket-btn"
              >
                <Plus className="w-5 h-5 mr-2" />
                New Ticket
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tickets List */}
      <Card className="card-premium overflow-hidden">
        <CardHeader className="border-b border-slate-100 bg-gradient-to-r from-slate-50/80 to-white">
          <CardTitle className="text-xl font-semibold text-[#0b1f3b]" style={{ fontFamily: 'Outfit' }}>
            Issue Tickets
          </CardTitle>
          <CardDescription>
            {isAdmin ? 'Manage and resolve employee support requests' : 'Track your support tickets'}
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 animate-spin text-[#063c88]" />
            </div>
          ) : tickets.length === 0 ? (
            <div className="text-center py-20">
              <div className="w-20 h-20 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4">
                <MessageSquare className="w-10 h-10 text-slate-400" />
              </div>
              <p className="text-slate-500 text-lg">No tickets found</p>
              <p className="text-slate-400 text-sm mt-1">Create a new ticket to get started</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {tickets.map((ticket, index) => {
                const StatusIcon = STATUS_CONFIG[ticket.status]?.icon || AlertCircle;
                const CategoryIcon = CATEGORY_ICONS[ticket.category] || MessageSquare;
                
                return (
                  <div 
                    key={ticket.id}
                    className="p-5 hover:bg-slate-50/50 transition-colors cursor-pointer group animate-slide-up"
                    style={{ animationDelay: `${index * 0.03}s` }}
                    onClick={() => setSelectedTicket(ticket)}
                    data-testid={`ticket-row-${ticket.id}`}
                  >
                    <div className="flex items-start gap-4">
                      {/* Category Icon */}
                      <div className={`w-12 h-12 rounded-xl ${CATEGORY_COLORS[ticket.category]} flex items-center justify-center flex-shrink-0`}>
                        <CategoryIcon className="w-6 h-6" />
                      </div>
                      
                      {/* Ticket Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-xs font-mono text-slate-500">{ticket.ticket_number}</span>
                              <Badge className={`${PRIORITY_CONFIG[ticket.priority]?.color} border text-[10px] px-2`}>
                                {ticket.priority}
                              </Badge>
                            </div>
                            <h3 className="font-semibold text-slate-900 line-clamp-1 group-hover:text-[#063c88] transition-colors">
                              {ticket.subject}
                            </h3>
                            <p className="text-sm text-slate-500 line-clamp-1 mt-0.5">{ticket.description}</p>
                          </div>
                          <Badge className={`${STATUS_CONFIG[ticket.status]?.color} border flex items-center gap-1.5 px-3 py-1`}>
                            <StatusIcon className="w-3.5 h-3.5" />
                            {ticket.status}
                          </Badge>
                        </div>
                        
                        <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
                          <div className="flex items-center gap-1.5">
                            <User className="w-3.5 h-3.5" />
                            <span>{ticket.emp_name}</span>
                          </div>
                          <span className="text-slate-300">•</span>
                          <div className="flex items-center gap-1.5">
                            <CategoryIcon className="w-3.5 h-3.5" />
                            <span>{ticket.subcategory}</span>
                          </div>
                          <span className="text-slate-300">•</span>
                          <div className="flex items-center gap-1.5">
                            <Calendar className="w-3.5 h-3.5" />
                            <span>{new Date(ticket.created_at).toLocaleDateString()}</span>
                          </div>
                          {ticket.attachments?.length > 0 && (
                            <>
                              <span className="text-slate-300">•</span>
                              <div className="flex items-center gap-1">
                                <Paperclip className="w-3.5 h-3.5" />
                                <span>{ticket.attachments.length} files</span>
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                      
                      <ChevronRight className="w-5 h-5 text-slate-300 group-hover:text-slate-500 group-hover:translate-x-1 transition-all flex-shrink-0" />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Ticket Modal */}
      <Dialog open={createModal} onOpenChange={setCreateModal}>
        <DialogContent className="max-w-2xl glass">
          <DialogHeader>
            <DialogTitle className="text-2xl" style={{ fontFamily: 'Outfit' }}>Create New Ticket</DialogTitle>
            <DialogDescription>
              {isAdmin ? 'Create a ticket for yourself or on behalf of an employee' : 'Describe your issue and we\'ll help you resolve it'}
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-5 py-4">
            {/* Employee Selection (Admin Only) */}
            {isAdmin && (
              <div>
                <label className="text-sm font-medium text-slate-700 mb-2 block">Create on behalf of (Optional)</label>
                <Select 
                  value={newTicket.employee_id || "self"} 
                  onValueChange={(v) => setNewTicket({ ...newTicket, employee_id: v === "self" ? "" : v })}
                >
                  <SelectTrigger data-testid="employee-select">
                    <SelectValue placeholder="Select employee (or leave blank for yourself)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="self">Myself</SelectItem>
                    {employees.map(emp => (
                      <SelectItem key={emp.id} value={emp.id}>
                        {emp.full_name} ({emp.emp_id})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Category & Subcategory */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-slate-700 mb-2 block">Category *</label>
                <Select 
                  value={newTicket.category} 
                  onValueChange={(v) => setNewTicket({ ...newTicket, category: v, subcategory: '' })}
                >
                  <SelectTrigger data-testid="category-select">
                    <SelectValue placeholder="Select category" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map(cat => {
                      const Icon = CATEGORY_ICONS[cat.category] || MessageSquare;
                      return (
                        <SelectItem key={cat.category} value={cat.category}>
                          <div className="flex items-center gap-2">
                            <Icon className="w-4 h-4" />
                            {cat.category}
                          </div>
                        </SelectItem>
                      );
                    })}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700 mb-2 block">Subcategory *</label>
                <Select 
                  value={newTicket.subcategory} 
                  onValueChange={(v) => setNewTicket({ ...newTicket, subcategory: v })}
                  disabled={!newTicket.category}
                >
                  <SelectTrigger data-testid="subcategory-select">
                    <SelectValue placeholder="Select subcategory" />
                  </SelectTrigger>
                  <SelectContent>
                    {getSubcategories().map(sub => (
                      <SelectItem key={sub} value={sub}>{sub}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Subject */}
            <div>
              <label className="text-sm font-medium text-slate-700 mb-2 block">Subject *</label>
              <Input
                placeholder="Brief summary of your issue..."
                value={newTicket.subject}
                onChange={(e) => setNewTicket({ ...newTicket, subject: e.target.value })}
                className="h-12 bg-white/50"
                data-testid="subject-input"
              />
            </div>

            {/* Description */}
            <div>
              <label className="text-sm font-medium text-slate-700 mb-2 block">Description *</label>
              <Textarea
                placeholder="Provide detailed information about your issue..."
                value={newTicket.description}
                onChange={(e) => setNewTicket({ ...newTicket, description: e.target.value })}
                rows={4}
                className="bg-white/50"
                data-testid="description-input"
              />
            </div>

            {/* Priority */}
            <div>
              <label className="text-sm font-medium text-slate-700 mb-2 block">Priority</label>
              <div className="flex gap-3">
                {['Low', 'Medium', 'High'].map(priority => (
                  <button
                    key={priority}
                    type="button"
                    onClick={() => setNewTicket({ ...newTicket, priority })}
                    className={`flex-1 h-12 rounded-xl border-2 transition-all flex items-center justify-center gap-2 ${
                      newTicket.priority === priority 
                        ? 'border-[#063c88] bg-[#063c88]/5 text-[#063c88]' 
                        : 'border-slate-200 hover:border-slate-300'
                    }`}
                    data-testid={`priority-${priority.toLowerCase()}`}
                  >
                    <Flag className={`w-4 h-4 ${priority === 'High' ? 'text-red-500' : priority === 'Medium' ? 'text-amber-500' : 'text-slate-400'}`} />
                    {priority}
                  </button>
                ))}
              </div>
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateModal(false)} className="rounded-xl">
              Cancel
            </Button>
            <Button 
              onClick={handleCreateTicket}
              disabled={processing}
              className="bg-[#063c88] hover:bg-[#052d66] rounded-xl px-8"
              data-testid="submit-ticket-btn"
            >
              {processing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Plus className="w-4 h-4 mr-2" />}
              Create Ticket
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Ticket Detail Modal */}
      <Dialog open={!!selectedTicket} onOpenChange={() => setSelectedTicket(null)}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          {selectedTicket && (
            <>
              <DialogHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs font-mono text-slate-500 mb-1">{selectedTicket.ticket_number}</p>
                    <DialogTitle className="text-xl" style={{ fontFamily: 'Outfit' }}>
                      {selectedTicket.subject}
                    </DialogTitle>
                  </div>
                  <Badge className={`${STATUS_CONFIG[selectedTicket.status]?.color} border`}>
                    {selectedTicket.status}
                  </Badge>
                </div>
              </DialogHeader>
              
              <Tabs defaultValue="details" className="mt-4">
                <TabsList className="bg-slate-100 p-1 rounded-xl">
                  <TabsTrigger value="details" className="rounded-lg">Details</TabsTrigger>
                  <TabsTrigger value="timeline" className="rounded-lg">Timeline</TabsTrigger>
                  {isAdmin && <TabsTrigger value="actions" className="rounded-lg">Actions</TabsTrigger>}
                </TabsList>
                
                <TabsContent value="details" className="space-y-4 mt-4">
                  {/* Meta Info */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 bg-slate-50 rounded-xl">
                      <p className="text-xs text-slate-500 mb-1">Employee</p>
                      <p className="font-medium text-slate-900">{selectedTicket.emp_name}</p>
                      <p className="text-sm text-slate-500">{selectedTicket.department}</p>
                    </div>
                    <div className="p-4 bg-slate-50 rounded-xl">
                      <p className="text-xs text-slate-500 mb-1">Category</p>
                      <div className="flex items-center gap-2">
                        {(() => {
                          const Icon = CATEGORY_ICONS[selectedTicket.category] || MessageSquare;
                          return <Icon className="w-4 h-4 text-slate-600" />;
                        })()}
                        <span className="font-medium text-slate-900">{selectedTicket.category}</span>
                      </div>
                      <p className="text-sm text-slate-500">{selectedTicket.subcategory}</p>
                    </div>
                    <div className="p-4 bg-slate-50 rounded-xl">
                      <p className="text-xs text-slate-500 mb-1">Priority</p>
                      <Badge className={`${PRIORITY_CONFIG[selectedTicket.priority]?.color} border`}>
                        {selectedTicket.priority}
                      </Badge>
                    </div>
                    <div className="p-4 bg-slate-50 rounded-xl">
                      <p className="text-xs text-slate-500 mb-1">Created</p>
                      <p className="font-medium text-slate-900">
                        {new Date(selectedTicket.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                  
                  {/* Description */}
                  <div className="p-4 bg-slate-50 rounded-xl">
                    <p className="text-xs text-slate-500 mb-2">Description</p>
                    <p className="text-slate-700 whitespace-pre-wrap">{selectedTicket.description}</p>
                  </div>
                  
                  {/* Resolution */}
                  {selectedTicket.resolution && (
                    <div className="p-4 bg-emerald-50 rounded-xl border border-emerald-200">
                      <p className="text-xs text-emerald-600 font-medium mb-2">Resolution</p>
                      <p className="text-emerald-800">{selectedTicket.resolution}</p>
                      {selectedTicket.resolved_by_name && (
                        <p className="text-xs text-emerald-600 mt-2">
                          Resolved by {selectedTicket.resolved_by_name}
                        </p>
                      )}
                    </div>
                  )}
                  
                  {/* Attachments */}
                  {selectedTicket.attachments?.length > 0 && (
                    <div>
                      <p className="text-sm font-medium text-slate-700 mb-2">Attachments</p>
                      <div className="space-y-2">
                        {selectedTicket.attachments.map((att, i) => (
                          <a 
                            key={i}
                            href={att.file_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors"
                          >
                            <Paperclip className="w-4 h-4 text-slate-500" />
                            <span className="text-sm text-slate-700">{att.file_name}</span>
                            <ArrowUpRight className="w-4 h-4 text-slate-400 ml-auto" />
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {/* Feedback */}
                  {selectedTicket.feedback && (
                    <div className="p-4 bg-amber-50 rounded-xl border border-amber-200">
                      <p className="text-xs text-amber-700 font-medium mb-2">Employee Feedback</p>
                      <div className="flex items-center gap-1 mb-2">
                        {[1, 2, 3, 4, 5].map(star => (
                          <Star 
                            key={star} 
                            className={`w-5 h-5 ${star <= selectedTicket.feedback.rating ? 'text-amber-500 fill-amber-500' : 'text-slate-300'}`} 
                          />
                        ))}
                      </div>
                      {selectedTicket.feedback.comment && (
                        <p className="text-sm text-amber-800">{selectedTicket.feedback.comment}</p>
                      )}
                    </div>
                  )}
                </TabsContent>
                
                <TabsContent value="timeline" className="mt-4">
                  <div className="space-y-4">
                    {selectedTicket.status_history?.map((update, i) => (
                      <div key={i} className="flex gap-4">
                        <div className="flex flex-col items-center">
                          <div className={`w-3 h-3 rounded-full ${STATUS_CONFIG[update.status]?.color.split(' ')[0] || 'bg-slate-300'}`} />
                          {i < selectedTicket.status_history.length - 1 && (
                            <div className="w-px h-full bg-slate-200 my-1" />
                          )}
                        </div>
                        <div className="pb-4">
                          <div className="flex items-center gap-2">
                            <Badge className={`${STATUS_CONFIG[update.status]?.color} border text-xs`}>
                              {update.status}
                            </Badge>
                            <span className="text-xs text-slate-500">
                              {new Date(update.updated_at).toLocaleString()}
                            </span>
                          </div>
                          <p className="text-sm text-slate-600 mt-1">{update.notes || 'Status updated'}</p>
                          <p className="text-xs text-slate-400 mt-1">by {update.updated_by_name}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </TabsContent>
                
                {isAdmin && (
                  <TabsContent value="actions" className="mt-4 space-y-4">
                    <div>
                      <label className="text-sm font-medium text-slate-700 mb-2 block">Update Status</label>
                      <Select 
                        value={statusUpdate.status} 
                        onValueChange={(v) => setStatusUpdate({ ...statusUpdate, status: v })}
                      >
                        <SelectTrigger data-testid="status-update-select">
                          <SelectValue placeholder="Select new status" />
                        </SelectTrigger>
                        <SelectContent>
                          {Object.keys(STATUS_CONFIG).map(status => (
                            <SelectItem key={status} value={status}>{status}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div>
                      <label className="text-sm font-medium text-slate-700 mb-2 block">Notes</label>
                      <Textarea
                        placeholder="Add notes about this status change..."
                        value={statusUpdate.notes}
                        onChange={(e) => setStatusUpdate({ ...statusUpdate, notes: e.target.value })}
                        rows={2}
                      />
                    </div>
                    
                    {(statusUpdate.status === 'Resolved' || statusUpdate.status === 'Closed') && (
                      <div>
                        <label className="text-sm font-medium text-slate-700 mb-2 block">Resolution</label>
                        <Textarea
                          placeholder="Describe how the issue was resolved..."
                          value={statusUpdate.resolution}
                          onChange={(e) => setStatusUpdate({ ...statusUpdate, resolution: e.target.value })}
                          rows={3}
                        />
                      </div>
                    )}
                    
                    <Button 
                      onClick={handleStatusUpdate}
                      disabled={processing || !statusUpdate.status}
                      className="w-full bg-[#063c88] hover:bg-[#052d66] rounded-xl"
                      data-testid="update-status-btn"
                    >
                      {processing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                      Update Ticket
                    </Button>
                  </TabsContent>
                )}
              </Tabs>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default IssueTickets;
