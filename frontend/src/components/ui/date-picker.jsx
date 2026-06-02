import * as React from "react";
import { Calendar as CalendarIcon } from "lucide-react";
import { format } from "date-fns";
import { cn } from "@/lib/utils";
import { Button } from "./button";
import { Calendar } from "./calendar";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";

function DatePicker({ value, onChange, className, placeholder = "Pick a date", disabled = false, min, max, "data-testid": dataTestId }) {
  const [date, setDate] = React.useState(value ? new Date(value) : undefined);

  React.useEffect(() => {
    if (value) {
      setDate(new Date(value));
    } else {
      setDate(undefined);
    }
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
