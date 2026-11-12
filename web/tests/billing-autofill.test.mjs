import assert from 'node:assert/strict'
import test from 'node:test'
import {
  addDays,
  monthEnd,
  daysBetween,
  alignPeriod,
  nextPeriod,
  orderDefaults,
} from '../src/views/product-center/billing/autofill.mjs'

test('payment defaults use the billing month end across short, leap and year-end months', () => {
  assert.equal(monthEnd('2026-11-01'), '2026-11-30')
  assert.equal(monthEnd('2026-12-12'), '2026-12-31')
  assert.equal(monthEnd('2025-02-01'), '2025-02-28')
  assert.equal(monthEnd('2024-02-10'), '2024-02-29')
  assert.equal(monthEnd(null), null)
})

test('calendar billing normalizes the month and advances across the year', () => {
  const form = { calendar_mode: 'calendar', period_start: '2026-11-13', months: 3 }
  form.period_start = alignPeriod(form)
  assert.equal(form.period_start, '2026-11-01')
  assert.equal(nextPeriod(form), '2027-02-01')
})

test('anniversary billing retains the original day after short and leap months', () => {
  const form = {
    calendar_mode: 'anniversary',
    service_start: '2024-01-31',
    period_start: '2024-02-13',
    months: 1,
  }
  form.period_start = alignPeriod(form)
  assert.equal(form.period_start, '2024-02-29')
  assert.equal(nextPeriod(form), '2024-03-31')
  form.period_start = '2023-12-01'
  assert.equal(alignPeriod(form), '2024-01-31')
})

test('payment terms use calendar days without timezone drift', () => {
  assert.equal(daysBetween('2026-11-06', '2026-12-06'), 30)
  assert.equal(addDays('2026-12-20', 30), '2027-01-19')
  assert.equal(addDays('2024-02-01', 29), '2024-03-01')
  assert.equal(addDays(null, 30), null)
})

test('defaults only inherit matching currency cycles and flag mixed terms', () => {
  const orders = [
    {
      name: 'Order',
      items: [
        { currency: 'USD', period_months: 3 },
        { currency: 'CNY', period_months: 1 },
      ],
    },
  ]
  assert.equal(orderDefaults(orders, 'USD').months, 3)
  assert.equal(orderDefaults(orders, 'CNY').months, 1)
  assert.equal(orderDefaults(orders, 'EUR').currency, 'CNY')
  orders[0].items.push({ currency: 'USD', period_months: 1 })
  assert.equal(orderDefaults(orders, 'USD').months, null)
  assert.equal(orderDefaults(orders, 'USD').mixedPeriods, true)
  assert.equal(orderDefaults([], 'USD').currency, null)
})
