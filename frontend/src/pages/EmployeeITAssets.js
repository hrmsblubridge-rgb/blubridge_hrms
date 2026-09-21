import { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Card, CardContent } from '../components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Laptop } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function EmployeeITAssets() {
  const { token } = useAuth();
  const authHeaders = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API}/employee/it-assets`, { headers: authHeaders })
      .then(r => setItems(r.data.items || [])).catch(() => {}).finally(() => setLoading(false));
  }, [authHeaders]);

  return (
    <div className="space-y-6" data-testid="employee-it-assets-page">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2"><Laptop className="w-6 h-6" />My IT Assets</h1>
        <p className="text-sm text-slate-500">IT assets currently assigned to you.</p>
      </div>
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Asset ID</TableHead><TableHead>Category</TableHead><TableHead>Brand / Model</TableHead>
              <TableHead>Serial</TableHead><TableHead>Condition</TableHead><TableHead>Assigned Date</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {loading && <TableRow><TableCell colSpan={6} className="text-center text-slate-400 py-8">Loading…</TableCell></TableRow>}
              {!loading && items.length === 0 && <TableRow><TableCell colSpan={6} className="text-center text-slate-400 py-8">No IT assets are assigned to you.</TableCell></TableRow>}
              {items.map(a => (
                <TableRow key={a.asset_id} data-testid={`my-asset-${a.asset_id}`}>
                  <TableCell className="font-medium">{a.asset_id}</TableCell>
                  <TableCell>{a.category}</TableCell>
                  <TableCell className="text-sm">{[a.brand, a.model].filter(Boolean).join(' ') || '—'}</TableCell>
                  <TableCell className="text-sm text-slate-500">{a.serial_number || '—'}</TableCell>
                  <TableCell className="text-sm">{a.condition || '—'}</TableCell>
                  <TableCell className="text-sm">{a.assigned_date || '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
