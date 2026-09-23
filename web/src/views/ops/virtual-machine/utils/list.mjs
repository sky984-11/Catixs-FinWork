const identity = (vm) => JSON.stringify([vm.remote || '', vm.type || '', String(vm.vmid ?? vm.id)])

export function stableVmOrder(previous, incoming) {
  const positions = new Map(previous.map((vm, index) => [identity(vm), index]))
  return [...incoming].sort((left, right) => {
    const leftPosition = positions.get(identity(left))
    const rightPosition = positions.get(identity(right))
    if (leftPosition !== undefined || rightPosition !== undefined) {
      return (leftPosition ?? Infinity) - (rightPosition ?? Infinity)
    }
    return (
      String(left.remote || '').localeCompare(String(right.remote || '')) ||
      String(left.vmid ?? left.id).localeCompare(String(right.vmid ?? right.id), undefined, {
        numeric: true,
      }) ||
      String(left.type || '').localeCompare(String(right.type || ''))
    )
  })
}
