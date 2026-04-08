import { useState, useEffect } from 'react';
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
  Ticket,
  AlertCircle,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  MessageSquare,
  User,
  Plus
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_CONFIG = {
  open: { color: 'bg-blue-100 text-blue-700', label: 'Open' },
  in_progress: { color: 'bg-amber-100 text-amber-700', label: 'In Progress' },
  resolved: { color: 'bg-emerald-100 text-emerald-700', label: 'Resolved' },
  closed: { color: 'bg-slate-100 text-slate-600', label: 'Closed' }
};

const PRIORITY_CONFIG = {
  low: { color: 'bg-slate-100 text-slate-600', label: 'Low' },
  medium: { color: 'bg-amber-100 text-amber-700', label: 'Medium' },
  high: { color: 'bg-red-100 text-red-700', label: 'High' }
};

const Tickets = () => {
  const { token, user } = useAuth();
  
  const [tickets, setTickets] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState('All');
  const [priorityFilter, setPriorityFilter] = useState('All');
  const [searchTerm, setSearchTerm] = useState('');
  
  // Modal states
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [newTicketModal, setNewTicketModal] = useState(false);
  const [newTicket, setNewTicket] = useState({ subject: '', description: '', priority: 'medium' });
  const [resolution, setResolution] = useState('');
  const [processingAction, setProcessingAction] = useState(null);

  const isAdmin = ['hr'].includes(user?.role);

  useEffect(() => {
    fetchData();
  }, [statusFilter, priorityFilter]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const params = {
        status: statusFilter !== 'All' ? statusFilter : undefined,
        priority: priorityFilter !== 'All' ? priorityFilter : undefined
      };
      
      const requests = [
        axios.get(`${API}/tickets`, { params, headers: { Authorization: `Bearer ${token}` } })
      ];
      
      if (isAdmin) {
        requests.push(
          axios.get(`${API}/tickets/stats`, { headers: { Authorization: `Bearer ${token}` } })
        );
      }
      
      const responses = await Promise.all(requests);
      setTickets(responses[0].data);
      if (responses[1]) {
        setStats(responses[1].data);
      }
    } catch (error) {
      console.error('Error fetching tickets:', error);
      toast.error('Failed to load tickets');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTicket = async () => {
    if (!newTicket.subject.trim() || !newTicket.description.trim()) {
      toast.error('Please fill in all fields');
      return;
    }
    
    setProcessingAction('create');
    try {
      await axios.post(`${API}/tickets`, newTicket, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Ticket created successfully');
      setNewTicketModal(false);
      setNewTicket({ subject: '', description: '', priority: 'medium' });
      fetchData();
    } catch (error) {
      toast.error('Failed to create ticket');
    } finally {
      setProcessingAction(null);
    }
  };

  const handleUpdateStatus = async (ticketId, newStatus) => {
    setProcessingAction(ticketId);
    try {
      await axios.put(`${API}/tickets/${ticketId}/status`, null, {
        params: { 
          status: newStatus,
          resolution: newStatus === 'resolved' ? resolution : undefined
        },
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`Ticket ${newStatus}`);
      setSelectedTicket(null);
      setResolution('');
      fetchData();
    } catch (error) {
      toast.error('Failed to update ticket');
    } finally {
      setProcessingAction(null);
    }
  };

  const filteredTickets = tickets.filter(ticket => {
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      return ticket.subject.toLowerCase().includes(search) ||
             ticket.emp_name?.toLowerCase().includes(search) ||
             ticket.description.toLowerCase().includes(search);
    }
    return true;
  });

  return (
    <div className="space-y-6" data-testid="tickets-page">
      {/* Stats Cards (Admin only) */}
      {isAdmin && stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="bg-[#fffdf7] border-0 shadow-sm">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-slate-500">Total Tickets</p>
                  <p className="text-2xl font-bold text-slate-900">{stats.total}</p>
                </div>
                <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                  <Ticket className="w-5 h-5 text-blue-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#fffdf7] border-0 shadow-sm">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-slate-500">Open</p>
                  <p className="text-2xl font-bold text-blue-600">{stats.open}</p>
                </div>
                <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                  <AlertCircle className="w-5 h-5 text-blue-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#fffdf7] border-0 shadow-sm">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-slate-500">In Progress</p>
                  <p className="text-2xl font-bold text-amber-600">{stats.in_progress}</p>
                </div>
                <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
                  <Clock className="w-5 h-5 text-amber-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#fffdf7] border-0 shadow-sm">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-slate-500">Resolved</p>
                  <p className="text-2xl font-bold text-emerald-600">{stats.resolved}</p>
                </div>
                <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters and Actions */}
      <Card className="bg-[#fffdf7] border-0 shadow-sm">
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                placeholder="Search tickets..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
                data-testid="ticket-search"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All Status</SelectItem>
                <SelectItem value="open">Open</SelectItem>
                <SelectItem value="in_progress">In Progress</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
                <SelectItem value="closed">Closed</SelectItem>
              </SelectContent>
            </Select>
            <Select value={priorityFilter} onValueChange={setPriorityFilter}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Priority" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All Priority</SelectItem>
                <SelectItem value="low">Low</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="high">High</SelectItem>
              </SelectContent>
            </Select>
            <Button onClick={() => setNewTicketModal(true)} data-testid="create-ticket-btn">
              <Plus className="w-4 h-4 mr-2" />
              New Ticket
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Tickets List */}
      <Card className="bg-[#fffdf7] border-0 shadow-sm">
        <CardHeader>
          <CardTitle className="text-lg">Support Tickets</CardTitle>
          <CardDescription>
            {isAdmin ? 'Manage employee support requests' : 'Your support tickets'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
            </div>
          ) : filteredTickets.length === 0 ? (
            <div className="text-center py-12">
              <Ticket className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500">No tickets found</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ticket</TableHead>
                  {isAdmin && <TableHead>Employee</TableHead>}
                  <TableHead>Priority</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTickets.map((ticket) => {
                  const statusConfig = STATUS_CONFIG[ticket.status] || STATUS_CONFIG.open;
                  const priorityConfig = PRIORITY_CONFIG[ticket.priority] || PRIORITY_CONFIG.medium;
                  
                  return (
                    <TableRow key={ticket.id} data-testid={`ticket-row-${ticket.id}`}>
                      <TableCell>
                        <div>
                          <p className="font-medium text-slate-900">{ticket.subject}</p>
                          <p className="text-xs text-slate-500 line-clamp-1">{ticket.description}</p>
                        </div>
                      </TableCell>
                      {isAdmin && (
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center">
                              <User className="w-4 h-4 text-slate-500" />
                            </div>
                            <div>
                              <p className="text-sm text-slate-700">{ticket.emp_name}</p>
                              <p className="text-xs text-slate-500">{ticket.department}</p>
                            </div>
                          </div>
                        </TableCell>
                      )}
                      <TableCell>
                        <Badge className={priorityConfig.color}>
                          {priorityConfig.label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={statusConfig.color}>
                          {statusConfig.label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <p className="text-sm text-slate-600">
                          {new Date(ticket.created_at).toLocaleDateString()}
                        </p>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedTicket(ticket)}
                        >
                          <MessageSquare className="w-4 h-4 mr-1" />
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* New Ticket Modal */}
      <Dialog open={newTicketModal} onOpenChange={setNewTicketModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Ticket</DialogTitle>
            <DialogDescription>
              Describe your issue and our team will help you resolve it.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-slate-700">Subject</label>
              <Input
                placeholder="Brief description of the issue..."
                value={newTicket.subject}
                onChange={(e) => setNewTicket({ ...newTicket, subject: e.target.value })}
                data-testid="ticket-subject-input"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">Description</label>
              <Textarea
                placeholder="Provide more details about your issue..."
                value={newTicket.description}
                onChange={(e) => setNewTicket({ ...newTicket, description: e.target.value })}
                rows={4}
                data-testid="ticket-description-input"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">Priority</label>
              <Select 
                value={newTicket.priority} 
                onValueChange={(value) => setNewTicket({ ...newTicket, priority: value })}
              >
                <SelectTrigger data-testid="ticket-priority-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNewTicketModal(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleCreateTicket}
              disabled={processingAction === 'create'}
              data-testid="submit-ticket-btn"
            >
              {processingAction === 'create' ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : null}
              Create Ticket
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Ticket Detail Modal */}
      <Dialog open={!!selectedTicket} onOpenChange={() => setSelectedTicket(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{selectedTicket?.subject}</DialogTitle>
            <DialogDescription>
              Created on {selectedTicket && new Date(selectedTicket.created_at).toLocaleDateString()}
            </DialogDescription>
          </DialogHeader>
          
          {selectedTicket && (
            <div className="space-y-4">
              <div className="flex gap-2">
                <Badge className={STATUS_CONFIG[selectedTicket.status]?.color}>
                  {STATUS_CONFIG[selectedTicket.status]?.label}
                </Badge>
                <Badge className={PRIORITY_CONFIG[selectedTicket.priority]?.color}>
                  {PRIORITY_CONFIG[selectedTicket.priority]?.label} Priority
                </Badge>
              </div>
              
              {isAdmin && (
                <div className="flex items-center gap-2 p-3 bg-slate-50 rounded-lg">
                  <User className="w-4 h-4 text-slate-500" />
                  <span className="text-sm text-slate-700">{selectedTicket.emp_name}</span>
                  <span className="text-xs text-slate-500">• {selectedTicket.department}</span>
                </div>
              )}
              
              <div>
                <label className="text-sm font-medium text-slate-700">Description</label>
                <p className="text-sm text-slate-600 mt-1 p-3 bg-slate-50 rounded-lg">
                  {selectedTicket.description}
                </p>
              </div>
              
              {selectedTicket.resolution && (
                <div>
                  <label className="text-sm font-medium text-slate-700">Resolution</label>
                  <p className="text-sm text-slate-600 mt-1 p-3 bg-emerald-50 rounded-lg border border-emerald-200">
                    {selectedTicket.resolution}
                  </p>
                </div>
              )}
              
              {isAdmin && selectedTicket.status !== 'resolved' && selectedTicket.status !== 'closed' && (
                <div>
                  <label className="text-sm font-medium text-slate-700">Resolution (optional)</label>
                  <Textarea
                    placeholder="Add resolution notes..."
                    value={resolution}
                    onChange={(e) => setResolution(e.target.value)}
                    rows={3}
                  />
                </div>
              )}
            </div>
          )}
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedTicket(null)}>
              Close
            </Button>
            {isAdmin && selectedTicket?.status === 'open' && (
              <Button 
                className="bg-amber-600 hover:bg-amber-700"
                onClick={() => handleUpdateStatus(selectedTicket.id, 'in_progress')}
                disabled={processingAction === selectedTicket?.id}
              >
                {processingAction === selectedTicket?.id ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Clock className="w-4 h-4 mr-2" />
                )}
                Mark In Progress
              </Button>
            )}
            {isAdmin && (selectedTicket?.status === 'open' || selectedTicket?.status === 'in_progress') && (
              <Button 
                className="bg-emerald-600 hover:bg-emerald-700"
                onClick={() => handleUpdateStatus(selectedTicket.id, 'resolved')}
                disabled={processingAction === selectedTicket?.id}
              >
                {processingAction === selectedTicket?.id ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                )}
                Mark Resolved
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Tickets;
