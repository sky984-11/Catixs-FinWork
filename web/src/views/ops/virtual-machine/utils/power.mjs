export async function waitForVmPower({
  api,
  row,
  upid,
  target,
  cancelled,
  update,
  timeout = 120000,
  delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  now = Date.now,
}) {
  const deadline = now() + timeout
  let taskFinished = !upid
  while (now() < deadline && !cancelled()) {
    if (!taskFinished) {
      const response = await api.taskStatus({ remote: row.remote, upid })
      if (cancelled()) return false
      const task = response.data || {}
      if (task.finished) {
        if (!task.success)
          throw new Error(task.failure_reason || task.result_status || '虚拟机任务失败')
        taskFinished = true
      }
    }
    const response = await api.pveVms({ node: row.remote, vmid: row.vmid })
    if (cancelled()) return false
    const current = response.data?.items?.find(
      (item) => item.remote === row.remote && String(item.vmid) === String(row.vmid)
    )
    if (current) {
      update(current)
      if (taskFinished && current.status === target) return true
    }
    await delay(2000)
  }
  return false
}

export function mergeVmRuntime(vm, current) {
  const next = { ...vm }
  for (const key of ['status', 'cpu', 'mem', 'disk', 'maxmem', 'maxdisk', 'maxcpu', 'uptime']) {
    if (current[key] !== undefined) next[key] = current[key]
  }
  return next
}
