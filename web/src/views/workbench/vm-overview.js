const gib = 1024 ** 3

export function summarizeVmFleet(items = [], nodes = []) {
  const regions = new Map(
    nodes.map((node) => [node.remote || node.value, node.region_name || '未关联地区'])
  )
  const unique = new Map()
  for (const vm of items) {
    if (vm.template || !['pve-qemu', 'qemu'].includes(vm.type)) continue
    unique.set(`${vm.remote}:${vm.vmid}`, vm)
  }
  return [...unique.values()].map((vm) => ({
    ...vm,
    key: `${vm.remote}:${vm.vmid}`,
    customerKey: vm.customer_id ? `customer:${vm.customer_id}` : `name:${vm.customer_name || ''}`,
    customerName: vm.customer_name || (vm.customer_id ? `客户 #${vm.customer_id}` : '未分配客户'),
    region: regions.get(vm.remote) || '未关联地区',
    cores: Number(vm.maxcpu) || 0,
    memory: (Number(vm.maxmem) || 0) / gib,
    storage: (Number(vm.maxdisk) || 0) / gib,
  }))
}

export function groupVmCustomers(vms) {
  const customers = new Map()
  for (const vm of vms) {
    if (!customers.has(vm.customerKey)) {
      customers.set(vm.customerKey, {
        key: vm.customerKey,
        name: vm.customerName,
        items: [],
        cores: 0,
        memory: 0,
        storage: 0,
      })
    }
    const customer = customers.get(vm.customerKey)
    customer.items.push(vm)
    customer.cores += vm.cores
    customer.memory += vm.memory
    customer.storage += vm.storage
  }
  return [...customers.values()].sort(
    (a, b) => b.items.length - a.items.length || a.name.localeCompare(b.name, 'zh-CN')
  )
}
