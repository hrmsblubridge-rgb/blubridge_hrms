import * as React from "react";
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon } from "lucide-react";
import { Button } from "./button";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { cn } from "@/lib/utils";

const months = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
];

function MonthPicker({ value, onChange, className, placeholder = "Select month", disabled = false }) {
  const [isOpen, setIsOpen] = React.useState(false);
  
  // Parse value (format: "YYYY-MM")
  const [selectedYear, selectedMonth] = React.useMemo(() => {
    if (!value) return [new Date().getFullYear(), new Date().getMonth()];
    const parts = value.split("-");
    return [parseInt(parts[0]), parseInt(parts[1]) - 1];
  }, [value]);

  const [viewYear, setViewYear] = React.useState(selectedYear);

  const handleMonthSelect = (monthIndex) => {
    const newValue = `${viewYear}-${String(monthIndex + 1).padStart(2, "0")}`;
    onChange(newValue);
    setIsOpen(false);
  };

  const formatDisplayValue = () => {
    if (!value) return placeholder;
    return `${months[selectedMonth]} ${selectedYear}`;
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          disabled={disabled}
          className={cn(
            "w-[140px] justify-start text-left font-normal bg-white border-gray-300",
            !value && "text-muted-foreground",
            className
          )}
        >
          <CalendarIcon className="mr-2 h-4 w-4 text-gray-500" />
          {formatDisplayValue()}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[280px] p-0 bg-white" align="start">
        <div className="p-3">
          {/* Year Navigation */}
          <div className="flex items-center justify-between mb-4">
            <Button
              variant="outline"
              size="icon"
              className="h-7 w-7"
              onClick={() => setViewYear(viewYear - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm font-medium">{viewYear}</span>
            <Button
              variant="outline"
              size="icon"
              className="h-7 w-7"
              onClick={() => setViewYear(viewYear + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
          
          {/* Month Grid */}
          <div className="grid grid-cols-4 gap-2">
            {months.map((month, index) => {
              const isSelected = selectedYear === viewYear && selectedMonth === index;
              return (
                <Button
                  key={month}
                  variant={isSelected ? "default" : "ghost"}
                  className={cn(
                    "h-9 text-sm",
                    isSelected && "bg-[#0b1f3b] text-white hover:bg-[#162d4d]"
                  )}
                  onClick={() => handleMonthSelect(index)}
                >
                  {month}
                </Button>
              );
            })}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

MonthPicker.displayName = "MonthPicker";

export { MonthPicker };
