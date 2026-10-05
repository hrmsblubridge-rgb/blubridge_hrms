import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '../components/ui/select';
import { Button } from '../components/ui/button';
import {
  Calendar,
  CalendarDays,
  Search,
  Loader2,
  Flag,
  Sun,
  Star,
  Sparkles,
  PartyPopper,
  ChevronLeft,
  ChevronRight,
  Clock
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

const EmployeeHolidays = () => {
  const { token } = useAuth();
  
  const [holidays, setHolidays] = useState([]);
  const [upcomingHolidays, setUpcomingHolidays] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [year, setYear] = useState(2026);
  const [typeFilter, setTypeFilter] = useState('All');
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchData();
  }, [year]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [holidaysRes, upcomingRes] = await Promise.all([
        axios.get(`${API}/holidays?year=${year}`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        axios.get(`${API}/holidays/upcoming?limit=3`, {
          headers: { Authorization: `Bearer ${token}` }
        })
      ]);
      setHolidays(holidaysRes.data.holidays || []);
      setStats(holidaysRes.data.stats);
      setUpcomingHolidays(upcomingRes.data || []);
    } catch (error) {
      console.error('Error fetching holidays:', error);
      toast.error('Failed to load holidays');
    } finally {
      setLoading(false);
    }
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

  const getDaysUntil = (dateStr) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = Math.ceil((date - now) / (1000 * 60 * 60 * 24));
    if (diff === 0) return 'Today';
    if (diff === 1) return 'Tomorrow';
    return `${diff} days`;
  };

  return (
    <div className="space-y-6" data-testid="employee-holidays-page">
      {/* Upcoming Holidays Banner */}
      {upcomingHolidays.length > 0 && (
        <Card className="bg-gradient-to-r from-[#063c88] to-[#0a5cba] border-0 shadow-lg text-white overflow-hidden">
          <CardContent className="p-6">
            <div className="flex items-center gap-2 mb-4">
              <PartyPopper className="w-5 h-5" />
              <h3 className="font-semibold">Upcoming Holidays</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {upcomingHolidays.map((holiday) => {
                const typeConfig = TYPE_CONFIG[holiday.type] || TYPE_CONFIG.company;
                return (
                  <div 
                    key={holiday.id}
                    className="bg-white/10 backdrop-blur-sm rounded-xl p-4 border border-white/20"
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-12 h-12 rounded-lg bg-gradient-to-br ${typeConfig.gradient} flex flex-col items-center justify-center shadow-md`}>
                        <span className="text-lg font-bold leading-none">
                          {holiday.date.split('-')[2]}
                        </span>
                        <span className="text-[9px] uppercase">
                          {MONTHS[parseInt(holiday.date.split('-')[1]) - 1].slice(0, 3)}
                        </span>
                      </div>
                      <div>
                        <p className="font-medium">{holiday.name}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <Clock className="w-3 h-3 opacity-70" />
                          <span className="text-xs opacity-80">{getDaysUntil(holiday.date)}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-[#fffdf7] border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-500">Total Holidays</p>
                <p className="text-2xl font-bold text-slate-900">{stats?.total || 0}</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                <CalendarDays className="w-5 h-5 text-blue-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#fffdf7] border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-500">Remaining</p>
                <p className="text-2xl font-bold text-emerald-600">{stats?.upcoming || 0}</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center">
                <PartyPopper className="w-5 h-5 text-emerald-600" />
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
              </div>
              <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center">
                <Flag className="w-5 h-5 text-orange-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#fffdf7] border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-500">Regional</p>
                <p className="text-2xl font-bold text-emerald-600">{stats?.by_type?.regional || 0}</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center">
                <Sun className="w-5 h-5 text-emerald-600" />
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
              />
            </div>
            
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-[150px]">
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
          </div>
        </CardContent>
      </Card>

      {/* Holiday List */}
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
        <div className="space-y-4">
          {Object.entries(groupedByMonth).sort(([a], [b]) => parseInt(a) - parseInt(b)).map(([month, monthHolidays]) => (
            <Card key={month} className="bg-[#fffdf7] border-0 shadow-sm overflow-hidden">
              <div className="bg-gradient-to-r from-slate-800 to-slate-700 px-5 py-2.5">
                <h3 className="text-white font-medium text-sm">{MONTHS[parseInt(month)]} {year}</h3>
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
                        className={`px-5 py-3 flex items-center gap-4 ${
                          isPast ? 'opacity-50' : 
                          isToday ? 'bg-amber-50/50' : ''
                        }`}
                      >
                        <div className={`w-11 h-11 rounded-lg bg-gradient-to-br ${typeConfig.gradient} flex flex-col items-center justify-center text-white`}>
                          <span className="text-base font-bold leading-none">
                            {holiday.date.split('-')[2]}
                          </span>
                          <span className="text-[8px] uppercase tracking-wider">
                            {holiday.day.slice(0, 3)}
                          </span>
                        </div>
                        
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-slate-900">{holiday.name}</span>
                            {isToday && (
                              <Badge className="bg-amber-100 text-amber-700 text-[10px] px-1.5">Today</Badge>
                            )}
                          </div>
                          {holiday.note && (
                            <p className="text-xs text-slate-500 mt-0.5">{holiday.note}</p>
                          )}
                        </div>
                        
                        <Badge variant="outline" className={`${typeConfig.color} text-xs`}>
                          <IconComponent className="w-3 h-3 mr-1" />
                          {typeConfig.label}
                        </Badge>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default EmployeeHolidays;
