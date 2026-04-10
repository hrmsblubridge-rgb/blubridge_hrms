import { forwardRef } from 'react';

const fmt = (v) => {
  if (!v && v !== 0) return '-';
  return Number(v).toLocaleString('en-IN', { maximumFractionDigits: 0 });
};

const SalarySlip = forwardRef(({ employee, salary, month }, ref) => {
  if (!salary) return null;

  const empName = employee?.full_name || employee?.name || 'Employee';
  const empId = employee?.custom_employee_id || employee?.emp_id || employee?.id?.slice(0, 8) || '';
  const desig = employee?.designation || '-';
  const tier = employee?.tier_level || '-';
  const dept = employee?.department || '-';
  const doj = employee?.date_of_joining || '-';
  const monthLabel = month || new Date().toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });

  const BLUE = '#0a3d7c';
  const LIGHT_BG = '#f0f5fb';
  const BORDER = '#d6e2f0';

  const medInsurance = 300000;
  const accInsurance = Math.max(salary.annual_ctc || 0, 500000);
  const lifeInsurance = 500000;

  return (
    <div ref={ref} style={{ fontFamily: "'Segoe UI', Tahoma, sans-serif", fontSize: '13px', color: '#1a1a2e', maxWidth: '860px', margin: '0 auto', background: '#f4f6f9' }}>
      {/* Header Banner */}
      <div style={{ background: BLUE, padding: '36px 40px 32px', position: 'relative' }}>
        <img src="/logo-blubridge.webp" alt="BluBridge" style={{ position: 'absolute', top: '24px', right: '32px', height: '44px', opacity: 0.9, filter: 'brightness(0) invert(1)' }} />
        <h1 style={{ fontSize: '26px', fontWeight: '800', color: '#fff', margin: 0, letterSpacing: '-0.3px' }}>Compensation & Benefits Structure</h1>
        <p style={{ fontSize: '15px', color: '#c5d8ef', margin: '8px 0 0', fontStyle: 'italic' }}>Payslip for {monthLabel}</p>
        <p style={{ fontSize: '13px', color: '#a3bdd6', margin: '6px 0 0' }}>BluBridge Technologies Pvt Ltd | Chennai, Tamil Nadu, India</p>
      </div>

      {/* Content Area */}
      <div style={{ padding: '28px 40px 32px' }}>
        {/* Employee Info Card */}
        <div style={{ background: '#fff', border: `1px solid ${BORDER}`, borderRadius: '8px', padding: '20px 24px', marginBottom: '28px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '16px' }}>
            {[
              ['EMPLOYEE NAME', empName],
              ['EMPLOYEE ID', empId],
              ['DESIGNATION', desig],
              ['TIER', tier],
            ].map(([label, value]) => (
              <div key={label}>
                <p style={{ fontSize: '10px', color: '#7c8da6', margin: 0, textTransform: 'uppercase', letterSpacing: '0.8px', fontWeight: '600' }}>{label}</p>
                <p style={{ fontSize: '15px', fontWeight: '700', color: '#1a2740', margin: '4px 0 0' }}>{value}</p>
              </div>
            ))}
          </div>
        </div>

        {/* A - Base Components */}
        <SectionHeader badge="A" title="Base Components" color={BLUE} />
        <CompTable
          rows={[
            ['Basic', salary.basic],
            ['House Rent Allowance (HRA)', salary.hra],
          ]}
          total={['Base Components Total (A)', salary.base_components_total]}
          borderColor={BORDER}
          lightBg={LIGHT_BG}
        />

        {/* B - Basket of Allowances */}
        <SectionHeader badge="B" title="Basket of Allowances" color={BLUE} />
        <CompTable
          rows={[
            ['Leave Travel Allowance (LTA)', salary.lta],
            ['Phone & Internet', salary.phone_internet],
            ['Bonus', salary.bonus],
            ['Stay and Travel Allowance', salary.stay_travel],
            ['Special Allowance', salary.special_allowance],
            ['Food Reimbursement', salary.food_reimbursement],
            ...(salary.medical_allowance > 0 ? [['Medical Allowance', salary.medical_allowance]] : []),
            ...(salary.conveyance > 0 ? [['Conveyance', salary.conveyance]] : []),
          ]}
          total={['Basket of Allowances Total (B)', salary.basket_allowances_total]}
          borderColor={BORDER}
          lightBg={LIGHT_BG}
        />

        {/* C - Retirement Benefits */}
        <SectionHeader badge="C" title="Retirement Benefits" color={BLUE} />
        <CompTable
          rows={[
            ['PF Company Contribution', salary.pf_employer],
            ['Gratuity', salary.gratuity],
          ]}
          total={['Retirement Benefits Total (C)', salary.retirement_benefits_total]}
          borderColor={BORDER}
          lightBg={LIGHT_BG}
        />

        {/* Fixed Compensation Summary */}
        <div style={{ background: LIGHT_BG, border: `1.5px solid ${BLUE}`, borderRadius: '8px', padding: '14px 20px', marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '14px', fontWeight: '800', color: BLUE }}>Fixed Compensation (A+B+C)</span>
          <span style={{ fontSize: '16px', fontWeight: '800', color: BLUE }}>{`\u20B9${fmt(salary.fixed_compensation)}`}</span>
        </div>

        {/* D - Variable + CTC */}
        <SectionHeader badge="D" title="Variable & Total CTC" color={BLUE} />
        <CompTable
          rows={[
            ['Variable Compensation (at 100%)', salary.variable_compensation],
          ]}
          total={['Cost To Company (CTC)', salary.monthly_ctc]}
          totalAnnual={salary.annual_ctc}
          borderColor={BORDER}
          lightBg={LIGHT_BG}
          ctcRow
        />

        {/* E - Insurance Coverage */}
        <SectionHeader badge="E" title="Insurance Coverage" color={BLUE} />
        <div style={{ marginBottom: '24px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              {[
                ['Medical Insurance (Floating Coverage)', `Up to \u20B9${fmt(medInsurance)} p.a.`],
                ['Accident Insurance', `1x CTC (Min \u20B9${fmt(accInsurance)})`],
                ['Life Insurance', `\u20B9${fmt(lifeInsurance)}`],
              ].map(([label, val], i) => (
                <tr key={i} style={{ borderBottom: `1px solid ${BORDER}` }}>
                  <td style={{ padding: '10px 16px', fontSize: '13px', color: '#374151' }}>{label}</td>
                  <td style={{ padding: '10px 16px', fontSize: '13px', fontWeight: '600', color: '#1a2740', textAlign: 'right' }}>{val}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* F - Employee Deductions */}
        <SectionHeader badge="F" title="Employee Deductions (Monthly)" color="#b91c1c" />
        <div style={{ marginBottom: '24px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ padding: '8px 16px', fontSize: '11px', color: '#7c8da6', textAlign: 'left', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Deduction</th>
                <th style={{ padding: '8px 16px', fontSize: '11px', color: '#7c8da6', textAlign: 'right', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Monthly</th>
              </tr>
            </thead>
            <tbody>
              {[
                ['PF (Employee Contribution)', salary.pf_employee],
                ...(salary.esi_employee > 0 ? [['ESI', salary.esi_employee]] : []),
                ['Professional Tax', salary.professional_tax],
                ...(salary.tds > 0 ? [['TDS', salary.tds]] : []),
              ].map(([label, val], i) => (
                <tr key={i} style={{ borderBottom: `1px solid ${BORDER}` }}>
                  <td style={{ padding: '10px 16px', fontSize: '13px', color: '#374151' }}>{label}</td>
                  <td style={{ padding: '10px 16px', fontSize: '13px', fontWeight: '600', color: '#b91c1c', textAlign: 'right' }}>{`\u20B9${fmt(val)}`}</td>
                </tr>
              ))}
              <tr style={{ background: '#fef2f2' }}>
                <td style={{ padding: '10px 16px', fontSize: '13px', fontWeight: '800', color: '#b91c1c' }}>Total Deductions</td>
                <td style={{ padding: '10px 16px', fontSize: '14px', fontWeight: '800', color: '#b91c1c', textAlign: 'right' }}>{`\u20B9${fmt(salary.total_deductions)}`}</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Net Salary */}
        <div style={{ background: `linear-gradient(135deg, ${BLUE}, #1565c0)`, borderRadius: '10px', padding: '20px 28px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div>
            <p style={{ color: '#93c5fd', fontSize: '10px', margin: 0, textTransform: 'uppercase', letterSpacing: '1.2px', fontWeight: '600' }}>Monthly Net Salary (Take Home)</p>
            <p style={{ color: '#fff', fontSize: '30px', fontWeight: '900', margin: '4px 0 0', letterSpacing: '-0.5px' }}>{`\u20B9${fmt(salary.net_salary)}`}</p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <p style={{ color: '#93c5fd', fontSize: '10px', margin: 0, textTransform: 'uppercase', letterSpacing: '1px', fontWeight: '600' }}>Annual Take Home</p>
            <p style={{ color: '#fff', fontSize: '20px', fontWeight: '800', margin: '4px 0 0' }}>{`\u20B9${fmt(salary.net_salary * 12)}`}</p>
          </div>
        </div>

        {/* Footer */}
        <div style={{ textAlign: 'center', paddingTop: '12px', borderTop: `1px solid ${BORDER}` }}>
          <p style={{ color: '#94a3b8', fontSize: '10px', margin: 0 }}>This is a system-generated document. For queries, contact HR at hr@blubridge.com</p>
          <p style={{ color: '#cbd5e1', fontSize: '9px', margin: '4px 0 0' }}>BluBridge Technologies Pvt. Ltd. | Confidential</p>
        </div>
      </div>
    </div>
  );
});

SalarySlip.displayName = 'SalarySlip';

/* Section Header with Badge */
const SectionHeader = ({ badge, title, color }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px', marginTop: '4px' }}>
    <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '26px', height: '26px', background: color, color: '#fff', fontSize: '13px', fontWeight: '800', borderRadius: '5px' }}>{badge}</span>
    <span style={{ fontSize: '16px', fontWeight: '700', color: '#1a2740' }}>{title}</span>
  </div>
);

/* Compensation Table */
const CompTable = ({ rows, total, totalAnnual, borderColor, lightBg, ctcRow }) => (
  <div style={{ marginBottom: '24px' }}>
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr>
          <th style={{ padding: '8px 16px', fontSize: '11px', color: '#7c8da6', textAlign: 'left', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Component</th>
          <th style={{ padding: '8px 16px', fontSize: '11px', color: '#7c8da6', textAlign: 'right', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Monthly ({'\u20B9'})
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([label, val], i) => (
          <tr key={i} style={{ borderBottom: `1px solid ${borderColor}` }}>
            <td style={{ padding: '10px 16px', fontSize: '13px', color: '#374151' }}>{label}</td>
            <td style={{ padding: '10px 16px', fontSize: '14px', fontWeight: '600', color: '#1a2740', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{`\u20B9${fmt(val)}`}</td>
          </tr>
        ))}
        {total && (
          <tr style={{ background: ctcRow ? '#0a3d7c' : lightBg, borderTop: `2px solid ${borderColor}` }}>
            <td style={{ padding: '12px 16px', fontSize: '13px', fontWeight: '800', color: ctcRow ? '#fff' : '#1a2740' }}>{total[0]}</td>
            <td style={{ padding: '12px 16px', fontSize: '15px', fontWeight: '800', color: ctcRow ? '#fff' : '#1a2740', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
              {ctcRow && totalAnnual
                ? `\u20B9${fmt(total[1])} / \u20B9${fmt(totalAnnual)} p.a.`
                : `\u20B9${fmt(total[1])}`}
            </td>
          </tr>
        )}
      </tbody>
    </table>
  </div>
);

export default SalarySlip;
