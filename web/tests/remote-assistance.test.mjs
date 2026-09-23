import { exampleBillingRules } from './fixtures/maintenance-rules.mjs'
import assert from 'node:assert/strict'
import test from 'node:test'
import {
  createMaintenanceRules,
  cloneBillingRules,
  validateBillingRules,
  beijingDateTime,
  beijingTimestamp,
  billingSummary,
  billingTotalLabel,
  editableBillingRules,
} from '../src/views/ops/remote-assistance/billing.mjs'
import { recordsCsv } from '../src/views/ops/remote-assistance/export.mjs'

test('engineer editing converts transport once and removes retired sections', () => {
  const original = exampleBillingRules('los_angeles')
  const rules = editableBillingRules(original)
  assert.equal(rules.transport_mode, 'none')
  assert.equal(rules.additional_fees[0].amount, 55)
  assert.equal(rules.additional_fees[0].minutes_source, 'actual')
  assert.equal(editableBillingRules(rules).additional_fees.length, 1)
  assert.equal(original.transport_mode, 'hourly')
  const japan = editableBillingRules(exampleBillingRules('japan'))
  assert.equal(japan.emergency_fee, null)
  assert.deepEqual(japan.payment_methods, [])
  assert.equal(validateBillingRules(rules), '')
})

test('mixed currencies display separately and are not mistaken for pending', () => {
  assert.equal(
    billingTotalLabel({
      status: 'calculated',
      total: null,
      totals: { USD: '200.00', CNY: '500.00' },
    }),
    '200.00 USD + 500.00 CNY'
  )
  assert.equal(billingTotalLabel({ status: 'pending', total: null }), '待确认')
  assert.equal(
    billingTotalLabel({ status: 'calculated', total: '0.00', currency: 'USD' }),
    '0.00 USD'
  )
})

test('new rules have no preset region, fee, local night window or payment method', () => {
  const rules = createMaintenanceRules()
  assert.equal(rules.hourly_rate, null)
  assert.equal(rules.currency, 'CNY')
  assert.equal(rules.night_enabled, false)
  assert.equal(rules.night_start, null)
  assert.equal(rules.transport_mode, 'none')
  assert.deepEqual(rules.payment_methods, [])
  assert.deepEqual(rules.emergency_regions, [])
  assert.equal(validateBillingRules(rules), '')
})
test('examples are explicit templates with confirmed currency and independent data', () => {
  const sg = exampleBillingRules('singapore')
  assert.equal(sg.currency, 'USD')
  assert.equal(sg.hourly_rate, 30)
  assert.equal(sg.transport_fee, 100)
  assert.equal(exampleBillingRules('uk').currency, 'GBP')
  assert.equal(exampleBillingRules('uk').commute_minutes, 60)
  assert.equal(exampleBillingRules('germany').hourly_rate, 20)
  assert.equal(exampleBillingRules('new_york').minimum_minutes, 120)
  assert.equal(exampleBillingRules('los_angeles').hourly_rate, 55)
  assert.equal(exampleBillingRules('los_angeles').billing_increment_minutes, 60)
  assert.equal(exampleBillingRules('los_angeles').commute_mode, 'actual')
  assert.equal(exampleBillingRules('japan').night_start, null)
  assert.equal(exampleBillingRules('japan').night_applies_to_emergency, false)
  for (const name of [
    'singapore',
    'seoul',
    'us',
    'new_york',
    'los_angeles',
    'germany',
    'uk',
    'japan',
  ])
    assert.equal(validateBillingRules(exampleBillingRules(name)), '')
})
test('old hourly rules preserve all tiers and do not share mutable data', () => {
  const source = {
    currency: 'USD',
    tiers: [
      { up_to_minutes: 60, hourly_rate: '50.00' },
      { up_to_minutes: null, hourly_rate: '60.00' },
    ],
  }
  const normalized = cloneBillingRules(source)
  assert.equal(normalized.pricing, 'tiered_hourly')
  assert.equal(normalized.hourly_tiers[0].hourly_rate, 50)
  normalized.hourly_tiers[0].hourly_rate = 20
  assert.equal(source.tiers[0].hourly_rate, '50.00')
  assert.equal(validateBillingRules(source), '')
  assert.ok(billingSummary(source)[0].includes('USD'))
})
test('invalid drafts and missing package prices cannot silently become free', () => {
  for (const patch of [
    { hourly_rate: -1 },
    { billing_increment_minutes: 0 },
    { night_multiplier: 0 },
    { night_start: '22:00', night_end: null },
    { emergency_regions: ['北京'], emergency_confirmation_regions: ['北京'] },
    { pricing: 'package', tiers: [] },
    { pricing: 'package', tiers: [{ up_to_minutes: 60, total_fee: null }] },
  ]) {
    assert.ok(validateBillingRules({ ...createMaintenanceRules(), ...patch }))
  }
})
test('Beijing time is independent of browser/process timezone and DST', () => {
  assert.equal(beijingDateTime(new Date('2026-09-22T02:00:00Z')), '2026-09-22T10:00')
  assert.equal(beijingTimestamp('2026-09-22T10:00'), Date.parse('2026-09-22T02:00:00Z'))
  assert.equal(beijingTimestamp('2026-09-22T02:00Z'), beijingTimestamp('2026-09-22T10:00'))
  assert.equal(
    (beijingTimestamp('2026-03-08T16:30') - beijingTimestamp('2026-03-08T14:30')) / 60000,
    120
  )
})
test('CSV preserves Chinese and neutralizes formulas', () => {
  assert.ok(recordsCsv([['客户', '=1+1', 'a,b']]).startsWith('\uFEFF'))
  assert.ok(recordsCsv([['=1+1']]).includes("'=1+1"))
  assert.ok(recordsCsv([['a,b']]).includes('"a,b"'))
})
