import assert from 'node:assert/strict'
import test from 'node:test'
import { calculateTierFee, validateBillingRules } from '../src/views/ops/remote-assistance/billing.mjs'
import { recordsCsv } from '../src/views/ops/remote-assistance/export.mjs'

const rules = { currency: 'CNY', tiers: [
  { up_to_minutes: 60, hourly_rate: '120.00' },
  { up_to_minutes: 180, hourly_rate: '90.00' },
  { up_to_minutes: null, hourly_rate: '60.00' },
] }

test('tier fees accumulate by actual minutes at boundaries and across tiers', () => {
  for (const [minutes, fee] of [[0, '0.00'], [30, '60.00'], [60, '120.00'], [61, '121.50'], [180, '300.00'], [240, '360.00']]) {
    assert.equal(calculateTierFee(rules, minutes), fee)
  }
  assert.equal(calculateTierFee({ currency: 'USD', tiers: [{ up_to_minutes: null, hourly_rate: 0.30 }] }, 1), '0.01')
  assert.equal(calculateTierFee(null, 60), null)
})

test('invalid ranges and prices cannot be used for calculation', () => {
  for (const tiers of [[], [{ up_to_minutes: 60, hourly_rate: 1 }],
    [{ up_to_minutes: null, hourly_rate: -1 }],
    [{ up_to_minutes: null, hourly_rate: 1.001 }],
    [{ up_to_minutes: 60, hourly_rate: 1 }, { up_to_minutes: 60, hourly_rate: 1 }, { up_to_minutes: null, hourly_rate: 1 }],
    [{ up_to_minutes: null, hourly_rate: 1 }, { up_to_minutes: null, hourly_rate: 1 }]]) {
    assert.ok(validateBillingRules({ currency: 'CNY', tiers }))
    assert.equal(calculateTierFee({ currency: 'CNY', tiers }, 60), null)
  }
})

test('CSV preserves Chinese, delimiters, newlines and neutralizes formulas', () => {
  assert.equal(recordsCsv([['客户', 'a,"b"\nc', '=1+1', ' @SUM(A1)', null]]), '\uFEFF"客户","a,""b""\nc","\'=1+1","\' @SUM(A1)",""')
})
