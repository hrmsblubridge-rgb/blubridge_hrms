import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';

// Standard page-size options across HRMS listings: every 25 up to 100, then every 50 up to 500.
export const PAGE_SIZE_OPTIONS = [25, 50, 75, 100, 150, 200, 250, 300, 350, 400, 450, 500];

/**
 * Reusable page-size selector for table pagination.
 * Props:
 *  - value: number (current page size)
 *  - onChange: (number) => void
 *  - testId: optional data-testid for the trigger
 *  - className: optional override for trigger width
 *  - showLabel: whether to render the "Rows per page:" prefix label (default true)
 */
export function PageSizeSelector({ value, onChange, testId = 'rows-per-page-select', className = 'w-[88px] h-8 rounded-lg text-sm', showLabel = true }) {
  return (
    <div className="flex items-center gap-2">
      {showLabel && <label className="text-sm text-slate-500">Rows per page:</label>}
      <Select value={String(value)} onValueChange={(v) => onChange(Number(v))}>
        <SelectTrigger className={className} data-testid={testId}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {PAGE_SIZE_OPTIONS.map(opt => (
            <SelectItem key={opt} value={String(opt)} data-testid={`${testId}-option-${opt}`}>{opt}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
