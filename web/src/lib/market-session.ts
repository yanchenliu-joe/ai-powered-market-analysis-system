/** Lightweight NYSE session helper. Does not fabricate pipeline as_of_date. */

export const DEFAULT_SESSION_COMPLETE_HOUR_ET = 16;

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

export function ymd(year: number, month: number, day: number): string {
  return `${year}-${pad2(month)}-${pad2(day)}`;
}

export function addUtcDays(isoDate: string, days: number): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  const stamp = Date.UTC(year, month - 1, day + days);
  const next = new Date(stamp);
  return ymd(next.getUTCFullYear(), next.getUTCMonth() + 1, next.getUTCDate());
}

export function weekdayUtc(isoDate: string): number {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day)).getUTCDay();
}

function nthWeekday(year: number, month: number, weekday: number, nth: number): string {
  const first = ymd(year, month, 1);
  const offset = (weekday - weekdayUtc(first) + 7) % 7;
  return addUtcDays(first, offset + (nth - 1) * 7);
}

function lastWeekday(year: number, month: number, weekday: number): string {
  const last = ymd(year, month + 1, 0);
  const back = (weekdayUtc(last) - weekday + 7) % 7;
  return addUtcDays(last, -back);
}

function easterSunday(year: number): string {
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31);
  const day = ((h + l - 7 * m + 114) % 31) + 1;
  return ymd(year, month, day);
}

function observedWeekdayHoliday(isoDate: string): string {
  const weekday = weekdayUtc(isoDate);
  if (weekday === 6) {
    return addUtcDays(isoDate, -1);
  }
  if (weekday === 0) {
    return addUtcDays(isoDate, 1);
  }
  return isoDate;
}

export function nyseHolidays(year: number): Set<string> {
  return new Set([
    observedWeekdayHoliday(ymd(year, 1, 1)),
    nthWeekday(year, 1, 1, 3),
    nthWeekday(year, 2, 1, 3),
    addUtcDays(easterSunday(year), -2),
    lastWeekday(year, 5, 1),
    observedWeekdayHoliday(ymd(year, 6, 19)),
    observedWeekdayHoliday(ymd(year, 7, 4)),
    nthWeekday(year, 9, 1, 1),
    nthWeekday(year, 11, 4, 4),
    observedWeekdayHoliday(ymd(year, 12, 25)),
  ]);
}

export function isNyseTradingDay(isoDate: string): boolean {
  const weekday = weekdayUtc(isoDate);
  if (weekday === 0 || weekday === 6) {
    return false;
  }
  const year = Number(isoDate.slice(0, 4));
  const holidays = nyseHolidays(year);
  const nextNewYearObserved = observedWeekdayHoliday(ymd(year + 1, 1, 1));
  if (nextNewYearObserved.startsWith(String(year))) {
    holidays.add(nextNewYearObserved);
  }
  return !holidays.has(isoDate);
}

export function previousNyseTradingDay(isoDate: string): string {
  let cursor = addUtcDays(isoDate, -1);
  for (let i = 0; i < 14; i += 1) {
    if (isNyseTradingDay(cursor)) {
      return cursor;
    }
    cursor = addUtcDays(cursor, -1);
  }
  return cursor;
}

export function newYorkDateTime(now: Date): { date: string; hour: number; minute: number } {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(now);
  const value = (type: Intl.DateTimeFormatPartTypes): string =>
    parts.find((part) => part.type === type)?.value ?? "0";
  return {
    date: `${value("year")}-${value("month")}-${value("day")}`,
    hour: Number(value("hour")),
    minute: Number(value("minute")),
  };
}

export function expectedLatestCompletedSession(
  now: Date,
  sessionCompleteHourEt: number = DEFAULT_SESSION_COMPLETE_HOUR_ET,
): string {
  const { date, hour } = newYorkDateTime(now);
  if (isNyseTradingDay(date) && hour >= sessionCompleteHourEt) {
    return date;
  }
  return previousNyseTradingDay(date);
}

export function isAcceptedAsOfCurrent(
  asOfDate: string,
  now: Date,
  sessionCompleteHourEt: number = DEFAULT_SESSION_COMPLETE_HOUR_ET,
): boolean {
  return asOfDate >= expectedLatestCompletedSession(now, sessionCompleteHourEt);
}
