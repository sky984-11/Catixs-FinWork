// Date-only arithmetic in UTC, matching the backend's clamped anniversary dates.
export function monthEnd(value) {
  if (!value) return null
  const [year, month] = value.split('-').map(Number)
  const date = new Date(Date.UTC(year, month, 0))
  return Number.isNaN(date.getTime()) ? null : date.toISOString().slice(0, 10)
}

export function addDays(value, days) {
  if (!value) return null
  const date = new Date(`${value}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return Number.isNaN(date.getTime()) ? null : date.toISOString().slice(0, 10)
}

export function daysBetween(start, end) {
  return Math.round((Date.parse(end) - Date.parse(start)) / 86400000)
}

export function addMonths(value, months) {
  if (!value) return null
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1 + months, 1))
  const last = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate()
  date.setUTCDate(Math.min(day, last))
  return date.toISOString().slice(0, 10)
}

function monthOffset(start, end) {
  const a = start.split('-').map(Number)
  const b = end.split('-').map(Number)
  return (b[0] - a[0]) * 12 + b[1] - a[1]
}

export function alignPeriod(form) {
  const date = form.period_start || form.service_start
  if (!date) return null
  if (form.calendar_mode === 'calendar') return `${date.slice(0, 7)}-01`
  if (!form.service_start) return null
  return addMonths(form.service_start, Math.max(0, monthOffset(form.service_start, date)))
}

export function nextPeriod(form) {
  if (!form.period_start || !form.months) return null
  if (form.calendar_mode === 'calendar') return addMonths(form.period_start, form.months)
  if (!form.service_start) return null
  return addMonths(
    form.service_start,
    monthOffset(form.service_start, form.period_start) + form.months
  )
}

export function orderDefaults(orders, currency) {
  const items = orders.flatMap((order) => order.items || [])
  const currencies = [...new Set(items.map((item) => item.currency).filter(Boolean))].sort()
  const selectedCurrency = currencies.includes(currency) ? currency : currencies[0] || null
  const periods = [
    ...new Set(
      items.filter((item) => item.currency === selectedCurrency).map((item) => item.period_months)
    ),
  ]
  return {
    currencies,
    currency: selectedCurrency,
    months: periods.length === 1 && [1, 3, 6, 12, 24, 36].includes(periods[0]) ? periods[0] : null,
    mixedPeriods: periods.length > 1,
    title: orders
      .map((order) => order.name)
      .join(' / ')
      .slice(0, 160),
  }
}
