import * as React from "react";
import { Calendar as CalendarIcon } from "lucide-react";
import { format } from "date-fns";
import { cn } from "@/lib/utils";
import { Button } from "./button";
import { Calendar } from "./calendar";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";

// Parse a value into a Date WITHOUT timezone off-by-one. A bare "yyyy-MM-dd"
// string is parsed by JS as UTC midnight, which can render as the previous
// day in negative-offset timezones. We parse those components as a LOCAL date
// so the picker always shows the exact day the user picked / was stored.
function parseLocalDate(v) {
  if (!v) return undefined;
  if (v instanceof Date) return isNaN(v.getTime()) ? undefined : v;
  if (typeof v === "string") {
    const m = v.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (m) {
      const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
      return isNaN(d.getTime()) ? undefined : d;
    }
  }
  const d = new Date(v);
  return isNaN(d.getTime()) ? undefined : d;
}

function DatePicker({ value, onChange, className, placeholder = "Pick a date", disabled = false, min, max, "data-testid": dataTestId }) {
  const [date, setDate] = React.useState(parseLocalDate(value));

  React.useEffect(() => {
    setDate(parseLocalDate(value));
  }, [value]);

  const handleSelect = (selectedDate) => {
    setDate(selectedDate);
    if (selectedDate) {
      // Format as YYYY-MM-DD for input compatibility
      const formattedDate = format(selectedDate, "yyyy-MM-dd");
      onChange(formattedDate);
    }
  };

  // Optional min/max as YYYY-MM-DD strings or Date objects. When provided,
  // disable any calendar day outside that range. Strictly additive — when
  // min/max are undefined the Calendar receives no `disabled` prop and
  // behaves exactly as before for all existing admin call sites.
  const toDate = React.useCallback((v) => {
    if (!v) return null;
    if (v instanceof Date) return v;
    const d = new Date(v);
    return isNaN(d.getTime()) ? null : d;
  }, []);
  const minDate = toDate(min);
  const maxDate = toDate(max);
  const dayDisabled = React.useMemo(() => {
    if (!minDate && !maxDate) return undefined;
    return (day) => {
      const t = day.setHours(0, 0, 0, 0);
      if (minDate && t < minDate.setHours(0, 0, 0, 0)) return true;
      if (maxDate && t > maxDate.setHours(0, 0, 0, 0)) return true;
      return false;
    };
  }, [minDate, maxDate]);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          disabled={disabled}
          data-testid={dataTestId}
          className={cn(
            "w-full justify-start text-left font-normal bg-white border-gray-300",
            !date && "text-muted-foreground",
            className
          )}
        >
          <CalendarIcon className="mr-2 h-4 w-4 text-gray-500" />
          {date ? format(date, "dd-MMM-yyyy") : <span>{placeholder}</span>}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0 bg-white" align="start">
        <Calendar
          mode="single"
          selected={date}
          onSelect={handleSelect}
          disabled={dayDisabled}
          initialFocus
        />
      </PopoverContent>
    </Popover>
  );
}

DatePicker.displayName = "DatePicker";

export { DatePicker };
