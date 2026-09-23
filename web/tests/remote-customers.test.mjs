import assert from 'node:assert/strict'
import test from 'node:test'
import {
  buildCustomerOptions,
  selectedCustomerValue,
} from '../src/views/ops/remote-assistance/customers.mjs'

const customers = [
  {
    value: 1,
    name: '南凌',
    short_name: '南凌',
    label: '南凌一公司',
    signing_entity_name: '科特思',
  },
  {
    value: 2,
    name: '南凌',
    short_name: '南凌',
    label: '南凌二公司',
    signing_entity_name: '77 Telecom',
  },
  {
    value: 3,
    name: '其他客户',
    short_name: '其他客户',
    label: '其他公司',
    signing_entity_name: 'Catixs',
  },
]

test('customer IDs remain unique even when customer names repeat', () => {
  const options = buildCustomerOptions(customers)
  assert.equal(new Set(options.map((item) => item.value)).size, options.length)
  assert.deepEqual(
    options.map((item) => item.label),
    ['Catixs', '南凌', '南凌', '其他客户']
  )
  assert.equal(selectedCustomerValue(options, '南凌', 'customer:2'), 'customer:2')
  assert.equal(
    options.find((item) => item.value === 'customer:2').signing_entity_name,
    '77 Telecom'
  )
  assert.equal(options.find((item) => item.value === 'customer:3').customerName, '其他客户')
})

test('legacy names remain unchanged and full names resolve to the matching customer', () => {
  const options = buildCustomerOptions(customers, '历史客户')
  assert.equal(selectedCustomerValue(options, '历史客户', null), 'legacy:历史客户')
  assert.equal(selectedCustomerValue(options, '南凌二公司', null), 'customer:2')
  assert.equal(selectedCustomerValue(options, '', null), null)
})

test('Catixs is selectable without duplicating an existing customer', () => {
  const options = buildCustomerOptions(customers)
  assert.equal(selectedCustomerValue(options, 'Catixs', null), 'builtin:catixs')
  const existing = buildCustomerOptions([{ value: 4, name: 'Catixs', label: 'Catixs' }])
  assert.equal(existing.length, 1)
  assert.equal(selectedCustomerValue(existing, 'Catixs', null), 'customer:4')
})
