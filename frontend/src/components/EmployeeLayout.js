import { useState } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import NotificationBell from './NotificationBell';
import { 
  LayoutDashboard, 
  CalendarCheck, 
  CalendarDays, 
  User,
  LogOut,
  Menu,
  X,
  ChevronDown,
  KeyRound,
  PartyPopper,
  GraduationCap,
  BookOpen,
  MessageSquarePlus,
  FileText,
  Wallet,
  Clock,
  LogOut as LogOutIcon,
  Fingerprint
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
  { path: '/employee/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/employee/attendance', label: 'My Attendance', icon: CalendarCheck },
  { path: '/employee/leave', label: 'Leave', icon: CalendarDays },
  { path: '/employee/late-request', label: 'Late Request', icon: Clock },
  { path: '/employee/early-out', label: 'Early Out', icon: LogOutIcon },
  { path: '/employee/missed-punch', label: 'Missed Punch', icon: Fingerprint },
  { path: '/employee/salary', label: 'My Salary', icon: Wallet },
  { path: '/employee/holidays', label: 'Holidays', icon: PartyPopper },
  { path: '/employee/education-experience', label: 'Education & Experience', icon: GraduationCap },
  { path: '/employee/policies', label: 'Policies', icon: BookOpen },
  { path: '/employee/documents', label: 'My Documents', icon: FileText },
  { path: '/employee/tickets', label: 'Support Tickets', icon: MessageSquarePlus },
  { path: '/employee/profile', label: 'Profile', icon: User },
];

const EmployeeLayout = ({ children }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const getPageTitle = () => {
    const current = navItems.find(item => location.pathname === item.path);
    return current?.label || 'Dashboard';
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
              <p className="text-[10px] text-slate-500 uppercase tracking-widest font-medium">Employee Portal</p>
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
          <p className="px-4 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-widest">Menu</p>
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
                data-testid={`nav-${item.path.replace('/employee/', '')}`}
              >
                <item.icon className="w-5 h-5" strokeWidth={isActive ? 2 : 1.5} />
                <span>{item.label}</span>
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
              <p className="text-xs text-slate-500">Employee</p>
            </div>
          </div>
          <Button
            variant="ghost"
            className="w-full justify-start gap-3 text-slate-600 hover:text-red-600 hover:bg-red-50 rounded-xl h-11"
            onClick={handleLogout}
            data-testid="employee-logout-btn"
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
                data-testid="employee-mobile-menu-btn"
              >
                <Menu className="w-6 h-6 text-slate-700" />
              </button>
              <div>
                <h2 className="text-xl lg:text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit' }}>
                  {getPageTitle()}
                </h2>
                <p className="text-xs text-slate-500 hidden sm:block">
                  {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
                </p>
              </div>
            </div>
            
            {/* Right: Actions */}
            <div className="flex items-center gap-2">
              {/* Notifications */}
              <NotificationBell />

              {/* Profile Dropdown */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button className="flex items-center gap-3 hover:bg-slate-100 rounded-xl px-3 py-2 transition-colors">
                    <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[#063c88] to-[#0a5cba] flex items-center justify-center shadow-md">
                      <span className="text-white font-semibold text-sm">
                        {user?.name?.charAt(0)?.toUpperCase()}
                      </span>
                    </div>
                    <div className="hidden sm:block text-left">
                      <p className="text-sm font-medium text-slate-900">{user?.name}</p>
                      <p className="text-xs text-slate-500">Employee</p>
                    </div>
                    <ChevronDown className="w-4 h-4 text-slate-500" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56 bg-white/95 backdrop-blur-xl border border-slate-200 shadow-xl rounded-xl p-1">
                  <DropdownMenuItem 
                    onClick={() => navigate('/employee/profile')}
                    className="cursor-pointer rounded-lg"
                  >
                    <User className="w-4 h-4 mr-2" />
                    My Profile
                  </DropdownMenuItem>
                  <DropdownMenuSeparator className="my-1" />
                  <DropdownMenuItem 
                    onClick={handleLogout}
                    className="cursor-pointer text-red-600 focus:text-red-600 focus:bg-red-50 rounded-lg"
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

export default EmployeeLayout;
