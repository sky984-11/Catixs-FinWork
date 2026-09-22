export const billingCurrencies = ['CNY', 'USD', 'HKD', 'EUR', 'GBP', 'SGD', 'JPY']

export function validateBillingRules(rules) {
  if (!rules) return ''
  if (!billingCurrencies.includes(rules.currency)) return '请选择计费币种'
  if (!rules.tiers.length || rules.tiers.length > 20) return '请配置 1 至 20 档计费规则'
  let previous = 0
  for (const [index, tier] of rules.tiers.entries()) {
    const rate = Number(tier.hourly_rate)
    if (tier.hourly_rate === null || tier.hourly_rate === '' || !Number.isFinite(rate) || rate < 0 || rate > 9999999999.99
      || Math.abs(rate * 100 - Math.round(rate * 100)) > 0.0001) return '小时单价须为非负金额，最多两位小数'
    if (tier.up_to_minutes === null) {
      if (index !== rules.tiers.length - 1) return '仅最后一档可以不设工时上限'
    } else if (!Number.isInteger(tier.up_to_minutes) || tier.up_to_minutes <= previous || tier.up_to_minutes > 525600) {
      return '工时上限须为递增的正整数分钟，最多 525600 分钟'
    } else previous = tier.up_to_minutes
  }
  return rules.tiers.at(-1).up_to_minutes === null ? '' : '最后一档必须不设上限'
}

export function calculateTierFee(rules, minutes) {
  if (!rules || validateBillingRules(rules) || !Number.isInteger(minutes) || minutes < 0) return null
  let start = 0
  let centMinutes = 0n
  for (const tier of rules.tiers) {
    const end = Math.min(minutes, tier.up_to_minutes ?? minutes)
    centMinutes += BigInt(Math.max(0, end - start)) * BigInt(Math.round(Number(tier.hourly_rate) * 100))
    if (end >= minutes) break
    start = end
  }
  const cents = (centMinutes + 30n) / 60n
  return `${cents / 100n}.${String(cents % 100n).padStart(2, '0')}`
}
