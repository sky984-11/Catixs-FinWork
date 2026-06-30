<template>
  <AppPage :show-footer="false">
    <div class="vm-edit-page">
      <div class="edit-header">
        <div>
          <span class="eyebrow">PVE VM CONFIG</span>
          <h2>编辑虚拟机 · {{ vmName }}</h2>
          <p>{{ remote }} / VMID {{ vmid }}</p>
        </div>
        <n-space>
          <n-button :loading="rebooting" secondary type="warning" @click="rebootVm">
            <template #icon>
              <TheIcon icon="mdi:restart" :size="16" />
            </template>
            重启虚拟机
          </n-button>
          <n-button @click="router.back()">返回</n-button>
          <n-button type="primary" :loading="saving" @click="saveConfig">保存配置</n-button>
        </n-space>
      </div>

      <n-alert type="info" :bordered="false" class="edit-alert">
        部分配置保存后需要重启虚拟机才会生效。
      </n-alert>

      <n-spin :show="loading">
        <section class="edit-grid">
          <n-card title="基础资源" :bordered="false">
            <n-form label-placement="left" label-width="110">
              <n-grid :cols="2" :x-gap="18">
                <n-form-item-gi label="CPU 核心">
                  <n-input-number v-model:value="form.cores" :min="1" :max="256" class="full-width" />
                </n-form-item-gi>
                <n-form-item-gi label="内存 GiB">
                  <n-input-number v-model:value="form.memory_gb" :min="1" :max="4096" class="full-width" />
                </n-form-item-gi>
                <n-form-item-gi label="磁盘设备">
                  <n-select v-model:value="form.disk_key" :options="diskOptions" placeholder="选择磁盘" />
                </n-form-item-gi>
                <n-form-item-gi label="磁盘 GiB">
                  <n-input-number v-model:value="form.disk_gb" :min="minDiskGb" :max="50000" class="full-width" />
                </n-form-item-gi>
              </n-grid>
            </n-form>
            <p class="hint">磁盘只支持扩容，不支持缩小。</p>
          </n-card>

          <n-card title="网卡配置" :bordered="false">
            <template #header-extra>
              <n-button size="small" type="primary" secondary @click="addNetwork">
                <template #icon>
                  <TheIcon icon="mdi:plus" :size="15" />
                </template>
                添加网卡
              </n-button>
            </template>

            <div v-if="!form.networks.length" class="empty-net">暂无网卡</div>
            <div v-for="(network, index) in form.networks" :key="network.uid" class="net-card">
              <div class="net-title">
                <strong>{{ network.key || `新增网卡 ${index + 1}` }}</strong>
                <n-button size="tiny" type="error" secondary @click="removeNetwork(index)">
                  <template #icon>
                    <TheIcon icon="material-symbols:delete-outline-rounded" :size="14" />
                  </template>
                  删除
                </n-button>
              </div>
              <n-grid :cols="4" :x-gap="12">
                <n-form-item-gi label="模型">
                  <n-select v-model:value="network.model" :options="modelOptions" />
                </n-form-item-gi>
                <n-form-item-gi label="网桥">
                  <n-select v-model:value="network.bridge" :options="bridgeOptions" filterable tag />
                </n-form-item-gi>
                <n-form-item-gi label="VLAN">
                  <n-input-number v-model:value="network.vlan" clearable :min="1" :max="4094" class="full-width" />
                </n-form-item-gi>
                <n-form-item-gi label="MTU">
                  <n-input-number v-model:value="network.mtu" clearable :min="576" :max="65520" class="full-width" />
                </n-form-item-gi>
                <n-form-item-gi label="限速 MB/s">
                  <n-input-number v-model:value="network.rate" clearable :min="0" :max="100000" class="full-width" />
                </n-form-item-gi>
                <n-form-item-gi label="防火墙">
                  <n-switch v-model:value="network.firewall" />
                </n-form-item-gi>
              </n-grid>
            </div>
          </n-card>
        </section>
      </n-spin>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const loading = ref(false)
const saving = ref(false)
const rebooting = ref(false)
const config = ref(null)
const deletedNetworks = ref([])

const remote = computed(() => String(route.query.remote || ''))
const vmid = computed(() => Number(route.query.vmid || 0))
const vmType = computed(() => String(route.query.type || 'pve-qemu'))
const vmName = computed(() => String(route.query.name || `VM ${vmid.value}`))

const form = reactive({
  cores: 1,
  memory_gb: 1,
  disk_key: '',
  disk_gb: 0,
  networks: [],
})

const modelOptions = [
  { label: 'VirtIO（半虚拟化）', value: 'virtio' },
  { label: 'Intel E1000', value: 'e1000' },
  { label: 'VMware vmxnet3', value: 'vmxnet3' },
  { label: 'Realtek RTL8139', value: 'rtl8139' },
]

const diskOptions = computed(() =>
  (config.value?.disks || []).map((disk) => ({
    label: `${disk.key} · ${disk.size_gb || 0} GiB`,
    value: disk.key,
  }))
)

const bridgeOptions = computed(() =>
  (config.value?.bridges || ['vmbr10', 'vmbr20']).map((bridge) => ({ label: bridge, value: bridge }))
)

const minDiskGb = computed(() => {
  const disk = (config.value?.disks || []).find((item) => item.key === form.disk_key)
  return Math.max(1, Number(disk?.size_gb || 1))
})

function normalizeNetwork(network) {
  return {
    uid: `${network.key || 'new'}-${Math.random().toString(36).slice(2)}`,
    key: network.key || '',
    model: network.model || 'virtio',
    macaddr: network.macaddr || '',
    bridge: network.bridge || bridgeOptions.value[0]?.value || 'vmbr10',
    vlan: network.vlan ?? null,
    mtu: network.mtu ?? null,
    rate: network.rate ?? null,
    firewall: Boolean(network.firewall),
  }
}

async function fetchConfig() {
  if (!remote.value || !vmid.value) {
    message.error('缺少虚拟机远程或 VMID 信息')
    return
  }
  loading.value = true
  try {
    const res = await api.virtualMachineApi.vmConfig({
      remote: remote.value,
      vmid: vmid.value,
      type: vmType.value,
    })
    config.value = res.data || {}
    form.cores = config.value.cores || 1
    form.memory_gb = config.value.memory_gb || 1
    form.disk_key = config.value.disk_key || config.value.disks?.[0]?.key || ''
    form.disk_gb = config.value.disk_gb || config.value.disks?.[0]?.size_gb || 0
    form.networks = (config.value.networks || []).map(normalizeNetwork)
    deletedNetworks.value = []
  } catch (error) {
    message.error(error.message || '读取虚拟机配置失败')
  } finally {
    loading.value = false
  }
}

function addNetwork() {
  form.networks.push(
    normalizeNetwork({
      bridge: bridgeOptions.value[0]?.value || 'vmbr10',
      model: 'virtio',
    })
  )
}

function removeNetwork(index) {
  const [network] = form.networks.splice(index, 1)
  if (network?.key) {
    deletedNetworks.value.push({ key: network.key, delete: true })
  }
}

function buildPayload() {
  return {
    remote: remote.value,
    vmid: vmid.value,
    type: vmType.value,
    node: route.query.node || undefined,
    cores: form.cores,
    memory_gb: form.memory_gb,
    disk_key: form.disk_key,
    disk_gb: form.disk_gb,
    networks: [
      ...form.networks.map((network) => ({
        key: network.key || undefined,
        model: network.model || 'virtio',
        macaddr: network.macaddr || undefined,
        bridge: network.bridge || 'vmbr10',
        vlan: network.vlan ?? undefined,
        mtu: network.mtu ?? undefined,
        rate: network.rate ?? undefined,
        firewall: Boolean(network.firewall),
      })),
      ...deletedNetworks.value,
    ],
  }
}

async function saveConfig() {
  if (form.disk_gb < minDiskGb.value) {
    message.warning('磁盘不支持缩小，只能扩容')
    return
  }
  if (form.networks.some((network) => !network.bridge)) {
    message.warning('请填写所有网卡的网桥')
    return
  }
  saving.value = true
  try {
    const res = await api.virtualMachineApi.updateVmConfig(buildPayload())
    message.success(res.msg || '虚拟机配置已更新，重启后生效')
    await fetchConfig()
  } catch (error) {
    message.error(error.message || '保存虚拟机配置失败')
  } finally {
    saving.value = false
  }
}

async function rebootVm() {
  rebooting.value = true
  try {
    const res = await api.virtualMachineApi.rebootVm({
      remote: remote.value,
      vmid: vmid.value,
      type: vmType.value,
      node: route.query.node || undefined,
    })
    message.success(res.msg || '重启请求已发送')
  } catch (error) {
    message.error(error.message || '重启虚拟机失败')
  } finally {
    rebooting.value = false
  }
}

onMounted(fetchConfig)
</script>

<style scoped>
.vm-edit-page {
  min-height: calc(100vh - 118px);
  padding: 16px;
  background: #f5f7fb;
}

.edit-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.edit-header h2 {
  margin: 4px 0;
  color: #0f172a;
  font-size: 22px;
  font-weight: 800;
}

.edit-header p,
.hint {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}

.eyebrow {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
}

.edit-alert {
  margin-bottom: 14px;
}

.edit-grid {
  display: grid;
  gap: 14px;
}

.full-width {
  width: 100%;
}

.net-card {
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.net-card + .net-card {
  margin-top: 12px;
}

.net-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.empty-net {
  padding: 24px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  color: #94a3b8;
  text-align: center;
}
</style>
