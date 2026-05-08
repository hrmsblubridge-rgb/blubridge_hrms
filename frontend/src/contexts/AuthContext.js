import { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem('blubridge_token'));

  useEffect(() => {
    const initAuth = async () => {
      const savedToken = localStorage.getItem('blubridge_token');
      if (savedToken) {
        try {
          const response = await axios.get(`${API}/auth/me`, {
            headers: { Authorization: `Bearer ${savedToken}` }
          });
          setUser(response.data);
          setToken(savedToken);
        } catch (error) {
          console.error('Auth init error:', error);
          localStorage.removeItem('blubridge_token');
          setToken(null);
        }
      }
      setLoading(false);
    };
    initAuth();
  }, []);

  const login = async (username, password) => {
    try {
      const response = await axios.post(`${API}/auth/login`, { username, password });
      const { token: newToken, user: userData } = response.data;
      localStorage.setItem('blubridge_token', newToken);
      setToken(newToken);
      setUser(userData);
      return { success: true, user: userData };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Login failed' 
      };
    }
  };

  const logout = () => {
    localStorage.removeItem('blubridge_token');
    setToken(null);
    setUser(null);
  };

  const updateUser = (updates) => {
    setUser(prev => ({ ...prev, ...updates }));
  };

  const getAuthHeaders = () => ({
    Authorization: `Bearer ${token}`
  });

  // Check if user needs onboarding
  const needsOnboarding = () => {
    if (!user) return false;
    if (user.role !== 'employee') return false;
    return user.onboarding_status !== 'approved' && !user.onboarding_completed;
  };

  // Temporary 14-day document-verification bypass for newly created employees.
  // Returns true ONLY for users whose `documents_bypassed_until` (set at
  // creation by the backend) is still in the future. Existing employees and
  // admins are unaffected because the flag is missing on their records.
  const isWithinDocumentBypass = () => {
    if (!user) return false;
    const ts = user.documents_bypassed_until;
    if (!ts) return false;
    const exp = new Date(ts);
    if (Number.isNaN(exp.getTime())) return false;
    return exp.getTime() > Date.now();
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, getAuthHeaders, updateUser, needsOnboarding, isWithinDocumentBypass }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
