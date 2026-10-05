import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Button } from './ui/button';

/**
 * Professional pagination for client-side sliced lists.
 * Props:
 *   page          1-indexed current page
 *   pageSize      rows per page
 *   total         total records (after filtering)
 *   onPageChange  (page) => void
 *   onPageSizeChange (size) => void
 *   pageSizeOptions optional [10,25,50,100]
 *   testid        prefix for data-testids (default 'pagination')
 */
export const Pagination = ({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 25, 50, 100],
  testid = 'pagination',
}) => {
  const totalPages = Math.max(1, Math.ceil((total || 0) / (pageSize || 10)));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const start = total === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const end = Math.min(safePage * pageSize, total);

  // Build a compact page list with ellipses for large totals.
  const buildPages = () => {
    if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
    const pages = new Set([1, totalPages, safePage - 1, safePage, safePage + 1]);
    const list = [...pages].filter((p) => p >= 1 && p <= totalPages).sort((a, b) => a - b);
    const result = [];
    for (let i = 0; i < list.length; i++) {
      if (i > 0 && list[i] - list[i - 1] > 1) result.push('...');
      result.push(list[i]);
    }
    return result;
  };

  const goto = (p) => {
    if (p < 1 || p > totalPages || p === safePage) return;
    onPageChange(p);
  };

  return (
    <div
      className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 px-4 py-3 border-t border-slate-100 bg-white rounded-b-xl"
      data-testid={`${testid}-bar`}
    >
      <div className="text-sm text-slate-500" data-testid={`${testid}-summary`}>
        {total === 0 ? 'No records' : <>Showing <span className="font-medium text-slate-800">{start}</span>–<span className="font-medium text-slate-800">{end}</span> of <span className="font-medium text-slate-800">{total}</span> records</>}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Rows per page</span>
          <Select value={String(pageSize)} onValueChange={(v) => onPageSizeChange(Number(v))}>
            <SelectTrigger className="h-8 w-[78px] rounded-lg text-sm" data-testid={`${testid}-page-size`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {pageSizeOptions.map((opt) => (
                <SelectItem key={opt} value={String(opt)}>{opt}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={() => goto(1)} disabled={safePage === 1} data-testid={`${testid}-first`} aria-label="First page">
            <ChevronsLeft className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={() => goto(safePage - 1)} disabled={safePage === 1} data-testid={`${testid}-prev`} aria-label="Previous page">
            <ChevronLeft className="w-4 h-4" />
          </Button>
          {buildPages().map((p, idx) =>
            p === '...' ? (
              <span key={`ell-${idx}`} className="px-2 text-slate-400 text-sm">…</span>
            ) : (
              <Button
                key={p}
                variant={p === safePage ? 'default' : 'ghost'}
                size="sm"
                className={`h-8 min-w-8 px-2 text-sm ${p === safePage ? 'bg-[#063c88] hover:bg-[#052d66] text-white' : ''}`}
                onClick={() => goto(p)}
                data-testid={`${testid}-page-${p}`}
              >
                {p}
              </Button>
            )
          )}
          <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={() => goto(safePage + 1)} disabled={safePage === totalPages} data-testid={`${testid}-next`} aria-label="Next page">
            <ChevronRight className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={() => goto(totalPages)} disabled={safePage === totalPages} data-testid={`${testid}-last`} aria-label="Last page">
            <ChevronsRight className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};

export default Pagination;
