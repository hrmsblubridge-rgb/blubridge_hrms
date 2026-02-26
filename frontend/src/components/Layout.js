import { useState } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { 
  LayoutDashboard, 
  CalendarCheck, 
  CalendarDays, 
  Star, 
  Users, 
  FileText, 
  LogOut,
  Menu,
  X,
  UserCog,
  Wallet,
  User,
  KeyRound,
  ChevronDown,
  Search,
  Bell,
  Settings,
  ClipboardCheck,
  Ticket,
  ScrollText,
  PartyPopper,
  BookOpen,
  MessageSquarePlus
} from 'lucide-react';
import { Button } from './ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/employees', label: 'Employees', icon: UserCog },
  { path: '/verification', label: 'Verification', icon: ClipboardCheck },
  { path: '/attendance', label: 'Attendance', icon: CalendarCheck },
  { path: '/leave', label: 'Leave', icon: CalendarDays },
  { path: '/holidays', label: 'Holidays', icon: PartyPopper },
  { path: '/policies', label: 'Policies', icon: BookOpen },
  { path: '/star-reward', label: 'Star Reward', icon: Star },
  { path: '/team', label: 'Team', icon: Users },
  { path: '/payroll', label: 'Payroll', icon: Wallet },
  { path: '/tickets', label: 'Tickets', icon: Ticket },
  { path: '/reports', label: 'Reports', icon: FileText },
  { path: '/audit-logs', label: 'Audit Logs', icon: ScrollText },
];

const Layout = ({ children }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [headerSearch, setHeaderSearch] = useState('');

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const getPageTitle = () => {
    const current = navItems.find(item => location.pathname === item.path);
    return current?.label || 'Dashboard';
  };

  // Handle search navigation
  const handleHeaderSearch = (e) => {
    if (e.key === 'Enter' && headerSearch.trim()) {
      const searchLower = headerSearch.toLowerCase();
      // Navigate to relevant page based on search
      if (searchLower.includes('employee') || searchLower.includes('staff') || searchLower.includes('worker')) {
        navigate(`/employees?search=${encodeURIComponent(headerSearch)}`);
      } else if (searchLower.includes('attend') || searchLower.includes('check') || searchLower.includes('login')) {
        navigate('/attendance');
      } else if (searchLower.includes('leave') || searchLower.includes('vacation') || searchLower.includes('holiday')) {
        navigate('/leave');
      } else if (searchLower.includes('team') || searchLower.includes('department')) {
        navigate('/team');
      } else if (searchLower.includes('payroll') || searchLower.includes('salary') || searchLower.includes('pay')) {
        navigate('/payroll');
      } else if (searchLower.includes('star') || searchLower.includes('reward') || searchLower.includes('point')) {
        navigate('/star-reward');
      } else if (searchLower.includes('report')) {
        navigate('/reports');
      } else {
        // Default: search in employees
        navigate(`/employees?search=${encodeURIComponent(headerSearch)}`);
      }
      setHeaderSearch('');
    }
  };

  return (
    <div className="min-h-screen bg-[#efede5]">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40 lg:hidden transition-opacity"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed top-0 left-0 h-full w-72 z-50
        bg-[#fffdf7]/90 backdrop-blur-2xl
        border-r border-black/5
        transform transition-transform duration-300 ease-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        flex flex-col
      `}>
        {/* Logo Section */}
        <div className="h-20 flex items-center px-6 border-b border-black/5">
          <div className="flex items-center gap-3">
            <img src="/logo-black.png" alt="BluBridge" className="w-auto" />
            <div>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest font-medium">HRMS Platform</p>
            </div>
          </div>
          <button 
            className="ml-auto lg:hidden p-2 hover:bg-black/5 rounded-lg transition-colors"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          <p className="px-4 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-widest">Main Menu</p>
          {navItems.map((item, index) => {
            const isActive = location.pathname === item.path;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={() => setSidebarOpen(false)}
                className={`
                  nav-item animate-slide-up
                  ${isActive ? 'nav-item-active' : 'nav-item-inactive'}
                `}
                style={{ animationDelay: `${index * 0.03}s` }}
                data-testid={`nav-${item.path.replace('/', '')}`}
              >
                <item.icon className="w-5 h-5" strokeWidth={isActive ? 2 : 1.5} />
                <span>{item.label}</span>
                {item.path === '/star-reward' && (
                  <span className="ml-auto w-2 h-2 rounded-full bg-amber-400 animate-pulse-soft" />
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* User Section */}
        <div className="p-4 border-t border-black/5">
          <div className="flex items-center gap-3 p-3 rounded-xl bg-slate-50/80 mb-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#063c88] to-[#0a5cba] flex items-center justify-center shadow-md">
              <span className="text-white font-semibold text-sm">
                {user?.name?.charAt(0)?.toUpperCase()}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-slate-900 truncate">{user?.name}</p>
              <p className="text-xs text-slate-500 capitalize">{user?.role?.replace('_', ' ')}</p>
            </div>
          </div>
          <Button
            variant="ghost"
            className="w-full justify-start gap-3 text-slate-600 hover:text-red-600 hover:bg-red-50 rounded-xl h-11"
            onClick={handleLogout}
            data-testid="logout-btn"
          >
            <LogOut className="w-5 h-5" strokeWidth={1.5} />
            <span>Sign Out</span>
          </Button>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-72">
        {/* Header */}
        <header className="h-20 bg-[#fffdf7]/70 backdrop-blur-xl border-b border-black/5 sticky top-0 z-30">
          <div className="h-full px-4 lg:px-8 flex items-center justify-between max-w-[1600px] mx-auto">
            {/* Left: Mobile menu + Page title */}
            <div className="flex items-center gap-4">
              <button 
                className="lg:hidden p-2.5 hover:bg-black/5 rounded-xl transition-colors"
                onClick={() => setSidebarOpen(true)}
                data-testid="mobile-menu-btn"
              >
                <Menu className="w-6 h-6 text-slate-700" />
              </button>
              <div>
                <h2 className="text-xl lg:text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>
                  {getPageTitle()}
                </h2>
                <p className="text-xs text-slate-500 hidden sm:block">
                  {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
                </p>
              </div>
            </div>
            
            {/* Right: Actions */}
            <div className="flex items-center gap-2">
              {/* Search - Desktop only */}
              <div className="hidden lg:flex items-center">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input 
                    type="text" 
                    placeholder="Search..." 
                    value={headerSearch}
                    onChange={(e) => setHeaderSearch(e.target.value)}
                    onKeyDown={handleHeaderSearch}
                    className="w-64 h-10 pl-10 pr-4 rounded-xl bg-slate-100/80 border-0 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#063c88]/20 focus:bg-white transition-all"
                    data-testid="header-search-input"
                  />
                </div>
              </div>

              {/* Notifications */}
              <button className="relative p-2.5 hover:bg-slate-100 rounded-xl transition-colors">
                <Bell className="w-5 h-5 text-slate-600" strokeWidth={1.5} />
                <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full" />
              </button>

              {/* Profile Dropdown */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button 
                    className="flex items-center gap-3 hover:bg-slate-100 rounded-xl px-3 py-2 transition-colors" 
                    data-testid="admin-profile-dropdown"
                  >
                    <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[#063c88] to-[#0a5cba] flex items-center justify-center shadow-md">
                      <span className="text-white font-semibold text-sm">
                        {user?.name?.charAt(0)?.toUpperCase()}
                      </span>
                    </div>
                    <ChevronDown className="w-4 h-4 text-slate-500" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56 bg-white/95 backdrop-blur-xl border border-slate-200 shadow-xl rounded-xl p-1">
                  <div className="px-3 py-2 border-b border-slate-100 mb-1">
                    <p className="text-sm font-semibold text-slate-900">{user?.name}</p>
                    <p className="text-xs text-slate-500 capitalize">{user?.role?.replace('_', ' ')}</p>
                  </div>
                  <DropdownMenuItem 
                    onClick={() => navigate('/admin-profile')}
                    className="cursor-pointer rounded-lg"
                    data-testid="admin-profile-btn"
                  >
                    <User className="w-4 h-4 mr-2" />
                    Profile
                  </DropdownMenuItem>
                  <DropdownMenuItem 
                    onClick={() => navigate('/change-password')}
                    className="cursor-pointer rounded-lg"
                    data-testid="change-password-btn"
                  >
                    <KeyRound className="w-4 h-4 mr-2" />
                    Change Password
                  </DropdownMenuItem>
                  <DropdownMenuSeparator className="my-1" />
                  <DropdownMenuItem 
                    onClick={handleLogout}
                    className="cursor-pointer text-red-600 focus:text-red-600 focus:bg-red-50 rounded-lg"
                    data-testid="dropdown-logout-btn"
                  >
                    <LogOut className="w-4 h-4 mr-2" />
                    Sign Out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 lg:p-8 max-w-[1600px] mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;
