import assert from 'node:assert/strict'
import test from 'node:test'
import { waitForVmPower, mergeVmRuntime } from '../src/views/ops/virtual-machine/utils/power.mjs'

const row = { remote: 'a', vmid: 1 }
function setup(task = { finished: true, success: true }, status = 'stopped') {
  const calls = []
  let clock = 0
  return {
    calls,
    options: {
      row,
      upid: 'UPID:test',
      target: 'stopped',
      cancelled: () => false,
      now: () => clock,
      timeout: 4000,
      delay: async (ms) => {
        clock += ms
      },
      update: (vm) => calls.push(vm.status),
      api: {
        taskStatus: async () => ({ data: task }),
        pveVms: async (params) => {
          assert.deepEqual(params, { node: 'a', vmid: 1 })
          return { data: { items: [{ ...row, status }] } }
        },
      },
    },
  }
}
test('completed task and actual target status finish without fleet reads', async () => {
  const { options, calls } = setup()
  assert.equal(await waitForVmPower(options), true)
  assert.deepEqual(calls, ['stopped'])
})
test('failed task stops immediately and surfaces its reason', async () => {
  const { options, calls } = setup({ finished: true, success: false, failure_reason: 'denied' })
  await assert.rejects(waitForVmPower(options), /denied/)
  assert.deepEqual(calls, [])
})
test('a submitted task is not treated as completed and has a timeout', async () => {
  const { options } = setup({ finished: false }, 'running')
  assert.equal(await waitForVmPower(options), false)
})
test('leaving the target ignores in-flight responses', async () => {
  const { options, calls } = setup()
  let cancelled = false
  options.cancelled = () => cancelled
  options.api.pveVms = async () => {
    cancelled = true
    return { data: { items: [{ ...row, status: 'stopped' }] } }
  }
  assert.equal(await waitForVmPower(options), false)
  assert.deepEqual(calls, [])
})

test('runtime updates preserve manually loaded IPs and customer metadata', () => {
  const vm = { status: 'running', ips: ['192.0.2.1'], customer_name: 'customer' }
  assert.deepEqual(
    mergeVmRuntime(vm, { status: 'stopped', uptime: 0, ips: [], customer_name: '' }),
    {
      ...vm,
      status: 'stopped',
      uptime: 0,
    }
  )
})
