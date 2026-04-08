import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '../components/ui/dialog';
import {
  Calendar,
  CalendarDays,
  Plus,
  Search,
  Loader2,
  Flag,
  Sun,
  Star,
  Sparkles,
  PartyPopper,
  Edit2,
  Trash2,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TYPE_CONFIG = {
  national: { 
    color: 'bg-orange-100 text-orange-700 border-orange-200', 
    icon: Flag, 
    label: 'National',
    gradient: 'from-orange-500 to-amber-500'
  },
  regional: { 
    color: 'bg-emerald-100 text-emerald-700 border-emerald-200', 
    icon: Sun, 
    label: 'Regional',
    gradient: 'from-emerald-500 to-teal-500'
  },
  religious: { 
    color: 'bg-purple-100 text-purple-700 border-purple-200', 
    icon: Star, 
    label: 'Religious',
    gradient: 'from-purple-500 to-pink-500'
  },
  company: { 
    color: 'bg-blue-100 text-blue-700 border-blue-200', 
    icon: Sparkles, 
    label: 'Company',
    gradient: 'from-blue-500 to-indigo-500'
  }
};

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

const Holidays = () => {
  const { token, user } = useAuth();
  
  const [holidays, setHolidays] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [year, setYear] = useState(2026);
  const [typeFilter, setTypeFilter] = useState('All');
  const [searchTerm, setSearchTerm] = useState('');
  
  // Modal states
  const [addModal, setAddModal] = useState(false);
  const [editModal, setEditModal] = useState(null);
  const [deleteModal, setDeleteModal] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    date: '',
    day: '',
    type: 'company',
    note: ''
  });
  const [processing, setProcessing] = useState(false);

  const isAdmin = ['hr'].includes(user?.role);

  useEffect(() => {
    fetchHolidays();
  }, [year]);

  const fetchHolidays = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/holidays?year=${year}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setHolidays(response.data.holidays || []);
      setStats(response.data.stats);
    } catch (error) {
      console.error('Error fetching holidays:', error);
      toast.error('Failed to load holidays');
    } finally {
      setLoading(false);
    }
  };

  const handleDateChange = (date) => {
    setFormData(prev => {
      const d = new Date(date);
      const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
      return { ...prev, date, day: days[d.getDay()] };
    });
  };

  const handleAddHoliday = async () => {
    if (!formData.name || !formData.date) {
      toast.error('Please fill in required fields');
      return;
    }
    
    setProcessing(true);
    try {
      await axios.post(`${API}/holidays`, formData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Holiday added successfully');
      setAddModal(false);
      setFormData({ name: '', date: '', day: '', type: 'company', note: '' });
      fetchHolidays();
    } catch (error) {
      toast.error('Failed to add holiday');
    } finally {
      setProcessing(false);
    }
  };

  const handleEditHoliday = async () => {
    if (!formData.name || !formData.date) {
      toast.error('Please fill in required fields');
      return;
    }
    
    setProcessing(true);
    try {
      await axios.put(`${API}/holidays/${editModal}`, formData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Holiday updated successfully');
      setEditModal(null);
      setFormData({ name: '', date: '', day: '', type: 'company', note: '' });
      fetchHolidays();
    } catch (error) {
      toast.error('Failed to update holiday');
    } finally {
      setProcessing(false);
    }
  };

  const handleDeleteHoliday = async () => {
    setProcessing(true);
    try {
      await axios.delete(`${API}/holidays/${deleteModal}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Holiday deleted');
      setDeleteModal(null);
      fetchHolidays();
    } catch (error) {
      toast.error('Failed to delete holiday');
    } finally {
      setProcessing(false);
    }
  };

  const openEditModal = (holiday) => {
    setFormData({
      name: holiday.name,
      date: holiday.date,
      day: holiday.day,
      type: holiday.type,
      note: holiday.note || ''
    });
    setEditModal(holiday.id);
  };

  // Filter holidays
  const filteredHolidays = holidays.filter(h => {
    if (typeFilter !== 'All' && h.type !== typeFilter) return false;
    if (searchTerm && !h.name.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    return true;
  });

  // Group by month
  const groupedByMonth = filteredHolidays.reduce((acc, h) => {
    const month = parseInt(h.date.split('-')[1]) - 1;
    if (!acc[month]) acc[month] = [];
    acc[month].push(h);
    return acc;
  }, {});

  const today = new Date().toISOString().split('T')[0];

  return (
    <div className="space-y-6" data-testid="holidays-page">
      {/* Header with Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-[#fffdf7] border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-500">Total Holidays</p>
                <p className="text-2xl font-bold text-slate-900">{stats?.total || 0}</p>
                <p className="text-xs text-slate-500 mt-1">in {year}</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center">
                <CalendarDays className="w-5 h-5 text-white" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#fffdf7] border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-500">Upcoming</p>
                <p className="text-2xl font-bold text-emerald-600">{stats?.upcoming || 0}</p>
                <p className="text-xs text-slate-500 mt-1">holidays left</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
                <PartyPopper className="w-5 h-5 text-white" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#fffdf7] border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-500">National</p>
                <p className="text-2xl font-bold text-orange-600">{stats?.by_type?.national || 0}</p>
                <p className="text-xs text-slate-500 mt-1">holidays</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-orange-500 to-amber-500 flex items-center justify-center">
                <Flag className="w-5 h-5 text-white" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#fffdf7] border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-500">Religious</p>
                <p className="text-2xl font-bold text-purple-600">{stats?.by_type?.religious || 0}</p>
                <p className="text-xs text-slate-500 mt-1">holidays</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                <Star className="w-5 h-5 text-white" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="bg-[#fffdf7] border-0 shadow-sm">
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row gap-4 items-center">
            <div className="flex items-center gap-2">
              <Button 
                variant="ghost" 
                size="icon"
                onClick={() => setYear(y => y - 1)}
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <span className="font-semibold text-lg text-slate-900 w-16 text-center">{year}</span>
              <Button 
                variant="ghost" 
                size="icon"
                onClick={() => setYear(y => y + 1)}
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
            
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                placeholder="Search holidays..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
                data-testid="holiday-search"
              />
            </div>
            
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-[150px]" data-testid="type-filter">
                <SelectValue placeholder="Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All Types</SelectItem>
                <SelectItem value="national">National</SelectItem>
                <SelectItem value="regional">Regional</SelectItem>
                <SelectItem value="religious">Religious</SelectItem>
                <SelectItem value="company">Company</SelectItem>
              </SelectContent>
            </Select>

            {isAdmin && (
              <Button onClick={() => setAddModal(true)} data-testid="add-holiday-btn">
                <Plus className="w-4 h-4 mr-2" />
                Add Holiday
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Holiday List by Month */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
        </div>
      ) : filteredHolidays.length === 0 ? (
        <Card className="bg-[#fffdf7] border-0 shadow-sm">
          <CardContent className="py-12 text-center">
            <CalendarDays className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500">No holidays found</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {Object.entries(groupedByMonth).sort(([a], [b]) => parseInt(a) - parseInt(b)).map(([month, monthHolidays]) => (
            <Card key={month} className="bg-[#fffdf7] border-0 shadow-sm overflow-hidden">
              <div className="bg-gradient-to-r from-[#063c88] to-[#0a5cba] px-6 py-3">
                <h3 className="text-white font-semibold">{MONTHS[parseInt(month)]}</h3>
              </div>
              <CardContent className="p-0">
                <div className="divide-y divide-slate-100">
                  {monthHolidays.map((holiday) => {
                    const typeConfig = TYPE_CONFIG[holiday.type] || TYPE_CONFIG.company;
                    const IconComponent = typeConfig.icon;
                    const isPast = holiday.date < today;
                    const isToday = holiday.date === today;
                    
                    return (
                      <div 
                        key={holiday.id}
                        className={`p-4 flex items-center gap-4 transition-colors ${
                          isPast ? 'bg-slate-50/50 opacity-60' : 
                          isToday ? 'bg-amber-50 border-l-4 border-amber-400' : 
                          'hover:bg-slate-50'
                        }`}
                        data-testid={`holiday-${holiday.id}`}
                      >
                        {/* Date Box */}
                        <div className={`w-14 h-14 rounded-xl bg-gradient-to-br ${typeConfig.gradient} flex flex-col items-center justify-center text-white shadow-md`}>
                          <span className="text-xl font-bold leading-none">
                            {holiday.date.split('-')[2]}
                          </span>
                          <span className="text-[10px] uppercase tracking-wider">
                            {holiday.day.slice(0, 3)}
                          </span>
                        </div>
                        
                        {/* Holiday Info */}
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <h4 className="font-semibold text-slate-900">{holiday.name}</h4>
                            {isToday && (
                              <Badge className="bg-amber-100 text-amber-700 text-[10px]">Today</Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-3 mt-1">
                            <Badge variant="outline" className={`${typeConfig.color} text-xs`}>
                              <IconComponent className="w-3 h-3 mr-1" />
                              {typeConfig.label}
                            </Badge>
                            {holiday.note && (
                              <span className="text-xs text-slate-500 italic">{holiday.note}</span>
                            )}
                          </div>
                        </div>
                        
                        {/* Actions (Admin only) */}
                        {isAdmin && !isPast && (
                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openEditModal(holiday)}
                            >
                              <Edit2 className="w-4 h-4 text-slate-500" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setDeleteModal(holiday.id)}
                            >
                              <Trash2 className="w-4 h-4 text-red-500" />
                            </Button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Add/Edit Holiday Modal */}
      <Dialog open={addModal || !!editModal} onOpenChange={() => { setAddModal(false); setEditModal(null); setFormData({ name: '', date: '', day: '', type: 'company', note: '' }); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editModal ? 'Edit Holiday' : 'Add New Holiday'}</DialogTitle>
            <DialogDescription>
              {editModal ? 'Update the holiday details' : 'Add a new holiday to the calendar'}
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-slate-700">Holiday Name *</label>
              <Input
                placeholder="e.g., Company Foundation Day"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                data-testid="holiday-name-input"
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-slate-700">Date *</label>
                <Input
                  type="date"
                  value={formData.date}
                  onChange={(e) => handleDateChange(e.target.value)}
                  data-testid="holiday-date-input"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700">Day</label>
                <Input
                  value={formData.day}
                  disabled
                  placeholder="Auto-calculated"
                />
              </div>
            </div>
            
            <div>
              <label className="text-sm font-medium text-slate-700">Type</label>
              <Select value={formData.type} onValueChange={(v) => setFormData({ ...formData, type: v })}>
                <SelectTrigger data-testid="holiday-type-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="national">National</SelectItem>
                  <SelectItem value="regional">Regional</SelectItem>
                  <SelectItem value="religious">Religious</SelectItem>
                  <SelectItem value="company">Company</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <label className="text-sm font-medium text-slate-700">Note (Optional)</label>
              <Input
                placeholder="Any additional notes..."
                value={formData.note}
                onChange={(e) => setFormData({ ...formData, note: e.target.value })}
              />
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => { setAddModal(false); setEditModal(null); }}>
              Cancel
            </Button>
            <Button 
              onClick={editModal ? handleEditHoliday : handleAddHoliday}
              disabled={processing}
            >
              {processing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              {editModal ? 'Update' : 'Add'} Holiday
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog open={!!deleteModal} onOpenChange={() => setDeleteModal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Holiday?</DialogTitle>
            <DialogDescription>
              This action cannot be undone. The holiday will be permanently removed.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteModal(null)}>
              Cancel
            </Button>
            <Button 
              variant="destructive" 
              onClick={handleDeleteHoliday}
              disabled={processing}
            >
              {processing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Holidays;
