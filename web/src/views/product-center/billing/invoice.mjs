import { daysBetween } from './autofill.mjs'

const escape = (value) =>
  String(value ?? '').replace(
    /[&<>"']/g,
    (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char])
  )

function cents(value) {
  const match = String(value ?? '0').match(/^(-?)(\d+)(?:\.(\d{0,2}))?$/)
  if (!match) return 0n
  const amount = BigInt(match[2]) * 100n + BigInt((match[3] || '').padEnd(2, '0'))
  return match[1] ? -amount : amount
}
function format(value) {
  const sign = value < 0n ? '-' : ''
  const absolute = value < 0n ? -value : value
  return `${sign}${(absolute / 100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${(
    absolute % 100n
  )
    .toString()
    .padStart(2, '0')}`
}
const money = (value) => format(cents(value))
const date = (value) => escape(value?.replaceAll('-', '/') || '—')

export function invoiceHtml(bill, origin) {
  const customer = bill.customer_snapshot || bill.customer || {}
  const terms = bill.settings || bill
  const lines = bill.lines || []
  const currency = escape(bill.currency || '—')
  const issuer = escape(customer.signing_entity || bill.signing_entity_name || '—')
  const logoUrl = bill.signing_entity_logo_url ?? customer.signing_entity_logo_url
  let logo = ''
  if (logoUrl) {
    try {
      const url = new URL(logoUrl, origin)
      if (['http:', 'https:'].includes(url.protocol)) logo = url.href
    } catch {
      /* Invalid historical logo URLs fall back to the issuer name. */
    }
  }
  const sum = (key) => format(lines.reduce((total, line) => total + cents(line[key]), 0n))
  const totalDue = ['void', 'deleted'].includes(bill.status)
    ? '0.00'
    : bill.outstanding ?? bill.amount
  const summary = (label, value, bold = false) =>
    `<tr${bold ? ' class="strong"' : ''}><td>${label}</td><td>${value}</td></tr>`
  const net = cents(bill.subtotal) - cents(terms.discount) + cents(terms.adjustment)
  const status = !bill.bill_no
    ? 'PREVIEW · 未生成账单'
    : { draft: 'DRAFT · 草稿', void: 'VOID · 已作废', deleted: 'DELETED · 已删除' }[bill.status] ||
      ''
  const rows = lines
    .map((line) => {
      const specs = Array.isArray(line.spec_snapshot) ? line.spec_snapshot : []
      const value = (field) =>
        `${Array.isArray(field.value) ? field.value.join(', ') : field.value ?? ''}${
          field.unit || ''
        }`
      const item = [
        line.variant_name,
        ...specs.map((field) => `${field.name}: ${value(field)}`),
        `Qty: ${line.quantity ?? 1}`,
      ]
        .filter(Boolean)
        .map(escape)
        .join('<br>')
      return `<tr><td>${escape(line.order_no || '—')}</td><td>${escape(
        line.product_name || '—'
      )}</td><td class="item">${item}</td><td>${date(line.period_start)}</td><td>${date(
        line.period_end
      )}</td><td class="number">${money(line.nrc_amount)}</td><td class="number">${money(
        line.mrc_amount
      )}</td></tr>`
    })
    .join('')
  const foot = (label, value) =>
    `<tr><td colspan="5" class="number">${label}</td><td colspan="2" class="number">${value}</td></tr>`
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${escape(
    bill.bill_no || bill.title || 'Invoice Preview'
  )}</title><style>
    *{box-sizing:border-box}body{margin:0;background:#fff;color:#171b22;font:12px Arial,"Microsoft YaHei",sans-serif}.paper{padding:36px 40px;max-width:900px;margin:auto}h1{font-size:23px;margin:0 0 12px;overflow-wrap:anywhere}.status{color:#777;font-size:11px;margin-bottom:22px}.header,.parties{display:flex;justify-content:space-between;gap:32px}.header{align-items:center;margin:28px 0 45px}.logo{max-width:235px;max-height:80px;object-fit:contain}.brand{font-size:32px;font-weight:bold}.issuer{text-align:right;width:220px;font-weight:bold;line-height:1.6;white-space:pre-line}.customer{max-width:55%;line-height:1.7;white-space:pre-line}.meta{width:240px}.meta td{padding:3px 0}.meta td:last-child{text-align:right}.summary{width:290px;margin:42px 0 50px}.summary td{padding:4px 0}.summary td:last-child{text-align:right}.strong{font-weight:bold}.summary .strong:last-child td{padding-top:20px}.details{width:100%;border-collapse:collapse;table-layout:fixed;font-size:10px}.details th,.details td{border:1px solid #d7dbe1;padding:9px 6px;overflow-wrap:anywhere;vertical-align:middle}.details th{font-weight:normal}.details caption{background:#f2f3f5;border:1px solid #d7dbe1;border-bottom:0;padding:10px;font-size:17px}.details .item{line-height:1.6}.number{text-align:right}.remark{white-space:pre-wrap;overflow-wrap:anywhere;margin-top:24px}.details tr{break-inside:avoid}thead{display:table-header-group}@page{size:A4;margin:14mm}@media print{.paper{padding:0;max-width:none}.header{margin-top:20px}.details{font-size:9px}body{print-color-adjust:exact}}
  </style></head><body><main class="paper"><h1>${escape(
    bill.title || 'Invoice'
  )}</h1><div class="status">${status}</div>
  <header class="header"><div>${
    logo
      ? `<img class="logo" src="${escape(logo)}" alt="${issuer}">`
      : `<div class="brand">${issuer}</div>`
  }</div><div class="issuer">${issuer}<br>${escape(
    customer.signing_entity_address || ''
  )}</div></header>
  <section class="parties"><div class="customer"><strong>${escape(
    customer.name || bill.customer_name || '—'
  )}</strong><br>${escape(customer.address || '')}</div><table class="meta"><tbody>
  ${summary('Invoice#', escape(bill.bill_no || '待生成'))}${summary(
    'Invoice Date',
    date(terms.bill_date)
  )}${summary('Due Date', date(terms.due_date))}${summary(
    'Term',
    Number.isFinite(daysBetween(terms.bill_date, terms.due_date))
      ? `Net ${daysBetween(terms.bill_date, terms.due_date)}`
      : '—'
  )}${summary('Currency', currency)}
  </tbody></table></section><table class="summary"><tbody>${summary(
    'Summary',
    currency,
    true
  )}${summary('Recurring', sum('mrc_amount'))}${summary('Non-Recurring', sum('nrc_amount'))}${
    cents(terms.discount) ? summary('Discount', money(terms.discount)) : ''
  }${cents(terms.adjustment) ? summary('Adjustment', money(terms.adjustment)) : ''}${summary(
    'VAT Amount',
    money(bill.tax_amount)
  )}${summary('Total Charges', money(bill.amount))}${
    cents(bill.paid_amount) ? summary('Paid', money(bill.paid_amount)) : ''
  }${summary('Total Due', money(totalDue), true)}</tbody></table>
  <table class="details"><caption>Invoice Summary</caption><colgroup><col style="width:20%"><col style="width:10%"><col style="width:29%"><col style="width:11%"><col style="width:11%"><col style="width:9%"><col style="width:10%"></colgroup><thead><tr><th>Order / Cct ID</th><th>Service</th><th>Item</th><th>Start Date</th><th>End Date</th><th>NRC ${currency}</th><th>MRC ${currency}</th></tr></thead><tbody>${
    rows || '<tr><td colspan="7">暂无明细</td></tr>'
  }${foot('Net Amount', format(net))}${foot('VAT Amount', money(bill.tax_amount))}${foot(
    'Total Amount',
    money(bill.amount)
  )}</tbody></table>
  ${terms.remark ? `<p class="remark">${escape(terms.remark)}</p>` : ''}</main></body></html>`
}
