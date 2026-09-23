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
