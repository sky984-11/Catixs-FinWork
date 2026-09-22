export function numeric(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) && number >= 0 ? number : null
}

export function bytes(value) {
  const number = numeric(value)
  if (number === null) return '—'
  if (number === 0) return '0 B'
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
  const index = Math.min(Math.floor(Math.log(number) / Math.log(1024)), units.length - 1)
  return `${Number((number / 1024 ** Math.max(0, index)).toFixed(1))} ${units[Math.max(0, index)]}`
}

export function percent(used, total) {
  const denominator = numeric(total)
  const numerator = numeric(used)
  return denominator && numerator !== null
    ? Math.min(100, Math.max(0, (numerator / denominator) * 100))
    : null
}

export function aggregateCluster(nodes) {
  const usable = nodes.filter((node) => !node.error && node.status !== 'offline')
  function sumPair(totalKey, usedKey, ratioKey) {
    let total = 0
    let used = 0
    let measured = 0
    for (const node of usable) {
      const capacity = numeric(node[totalKey])
      const amount = numeric(node[usedKey])
      const ratio = numeric(node[ratioKey])
      if (!capacity || (amount === null && ratio === null)) continue
      total += capacity
      used += Math.min(capacity, amount ?? (capacity * ratio) / 100)
      measured += 1
    }
    return { total, used, percent: measured ? percent(used, total) : null }
  }
  const cpuNodes = usable.map((node) => ({ ...node, cpu_ratio: node.cpu_usage ?? node.cpu }))
  let cpuTotal = 0
  let cpuUsed = 0
  for (const node of cpuNodes) {
    const cores = numeric(node.cpu_total)
    const ratio = numeric(node.cpu_ratio)
    if (!cores || ratio === null) continue
    cpuTotal += cores
    cpuUsed += (cores * Math.min(100, ratio)) / 100
  }
  return {
    cpu: { used: cpuUsed, total: cpuTotal, percent: percent(cpuUsed, cpuTotal) },
    memory: sumPair('maxmem', 'mem', 'mem_usage'),
    storage: sumPair('maxdisk', 'disk', 'disk_usage'),
    online: usable.length,
    unavailable: nodes.length - usable.length,
    guests: nodes.reduce((sum, node) => sum + (numeric(node.vm_count) || 0), 0),
  }
}

export function vmStatus(vm) {
  if (vm?.template) return { label: '模板', tone: 'info' }
  return (
    {
      running: { label: '运行中', tone: 'success' },
      stopped: { label: '已停止', tone: 'default' },
      paused: { label: '已暂停', tone: 'warning' },
      suspended: { label: '已挂起', tone: 'warning' },
      starting: { label: '启动中', tone: 'info' },
      stopping: { label: '关机中', tone: 'warning' },
      deleting: { label: '删除中', tone: 'warning' },
    }[vm?.status] || { label: '未知', tone: 'default' }
  )
}

export function vmOs(vm) {
  const type = String(vm?.os_type || vm?.ostype || '').toLowerCase()
  const known = {
    l26: ['Linux', 'mdi:linux'],
    linux: ['Linux', 'mdi:linux'],
    ubuntu: ['Ubuntu', 'mdi:ubuntu'],
    debian: ['Debian', 'mdi:debian'],
    centos: ['CentOS', 'mdi:centos'],
    alpine: ['Alpine Linux', 'mdi:linux'],
    fedora: ['Fedora', 'mdi:fedora'],
    archlinux: ['Arch Linux', 'mdi:arch'],
    win11: ['Windows 11 / Server', 'mdi:microsoft-windows'],
    win10: ['Windows 10 / Server', 'mdi:microsoft-windows'],
    win8: ['Windows 8 / Server', 'mdi:microsoft-windows'],
    win7: ['Windows 7 / Server', 'mdi:microsoft-windows'],
    other: ['其他系统', 'mdi:monitor'],
  }
  const [label, icon] = known[type] || [type || '未知系统', 'mdi:monitor']
  return { label, icon }
}

export function createdTime(value) {
  if (!value) return '—'
  const date = new Date(typeof value === 'number' ? value * 1000 : value)
  if (!Number.isFinite(date.getTime())) return '—'
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export function vmIps(vm) {
  const values = vm?.ips || vm?.ip_addresses || []
  return [
    ...new Set(
      (Array.isArray(values) ? values : []).filter((value) => typeof value === 'string' && value)
    ),
  ]
}

export function uptimeText(value) {
  const seconds = numeric(value)
  if (seconds === null) return '—'
  const whole = Math.floor(seconds)
  const days = Math.floor(whole / 86400)
  const hours = Math.floor((whole % 86400) / 3600)
  const minutes = Math.floor((whole % 3600) / 60)
  if (days) return `${days}天 ${hours}小时 ${minutes}分钟`
  if (hours) return `${hours}小时 ${minutes}分钟`
  if (minutes) return `${minutes}分钟`
  return `${whole}秒`
}
