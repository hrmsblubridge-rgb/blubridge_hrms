import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import Login from "./pages/Login";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import Dashboard from "./pages/Dashboard";
import Employees from "./pages/Employees";
import Attendance from "./pages/Attendance";
import Leave from "./pages/Leave";
import StarReward from "./pages/StarReward";
import Team from "./pages/Team";
import Reports from "./pages/Reports";
import Payroll from "./pages/Payroll";
import Holidays from "./pages/Holidays";
import Policies from "./pages/Policies";
import AdminProfile from "./pages/AdminProfile";
import ChangePassword from "./pages/ChangePassword";
import Verification from "./pages/Verification";
import Tickets from "./pages/Tickets";
import IssueTickets from "./pages/IssueTickets";
import AuditLogs from "./pages/AuditLogs";
import Layout from "./components/Layout";
import EmployeeLayout from "./components/EmployeeLayout";
import EmployeeDashboard from "./pages/EmployeeDashboard";
import EmployeeAttendance from "./pages/EmployeeAttendance";
import EmployeeLeave from "./pages/EmployeeLeave";
import EmployeeHolidays from "./pages/EmployeeHolidays";
import EmployeeEducationExperience from "./pages/EmployeeEducationExperience";
import EmployeeIssueTickets from "./pages/EmployeeIssueTickets";
import EmployeeDocuments from "./pages/EmployeeDocuments";
import EmployeeSalary from "./pages/EmployeeSalary";
import EmployeeProfile from "./pages/EmployeeProfile";
import EmployeeOnboarding from "./pages/EmployeeOnboarding";
import EmployeeLateRequest from "./pages/EmployeeLateRequest";
import EmployeeEarlyOut from "./pages/EmployeeEarlyOut";
import EmployeeMissedPunch from "./pages/EmployeeMissedPunch";
import AdminLateRequests from "./pages/AdminLateRequests";
import AdminEarlyOut from "./pages/AdminEarlyOut";
import AdminMissedPunch from "./pages/AdminMissedPunch";
import RoleManagement from "./pages/RoleManagement";
import OperationalChecklist from "./pages/OperationalChecklist";
import Settings from "./pages/Settings";
import CronManagement from "./pages/CronManagement";
import PolicyAcknowledgements from "./pages/PolicyAcknowledgements";
import "./App.css";

const ProtectedRoute = ({ children, allowedRoles }) => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen bg-[#efede5] flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#0b1f3b]"></div>
      </div>
    );
  }
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  
  // Check role-based access
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    // Redirect employee to employee dashboard
    if (user.role === 'employee') {
      return <Navigate to="/employee/dashboard" replace />;
    }
    // Redirect admins to admin dashboard
    return <Navigate to="/dashboard" replace />;
  }
  
  return children;
};

const AdminRoute = ({ children }) => {
  return (
    <ProtectedRoute allowedRoles={['hr', 'system_admin', 'office_admin']}>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  );
};

const EmployeeRoute = ({ children }) => {
  const { user, needsOnboarding } = useAuth();
  
  // If employee needs onboarding, redirect there
  if (user && user.role === 'employee' && needsOnboarding()) {
    return <Navigate to="/employee/onboarding" replace />;
  }
  
  return (
    <ProtectedRoute allowedRoles={['employee']}>
      <EmployeeLayout>{children}</EmployeeLayout>
    </ProtectedRoute>
  );
};

// Onboarding route - no layout, standalone page
const OnboardingRoute = ({ children }) => {
  return (
    <ProtectedRoute allowedRoles={['employee']}>
      {children}
    </ProtectedRoute>
  );
};

// Smart redirect based on role
const RoleBasedRedirect = () => {
  const { user, loading, needsOnboarding } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen bg-[#efede5] flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#0b1f3b]"></div>
      </div>
    );
  }
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  
  // Route based on role and onboarding status
  if (user.role === 'employee') {
    if (needsOnboarding()) {
      return <Navigate to="/employee/onboarding" replace />;
    }
    return <Navigate to="/employee/dashboard" replace />;
  }
  
  // All admin roles go to dashboard
  return <Navigate to="/dashboard" replace />;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster 
          position="top-right" 
          richColors 
          toastOptions={{
            style: {
              background: '#fffdf7',
              border: '1px solid rgba(0,0,0,0.05)',
            },
          }}
        />
        <Routes>
          {/* Auth Routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/admin" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          
          {/* Smart Root Redirect */}
          <Route path="/" element={<RoleBasedRedirect />} />
          
          {/* Admin Routes */}
          <Route path="/dashboard" element={<AdminRoute><Dashboard /></AdminRoute>} />
          <Route path="/employees" element={<AdminRoute><Employees /></AdminRoute>} />
          <Route path="/attendance" element={<AdminRoute><Attendance /></AdminRoute>} />
          <Route path="/leave" element={<AdminRoute><Leave /></AdminRoute>} />
          <Route path="/star-reward" element={<AdminRoute><StarReward /></AdminRoute>} />
          <Route path="/team" element={<AdminRoute><Team /></AdminRoute>} />
          <Route path="/payroll" element={<AdminRoute><Payroll /></AdminRoute>} />
          <Route path="/reports" element={<AdminRoute><Reports /></AdminRoute>} />
          <Route path="/holidays" element={<AdminRoute><Holidays /></AdminRoute>} />
          <Route path="/policies" element={<AdminRoute><Policies /></AdminRoute>} />
          <Route path="/policies/acknowledgements" element={<AdminRoute><PolicyAcknowledgements /></AdminRoute>} />
          <Route path="/verification" element={<AdminRoute><Verification /></AdminRoute>} />
          <Route path="/tickets" element={<AdminRoute><Tickets /></AdminRoute>} />
          <Route path="/issue-tickets" element={<AdminRoute><IssueTickets /></AdminRoute>} />
          <Route path="/audit-logs" element={<AdminRoute><AuditLogs /></AdminRoute>} />
          <Route path="/role-management" element={<AdminRoute><RoleManagement /></AdminRoute>} />
          <Route path="/operational-checklist" element={<AdminRoute><OperationalChecklist /></AdminRoute>} />
          <Route path="/settings" element={<AdminRoute><Settings /></AdminRoute>} />
          <Route path="/settings/cron-management" element={<AdminRoute><CronManagement /></AdminRoute>} />
          <Route path="/late-requests" element={<AdminRoute><AdminLateRequests /></AdminRoute>} />
          <Route path="/early-out-requests" element={<AdminRoute><AdminEarlyOut /></AdminRoute>} />
          <Route path="/missed-punches" element={<AdminRoute><AdminMissedPunch /></AdminRoute>} />
          <Route path="/admin-profile" element={<AdminRoute><AdminProfile /></AdminRoute>} />
          <Route path="/change-password" element={<AdminRoute><ChangePassword /></AdminRoute>} />
          
          {/* Employee Routes */}
          <Route path="/employee/onboarding" element={<OnboardingRoute><EmployeeOnboarding /></OnboardingRoute>} />
          <Route path="/employee/dashboard" element={<EmployeeRoute><EmployeeDashboard /></EmployeeRoute>} />
          <Route path="/employee/attendance" element={<EmployeeRoute><EmployeeAttendance /></EmployeeRoute>} />
          <Route path="/employee/leave" element={<EmployeeRoute><EmployeeLeave /></EmployeeRoute>} />
          <Route path="/employee/holidays" element={<EmployeeRoute><EmployeeHolidays /></EmployeeRoute>} />
          <Route path="/employee/education-experience" element={<EmployeeRoute><EmployeeEducationExperience /></EmployeeRoute>} />
          <Route path="/employee/policies" element={<EmployeeRoute><Policies /></EmployeeRoute>} />
          <Route path="/employee/tickets" element={<EmployeeRoute><EmployeeIssueTickets /></EmployeeRoute>} />
          <Route path="/employee/documents" element={<EmployeeRoute><EmployeeDocuments /></EmployeeRoute>} />
          <Route path="/employee/salary" element={<EmployeeRoute><EmployeeSalary /></EmployeeRoute>} />
          <Route path="/employee/late-request" element={<EmployeeRoute><EmployeeLateRequest /></EmployeeRoute>} />
          <Route path="/employee/early-out" element={<EmployeeRoute><EmployeeEarlyOut /></EmployeeRoute>} />
          <Route path="/employee/missed-punch" element={<EmployeeRoute><EmployeeMissedPunch /></EmployeeRoute>} />
          <Route path="/employee/profile" element={<EmployeeRoute><EmployeeProfile /></EmployeeRoute>} />
          
          {/* Fallback */}
          <Route path="*" element={<RoleBasedRedirect />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
