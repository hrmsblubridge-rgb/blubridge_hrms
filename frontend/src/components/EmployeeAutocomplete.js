import { useState, useRef, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { Search } from 'lucide-react';
import { Input } from './ui/input';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const EmployeeAutocomplete = ({
  value = '',
  onChange,
  onSelect,
  placeholder = 'Search employee...',
  className = '',
  'data-testid': testId = 'emp-autocomplete',
}) => {
  const { getAuthHeaders } = useAuth();
  const [suggestions, setSuggestions] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loading, setLoading] = useState(false);
  const wrapperRef = useRef(null);
  const debounceRef = useRef(null);

  const fetchSuggestions = useCallback(async (q) => {
    if (!q || q.trim().length < 1) {
      setSuggestions([]);
      setShowDropdown(false);
      return;
    }
    try {
      setLoading(true);
      const headers = getAuthHeaders();
      const res = await axios.get(`${API}/employees/autocomplete`, { headers, params: { q: q.trim() } });
      setSuggestions(res.data || []);
      setShowDropdown(true);
    } catch {
      setSuggestions([]);
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders]);

  const handleInputChange = (e) => {
    const val = e.target.value;
    if (onChange) onChange(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchSuggestions(val), 350);
  };

  const handleSelect = (emp) => {
    setShowDropdown(false);
    setSuggestions([]);
    if (onSelect) onSelect(emp);
    else if (onChange) onChange(emp.full_name);
  };

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={wrapperRef}>
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 z-10" />
      <Input
        placeholder={placeholder}
        value={value}
        onChange={handleInputChange}
        onFocus={() => { if (suggestions.length > 0) setShowDropdown(true); }}
        className={`pl-10 rounded-lg ${className}`}
        data-testid={testId}
        autoComplete="off"
      />
      {showDropdown && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-[280px] overflow-y-auto" data-testid={`${testId}-suggestions`}>
          {loading ? (
            <div className="px-4 py-3 text-sm text-slate-400">Searching...</div>
          ) : suggestions.length === 0 ? (
            <div className="px-4 py-3 text-sm text-slate-400">No matches found</div>
          ) : (
            suggestions.map((emp) => (
              <button
                key={emp.id}
                type="button"
                className="w-full text-left px-4 py-2.5 hover:bg-slate-50 flex items-center gap-3 border-b border-slate-100 last:border-0 transition-colors"
                onClick={() => handleSelect(emp)}
                data-testid={`${testId}-item-${emp.emp_id}`}
              >
                <div className="w-7 h-7 rounded-full bg-[#063c88]/10 flex items-center justify-center text-xs font-bold text-[#063c88] shrink-0">
                  {emp.full_name?.charAt(0)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-slate-800 truncate">{emp.full_name}</div>
                  <div className="text-xs text-slate-500 truncate">{emp.emp_id} &middot; {emp.official_email}</div>
                </div>
                <span className="text-[10px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded shrink-0">{emp.department}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
};
