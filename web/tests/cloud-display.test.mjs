import assert from 'node:assert/strict'
import test from 'node:test'
import {
  aggregateCluster,
  uptimeText,
  createdTime,
  bytes,
  vmStatus,
  percent,
  vmOs,
} from '../src/views/ops/virtual-machine/utils/display.mjs'

test('cluster CPU is weighted by capacity; offline nodes do not inflate load', () => {
  const result = aggregateCluster([
    { cpu_total: 4, cpu_usage: 100, maxmem: 100, mem: 80, maxdisk: 1000, disk: 500, vm_count: 2 },
    { cpu_total: 12, cpu_usage: 0, maxmem: 300, mem: 120, maxdisk: 3000, disk: 500, vm_count: 3 },
    { cpu_total: 100, cpu_usage: 100, error: 'offline', vm_count: 1 },
  ])
  assert.equal(result.cpu.percent, 25)
  assert.equal(result.memory.percent, 50)
  assert.equal(result.storage.percent, 25)
  assert.equal(result.online, 2)
  assert.equal(result.unavailable, 1)
  assert.equal(result.guests, 6)
})

test('zero load differs from unknown and invalid capacity', () => {
  assert.equal(aggregateCluster([]).cpu.percent, null)
  assert.equal(aggregateCluster([{ cpu_total: 4, cpu_usage: 0 }]).cpu.percent, 0)
  assert.equal(percent(null, 100), null)
  assert.equal(percent(1, 0), null)
  assert.equal(bytes(undefined), '—')
  assert.equal(bytes(0), '0 B')
  assert.equal(bytes(1073741824), '1 GiB')
})

test('display does not invent an OS, a creation date, or a stopped state', () => {
  assert.equal(vmOs({}).label, '未知系统')
  assert.equal(vmOs({ os_type: 'win11' }).label, 'Windows 11 / Server')
  assert.equal(createdTime(null), '—')
  assert.equal(createdTime('invalid'), '—')
  assert.equal(vmStatus({ status: 'unreachable' }).label, '未知')
})

test('uptime formats PVE seconds without inventing missing data', () => {
  assert.equal(uptimeText(undefined), '—')
  assert.equal(uptimeText(-1), '—')
  assert.equal(uptimeText(0), '0秒')
  assert.equal(uptimeText(59), '59秒')
  assert.equal(uptimeText(60), '1分钟')
  assert.equal(uptimeText(3600), '1小时 0分钟')
  assert.equal(uptimeText(90061), '1天 1小时 1分钟')
})

test('selected node load remains independent of other nodes', () => {
  const first = { cpu_total: 4, cpu_usage: 80, maxmem: 100, mem: 20 }
  const second = { cpu_total: 16, cpu_usage: 10, maxmem: 200, mem: 100 }
  assert.equal(aggregateCluster([first]).cpu.percent, 80)
  assert.equal(aggregateCluster([second]).cpu.percent, 10)
  assert.equal(aggregateCluster([first]).memory.percent, 20)
  assert.equal(aggregateCluster([second]).memory.percent, 50)
})
