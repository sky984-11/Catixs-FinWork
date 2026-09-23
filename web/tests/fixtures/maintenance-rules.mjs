import { createMaintenanceRules } from '../../src/views/ops/remote-assistance/billing.mjs'

export function exampleBillingRules(name) {
  const rules = createMaintenanceRules()
  if (name === 'singapore')
    Object.assign(rules, {
      currency: 'USD',
      hourly_rate: 30,
      transport_mode: 'fixed',
      transport_fee: 100,
    })
  if (name === 'seoul') Object.assign(rules, { currency: 'USD', hourly_rate: 50 })
  if (name === 'us') Object.assign(rules, { currency: 'USD', hourly_rate: 60 })
  if (name === 'new_york')
    Object.assign(rules, { currency: 'USD', hourly_rate: 60, minimum_minutes: 120 })
  if (name === 'los_angeles')
    Object.assign(rules, {
      currency: 'USD',
      hourly_rate: 55,
      billing_increment_minutes: 60,
      transport_mode: 'hourly',
      commute_mode: 'actual',
      commute_increment_minutes: 30,
    })
  if (name === 'germany')
    Object.assign(rules, {
      currency: 'USD',
      hourly_rate: 20,
      transport_mode: 'hourly',
      note: 'Catixs本公司报价：20 USD/小时，每次加1小时通勤。',
    })
  if (name === 'uk')
    Object.assign(rules, { currency: 'GBP', hourly_rate: 30, transport_mode: 'hourly' })
  if (name === 'japan')
    Object.assign(rules, {
      pricing: 'package',
      tiers: [
        { up_to_minutes: 240, total_fee: 1100 },
        { up_to_minutes: 480, total_fee: 1650 },
      ],
      overtime_enabled: true,
      overtime_hourly_rate: 300,
      overtime_threshold_minutes: 30,
      overtime_rounding: 'half_hour_round',
      night_enabled: true,
      night_multiplier: 1.25,
      emergency_fee: 500,
      emergency_response_minutes: 240,
      emergency_regions: ['东京'],
      emergency_confirmation_regions: ['大阪'],
      transport_mode: 'reimburse',
      transport_included_regions: ['东京', '东京都'],
      project_services: ['设备上架', '综合布线'],
      settlement_cycles: ['日结', '周结'],
      payment_methods: [
        {
          name: '个人微信收款',
          tax_mode: 'none',
          tax_rate: null,
          tax_base: 'subtotal',
          note: '国内个人微信账号收款',
        },
        {
          name: '公司转账',
          tax_mode: 'confirm',
          tax_rate: null,
          tax_base: 'subtotal',
          note: '日本可公对公，税费另行确认',
        },
      ],
      note: '请配置已确认的当地夜班起止时段；加班取整方式可按约定调整。',
    })
  return rules
}
