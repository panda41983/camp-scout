"use client";

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfWeek(year: number, month: number): number {
  return new Date(year, month, 1).getDay();
}

interface Props {
  availableDates: string[]; // YYYY-MM-DD strings
}

export function AvailabilityCalendar({ availableDates }: Props) {
  if (availableDates.length === 0) return null;

  // Group dates by month
  const dateSet = new Set(availableDates);
  const months = new Map<string, { year: number; month: number }>();

  for (const ds of availableDates) {
    const d = new Date(ds + "T00:00:00");
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    if (!months.has(key)) {
      months.set(key, { year: d.getFullYear(), month: d.getMonth() });
    }
  }

  return (
    <div className="mt-3 space-y-4">
      {[...months.values()].map(({ year, month }) => (
        <MiniMonth
          key={`${year}-${month}`}
          year={year}
          month={month}
          availableDates={dateSet}
        />
      ))}
    </div>
  );
}

function MiniMonth({
  year,
  month,
  availableDates,
}: {
  year: number;
  month: number;
  availableDates: Set<string>;
}) {
  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfWeek(year, month);
  const monthName = new Date(year, month).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });

  const cells: (number | null)[] = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  const rows: (number | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) {
    rows.push(cells.slice(i, i + 7));
  }

  return (
    <div>
      <p className="mb-1 text-xs font-semibold text-muted-foreground">{monthName}</p>
      <table className="border-collapse">
        <thead>
          <tr>
            {WEEKDAYS.map((wd) => (
              <th
                key={wd}
                className="h-6 w-7 text-center text-[10px] font-medium text-muted-foreground"
              >
                {wd}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {row.map((day, ci) => {
                if (day === null) {
                  return <td key={ci} className="h-7 w-7" />;
                }

                const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                const isAvailable = availableDates.has(dateStr);
                const dayOfWeek = new Date(year, month, day).getDay();
                const isWeekend = dayOfWeek === 0 || dayOfWeek === 5 || dayOfWeek === 6;

                return (
                  <td
                    key={ci}
                    className={`h-7 w-7 text-center text-xs rounded-sm
                      ${isAvailable
                        ? "bg-primary text-primary-foreground font-semibold"
                        : isWeekend
                          ? "text-muted-foreground/50"
                          : "text-muted-foreground/30"
                      }
                    `}
                  >
                    {day}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
