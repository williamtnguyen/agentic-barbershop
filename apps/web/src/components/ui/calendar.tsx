import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Dates are plain "YYYY-MM-DD" strings in the shop's calendar, so no timezone math. */
export type DateString = string;

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
const monthTitle = new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" });
const dayTitle = new Intl.DateTimeFormat(undefined, {
  weekday: "long",
  month: "long",
  day: "numeric",
});

export function toDateString(year: number, monthIndex: number, day: number): DateString {
  return `${year}-${String(monthIndex + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function monthKey(month: Date): string {
  return toDateString(month.getFullYear(), month.getMonth(), 1).slice(0, 7);
}

interface CalendarProps {
  month: Date; // any date within the month to show
  onMonthChange: (month: Date) => void;
  selected?: DateString;
  onSelect: (day: DateString) => void;
  isAvailable: (day: DateString) => boolean;
  minMonth?: Date;
  loading?: boolean;
  className?: string;
}

export function Calendar({
  month,
  onMonthChange,
  selected,
  onSelect,
  isAvailable,
  minMonth,
  loading,
  className,
}: CalendarProps) {
  const year = month.getFullYear();
  const index = month.getMonth();
  const leading = new Date(year, index, 1).getDay();
  const days = new Date(year, index + 1, 0).getDate();
  const atMin =
    minMonth !== undefined &&
    (year < minMonth.getFullYear() ||
      (year === minMonth.getFullYear() && index <= minMonth.getMonth()));

  return (
    <div className={cn("w-full", className)} aria-busy={loading}>
      <div className="mb-3 flex items-center justify-between">
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          aria-label="Previous month"
          disabled={atMin}
          onClick={() => onMonthChange(new Date(year, index - 1, 1))}
        >
          <ChevronLeft />
        </Button>
        <div className="text-sm font-medium" aria-live="polite">
          {monthTitle.format(new Date(year, index, 1))}
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          aria-label="Next month"
          onClick={() => onMonthChange(new Date(year, index + 1, 1))}
        >
          <ChevronRight />
        </Button>
      </div>
      <div role="grid" className="grid grid-cols-7 gap-1 text-center">
        {WEEKDAYS.map((d) => (
          <div key={d} role="columnheader" className="pb-1 text-xs text-muted-foreground">
            {d}
          </div>
        ))}
        {Array.from({ length: leading }, (_, i) => (
          <div key={`blank-${i}`} />
        ))}
        {Array.from({ length: days }, (_, i) => {
          const value = toDateString(year, index, i + 1);
          const available = !loading && isAvailable(value);
          const isSelected = value === selected;
          return (
            <button
              key={value}
              type="button"
              disabled={!available}
              aria-pressed={isSelected}
              aria-label={`${dayTitle.format(new Date(year, index, i + 1))}${available ? "" : ", no openings"}`}
              onClick={() => onSelect(value)}
              className={cn(
                "h-10 rounded-md text-sm transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                available
                  ? "font-medium text-foreground hover:bg-accent"
                  : "text-muted-foreground/40",
                available && !isSelected && "bg-primary/8",
                isSelected && "bg-primary text-primary-foreground hover:bg-primary",
              )}
            >
              {i + 1}
            </button>
          );
        })}
      </div>
    </div>
  );
}
