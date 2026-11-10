import assert from 'node:assert/strict'
import test from 'node:test'
import { invoiceHtml } from '../src/views/product-center/billing/invoice.mjs'

const bill = {
  title: 'Monthly service',
  currency: 'USD',
  amount: '0.33',
  subtotal: '0.30',
  tax_amount: '0.03',
  bill_date: '2026-11-01',
  due_date: '2026-12-01',
  customer: {
    name: '<script>alert(1)</script>',
    signing_entity: 'Issuer',
    signing_entity_logo_url: 'javascript:alert(1)',
  },
  lines: [
    { order_no: 'ORDER-1', mrc_amount: '0.10', nrc_amount: '0.00' },
    { mrc_amount: '0.20', nrc_amount: '0.00' },
  ],
}
test('invoice escapes business data, rejects script logos, and sums cents exactly', () => {
  const html = invoiceHtml(bill, 'https://example.test')
  assert.ok(html.includes('&lt;script&gt;'))
  assert.ok(!html.includes('<script>'))
  assert.ok(!html.includes('javascript:'))
  assert.match(html, /Recurring<\/td><td>0\.30/)
  assert.match(html, /Net 30/)
  assert.ok(html.includes('PREVIEW'))
  assert.ok(html.includes('ORDER-1'))
  assert.ok(!html.includes('<th>Location</th>'))
  assert.equal((html.match(/<th>/g) || []).length, 7)
})
test('invoice uses the selected entity current logo and never carries another entity logo', () => {
  for (const logo of ['/logos/catixs.png', '/logos/77-telecom.png', '/logos/custom.png']) {
    const html = invoiceHtml({ ...bill, signing_entity_logo_url: logo }, 'https://example.test')
    assert.ok(html.includes(`src="https://example.test${logo}"`))
  }
  const html = invoiceHtml({ ...bill, signing_entity_logo_url: '' }, 'https://example.test')
  assert.ok(!html.includes('<img'))
})
test('saved invoices show outstanding, adjustments, snapshots and void state', () => {
  const html = invoiceHtml(
    {
      ...bill,
      bill_no: 'INV-1',
      status: 'partial',
      outstanding: '0.23',
      paid_amount: '0.10',
      settings: { ...bill, discount: '0.05', adjustment: '0.02' },
      customer_snapshot: { name: 'Saved customer', signing_entity_logo_url: '/logos/catixs.png' },
    },
    'https://example.test'
  )
  assert.match(html, /Total Due<\/td><td>0\.23/)
  assert.match(html, /Net Amount<\/td><td colspan="2" class="number">0\.27/)
  assert.ok(html.includes('Saved customer'))
  assert.ok(html.includes('https://example.test/logos/catixs.png'))
  assert.ok(!html.includes('PREVIEW'))
  assert.match(
    invoiceHtml({ ...bill, status: 'void', bill_no: 'INV-1' }),
    /Total Due<\/td><td>0\.00/
  )
})
