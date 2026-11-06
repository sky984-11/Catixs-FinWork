import assert from 'node:assert/strict'
import test from 'node:test'
import {
  addDays,
  daysBetween,
  alignPeriod,
  nextPeriod,
  orderDefaults,
} from '../src/views/product-center/billing/autofill.mjs'

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
