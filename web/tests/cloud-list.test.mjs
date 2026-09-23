import assert from 'node:assert/strict'
import test from 'node:test'
import { stableVmOrder } from '../src/views/ops/virtual-machine/utils/list.mjs'

const vm = (vmid, status = 'running', remote = 'a') => ({ vmid, status, remote, type: 'pve-qemu' })
test('first load uses numeric VMID order without mutating the response', () => {
  const incoming = [vm(100), vm(20), vm(3)]
  assert.deepEqual(
    stableVmOrder([], incoming).map((row) => row.vmid),
    [3, 20, 100]
  )
  assert.deepEqual(
    incoming.map((row) => row.vmid),
    [100, 20, 3]
  )
})
test('shuffled responses update values without moving existing rows', () => {
  const previous = [vm(3), vm(20), vm(100)]
  const incoming = [vm(100), vm('3', 'stopped'), vm(20)]
  const result = stableVmOrder(previous, incoming)
  assert.deepEqual(
    result.map((row) => Number(row.vmid)),
    [3, 20, 100]
  )
  assert.equal(result[0].status, 'stopped')
  assert.equal(result[0], incoming[1])
})
test('deleted rows disappear and new rows append without disturbing survivors', () => {
  const result = stableVmOrder([vm(20), vm(100)], [vm(4), vm(100), vm(2)])
  assert.deepEqual(
    result.map((row) => row.vmid),
    [100, 2, 4]
  )
})
test('switching remotes does not reuse another remote ordering', () => {
  const result = stableVmOrder([vm(100), vm(20)], [vm(100, 'running', 'b'), vm(20, 'running', 'b')])
  assert.deepEqual(
    result.map((row) => row.vmid),
    [20, 100]
  )
})
