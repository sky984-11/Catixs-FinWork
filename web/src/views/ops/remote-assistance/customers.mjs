export function buildCustomerOptions(customers, current = '') {
  const options = customers.map((item) => ({
    label: item.short_name || item.name || item.label,
    value: `customer:${item.value}`,
    customerName: item.name || item.short_name || item.label,
    customerId: item.value,
    maintenance_hourly_rate: item.maintenance_hourly_rate,
    maintenance_currency: item.maintenance_currency || 'USD',
    aliases: [item.name, item.short_name, item.label].filter(Boolean),
    signing_entity_name: item.signing_entity_name,
    searchText: [item.short_name, item.name, item.label, item.customer_code]
      .filter(Boolean)
      .join(' '),
    class: 'remote-customer-option',
  }))
  if (!options.some((item) => item.customerName.toLowerCase() === 'catixs')) {
    options.unshift({
      label: 'Catixs',
      value: 'builtin:catixs',
      customerName: 'Catixs',
      aliases: ['Catixs'],
      signing_entity_name: 'Catixs',
      class: 'remote-customer-option',
    })
  }
  if (current && !options.some((item) => item.aliases.includes(current))) {
    options.push({
      label: current,
      value: `legacy:${current}`,
      customerName: current,
      aliases: [current],
      class: 'remote-customer-option',
    })
  }
  return options
}

export function selectedCustomerValue(options, name, selected) {
  const match = options.find((item) => item.value === selected && item.aliases.includes(name))
  return match?.value ?? options.find((item) => item.aliases.includes(name))?.value ?? null
}

export function buildPlanCustomerOptions(customers, plans) {
  const options = buildCustomerOptions(customers)
  for (const plan of plans) {
    if (!plan.customer) continue
    const value = plan.customer_id ? `customer:${plan.customer_id}` : `legacy:${plan.customer}`
    const exists = plan.customer_id
      ? options.some((option) => option.value === value)
      : options.some((option) => option.aliases.includes(plan.customer))
    if (!exists)
      options.push({
        value,
        label: plan.customer,
        customerName: plan.customer,
        customerId: plan.customer_id,
        aliases: [plan.customer],
        class: 'remote-customer-option',
      })
  }
  return options
}

export function matchesPlanCustomer(plan, option) {
  if (!option) return false
  if (plan.customer_id) return String(plan.customer_id) === String(option.customerId)
  return option.aliases.includes(plan.customer)
}
