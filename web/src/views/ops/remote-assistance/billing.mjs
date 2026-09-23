export const billingCurrencies = ['CNY', 'USD', 'HKD', 'EUR', 'GBP', 'SGD', 'JPY']
export const timezoneOptions = [
  ['北京时间', 'Asia/Shanghai'],
  ['日本', 'Asia/Tokyo'],
  ['新加坡', 'Asia/Singapore'],
  ['韩国', 'Asia/Seoul'],
  ['洛杉矶', 'America/Los_Angeles'],
  ['纽约', 'America/New_York'],
  ['德国', 'Europe/Berlin'],
  ['英国', 'Europe/London'],
].map(([label, value]) => ({ label: `${label} · ${value}`, value }))
export const overtimeRoundingOptions = [
  { label: '每小时余量满起计分钟进一小时，不足舍去', value: 'half_hour_round' },
  { label: '满起计分钟后，不足一小时按一小时', value: 'ceil_after_threshold' },
  { label: '满起计分钟后，按实际分钟折算', value: 'actual_after_threshold' },
]
export function createMaintenanceRules() {
  return {
    mode: 'general',
    currency: 'CNY',
    pricing: 'hourly',
    hourly_rate: null,
    additional_fees: [],
    tiers: [],
    hourly_tiers: [],
    minimum_minutes: 0,
    billing_increment_minutes: 1,
    overtime_enabled: false,
    overtime_hourly_rate: null,
    overtime_threshold_minutes: 1,
    overtime_rounding: 'actual_after_threshold',
    night_enabled: false,
    night_start: null,
    night_end: null,
    night_multiplier: 1,
    night_basis: 'proportional',
    night_applies_to_emergency: false,
    emergency_fee: null,
    emergency_response_minutes: null,
    emergency_regions: [],
    emergency_confirmation_regions: [],
    transport_mode: 'none',
    transport_fee: null,
    commute_minutes: 60,
    commute_mode: 'fixed',
    commute_increment_minutes: 30,
    commute_hourly_rate: null,
    transport_included_regions: [],
    project_services: [],
    settlement_cycles: [],
    payment_methods: [],
    note: '',
  }
}
export function cloneBillingRules(source) {
  if (!source) return createMaintenanceRules()
  let rules = JSON.parse(JSON.stringify(source))
  if (rules.mode === 'package') {
    rules = {
      ...createMaintenanceRules(),
      pricing: 'package',
      currency: rules.currency,
      tiers: rules.tiers,
      overtime_enabled: true,
      overtime_hourly_rate: rules.overtime_hourly_rate,
      overtime_threshold_minutes: rules.overtime_threshold_minutes,
      overtime_rounding: rules.overtime_rounding,
      night_enabled: Number(rules.night_multiplier) > 1,
      night_multiplier: rules.night_multiplier,
      night_applies_to_emergency: rules.night_applies_to_emergency,
      emergency_fee: rules.emergency_fee,
      emergency_response_minutes: rules.emergency_response_minutes,
      emergency_regions: [rules.emergency_region],
      emergency_confirmation_regions: [rules.emergency_confirmation_region],
      transport_mode: 'reimburse',
      transport_included_regions: [rules.transport_included_region],
      project_services: rules.project_services,
      settlement_cycles: rules.settlement_cycles.map(
        (v) => ({ daily: '日结', weekly: '周结' }[v] || v)
      ),
      payment_methods: [
        {
          name: '原国内收款',
          tax_mode: 'none',
          tax_rate: null,
          tax_base: 'subtotal',
          note: rules.domestic_payment,
        },
        {
          name: '原日本收款',
          tax_mode: 'confirm',
          tax_rate: null,
          tax_base: 'subtotal',
          note: rules.japan_payment,
        },
      ],
      note: '由旧固定档位转换；当地夜班起止时段需确认。',
    }
  } else if (rules.mode !== 'general') {
    rules = {
      ...createMaintenanceRules(),
      currency: rules.currency,
      pricing: 'tiered_hourly',
      hourly_tiers: rules.tiers,
    }
  } else rules = { ...createMaintenanceRules(), ...rules }
  for (const key of [
    'hourly_rate',
    'overtime_hourly_rate',
    'night_multiplier',
    'emergency_fee',
    'transport_fee',
    'commute_hourly_rate',
  ]) {
    if (rules[key] !== null) rules[key] = Number(rules[key])
  }
  rules.additional_fees.forEach((fee) => {
    if (fee.amount != null) fee.amount = Number(fee.amount)
  })
  rules.tiers.forEach((tier) => {
    if (tier.total_fee !== null) tier.total_fee = Number(tier.total_fee)
  })
  rules.hourly_tiers.forEach((tier) => {
    if (tier.hourly_rate !== null) tier.hourly_rate = Number(tier.hourly_rate)
  })
  rules.payment_methods.forEach((method) => {
    if (method.tax_rate != null) method.tax_rate = Number(method.tax_rate)
  })
  return rules
}
export function validateBillingRules(source) {
  if (!source) return ''
  const rules = cloneBillingRules(source)
  if (!billingCurrencies.includes(rules.currency)) return '请选择币种'
  if (!['hourly', 'package', 'tiered_hourly'].includes(rules.pricing)) return '请选择计费模式'
  const amountValid = (v) =>
    v === null ||
    (Number.isFinite(Number(v)) &&
      Number(v) >= 0 &&
      Number(v) <= 9999999999.99 &&
      Math.abs(Number(v) * 100 - Math.round(Number(v) * 100)) < 0.0001)
  if (rules.additional_fees.length > 30) return '附加费用最多30项'
  if (new Set(rules.additional_fees.map((fee) => fee.id)).size !== rules.additional_fees.length)
    return '附加费用标识不能重复'
  for (const fee of rules.additional_fees) {
    if (!fee.name?.trim()) return '请填写附加费用名称'
    if (!amountValid(fee.amount)) return '附加费用金额须为非负数，最多两位小数'
    if (
      !['fixed', 'hourly'].includes(fee.mode) ||
      !['fixed', 'actual', 'work'].includes(fee.minutes_source)
    )
      return '请选择附加费用计费方式'
    if (
      !Number.isInteger(fee.minutes) ||
      fee.minutes < 0 ||
      fee.minutes > 10080 ||
      !Number.isInteger(fee.increment_minutes) ||
      fee.increment_minutes < 1 ||
      fee.increment_minutes > 1440
    )
      return '请填写有效的附加费用时长和步长'
  }
  for (const key of [
    'hourly_rate',
    'overtime_hourly_rate',
    'emergency_fee',
    'transport_fee',
    'commute_hourly_rate',
  ]) {
    if (!amountValid(rules[key])) return '金额须为非负数，最多两位小数；未确认可留空'
  }
  for (const [key, min, max] of [
    ['minimum_minutes', 0, 10080],
    ['billing_increment_minutes', 1, 1440],
    ['overtime_threshold_minutes', 1, 60],
    ['commute_minutes', 1, 10080],
    ['commute_increment_minutes', 1, 1440],
  ]) {
    if (!Number.isInteger(rules[key]) || rules[key] < min || rules[key] > max)
      return '工时或计费步长超出允许范围'
  }
  if (rules.pricing !== 'hourly') {
    const tiers = rules.pricing === 'package' ? rules.tiers : rules.hourly_tiers
    if (!tiers.length || tiers.length > 20) return '请配置1至20个档位'
    let last = 0
    let fee = 0
    for (const [index, tier] of tiers.entries()) {
      if (
        rules.pricing === 'tiered_hourly' &&
        index === tiers.length - 1 &&
        tier.up_to_minutes === null
      ) {
        if (tier.hourly_rate === null || !amountValid(tier.hourly_rate)) return '请填写小时单价'
        continue
      }
      if (
        !Number.isInteger(tier.up_to_minutes) ||
        tier.up_to_minutes <= last ||
        tier.up_to_minutes > 525600
      )
        return '工时上限须严格递增'
      last = tier.up_to_minutes
      const rate = rules.pricing === 'package' ? tier.total_fee : tier.hourly_rate
      if (rate === null || !amountValid(rate)) return '请填写有效档位金额'
      if (rules.pricing === 'package' && rate < fee) return '档位总价不能降低'
      fee = rate
    }
    if (rules.pricing === 'tiered_hourly' && tiers.at(-1).up_to_minutes !== null)
      return '最后一档必须不限时长'
  }
  if (
    rules.night_multiplier === null ||
    !amountValid(rules.night_multiplier) ||
    rules.night_multiplier < 1 ||
    rules.night_multiplier > 10
  )
    return '夜班倍率须为1至10'
  if (
    Boolean(rules.night_start) !== Boolean(rules.night_end) ||
    (rules.night_start && rules.night_start === rules.night_end)
  )
    return '夜班起止时段须同时填写且不同'
  if (
    rules.emergency_regions.some((region) => rules.emergency_confirmation_regions.includes(region))
  )
    return '紧急服务区域与待确认区不能重叠'
  if (
    new Set(rules.payment_methods.map((m) => m.name.trim())).size !==
      rules.payment_methods.length ||
    rules.payment_methods.some((m) => !m.name.trim())
  )
    return '收款方式名称不能为空或重复'
  return ''
}
export function billingSummary(source) {
  if (!source) return ['未配置']
  const rules = cloneBillingRules(source)
  const lines =
    rules.pricing === 'hourly'
      ? [`${rules.hourly_rate ?? '待确认'} ${rules.currency}/小时`]
      : rules.pricing === 'package'
      ? rules.tiers.map((tier) => `${tier.up_to_minutes}分钟内 ${tier.total_fee} ${rules.currency}`)
      : rules.hourly_tiers.map(
          (tier) =>
            `${tier.up_to_minutes ?? '不限'}分钟上限 ${tier.hourly_rate} ${rules.currency}/小时`
        )
  for (const fee of rules.additional_fees)
    lines.push(
      `${fee.name} ${fee.amount ?? '待确认'} ${rules.currency}${
        fee.mode === 'hourly' ? '/小时' : '/次'
      }`
    )
  if (rules.transport_mode === 'fixed')
    lines.push(`每次交通费 ${rules.transport_fee ?? '待确认'} ${rules.currency}`)
  if (rules.minimum_minutes) lines.push(`最低${rules.minimum_minutes}分钟`)
  if (rules.billing_increment_minutes > 1)
    lines.push(`作业按${rules.billing_increment_minutes}分钟向上取整`)
  if (rules.transport_mode === 'hourly')
    lines.push(
      rules.commute_mode === 'actual'
        ? `实际往返通勤按${rules.commute_increment_minutes}分钟向上取整`
        : `每次通勤${rules.commute_minutes}分钟`
    )
  if (rules.transport_mode === 'reimburse') lines.push('交通费实报实销')
  if (rules.night_enabled)
    lines.push(
      `当地夜班 ${rules.night_start ?? '待确认'}–${rules.night_end ?? '待确认'} ×${
        rules.night_multiplier
      }`
    )
  return lines
}
export function beijingDateTime(value = new Date()) {
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  })
    .format(value)
    .replace(' ', 'T')
}
export function beijingTimestamp(value) {
  if (!value) return NaN
  return Date.parse(/[zZ]$|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}+08:00`)
}

export function billingTotalLabel(result) {
  if (!result || result.status !== 'calculated') return '待确认'
  if (result.totals)
    return Object.entries(result.totals)
      .map(([currency, amount]) => `${amount} ${currency}`)
      .join(' + ')
  return `${result.total} ${result.currency}`
}

export function editableBillingRules(source) {
  const rules = cloneBillingRules(source)
  if (
    ['fixed', 'hourly'].includes(rules.transport_mode) &&
    !rules.additional_fees.some((fee) => fee.id === 'legacy-transport')
  ) {
    rules.additional_fees.push({
      id: 'legacy-transport',
      name: rules.transport_mode === 'fixed' ? '打车费' : '通勤费',
      mode: rules.transport_mode === 'fixed' ? 'fixed' : 'hourly',
      amount:
        rules.transport_mode === 'fixed'
          ? rules.transport_fee
          : rules.commute_hourly_rate ?? rules.hourly_rate,
      minutes_source: rules.commute_mode === 'actual' ? 'actual' : 'fixed',
      minutes: rules.commute_minutes,
      increment_minutes: rules.commute_mode === 'actual' ? rules.commute_increment_minutes : 1,
      excluded_regions: [...rules.transport_included_regions],
    })
  }
  Object.assign(rules, {
    transport_mode: 'none',
    transport_fee: null,
    emergency_fee: null,
    emergency_response_minutes: null,
    emergency_regions: [],
    emergency_confirmation_regions: [],
    night_applies_to_emergency: false,
    project_services: [],
    settlement_cycles: [],
    payment_methods: [],
  })
  return rules
}
