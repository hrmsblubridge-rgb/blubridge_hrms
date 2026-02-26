import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Employees from "./pages/Employees";
import Attendance from "./pages/Attendance";
import Leave from "./pages/Leave";
import StarReward from "./pages/StarReward";
import Team from "./pages/Team";
import Reports from "./pages/Reports";
import Payroll from "./pages/Payroll";
import AdminProfile from "./pages/AdminProfile";
import ChangePassword from "./pages/ChangePassword";
import Verification from "./pages/Verification";
import Tickets from "./pages/Tickets";
import AuditLogs from "./pages/AuditLogs";
import Layout from "./components/Layout";
import EmployeeLayout from "./components/EmployeeLayout";
import EmployeeDashboard from "./pages/EmployeeDashboard";
import EmployeeAttendance from "./pages/EmployeeAttendance";
import EmployeeLeave from "./pages/EmployeeLeave";
import EmployeeProfile from "./pages/EmployeeProfile";
import EmployeeOnboarding from "./pages/EmployeeOnboarding";
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
  const { user } = useAuth();
  return (
    <ProtectedRoute allowedRoles={['super_admin', 'admin', 'hr_manager', 'team_lead']}>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  );
};

const EmployeeRoute = ({ children }) => {
  return (
    <ProtectedRoute allowedRoles={['employee']}>
      <EmployeeLayout>{children}</EmployeeLayout>
    </ProtectedRoute>
  );
};

// Smart redirect based on role
const RoleBasedRedirect = () => {
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
  
  // Route based on role
  if (user.role === 'employee') {
    return <Navigate to="/employee/dashboard" replace />;
  }
  
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
          <Route path="/admin-profile" element={<AdminRoute><AdminProfile /></AdminRoute>} />
          <Route path="/change-password" element={<AdminRoute><ChangePassword /></AdminRoute>} />
          
          {/* Employee Routes */}
          <Route path="/employee/dashboard" element={<EmployeeRoute><EmployeeDashboard /></EmployeeRoute>} />
          <Route path="/employee/attendance" element={<EmployeeRoute><EmployeeAttendance /></EmployeeRoute>} />
          <Route path="/employee/leave" element={<EmployeeRoute><EmployeeLeave /></EmployeeRoute>} />
          <Route path="/employee/profile" element={<EmployeeRoute><EmployeeProfile /></EmployeeRoute>} />
          
          {/* Fallback */}
          <Route path="*" element={<RoleBasedRedirect />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
