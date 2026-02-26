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
  Calendar,
  ArrowUpRight,
  PauseCircle,
  RefreshCw,
  Send,
  Upload
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Status configuration
const STATUS_CONFIG = {
  'Open': { color: 'bg-blue-50 text-blue-700 border-blue-200', icon: AlertCircle, description: 'Waiting for support' },
  'In Progress': { color: 'bg-purple-50 text-purple-700 border-purple-200', icon: RefreshCw, description: 'Being worked on' },
  'Waiting for Approval': { color: 'bg-amber-50 text-amber-700 border-amber-200', icon: Clock, description: 'Pending approval' },
  'On Hold': { color: 'bg-orange-50 text-orange-700 border-orange-200', icon: PauseCircle, description: 'Temporarily paused' },
  'Resolved': { color: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: CheckCircle2, description: 'Issue resolved' },
  'Closed': { color: 'bg-slate-100 text-slate-600 border-slate-200', icon: CheckCircle2, description: 'Ticket closed' },
  'Rejected': { color: 'bg-red-50 text-red-700 border-red-200', icon: XCircle, description: 'Request rejected' }
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
  'IT & System Support': 'text-blue-600 bg-blue-50 border-blue-200',
  'HR Support': 'text-rose-600 bg-rose-50 border-rose-200',
  'Finance & Accounts': 'text-emerald-600 bg-emerald-50 border-emerald-200',
  'Admin & Stationery': 'text-orange-600 bg-orange-50 border-orange-200',
  'Compliance & Legal': 'text-slate-600 bg-slate-100 border-slate-200',
  'Operations': 'text-teal-600 bg-teal-50 border-teal-200'
};

const EmployeeIssueTickets = () => {
  const { token, user } = useAuth();
  
  const [tickets, setTickets] = useState([]);
  const [stats, setStats] = useState(null);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState('All');
  const [searchTerm, setSearchTerm] = useState('');
  
  // Modal states
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [createModal, setCreateModal] = useState(false);
  const [feedbackModal, setFeedbackModal] = useState(null);
  const [newTicket, setNewTicket] = useState({
    category: '',
    subcategory: '',
    subject: '',
    description: '',
    priority: 'Medium'
  });
  const [feedback, setFeedback] = useState({ rating: 0, comment: '' });
  const [processing, setProcessing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const params = {
        status: statusFilter !== 'All' ? statusFilter : undefined,
        search: searchTerm || undefined
      };
      
      const [ticketsRes, statsRes, categoriesRes] = await Promise.all([
        axios.get(`${API}/issue-tickets`, { params, headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/issue-tickets/stats`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/issue-tickets/categories`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      
      setTickets(ticketsRes.data.tickets || []);
      setStats(statsRes.data);
      setCategories(categoriesRes.data);
    } catch (error) {
      console.error('Error fetching tickets:', error);
      toast.error('Failed to load tickets');
    } finally {
      setLoading(false);
    }
  }, [token, statusFilter, searchTerm]);

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
      toast.success('Ticket submitted successfully! We\'ll get back to you soon.');
      setCreateModal(false);
      setNewTicket({ category: '', subcategory: '', subject: '', description: '', priority: 'Medium' });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create ticket');
    } finally {
      setProcessing(false);
    }
  };

  const handleSubmitFeedback = async () => {
    if (feedback.rating === 0) {
      toast.error('Please select a rating');
      return;
    }
    
    setProcessing(true);
    try {
      await axios.post(`${API}/issue-tickets/${feedbackModal.id}/feedback`, feedback, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Thank you for your feedback!');
      setFeedbackModal(null);
      setFeedback({ rating: 0, comment: '' });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to submit feedback');
    } finally {
      setProcessing(false);
    }
  };

  const handleCloseTicket = async (ticketId) => {
    setProcessing(true);
    try {
      await axios.put(`${API}/issue-tickets/${ticketId}/status`, 
        { status: 'Closed', notes: 'Closed by employee' },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success('Ticket closed');
      setSelectedTicket(null);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to close ticket');
    } finally {
      setProcessing(false);
    }
  };

  const getSubcategories = () => {
    const cat = categories.find(c => c.category === newTicket.category);
    return cat?.subcategories || [];
  };

  return (
    <div className="space-y-6 animate-fade-in" data-testid="employee-tickets-page">
      {/* Header with Stats */}
      <div className="flex flex-col md:flex-row gap-6 items-start md:items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[#0b1f3b]" style={{ fontFamily: 'Outfit' }}>
            My Support Tickets
          </h1>
          <p className="text-slate-500 mt-1">Need help? Raise a ticket and we'll assist you.</p>
        </div>
        <Button 
          onClick={() => setCreateModal(true)} 
          className="h-12 px-6 bg-[#063c88] hover:bg-[#052d66] rounded-xl shadow-lg shadow-blue-900/20"
          data-testid="raise-ticket-btn"
        >
          <Plus className="w-5 h-5 mr-2" />
          Raise New Ticket
        </Button>
      </div>

      {/* Quick Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="card-flat">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-slate-500 font-medium">Total</p>
                  <p className="text-2xl font-bold text-[#0b1f3b]">{stats.total}</p>
                </div>
                <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
                  <MessageSquare className="w-5 h-5 text-blue-600" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="card-flat">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-slate-500 font-medium">Open</p>
                  <p className="text-2xl font-bold text-blue-600">{stats.by_status?.['Open'] || 0}</p>
                </div>
                <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
                  <AlertCircle className="w-5 h-5 text-blue-600" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="card-flat">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-slate-500 font-medium">In Progress</p>
                  <p className="text-2xl font-bold text-purple-600">{stats.by_status?.['In Progress'] || 0}</p>
                </div>
                <div className="w-10 h-10 rounded-xl bg-purple-100 flex items-center justify-center">
                  <RefreshCw className="w-5 h-5 text-purple-600" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="card-flat">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-slate-500 font-medium">Resolved</p>
                  <p className="text-2xl font-bold text-emerald-600">{stats.by_status?.['Resolved'] || 0}</p>
                </div>
                <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
          <Input
            placeholder="Search your tickets..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-12 h-12 bg-[#fffdf7] border-slate-200 rounded-xl"
            data-testid="search-input"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[160px] h-12 rounded-xl bg-[#fffdf7]" data-testid="status-filter">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="All">All Status</SelectItem>
            {Object.keys(STATUS_CONFIG).map(status => (
              <SelectItem key={status} value={status}>{status}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Tickets List */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-[#063c88]" />
        </div>
      ) : tickets.length === 0 ? (
        <Card className="card-premium">
          <CardContent className="py-16 text-center">
            <div className="w-20 h-20 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4">
              <MessageSquare className="w-10 h-10 text-slate-400" />
            </div>
            <h3 className="text-xl font-semibold text-slate-900 mb-2">No tickets yet</h3>
            <p className="text-slate-500 mb-6">You haven't raised any support tickets</p>
            <Button 
              onClick={() => setCreateModal(true)}
              className="bg-[#063c88] hover:bg-[#052d66] rounded-xl"
            >
              <Plus className="w-4 h-4 mr-2" />
              Raise Your First Ticket
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {tickets.map((ticket, index) => {
            const StatusIcon = STATUS_CONFIG[ticket.status]?.icon || AlertCircle;
            const CategoryIcon = CATEGORY_ICONS[ticket.category] || MessageSquare;
            const canGiveFeedback = ['Resolved', 'Closed'].includes(ticket.status) && !ticket.feedback;
            
            return (
              <Card 
                key={ticket.id}
                className="card-premium overflow-hidden hover:shadow-lg transition-all cursor-pointer group animate-slide-up"
                style={{ animationDelay: `${index * 0.05}s` }}
                onClick={() => setSelectedTicket(ticket)}
                data-testid={`ticket-card-${ticket.id}`}
              >
                <CardContent className="p-5">
                  <div className="flex items-start gap-4">
                    {/* Category Icon */}
                    <div className={`w-14 h-14 rounded-xl border ${CATEGORY_COLORS[ticket.category]} flex items-center justify-center flex-shrink-0`}>
                      <CategoryIcon className="w-7 h-7" />
                    </div>
                    
                    {/* Ticket Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-3 mb-2">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-mono text-slate-400">{ticket.ticket_number}</span>
                            <Badge className={`${PRIORITY_CONFIG[ticket.priority]?.color} border text-[10px]`}>
                              {ticket.priority}
                            </Badge>
                          </div>
                          <h3 className="font-semibold text-slate-900 group-hover:text-[#063c88] transition-colors line-clamp-1">
                            {ticket.subject}
                          </h3>
                        </div>
                        <Badge className={`${STATUS_CONFIG[ticket.status]?.color} border flex items-center gap-1.5 px-3 py-1.5 flex-shrink-0`}>
                          <StatusIcon className="w-3.5 h-3.5" />
                          {ticket.status}
                        </Badge>
                      </div>
                      
                      <p className="text-sm text-slate-500 line-clamp-2 mb-3">{ticket.description}</p>
                      
                      <div className="flex items-center gap-4 text-xs text-slate-500">
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
                        {canGiveFeedback && (
                          <button 
                            onClick={(e) => {
                              e.stopPropagation();
                              setFeedbackModal(ticket);
                            }}
                            className="ml-auto flex items-center gap-1 text-amber-600 hover:text-amber-700"
                          >
                            <Star className="w-3.5 h-3.5" />
                            <span>Give Feedback</span>
                          </button>
                        )}
                      </div>
                    </div>
                    
                    <ChevronRight className="w-5 h-5 text-slate-300 group-hover:text-slate-500 group-hover:translate-x-1 transition-all flex-shrink-0 mt-2" />
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create Ticket Modal */}
      <Dialog open={createModal} onOpenChange={setCreateModal}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="text-2xl flex items-center gap-3" style={{ fontFamily: 'Outfit' }}>
              <div className="w-10 h-10 rounded-xl bg-[#063c88] flex items-center justify-center">
                <Send className="w-5 h-5 text-white" />
              </div>
              Raise a Support Ticket
            </DialogTitle>
            <DialogDescription>
              Tell us about your issue and we'll help you resolve it as soon as possible.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-5 py-4">
            {/* Category Selection */}
            <div>
              <label className="text-sm font-medium text-slate-700 mb-3 block">What do you need help with?</label>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {categories.map(cat => {
                  const Icon = CATEGORY_ICONS[cat.category] || MessageSquare;
                  const isSelected = newTicket.category === cat.category;
                  return (
                    <button
                      key={cat.category}
                      type="button"
                      onClick={() => setNewTicket({ ...newTicket, category: cat.category, subcategory: '' })}
                      className={`p-4 rounded-xl border-2 text-left transition-all ${
                        isSelected 
                          ? 'border-[#063c88] bg-[#063c88]/5' 
                          : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                      }`}
                      data-testid={`category-btn-${cat.category.replace(/\s+/g, '-').toLowerCase()}`}
                    >
                      <div className={`w-10 h-10 rounded-lg ${CATEGORY_COLORS[cat.category]} flex items-center justify-center mb-2`}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <p className={`text-sm font-medium ${isSelected ? 'text-[#063c88]' : 'text-slate-700'}`}>
                        {cat.category.replace(' Support', '').replace(' & ', ' / ')}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Subcategory */}
            {newTicket.category && (
              <div className="animate-slide-up">
                <label className="text-sm font-medium text-slate-700 mb-2 block">Specific Issue</label>
                <Select 
                  value={newTicket.subcategory} 
                  onValueChange={(v) => setNewTicket({ ...newTicket, subcategory: v })}
                >
                  <SelectTrigger data-testid="subcategory-select">
                    <SelectValue placeholder="Select the specific issue type" />
                  </SelectTrigger>
                  <SelectContent>
                    {getSubcategories().map(sub => (
                      <SelectItem key={sub} value={sub}>{sub}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Subject */}
            <div>
              <label className="text-sm font-medium text-slate-700 mb-2 block">Subject</label>
              <Input
                placeholder="Brief summary of your issue..."
                value={newTicket.subject}
                onChange={(e) => setNewTicket({ ...newTicket, subject: e.target.value })}
                className="h-12"
                data-testid="subject-input"
              />
            </div>

            {/* Description */}
            <div>
              <label className="text-sm font-medium text-slate-700 mb-2 block">Description</label>
              <Textarea
                placeholder="Please provide as much detail as possible to help us assist you better..."
                value={newTicket.description}
                onChange={(e) => setNewTicket({ ...newTicket, description: e.target.value })}
                rows={4}
                data-testid="description-input"
              />
            </div>

            {/* Priority */}
            <div>
              <label className="text-sm font-medium text-slate-700 mb-2 block">How urgent is this?</label>
              <div className="flex gap-3">
                {[
                  { value: 'Low', label: 'Not urgent', icon: Flag, color: 'text-slate-400' },
                  { value: 'Medium', label: 'Moderate', icon: Flag, color: 'text-amber-500' },
                  { value: 'High', label: 'Very urgent', icon: Flag, color: 'text-red-500' }
                ].map(p => (
                  <button
                    key={p.value}
                    type="button"
                    onClick={() => setNewTicket({ ...newTicket, priority: p.value })}
                    className={`flex-1 p-3 rounded-xl border-2 transition-all ${
                      newTicket.priority === p.value 
                        ? 'border-[#063c88] bg-[#063c88]/5' 
                        : 'border-slate-200 hover:border-slate-300'
                    }`}
                    data-testid={`priority-${p.value.toLowerCase()}`}
                  >
                    <p.icon className={`w-5 h-5 mx-auto mb-1 ${p.color}`} />
                    <p className="text-sm font-medium text-slate-700">{p.label}</p>
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
              disabled={processing || !newTicket.category || !newTicket.subcategory || !newTicket.subject || !newTicket.description}
              className="bg-[#063c88] hover:bg-[#052d66] rounded-xl px-8"
              data-testid="submit-ticket-btn"
            >
              {processing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Send className="w-4 h-4 mr-2" />}
              Submit Ticket
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Ticket Detail Modal */}
      <Dialog open={!!selectedTicket} onOpenChange={() => setSelectedTicket(null)}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          {selectedTicket && (
            <>
              <DialogHeader>
                <div className="flex items-start gap-4">
                  <div className={`w-12 h-12 rounded-xl border ${CATEGORY_COLORS[selectedTicket.category]} flex items-center justify-center flex-shrink-0`}>
                    {(() => {
                      const Icon = CATEGORY_ICONS[selectedTicket.category] || MessageSquare;
                      return <Icon className="w-6 h-6" />;
                    })()}
                  </div>
                  <div className="flex-1">
                    <p className="text-xs font-mono text-slate-400 mb-1">{selectedTicket.ticket_number}</p>
                    <DialogTitle className="text-xl" style={{ fontFamily: 'Outfit' }}>
                      {selectedTicket.subject}
                    </DialogTitle>
                  </div>
                </div>
              </DialogHeader>
              
              <div className="space-y-4 mt-4">
                {/* Status & Priority */}
                <div className="flex items-center gap-3">
                  <Badge className={`${STATUS_CONFIG[selectedTicket.status]?.color} border`}>
                    {(() => {
                      const Icon = STATUS_CONFIG[selectedTicket.status]?.icon || AlertCircle;
                      return <Icon className="w-3.5 h-3.5 mr-1" />;
                    })()}
                    {selectedTicket.status}
                  </Badge>
                  <Badge className={`${PRIORITY_CONFIG[selectedTicket.priority]?.color} border`}>
                    {selectedTicket.priority} Priority
                  </Badge>
                  <span className="text-xs text-slate-500 ml-auto">
                    Created {new Date(selectedTicket.created_at).toLocaleDateString()}
                  </span>
                </div>
                
                {/* Category & Subcategory */}
                <div className="flex items-center gap-2 text-sm text-slate-600">
                  <span className="font-medium">{selectedTicket.category}</span>
                  <ChevronRight className="w-4 h-4 text-slate-400" />
                  <span>{selectedTicket.subcategory}</span>
                </div>
                
                {/* Description */}
                <div className="p-4 bg-slate-50 rounded-xl">
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">{selectedTicket.description}</p>
                </div>
                
                {/* Resolution */}
                {selectedTicket.resolution && (
                  <div className="p-4 bg-emerald-50 rounded-xl border border-emerald-200">
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      <p className="text-sm font-medium text-emerald-700">Resolution</p>
                    </div>
                    <p className="text-sm text-emerald-800">{selectedTicket.resolution}</p>
                    {selectedTicket.resolved_by_name && (
                      <p className="text-xs text-emerald-600 mt-2">
                        Resolved by {selectedTicket.resolved_by_name} on {new Date(selectedTicket.resolved_at).toLocaleDateString()}
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
                          <span className="text-sm text-slate-700 flex-1">{att.file_name}</span>
                          <ArrowUpRight className="w-4 h-4 text-slate-400" />
                        </a>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Status History */}
                {selectedTicket.status_history?.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-slate-700 mb-3">Timeline</p>
                    <div className="space-y-3">
                      {selectedTicket.status_history.slice().reverse().map((update, i) => (
                        <div key={i} className="flex items-start gap-3">
                          <div className={`w-2 h-2 rounded-full mt-2 ${STATUS_CONFIG[update.status]?.color.split(' ')[0] || 'bg-slate-300'}`} />
                          <div>
                            <div className="flex items-center gap-2">
                              <Badge className={`${STATUS_CONFIG[update.status]?.color} border text-xs px-2 py-0`}>
                                {update.status}
                              </Badge>
                              <span className="text-xs text-slate-500">
                                {new Date(update.updated_at).toLocaleString()}
                              </span>
                            </div>
                            {update.notes && (
                              <p className="text-sm text-slate-600 mt-1">{update.notes}</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Feedback Display */}
                {selectedTicket.feedback && (
                  <div className="p-4 bg-amber-50 rounded-xl border border-amber-200">
                    <p className="text-sm font-medium text-amber-700 mb-2">Your Feedback</p>
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
              </div>
              
              <DialogFooter className="mt-6">
                <Button variant="outline" onClick={() => setSelectedTicket(null)} className="rounded-xl">
                  Close
                </Button>
                {selectedTicket.status === 'Resolved' && !selectedTicket.feedback && (
                  <Button 
                    onClick={() => {
                      setSelectedTicket(null);
                      setFeedbackModal(selectedTicket);
                    }}
                    className="bg-amber-500 hover:bg-amber-600 rounded-xl"
                  >
                    <Star className="w-4 h-4 mr-2" />
                    Give Feedback
                  </Button>
                )}
                {selectedTicket.status === 'Resolved' && (
                  <Button 
                    onClick={() => handleCloseTicket(selectedTicket.id)}
                    disabled={processing}
                    className="bg-[#063c88] hover:bg-[#052d66] rounded-xl"
                  >
                    {processing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <CheckCircle2 className="w-4 h-4 mr-2" />}
                    Close Ticket
                  </Button>
                )}
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Feedback Modal */}
      <Dialog open={!!feedbackModal} onOpenChange={() => setFeedbackModal(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-xl flex items-center gap-3" style={{ fontFamily: 'Outfit' }}>
              <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center">
                <Star className="w-5 h-5 text-amber-600" />
              </div>
              Rate Your Experience
            </DialogTitle>
            <DialogDescription>
              Help us improve by sharing your feedback about this ticket resolution.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-5 py-4">
            {/* Star Rating */}
            <div>
              <label className="text-sm font-medium text-slate-700 mb-3 block">How satisfied are you?</label>
              <div className="flex justify-center gap-2">
                {[1, 2, 3, 4, 5].map(star => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => setFeedback({ ...feedback, rating: star })}
                    className="p-2 transition-transform hover:scale-110"
                  >
                    <Star 
                      className={`w-10 h-10 transition-colors ${
                        star <= feedback.rating 
                          ? 'text-amber-500 fill-amber-500' 
                          : 'text-slate-300 hover:text-amber-300'
                      }`} 
                    />
                  </button>
                ))}
              </div>
              <p className="text-center text-sm text-slate-500 mt-2">
                {feedback.rating === 0 && 'Click to rate'}
                {feedback.rating === 1 && 'Very dissatisfied'}
                {feedback.rating === 2 && 'Dissatisfied'}
                {feedback.rating === 3 && 'Neutral'}
                {feedback.rating === 4 && 'Satisfied'}
                {feedback.rating === 5 && 'Very satisfied'}
              </p>
            </div>
            
            {/* Comment */}
            <div>
              <label className="text-sm font-medium text-slate-700 mb-2 block">Additional Comments (Optional)</label>
              <Textarea
                placeholder="Share any additional thoughts..."
                value={feedback.comment}
                onChange={(e) => setFeedback({ ...feedback, comment: e.target.value })}
                rows={3}
              />
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setFeedbackModal(null)} className="rounded-xl">
              Skip
            </Button>
            <Button 
              onClick={handleSubmitFeedback}
              disabled={processing || feedback.rating === 0}
              className="bg-amber-500 hover:bg-amber-600 rounded-xl px-8"
            >
              {processing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Submit Feedback
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EmployeeIssueTickets;
