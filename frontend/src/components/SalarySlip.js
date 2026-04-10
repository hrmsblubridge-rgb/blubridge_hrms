import { forwardRef } from 'react';

const fmt = (v) => {
  if (!v && v !== 0) return '-';
  return Number(v).toLocaleString('en-IN', { maximumFractionDigits: 0 });
};

const SalarySlip = forwardRef(({ employee, salary, month }, ref) => {
  if (!salary) return null;

  const empName = employee?.full_name || employee?.name || 'Employee';
  const empId = employee?.employee_id_custom || employee?.id?.slice(0, 8) || '';
  const dept = employee?.department || '';
  const desig = employee?.designation || '';
  const doj = employee?.date_of_joining || '';
  const monthLabel = month || new Date().toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });

  const annual = (v) => fmt(v * 12);
  const monthly = (v) => fmt(v);

  // Insurance coverage
  const medInsurance = 300000;
  const accInsurance = Math.max(salary.annual_ctc || 0, 500000);
  const lifeInsurance = 500000;

  return (
    <div ref={ref} className="bg-white" style={{ fontFamily: "'Segoe UI', sans-serif", fontSize: '12px', color: '#1a1a2e', maxWidth: '900px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '24px 32px', borderBottom: '3px solid #063c88' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <img src="/logo.png" alt="Company Logo" style={{ height: '50px', width: 'auto' }} />
          <div>
            <h1 style={{ fontSize: '20px', fontWeight: '700', color: '#063c88', margin: 0, letterSpacing: '-0.3px' }}>BluBridge Technologies</h1>
            <p style={{ fontSize: '11px', color: '#666', margin: '2px 0 0' }}>Compensation Structure</p>
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <p style={{ fontSize: '11px', color: '#666', margin: 0 }}>{monthLabel}</p>
          <p style={{ fontSize: '11px', color: '#666', margin: '2px 0 0' }}>Emp ID: {empId}</p>
        </div>
      </div>

      {/* Employee Info */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '12px', padding: '16px 32px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
        <div><p style={{ fontSize: '10px', color: '#94a3b8', margin: 0, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Employee Name</p><p style={{ fontSize: '13px', fontWeight: '600', margin: '2px 0 0' }}>{empName}</p></div>
        <div><p style={{ fontSize: '10px', color: '#94a3b8', margin: 0, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Designation</p><p style={{ fontSize: '13px', fontWeight: '600', margin: '2px 0 0' }}>{desig || '-'}</p></div>
        <div><p style={{ fontSize: '10px', color: '#94a3b8', margin: 0, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Department</p><p style={{ fontSize: '13px', fontWeight: '600', margin: '2px 0 0' }}>{dept || '-'}</p></div>
        <div><p style={{ fontSize: '10px', color: '#94a3b8', margin: 0, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Date of Joining</p><p style={{ fontSize: '13px', fontWeight: '600', margin: '2px 0 0' }}>{doj || '-'}</p></div>
      </div>

      {/* Main Table */}
      <div style={{ padding: '20px 32px' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid #cbd5e1' }}>
          <thead>
            <tr style={{ background: '#063c88' }}>
              <th style={{ ...thStyle, color: 'white', width: '50%' }}>Particulars</th>
              <th style={{ ...thStyle, color: 'white', textAlign: 'right' }}>Monthly (INR)</th>
              <th style={{ ...thStyle, color: 'white', textAlign: 'right' }}>Annual (INR)</th>
            </tr>
          </thead>
          <tbody>
            {/* Base Components */}
            <tr style={sectionHeaderStyle}>
              <td style={tdBold} colSpan={3}>Base Components (A)</td>
            </tr>
            <tr style={rowStyle}>
              <td style={tdLeft}>Basic</td>
              <td style={tdRight}>{monthly(salary.basic)}</td>
              <td style={tdRight}>{annual(salary.basic)}</td>
            </tr>
            <tr style={rowStyle}>
              <td style={tdLeft}>HRA</td>
              <td style={tdRight}>{monthly(salary.hra)}</td>
              <td style={tdRight}>{annual(salary.hra)}</td>
            </tr>
            <tr style={totalRowStyle}>
              <td style={tdBold}>Sub Total (A)</td>
              <td style={tdRightBold}>{monthly(salary.base_components_total)}</td>
              <td style={tdRightBold}>{annual(salary.base_components_total)}</td>
            </tr>

            {/* Basket of Allowances */}
            <tr style={sectionHeaderStyle}>
              <td style={tdBold} colSpan={3}>Basket of Allowances (B)</td>
            </tr>
            <tr style={rowStyle}>
              <td style={tdLeft}>Leave Travel Assistance</td>
              <td style={tdRight}>{monthly(salary.lta)}</td>
              <td style={tdRight}>{annual(salary.lta)}</td>
            </tr>
            <tr style={rowStyle}>
              <td style={tdLeft}>Phone & Internet Reimbursement</td>
              <td style={tdRight}>{monthly(salary.phone_internet)}</td>
              <td style={tdRight}>{annual(salary.phone_internet)}</td>
            </tr>
            <tr style={rowStyle}>
              <td style={tdLeft}>Bonus</td>
              <td style={tdRight}>{monthly(salary.bonus)}</td>
              <td style={tdRight}>{annual(salary.bonus)}</td>
            </tr>
            <tr style={rowStyle}>
              <td style={tdLeft}>Stay and Travel Allowance</td>
              <td style={tdRight}>{monthly(salary.stay_travel)}</td>
              <td style={tdRight}>{annual(salary.stay_travel)}</td>
            </tr>
            <tr style={rowStyle}>
              <td style={tdLeft}>Special Allowance</td>
              <td style={tdRight}>{monthly(salary.special_allowance)}</td>
              <td style={tdRight}>{annual(salary.special_allowance)}</td>
            </tr>
            <tr style={rowStyle}>
              <td style={tdLeft}>Food Reimbursement</td>
              <td style={tdRight}>{monthly(salary.food_reimbursement)}</td>
              <td style={tdRight}>{annual(salary.food_reimbursement)}</td>
            </tr>
            <tr style={totalRowStyle}>
              <td style={tdBold}>Sub Total (B)</td>
              <td style={tdRightBold}>{monthly(salary.basket_allowances_total)}</td>
              <td style={tdRightBold}>{annual(salary.basket_allowances_total)}</td>
            </tr>

            {/* Retirement Benefits */}
            <tr style={sectionHeaderStyle}>
              <td style={tdBold} colSpan={3}>Retirement Benefits (C)</td>
            </tr>
            <tr style={rowStyle}>
              <td style={tdLeft}>PF Company Contribution</td>
              <td style={tdRight}>{monthly(salary.pf_employer)}</td>
              <td style={tdRight}>{annual(salary.pf_employer)}</td>
            </tr>
            <tr style={rowStyle}>
              <td style={tdLeft}>Gratuity</td>
              <td style={tdRight}>{monthly(salary.gratuity)}</td>
              <td style={tdRight}>{annual(salary.gratuity)}</td>
            </tr>
            <tr style={totalRowStyle}>
              <td style={tdBold}>Sub Total (C)</td>
              <td style={tdRightBold}>{monthly(salary.retirement_benefits_total)}</td>
              <td style={tdRightBold}>{annual(salary.retirement_benefits_total)}</td>
            </tr>

            {/* Fixed Compensation */}
            <tr style={grandTotalStyle}>
              <td style={{ ...tdBold, color: '#063c88' }}>Fixed Compensation (A+B+C)</td>
              <td style={{ ...tdRightBold, color: '#063c88' }}>{monthly(salary.fixed_compensation)}</td>
              <td style={{ ...tdRightBold, color: '#063c88' }}>{annual(salary.fixed_compensation)}</td>
            </tr>

            {/* Variable */}
            <tr style={rowStyle}>
              <td style={tdLeft}>Variable Compensation (at 100%)</td>
              <td style={tdRight}>{monthly(salary.variable_compensation)}</td>
              <td style={tdRight}>{annual(salary.variable_compensation)}</td>
            </tr>

            {/* CTC */}
            <tr style={{ background: '#063c88' }}>
              <td style={{ ...tdBold, color: 'white', padding: '10px 12px' }}>Cost To Company (CTC)</td>
              <td style={{ ...tdRightBold, color: 'white', padding: '10px 12px' }}>{monthly(salary.monthly_ctc)}</td>
              <td style={{ ...tdRightBold, color: 'white', padding: '10px 12px' }}>{fmt(salary.annual_ctc)}</td>
            </tr>
          </tbody>
        </table>

        {/* Insurance Coverage */}
        <div style={{ marginTop: '20px', border: '1px solid #cbd5e1', borderRadius: '8px', overflow: 'hidden' }}>
          <div style={{ background: '#f1f5f9', padding: '10px 16px', borderBottom: '1px solid #cbd5e1' }}>
            <p style={{ fontWeight: '700', fontSize: '12px', margin: 0, color: '#334155' }}>Insurance Coverage</p>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              <tr style={rowStyle}>
                <td style={{ ...tdLeft, width: '60%' }}>Medical Insurance (Floating Coverage)</td>
                <td style={tdRight}>Up to {fmt(medInsurance)} p.a.</td>
              </tr>
              <tr style={rowStyle}>
                <td style={tdLeft}>Accident Insurance</td>
                <td style={tdRight}>1x CTC (Min {fmt(accInsurance)})</td>
              </tr>
              <tr style={rowStyle}>
                <td style={tdLeft}>Life Insurance</td>
                <td style={tdRight}>{fmt(lifeInsurance)}</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Deductions Summary */}
        <div style={{ marginTop: '20px', border: '1px solid #cbd5e1', borderRadius: '8px', overflow: 'hidden' }}>
          <div style={{ background: '#fef2f2', padding: '10px 16px', borderBottom: '1px solid #fecaca' }}>
            <p style={{ fontWeight: '700', fontSize: '12px', margin: 0, color: '#b91c1c' }}>Employee Deductions (Monthly)</p>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              <tr style={rowStyle}>
                <td style={{ ...tdLeft, width: '60%' }}>PF (Employee Contribution)</td>
                <td style={tdRight}>{monthly(salary.pf_employee)}</td>
              </tr>
              {salary.esi_employee > 0 && <tr style={rowStyle}>
                <td style={tdLeft}>ESI</td>
                <td style={tdRight}>{monthly(salary.esi_employee)}</td>
              </tr>}
              <tr style={rowStyle}>
                <td style={tdLeft}>Professional Tax</td>
                <td style={tdRight}>{monthly(salary.professional_tax)}</td>
              </tr>
              {salary.tds > 0 && <tr style={rowStyle}>
                <td style={tdLeft}>TDS</td>
                <td style={tdRight}>{monthly(salary.tds)}</td>
              </tr>}
              <tr style={{ background: '#fef2f2' }}>
                <td style={{ ...tdBold, color: '#b91c1c' }}>Total Deductions</td>
                <td style={{ ...tdRightBold, color: '#b91c1c' }}>{monthly(salary.total_deductions)}</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Net Salary */}
        <div style={{ marginTop: '20px', background: 'linear-gradient(135deg, #063c88, #0a5cba)', borderRadius: '10px', padding: '16px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p style={{ color: '#93c5fd', fontSize: '11px', margin: 0, textTransform: 'uppercase', letterSpacing: '1px' }}>Monthly Net Salary (Take Home)</p>
            <p style={{ color: 'white', fontSize: '28px', fontWeight: '800', margin: '4px 0 0', letterSpacing: '-0.5px' }}>
              INR {monthly(salary.net_salary)}
            </p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <p style={{ color: '#93c5fd', fontSize: '11px', margin: 0 }}>Annual Take Home</p>
            <p style={{ color: 'white', fontSize: '18px', fontWeight: '700', margin: '2px 0 0' }}>INR {annual(salary.net_salary)}</p>
          </div>
        </div>

        {/* Footer */}
        <div style={{ marginTop: '24px', padding: '12px 0', borderTop: '1px solid #e2e8f0', textAlign: 'center' }}>
          <p style={{ color: '#94a3b8', fontSize: '10px', margin: 0 }}>This is a system-generated document. For queries, contact HR at hr@blubridge.com</p>
          <p style={{ color: '#cbd5e1', fontSize: '9px', margin: '4px 0 0' }}>BluBridge Technologies Pvt. Ltd. | Confidential</p>
        </div>
      </div>
    </div>
  );
});

SalarySlip.displayName = 'SalarySlip';

// Styles
const thStyle = { padding: '10px 12px', fontSize: '11px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px', textAlign: 'left', borderBottom: '2px solid #cbd5e1' };
const sectionHeaderStyle = { background: '#f1f5f9' };
const rowStyle = { borderBottom: '1px solid #e2e8f0' };
const totalRowStyle = { background: '#f8fafc', borderBottom: '2px solid #cbd5e1' };
const grandTotalStyle = { background: '#eff6ff', borderBottom: '2px solid #93c5fd' };
const tdLeft = { padding: '8px 12px', fontSize: '12px' };
const tdRight = { padding: '8px 12px', fontSize: '12px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' };
const tdBold = { padding: '8px 12px', fontSize: '12px', fontWeight: '700' };
const tdRightBold = { padding: '8px 12px', fontSize: '12px', textAlign: 'right', fontWeight: '700', fontVariantNumeric: 'tabular-nums' };

export default SalarySlip;
