<template>
  <AppPage :show-footer="false">
    <div class="cabinet-world-page" :class="{ 'is-map-home': viewMode === 'map' }">
      <section v-if="viewMode === 'map'" class="map-panel map-only">
        <div class="map-head">
          <div>
            <span class="eyebrow">Global Cabinet Map</span>
            <h2>机柜节点分布</h2>
          </div>
          <n-space>
            <n-tag round type="info">{{ regionNodes.length }} 个地区</n-tag>
            <n-tag round type="success">{{ cabinets.length }} 个机柜</n-tag>
            <n-tag round type="warning">{{ devices.length }} 台设备</n-tag>
            <n-button type="primary" round @click="openRegionModal">新增地区</n-button>
            <n-button secondary round :loading="loading" @click="loadData">刷新</n-button>
          </n-space>
        </div>

        <n-spin :show="loading" class="map-spin">
          <div ref="mapEl" class="world-map"></div>
        </n-spin>
      </section>

      <section v-else class="region-layout">
        <main class="cabinet-stage">
          <div class="stage-head">
            <div>
              <span class="eyebrow">{{ selectedRegion?.code || '-' }}</span>
              <h2>{{ selectedRegion?.name || '请选择地区' }}</h2>
              <div class="region-meta">
                <span>{{ selectedRegionNode?.locations.length || 0 }} 机房</span>
                <span>{{ selectedRegionNode?.cabinetCount || 0 }} 机柜</span>
                <span>{{ selectedRegionNode?.deviceCount || 0 }} 设备</span>
                <span>{{ rackUsedUnits }}/{{ rackCapacity }}U</span>
              </div>
            </div>
            <n-space align="center">
              <n-select
                v-model:value="selectedCabinetId"
                class="cabinet-select"
                :options="selectedCabinetOptions"
                placeholder="选择机柜"
                @update:value="loadCabinetDevices"
              />
              <n-button type="primary" round @click="openCabinetModal">新增机柜</n-button>
              <n-button secondary round @click="backToMap">返回地图</n-button>
            </n-space>
          </div>

          <div class="cabinet-content">
            <div class="cabinet-list">
              <div class="side-section-title">
                <span>Cabinets</span>
                <strong>{{ selectedCabinets.length }}</strong>
              </div>
              <button
                v-for="cabinet in selectedCabinets"
                :key="cabinet.id"
                class="cabinet-card"
                :class="{ active: selectedCabinetId === cabinet.id }"
                @click="selectCabinet(cabinet.id)"
              >
                <strong>{{ cabinet.name }}</strong>
                <span>{{ cabinetLocationName(cabinet) }}</span>
                <em>{{ cabinetDeviceCount(cabinet.id) }} 台设备 / {{ cabinet.capacity_u || 42 }}U</em>
              </button>
            </div>

            <n-spin :show="deviceLoading" class="rack-spin">
              <div v-if="selectedCabinet" class="rack-board">
                <div class="rack-title">
                  <div>
                    <span class="eyebrow">Rack Diagram</span>
                    <h3>{{ selectedCabinet.name }}</h3>
                  </div>
                  <n-space align="center">
                    <n-tag round :type="rackConflictCount ? 'error' : 'success'">
                      {{ rackConflictCount ? `${rackConflictCount} 个冲突U位` : 'U位正常' }}
                    </n-tag>
                    <n-button type="primary" round @click="openDeviceModal()">新增设备</n-button>
                  </n-space>
                </div>

                <div
                  class="rack-table-shell"
                  :style="{ '--rack-units': rackCapacity }"
                  @click="closeRackContextMenu"
                >
                  <table class="rack-table">
                    <thead>
                      <tr>
                        <th class="rack-u-head">U</th>
                        <th>{{ selectedCabinet.name }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in rackTableRows" :key="row.u">
                        <td class="rack-u-cell">{{ row.u }}</td>
                        <td
                          v-if="row.block"
                          class="rack-device-cell"
                          :class="[
                            `device-type-${Number(row.block.device.type)}`,
                            `device-status-${Number(row.block.device.status)}`,
                            { conflict: row.block.conflict },
                          ]"
                          :rowspan="row.block.height"
                          :title="row.block.device.remark || row.block.device.name"
                          @click.stop="openDeviceDetail(row.block.device)"
                          @contextmenu.prevent.stop="openRackContextMenu($event, row.u, row.block.device)"
                        >
                          <div class="rack-device-main">
                            <strong>{{ row.block.device.name || '-' }}</strong>
                            <span>{{ row.block.device.mgmt_ip || row.block.device.business_ip || formatDeviceUPosition(row.block.device) }}</span>
                          </div>
                          <i class="rack-status-dot"></i>
                        </td>
                        <td
                          v-else-if="!row.hidden"
                          class="rack-empty-cell"
                          @dblclick="openDeviceModal(null, row.u)"
                          @contextmenu.prevent.stop="openRackContextMenu($event, row.u)"
                        ></td>
                      </tr>
                    </tbody>
                  </table>

                  <div
                    v-if="rackContextMenu.show"
                    class="rack-context-menu"
                    :style="{ left: `${rackContextMenu.x}px`, top: `${rackContextMenu.y}px` }"
                    @click.stop
                  >
                    <button v-if="!rackContextMenu.device" @click="handleRackMenuAdd">新增设备</button>
                    <button v-if="rackContextMenu.device" @click="handleRackMenuEdit">编辑设备</button>
                    <button v-if="rackContextMenu.device" @click="handleRackMenuDelete">删除设备</button>
                  </div>
                </div>

                <n-empty
                  v-if="!rackBlocks.length"
                  class="rack-empty"
                  description="当前机柜暂无配置 U 位的设备"
                />
              </div>
              <n-empty v-else description="请选择一个机柜" />
            </n-spin>
          </div>
        </main>
      </section>

      <n-drawer v-model:show="deviceDrawer.show" width="560">
        <n-drawer-content :title="deviceDrawer.row?.name || '设备详情'" closable>
          <template v-if="deviceDrawer.row">
            <n-descriptions bordered :column="1" label-placement="left" size="small">
              <n-descriptions-item label="设备类型">{{ getDeviceType(deviceDrawer.row.type) }}</n-descriptions-item>
              <n-descriptions-item label="设备状态">{{ getDeviceStatus(deviceDrawer.row.status) }}</n-descriptions-item>
              <n-descriptions-item label="所在位置">
                {{ deviceDrawer.row.region_name || '-' }} / {{ deviceDrawer.row.location_name || '-' }} /
                {{ deviceDrawer.row.cabinet_name || selectedCabinet?.name || '-' }}
              </n-descriptions-item>
              <n-descriptions-item label="U位">{{ formatDeviceUPosition(deviceDrawer.row) }}</n-descriptions-item>
              <n-descriptions-item label="品牌型号">
                {{ [deviceDrawer.row.brand, deviceDrawer.row.model].filter(Boolean).join(' / ') || '-' }}
              </n-descriptions-item>
              <n-descriptions-item label="序列号">{{ deviceDrawer.row.serial_no || '-' }}</n-descriptions-item>
              <n-descriptions-item label="管理IP">{{ deviceDrawer.row.mgmt_ip || '-' }}</n-descriptions-item>
              <n-descriptions-item label="业务IP">{{ deviceDrawer.row.business_ip || '-' }}</n-descriptions-item>
              <n-descriptions-item label="负责人">{{ deviceDrawer.row.owner || '-' }}</n-descriptions-item>
              <n-descriptions-item label="备注">{{ deviceDrawer.row.remark || '-' }}</n-descriptions-item>
            </n-descriptions>

            <div class="detail-section">
              <h3>设备配置</h3>
              <n-empty v-if="!attributeRows.length" description="暂无配置" />
              <div v-else class="attribute-grid">
                <div v-for="item in attributeRows" :key="item.key" class="attribute-item">
                  <span>{{ item.key }}</span>
                  <strong>{{ item.value || '-' }}</strong>
                </div>
              </div>
            </div>

            <div v-if="fourNodeDetailNodes.length" class="detail-section">
              <h3>四合一节点</h3>
              <div class="node-detail-grid">
                <article v-for="node in fourNodeDetailNodes" :key="node.name" class="node-detail-card">
                  <strong>{{ node.device_name || node.name }}</strong>
                  <span>序号: {{ node.serial_no || '-' }}</span>
                  <span>CPU: {{ formatFourNodeCpu(node) }}</span>
                  <span>内存: {{ node.memory || '-' }}</span>
                  <span>磁盘: {{ node.disk || '-' }}</span>
                  <span>管理地址: {{ node.mgmt_ip || '-' }}</span>
                  <span>IPMI: {{ node.ipmi_user || '-' }}</span>
                  <span>备注: {{ node.remark || '-' }}</span>
                </article>
              </div>
            </div>
          </template>
        </n-drawer-content>
      </n-drawer>

      <n-modal v-model:show="regionModal.show" preset="dialog" title="新增地区">
        <n-form label-placement="top">
          <n-grid :cols="2" :x-gap="12">
            <n-form-item-gi label="地区名称" required>
              <n-input v-model:value="regionModal.form.name" placeholder="例如 Hong Kong" />
            </n-form-item-gi>
            <n-form-item-gi label="地区代码" required>
              <n-input v-model:value="regionModal.form.code" placeholder="例如 HK" />
            </n-form-item-gi>
          </n-grid>
          <n-form-item label="默认机房名称" required>
            <n-input v-model:value="regionModal.form.location_name" placeholder="例如 HK IDC" />
          </n-form-item>
          <n-form-item label="备注">
            <n-input v-model:value="regionModal.form.remark" type="textarea" placeholder="可填写地区说明" />
          </n-form-item>
        </n-form>
        <template #action>
          <n-button @click="regionModal.show = false">取消</n-button>
          <n-button type="primary" :loading="regionModal.submitting" @click="submitRegion">保存</n-button>
        </template>
      </n-modal>

      <n-modal v-model:show="cabinetModal.show" preset="dialog" title="新增机柜">
        <n-form label-placement="top">
          <n-form-item label="机房位置" required>
            <n-select
              v-model:value="cabinetModal.form.location_id"
              :options="selectedRegionLocationOptions"
              placeholder="选择机房"
            />
          </n-form-item>
          <n-grid :cols="2" :x-gap="12">
            <n-form-item-gi label="机柜名称" required>
              <n-input v-model:value="cabinetModal.form.name" placeholder="例如 A01" />
            </n-form-item-gi>
            <n-form-item-gi label="机柜代码">
              <n-input v-model:value="cabinetModal.form.code" placeholder="例如 A01" />
            </n-form-item-gi>
            <n-form-item-gi label="容量 U">
              <n-input-number v-model:value="cabinetModal.form.capacity_u" :min="1" :max="60" />
            </n-form-item-gi>
            <n-form-item-gi label="行/列">
              <n-input-group>
                <n-input v-model:value="cabinetModal.form.row" placeholder="行" />
                <n-input v-model:value="cabinetModal.form.column" placeholder="列" />
              </n-input-group>
            </n-form-item-gi>
          </n-grid>
          <n-form-item label="备注">
            <n-input v-model:value="cabinetModal.form.remark" type="textarea" />
          </n-form-item>
        </n-form>
        <template #action>
          <n-button @click="cabinetModal.show = false">取消</n-button>
          <n-button type="primary" :loading="cabinetModal.submitting" @click="submitCabinet">保存</n-button>
        </template>
      </n-modal>

      <n-modal v-model:show="deviceModal.show" preset="dialog" :title="deviceModalTitle" style="width: 760px">
        <n-form label-placement="top">
          <n-grid :cols="2" :x-gap="12">
            <n-form-item-gi label="设备名称" required>
              <n-input v-model:value="deviceModal.form.name" placeholder="例如 Server-01" />
            </n-form-item-gi>
            <n-form-item-gi label="设备类型">
              <n-select v-model:value="deviceModal.form.type" :options="deviceTypeOptions" />
            </n-form-item-gi>
            <n-form-item-gi label="设备形态">
              <n-select
                v-model:value="deviceModal.form.form_factor"
                :options="deviceFormFactorOptions"
                @update:value="handleDeviceFormFactorChange"
              />
            </n-form-item-gi>
            <n-form-item-gi label="占用 U 数">
              <n-input-number v-model:value="deviceModal.form.u_height" :min="1" :max="rackCapacity" />
            </n-form-item-gi>
            <n-form-item-gi label="起始 U 位">
              <n-input-number v-model:value="deviceModal.form.u_position" :min="1" :max="rackCapacity" />
            </n-form-item-gi>
            <n-form-item-gi label="状态">
              <n-select v-model:value="deviceModal.form.status" :options="deviceStatusOptions" />
            </n-form-item-gi>
            <n-form-item-gi label="品牌">
              <n-input v-model:value="deviceModal.form.brand" />
            </n-form-item-gi>
            <n-form-item-gi label="型号">
              <n-input v-model:value="deviceModal.form.model" />
            </n-form-item-gi>
            <n-form-item-gi label="序列号">
              <n-input v-model:value="deviceModal.form.serial_no" />
            </n-form-item-gi>
            <n-form-item-gi label="负责人">
              <n-input v-model:value="deviceModal.form.owner" />
            </n-form-item-gi>
            <n-form-item-gi label="管理 IP">
              <n-input v-model:value="deviceModal.form.mgmt_ip" />
            </n-form-item-gi>
            <n-form-item-gi label="业务 IP">
              <n-input v-model:value="deviceModal.form.business_ip" />
            </n-form-item-gi>
          </n-grid>
          <n-form-item label="备注">
            <n-input v-model:value="deviceModal.form.remark" type="textarea" />
          </n-form-item>

          <div v-if="deviceModal.form.form_factor === 'four_node'" class="four-node-editor">
            <div class="four-node-head">
              <div>
                <span class="eyebrow">Four Node Server</span>
                <h3>四合一节点配置</h3>
              </div>
              <n-tag round type="info">2U / N1-N4</n-tag>
            </div>
            <div class="four-node-grid">
              <article v-for="node in deviceModal.form.nodeList" :key="node.name" class="four-node-card">
                <strong>{{ node.name }}</strong>
                <div class="four-node-fields">
                  <n-input v-model:value="node.device_name" size="small" placeholder="设备名称" />
                  <n-input v-model:value="node.serial_no" size="small" placeholder="设备序号" />
                  <n-input-number v-model:value="node.cpu_count" size="small" placeholder="CPU数量" :min="0" />
                  <n-input v-model:value="node.cpu_model" size="small" placeholder="CPU型号" />
                  <n-input-number v-model:value="node.cpu_cores" size="small" placeholder="CPU核心数" :min="0" />
                  <n-input v-model:value="node.memory" size="small" placeholder="内存" />
                  <n-input v-model:value="node.disk" size="small" placeholder="磁盘" />
                  <n-input v-model:value="node.mgmt_ip" size="small" placeholder="管理地址" />
                  <n-input v-model:value="node.ipmi_user" size="small" placeholder="IPMI User" />
                  <n-input v-model:value="node.ipmi_password" size="small" placeholder="IPMI Password" type="password" show-password-on="click" />
                  <n-input v-model:value="node.remark" size="small" placeholder="备注" />
                </div>
              </article>
            </div>
          </div>
        </n-form>
        <template #action>
          <n-button @click="deviceModal.show = false">取消</n-button>
          <n-button type="primary" :loading="deviceModal.submitting" @click="submitDevice">保存</n-button>
        </template>
      </n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import api from '@/api'

defineOptions({ name: 'AssetCabinetWorldMap' })

const loading = ref(false)
const deviceLoading = ref(false)
const regions = ref([])
const locations = ref([])
const cabinets = ref([])
const devices = ref([])
const rackDevices = ref([])
const viewMode = ref('map')
const selectedRegionId = ref(null)
const selectedCabinetId = ref(null)
const mapEl = ref(null)
const deviceDrawer = reactive({ show: false, row: null })
const regionModal = reactive({
  show: false,
  submitting: false,
  form: createRegionForm(),
})
const cabinetModal = reactive({
  show: false,
  submitting: false,
  form: createCabinetForm(),
})
const deviceModal = reactive({
  show: false,
  submitting: false,
  form: createDeviceForm(),
})
const rackContextMenu = reactive({
  show: false,
  x: 0,
  y: 0,
  u: null,
  device: null,
})
let mapInstance = null
let mapTileLayer = null
let mapMarkerLayer = null

const deviceTypeOptions = [
  { label: '服务器', value: 0 },
  { label: '交换机', value: 1 },
  { label: '路由器', value: 2 },
  { label: '防火墙', value: 3 },
  { label: 'PDU', value: 4 },
  { label: '配件', value: 5 },
  { label: '其他', value: 99 },
]

const deviceStatusOptions = [
  { label: '空闲', value: 0 },
  { label: '故障', value: 3 },
  { label: '使用', value: 1 },
  { label: '下线', value: 4 },
]

const legacyDeviceStatusLabels = {
  2: '故障',
  5: '下线',
}

const deviceFormFactorOptions = [
  { label: '标准设备', value: 'standard' },
  { label: '四合一服务器', value: 'four_node' },
]

const knownRegionPoints = [
  { keys: ['HK', 'HONG KONG', '香港'], lat: 22.3193, lng: 114.1694 },
  { keys: ['SG', 'SINGAPORE', '新加坡'], lat: 1.3521, lng: 103.8198 },
  { keys: ['JP', 'JAPAN', '东京', '日本'], lat: 35.6762, lng: 139.6503 },
  { keys: ['TW', 'TAIWAN', '台湾'], lat: 25.033, lng: 121.5654 },
  { keys: ['SH', 'SHA', 'SHANGHAI', 'SHANG HAI', '上海'], lat: 31.2304, lng: 121.4737 },
  { keys: ['SZ', 'SHENZHEN', '深圳'], lat: 22.5431, lng: 114.0579 },
  { keys: ['DE', 'GERMANY', '德国', 'FRANKFURT'], lat: 50.1109, lng: 8.6821 },
  { keys: ['LON', 'LONDON', 'UK', 'GB', '英国', '伦敦'], lat: 51.5072, lng: -0.1276 },
  { keys: ['LA', 'LA3', 'LOS ANGELES', 'US', 'USA', '美国'], lat: 34.0522, lng: -118.2437 },
  { keys: ['NY', 'NY2', 'NEW YORK', 'NEWYORK', '纽约'], lat: 40.7128, lng: -74.006 },
]

const regionNodes = computed(() =>
  regions.value
    .map((region, index) => {
      const regionLocations = locations.value.filter((item) => item.region_id === region.id && item.type === 1)
      const regionCabinets = cabinets.value.filter((cabinet) =>
        regionLocations.some((location) => location.id === cabinet.location_id)
      )
      const regionDevices = devices.value.filter((device) => device.region_id === region.id)
      return {
        region,
        locations: regionLocations,
        cabinets: regionCabinets,
        cabinetCount: regionCabinets.length,
        deviceCount: regionDevices.length,
        point: regionPoint(region, index),
      }
    })
    .filter((node) => node.locations.length || node.cabinetCount || node.deviceCount)
)

const selectedRegion = computed(() => regions.value.find((item) => item.id === selectedRegionId.value) || null)
const selectedRegionNode = computed(
  () => regionNodes.value.find((node) => node.region.id === selectedRegionId.value) || null
)
const selectedCabinets = computed(() => selectedRegionNode.value?.cabinets || [])
const selectedCabinet = computed(() => cabinets.value.find((item) => item.id === selectedCabinetId.value) || null)
const selectedCabinetOptions = computed(() =>
  selectedCabinets.value.map((cabinet) => ({
    label: `${cabinet.name} / ${cabinetLocationName(cabinet)}`,
    value: cabinet.id,
  }))
)
const selectedRegionLocationOptions = computed(() =>
  (selectedRegionNode.value?.locations || []).map((location) => ({
    label: location.name,
    value: location.id,
  }))
)

const rackCapacity = computed(() => Math.max(Number(selectedCabinet.value?.capacity_u) || 42, 1))
const rackPlacedDevices = computed(() =>
  rackDevices.value
    .map((device) => {
      const start = Number(device.u_position || 0)
      const height = Math.max(Number(device.u_height || 1), 1)
      if (!start || start < 1 || start > rackCapacity.value) return null
      return {
        ...device,
        start,
        end: Math.min(start + height - 1, rackCapacity.value),
        height,
      }
    })
    .filter(Boolean)
)
const rackUnits = computed(() => {
  const units = []
  for (let no = rackCapacity.value; no >= 1; no -= 1) {
    const occupants = rackPlacedDevices.value.filter((item) => item.start <= no && item.end >= no)
    units.push({ no, occupied: Boolean(occupants.length), conflict: occupants.length > 1 })
  }
  return units
})
const rackConflictCount = computed(() => rackUnits.value.filter((unit) => unit.conflict).length)
const rackUsedUnits = computed(() => rackUnits.value.filter((unit) => unit.occupied).length)
const rackBlocks = computed(() =>
  rackPlacedDevices.value.map((device) => ({
    device,
    start: device.start,
    end: device.end,
    height: device.height,
    conflict: rackPlacedDevices.value.some(
      (other) => other.id !== device.id && other.start <= device.end && other.end >= device.start
    ),
  }))
)
const rackTableRows = computed(() => {
  const rows = []
  for (let u = rackCapacity.value; u >= 1; u -= 1) {
    const block = rackBlocks.value.find((item) => item.end === u)
    const covered = rackBlocks.value.some((item) => item.start <= u && item.end >= u)
    rows.push({
      u,
      block,
      hidden: covered && !block,
    })
  }
  return rows
})
const structuredAttributeKeys = new Set(['nodes', 'form_factor', 'node_count', '节点数量', '设备形态'])
const attributeRows = computed(() =>
  attributesToList(deviceDrawer.row?.attributes).filter((item) => !structuredAttributeKeys.has(item.key))
)
const deviceModalTitle = computed(() => (deviceModal.form.id ? '编辑设备' : '新增设备'))
const isFourNodeDrawerDevice = computed(() => isFourNodeAttributes(deviceDrawer.row?.attributes))
const fourNodeDetailNodes = computed(() =>
  isFourNodeDrawerDevice.value ? normalizeFourNodeList(deviceDrawer.row?.attributes?.nodes || []) : []
)

function isFourNodeAttributes(attributes) {
  return attributes?.form_factor === 'four_node' || attributes?.设备形态 === '四合一服务器'
}

function createRegionForm() {
  return {
    name: '',
    code: '',
    location_name: '',
    remark: '',
    status: true,
  }
}

function createCabinetForm() {
  return {
    location_id: null,
    name: '',
    code: '',
    row: '',
    column: '',
    capacity_u: 42,
    remark: '',
    status: true,
  }
}

function createDeviceForm() {
  return {
    cabinet_id: null,
    asset_no: '',
    name: '',
    type: 0,
    brand: '',
    model: '',
    serial_no: '',
    u_position: null,
    u_height: 1,
    status: 0,
    mgmt_ip: '',
    business_ip: '',
    owner: '',
    purchase_date: null,
    warranty_expire: null,
    attributes: {},
    remark: '',
    form_factor: 'standard',
    nodeList: createFourNodeList(),
  }
}

function createFourNodeList() {
  return ['N1', 'N2', 'N3', 'N4'].map((name, index) => ({
    name,
    device_name: '',
    serial_no: '',
    cpu_count: null,
    cpu_model: '',
    cpu_cores: null,
    memory: '',
    disk: '',
    mgmt_ip: '',
    ipmi_user: '',
    ipmi_password: '',
    remark: '',
    legacy_ip: '',
    legacy_cpu: '',
    sort: index + 1,
  }))
}

function normalizeFourNodeList(nodes) {
  const source = Array.isArray(nodes) ? nodes : []
  return createFourNodeList().map((fallback) => {
    const matched = source.find((item) => item?.name === fallback.name) || {}
    return {
      ...fallback,
      device_name: String(matched.device_name || matched.deviceName || matched.name || ''),
      serial_no: String(matched.serial_no || matched.serialNo || ''),
      cpu_count: matched.cpu_count ?? matched.cpuCount ?? null,
      cpu_model: String(matched.cpu_model || matched.cpuModel || matched.cpu || ''),
      cpu_cores: matched.cpu_cores ?? matched.cpuCores ?? null,
      memory: String(matched.memory || ''),
      disk: String(matched.disk || ''),
      mgmt_ip: String(matched.mgmt_ip || matched.mgmtIp || matched.ip || ''),
      ipmi_user: String(matched.ipmi_user || matched.ipmiUser || ''),
      ipmi_password: String(matched.ipmi_password || matched.ipmiPassword || ''),
      remark: String(matched.remark || ''),
      legacy_ip: String(matched.ip || ''),
      legacy_cpu: String(matched.cpu || ''),
      sort: Number(matched.sort || fallback.sort),
    }
  })
}

function formatFourNodeCpu(node) {
  return [node.cpu_count ? `${node.cpu_count}颗` : '', node.cpu_model, node.cpu_cores ? `${node.cpu_cores}核` : '']
    .filter(Boolean)
    .join(' / ') || '-'
}

function serializeFourNodeList(nodes) {
  return normalizeFourNodeList(nodes).map((node) => ({
    name: node.name,
    device_name: String(node.device_name || '').trim(),
    serial_no: String(node.serial_no || '').trim(),
    cpu_count: node.cpu_count === null || node.cpu_count === '' ? null : Number(node.cpu_count),
    cpu_model: String(node.cpu_model || '').trim(),
    cpu_cores: node.cpu_cores === null || node.cpu_cores === '' ? null : Number(node.cpu_cores),
    memory: String(node.memory || '').trim(),
    disk: String(node.disk || '').trim(),
    mgmt_ip: String(node.mgmt_ip || '').trim(),
    ipmi_user: String(node.ipmi_user || '').trim(),
    ipmi_password: String(node.ipmi_password || '').trim(),
    remark: String(node.remark || '').trim(),
  }))
}

function regionPoint(region, index) {
  const text = `${region.code || ''} ${region.name || ''} ${region.remark || ''}`.toUpperCase()
  const matched = knownRegionPoints.find((item) => item.keys.some((key) => text.includes(key.toUpperCase())))
  if (matched) return { lat: matched.lat, lng: matched.lng }
  return { lat: 38 - Math.floor(index / 8) * 12, lng: -145 + (index % 8) * 42 }
}

async function ensureMap() {
  if (viewMode.value !== 'map') return
  await nextTick()
  if (!mapEl.value) return
  if (!mapInstance) {
    mapInstance = L.map(mapEl.value, {
      attributionControl: true,
      maxBoundsViscosity: 0.8,
      minZoom: 2,
      worldCopyJump: true,
      zoomControl: true,
    }).setView([24, 18], 2)
    mapInstance.setMaxBounds([
      [-85, -180],
      [85, 180],
    ])
    mapTileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 8,
      minZoom: 2,
    }).addTo(mapInstance)
    mapMarkerLayer = L.layerGroup().addTo(mapInstance)
  }
  mapInstance.invalidateSize()
  renderMapMarkers()
}

function renderMapMarkers() {
  if (!mapInstance || !mapMarkerLayer) return
  mapMarkerLayer.clearLayers()
  const bounds = []
  regionNodes.value.forEach((node) => {
    const marker = L.marker([node.point.lat, node.point.lng], {
      icon: L.divIcon({
        className: 'cabinet-map-marker',
        html: mapMarkerHtml(node),
        iconAnchor: [22, 22],
        iconSize: [44, 44],
      }),
      title: node.region.name || node.region.code || '',
    })
    marker.on('click', () => selectRegion(node.region.id))
    marker.addTo(mapMarkerLayer)
    bounds.push([node.point.lat, node.point.lng])
  })
  if (bounds.length) {
    mapInstance.fitBounds(bounds, { maxZoom: 4, padding: [80, 80] })
  }
}

function mapMarkerHtml(node) {
  const label = node.region.code || node.region.name || ''
  const count = node.cabinetCount || 0
  return `
    <div class="cabinet-marker-wrap">
      <span class="cabinet-marker-count">${count}</span>
      <span class="cabinet-marker-label">${label}</span>
    </div>
  `
}

async function loadData() {
  loading.value = true
  try {
    const [regionRes, locationRes, cabinetRes, deviceRes] = await Promise.all([
      api.assetApi.regions({ page_size: 1000 }),
      api.assetApi.locations({ page_size: 1000 }),
      api.assetApi.cabinets({ page_size: 1000 }),
      api.assetApi.devices({ page: 1, page_size: 1000 }),
    ])
    regions.value = regionRes.data || []
    locations.value = locationRes.data || []
    cabinets.value = cabinetRes.data || []
    devices.value = deviceRes.data || []
    syncDefaultSelection()
  } finally {
    loading.value = false
  }
}

function syncDefaultSelection() {
  if (!selectedRegionId.value || !regionNodes.value.some((node) => node.region.id === selectedRegionId.value)) {
    selectedRegionId.value = regionNodes.value[0]?.region.id || null
  }
  const nextCabinet = selectedCabinets.value.some((cabinet) => cabinet.id === selectedCabinetId.value)
    ? selectedCabinetId.value
    : selectedCabinets.value[0]?.id || null
  selectedCabinetId.value = nextCabinet
  if (nextCabinet) loadCabinetDevices()
}

function selectRegion(regionId) {
  selectedRegionId.value = regionId
  selectedCabinetId.value = selectedCabinets.value[0]?.id || null
  rackDevices.value = []
  viewMode.value = 'region'
  if (selectedCabinetId.value) loadCabinetDevices()
}

function backToMap() {
  viewMode.value = 'map'
  deviceDrawer.show = false
  ensureMap()
}

function selectCabinet(cabinetId) {
  selectedCabinetId.value = cabinetId
  loadCabinetDevices()
}

async function loadCabinetDevices() {
  if (!selectedCabinetId.value) {
    rackDevices.value = []
    return
  }
  deviceLoading.value = true
  try {
    const res = await api.assetApi.devices({
      page: 1,
      page_size: 1000,
      cabinet_id: selectedCabinetId.value,
    })
    rackDevices.value = res.data || []
  } finally {
    deviceLoading.value = false
  }
}

function openRegionModal() {
  regionModal.form = createRegionForm()
  regionModal.show = true
}

async function submitRegion() {
  const name = String(regionModal.form.name || '').trim()
  const code = String(regionModal.form.code || '').trim()
  const locationName = String(regionModal.form.location_name || '').trim()
  if (!name || !code || !locationName) {
    window.$message?.warning('请填写地区名称、地区代码和默认机房名称')
    return
  }
  regionModal.submitting = true
  try {
    const regionRes = await api.assetApi.createRegion({
      name,
      code,
      remark: regionModal.form.remark || '',
      status: true,
    })
    const region = regionRes.data
    if (region?.id) {
      await api.assetApi.createLocation({
        region_id: region.id,
        name: locationName,
        type: 1,
        address: '',
        remark: '',
        status: true,
      })
      selectedRegionId.value = region.id
    }
    regionModal.show = false
    await loadData()
    if (region?.id) {
      selectedRegionId.value = region.id
      selectedCabinetId.value = null
      rackDevices.value = []
      viewMode.value = 'region'
    }
    window.$message?.success('地区已新增')
  } finally {
    regionModal.submitting = false
  }
}

function openCabinetModal() {
  cabinetModal.form = createCabinetForm()
  cabinetModal.form.location_id = selectedRegionLocationOptions.value[0]?.value || null
  cabinetModal.show = true
}

async function submitCabinet() {
  const name = String(cabinetModal.form.name || '').trim()
  if (!selectedRegionId.value) {
    window.$message?.warning('请先选择地区')
    return
  }
  if (!cabinetModal.form.location_id || !name) {
    window.$message?.warning('请选择机房并填写机柜名称')
    return
  }
  cabinetModal.submitting = true
  try {
    const payload = {
      ...cabinetModal.form,
      name,
      code: String(cabinetModal.form.code || name).trim(),
      capacity_u: Number(cabinetModal.form.capacity_u) || 42,
    }
    const res = await api.assetApi.createCabinet(payload)
    cabinetModal.show = false
    await loadData()
    selectedCabinetId.value = res.data?.id || selectedCabinetId.value
    if (selectedCabinetId.value) await loadCabinetDevices()
    window.$message?.success('机柜已新增')
  } finally {
    cabinetModal.submitting = false
  }
}

function openDeviceModal(device = null, uPosition = null) {
  if (!selectedCabinetId.value) {
    window.$message?.warning('请先选择机柜')
    return
  }
  const isFourNodeDevice = isFourNodeAttributes(device?.attributes)
  deviceModal.form = device
    ? {
        ...createDeviceForm(),
        ...device,
        form_factor: isFourNodeDevice ? 'four_node' : 'standard',
        nodeList: isFourNodeDevice ? normalizeFourNodeList(device.attributes?.nodes || []) : createFourNodeList(),
      }
    : createDeviceForm()
  deviceModal.form.cabinet_id = selectedCabinetId.value
  if (!device) {
    deviceModal.form.u_position = uPosition || firstAvailableU()
  }
  deviceModal.show = true
}

function handleDeviceFormFactorChange(value) {
  if (value === 'four_node') {
    deviceModal.form.type = 0
    deviceModal.form.u_height = Math.min(2, rackCapacity.value)
    deviceModal.form.nodeList = normalizeFourNodeList(deviceModal.form.nodeList)
  } else if (!deviceModal.form.u_height || deviceModal.form.u_height < 1) {
    deviceModal.form.u_height = 1
  }
}

function firstAvailableU() {
  for (let no = 1; no <= rackCapacity.value; no += 1) {
    const occupied = rackPlacedDevices.value.some((device) => device.start <= no && device.end >= no)
    if (!occupied) return no
  }
  return null
}

function hasRackOverlap(start, height, ignoredDeviceId = null) {
  const end = start + height - 1
  return rackPlacedDevices.value.some(
    (device) => device.id !== ignoredDeviceId && device.start <= end && device.end >= start
  )
}

async function submitDevice() {
  const name = String(deviceModal.form.name || '').trim()
  const start = Number(deviceModal.form.u_position || 0)
  const isFourNode = deviceModal.form.form_factor === 'four_node'
  const height = isFourNode ? 2 : Number(deviceModal.form.u_height || 1)
  if (!deviceModal.form.cabinet_id || !name) {
    window.$message?.warning('请选择机柜并填写设备名称')
    return
  }
  if (!start || start < 1 || height < 1 || start + height - 1 > rackCapacity.value) {
    window.$message?.warning('请填写有效的 U 位和占用 U 数')
    return
  }
  if (hasRackOverlap(start, height, deviceModal.form.id || null)) {
    window.$message?.warning('该 U 位已被占用，请调整起始 U 位或占用 U 数')
    return
  }

  deviceModal.submitting = true
  try {
    const attributes = {
      ...(deviceModal.form.attributes || {}),
      form_factor: isFourNode ? 'four_node' : 'standard',
      设备形态: isFourNode ? '四合一服务器' : '标准设备',
    }
    if (isFourNode) {
      attributes.node_count = '4'
      attributes.节点数量 = '4'
      attributes.nodes = serializeFourNodeList(deviceModal.form.nodeList)
    } else {
      delete attributes.node_count
      delete attributes.节点数量
      delete attributes.nodes
    }
    const payload = {
      ...deviceModal.form,
      asset_no: String(deviceModal.form.asset_no || name).trim(),
      name,
      u_position: start,
      u_height: height,
      attributes,
    }
    delete payload.form_factor
    delete payload.nodeList
    const submit = payload.id ? api.assetApi.updateDevice : api.assetApi.createDevice
    await submit(payload)
    deviceModal.show = false
    await loadData()
    selectedCabinetId.value = payload.cabinet_id
    await loadCabinetDevices()
    window.$message?.success('设备已新增')
  } finally {
    deviceModal.submitting = false
  }
}

function openRackContextMenu(event, u, device = null) {
  const shell = event.currentTarget?.closest?.('.rack-table-shell')
  const rect = shell?.getBoundingClientRect()
  rackContextMenu.show = true
  rackContextMenu.x = rect ? event.clientX - rect.left : event.offsetX
  rackContextMenu.y = rect ? event.clientY - rect.top : event.offsetY
  rackContextMenu.u = u
  rackContextMenu.device = device
}

function closeRackContextMenu() {
  rackContextMenu.show = false
}

function handleRackMenuAdd() {
  const u = rackContextMenu.u
  closeRackContextMenu()
  openDeviceModal(null, u)
}

function handleRackMenuEdit() {
  const device = rackContextMenu.device
  closeRackContextMenu()
  if (device) openDeviceModal(device)
}

async function handleRackMenuDelete() {
  const device = rackContextMenu.device
  closeRackContextMenu()
  if (!device?.id) return
  await api.assetApi.deleteDevice({ device_id: device.id })
  window.$message?.success('设备已删除')
  await loadData()
  await loadCabinetDevices()
}

function cabinetLocationName(cabinet) {
  return locations.value.find((location) => location.id === cabinet.location_id)?.name || '-'
}

function cabinetDeviceCount(cabinetId) {
  return devices.value.filter((device) => device.cabinet_id === cabinetId).length
}

function formatDeviceUPosition(row) {
  if (!row?.u_position) return '-'
  return row.u_height > 1 ? `${row.u_position}-${row.u_position + row.u_height - 1}U` : `${row.u_position}U`
}

function rackBlockStyle(block) {
  const capacity = rackCapacity.value
  return {
    gridRow: `${capacity - block.end + 1} / span ${Math.max(block.end - block.start + 1, 1)}`,
  }
}

function rackUnitGridRow(unit) {
  return String(rackCapacity.value - unit.no + 1)
}

function getDeviceType(value) {
  return deviceTypeOptions.find((item) => item.value === Number(value))?.label || '其他'
}

function getDeviceStatus(value) {
  const status = Number(value)
  return deviceStatusOptions.find((item) => item.value === status)?.label || legacyDeviceStatusLabels[status] || '未知'
}

function attributesToList(attributes) {
  if (!attributes || typeof attributes !== 'object') return []
  return Object.entries(attributes).map(([key, value]) => ({ key, value }))
}

function openDeviceDetail(device) {
  deviceDrawer.row = device
  deviceDrawer.show = true
}

watch(regionNodes, renderMapMarkers)
watch(viewMode, (mode) => {
  if (mode === 'map') ensureMap()
})

onMounted(async () => {
  await loadData()
  ensureMap()
})

onBeforeUnmount(() => {
  mapMarkerLayer?.clearLayers()
  mapTileLayer?.remove()
  mapInstance?.remove()
  mapMarkerLayer = null
  mapTileLayer = null
  mapInstance = null
})
</script>

<style scoped>
.cabinet-world-page {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  gap: 8px;
  overflow: hidden;
  background: #f5f7fb;
  padding: 8px;
}

.cabinet-world-page.is-map-home {
  height: 100%;
  min-height: 0;
  overflow: hidden;
  padding: 0;
}

.map-panel,
.region-list,
.cabinet-stage {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
}

.map-panel {
  padding: 16px;
}

.map-panel.map-only {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.map-spin {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.map-panel.map-only :deep(.n-spin-container),
.map-panel.map-only :deep(.n-spin-content) {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.map-head,
.stage-head,
.section-head,
.rack-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 12px;
}

.stage-head {
  min-height: 54px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 8px;
  background: #f8fafc;
  padding: 8px 10px;
}

.map-head h2,
.stage-head h2,
.section-head h3,
.rack-title h3 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 20px;
  line-height: 1.25;
}

.eyebrow {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.world-map {
  position: relative;
  overflow: hidden;
  min-height: 0;
  flex: 1;
  margin-top: 14px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 8px;
  background: #bcd7f2;
}

.world-map :deep(.leaflet-container) {
  width: 100%;
  height: 100%;
  min-height: inherit;
  background: #bcd7f2;
  font-family: inherit;
}

.world-map :deep(.leaflet-control-zoom a) {
  color: #111827;
  font-weight: 700;
}

.world-map :deep(.leaflet-control-attribution) {
  color: #475569;
  font-size: 11px;
}

.world-map :deep(.cabinet-map-marker) {
  border: 0;
  background: transparent;
}

.world-map :deep(.cabinet-marker-wrap) {
  position: relative;
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  cursor: pointer;
}

.world-map :deep(.cabinet-marker-count) {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 3px solid #e30613;
  border-radius: 999px;
  background: #fff;
  color: #111827;
  font-size: 14px;
  font-weight: 800;
  line-height: 1;
  box-shadow:
    0 0 0 3px rgba(255, 255, 255, 0.95),
    0 0 0 6px rgba(126, 58, 242, 0.55),
    0 8px 16px rgba(15, 23, 42, 0.26);
}

.world-map :deep(.cabinet-marker-label) {
  position: absolute;
  left: 38px;
  top: 50%;
  max-width: 140px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.32);
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.96);
  color: #111827;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  padding: 5px 9px;
  text-overflow: ellipsis;
  white-space: nowrap;
  box-shadow: 0 4px 10px rgba(15, 23, 42, 0.12);
  transform: translateY(-50%);
}

.world-map :deep(.leaflet-marker-icon:hover .cabinet-marker-count) {
  border-color: #b91c1c;
  box-shadow:
    0 0 0 3px rgba(255, 255, 255, 0.95),
    0 0 0 7px rgba(126, 58, 242, 0.7),
    0 10px 18px rgba(15, 23, 42, 0.3);
}

.region-layout {
  display: grid;
  min-height: 0;
  flex: 1;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}

.region-list,
.cabinet-stage {
  padding: 10px;
}

.cabinet-stage {
  display: flex;
  min-height: 0;
  flex-direction: column;
  padding: 8px;
}

.region-list {
  display: flex;
  min-height: 560px;
  flex-direction: column;
  gap: 10px;
}

.region-item,
.cabinet-card {
  display: flex;
  width: 100%;
  flex-direction: column;
  gap: 4px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  color: #0f172a;
  cursor: pointer;
  padding: 9px 10px;
  text-align: left;
}

.region-item:hover,
.region-item.active,
.cabinet-card:hover,
.cabinet-card.active {
  border-color: #fb5b2f;
  background: #fff7ed;
}

.region-item span,
.cabinet-card span,
.cabinet-card em {
  color: #64748b;
  font-size: 12px;
  font-style: normal;
}

.cabinet-select {
  width: clamp(280px, 28vw, 420px);
}

.region-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

.region-meta span {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 999px;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  line-height: 1;
  padding: 5px 9px;
}

.cabinet-content {
  display: grid;
  min-height: 0;
  flex: 1;
  grid-template-columns: minmax(620px, 1fr) clamp(260px, 22vw, 360px);
  gap: 8px;
  margin-top: 8px;
}

.cabinet-list {
  order: 2;
  display: flex;
  max-height: none;
  min-height: 0;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 8px;
  background: #f8fafc;
  padding: 8px;
}

.side-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  padding: 0 2px 9px;
  text-transform: uppercase;
}

.side-section-title strong {
  color: #0f172a;
  font-size: 14px;
}

.rack-spin {
  order: 1;
  display: flex;
  min-height: 0;
  flex-direction: column;
}

.rack-spin :deep(.n-spin-container),
.rack-spin :deep(.n-spin-content) {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.rack-board {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.rack-title {
  min-height: 38px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 8px;
  background: #f8fafc;
  padding: 7px 10px;
}

.rack-title h3 {
  font-size: 16px;
}

.rack-title :deep(.n-button) {
  height: 30px;
  padding-inline: 12px;
}

.rack-title :deep(.n-tag) {
  height: 26px;
}

.rack-table-shell {
  position: relative;
  width: 100%;
  max-height: none;
  min-height: 0;
  flex: 1;
  margin: 6px 0 0;
  overflow: auto;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 14px 28px rgba(15, 23, 42, 0.12);
}

.rack-table {
  width: 100%;
  min-width: 620px;
  border-collapse: collapse;
  table-layout: fixed;
}

.rack-table th {
  position: sticky;
  top: 0;
  z-index: 3;
  height: 30px;
  border: 1px solid #4b5563;
  background: #4b5563;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}

.rack-table th:not(.rack-u-head) {
  color: #f59e0b;
}

.rack-u-head,
.rack-u-cell {
  width: 54px;
}

.rack-u-cell,
.rack-empty-cell,
.rack-device-cell {
  height: clamp(14px, calc((100vh - 222px) / var(--rack-units, 42)), 25px);
  border: 1px solid #d1d5db;
}

.rack-u-cell {
  background: #f8fafc;
  color: #475569;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  text-align: center;
}

.rack-empty-cell {
  background:
    linear-gradient(90deg, rgba(148, 163, 184, 0.08), transparent 24%, transparent 76%, rgba(148, 163, 184, 0.08)),
    #fff;
  cursor: context-menu;
}

.rack-empty-cell:hover {
  background: #fef3c7;
}

.rack-device-cell {
  position: relative;
  overflow: hidden;
  background: #2563eb;
  color: #fff;
  cursor: pointer;
  padding: 2px 30px 2px 10px;
  text-align: center;
  vertical-align: middle;
}

.rack-device-cell:hover {
  filter: brightness(1.05);
}

.rack-device-cell.conflict {
  outline: 2px solid #dc2626;
  outline-offset: -2px;
}

.rack-device-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.rack-device-main strong,
.rack-device-main span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rack-device-main strong {
  font-size: 12px;
  line-height: 1.1;
}

.rack-device-main span {
  opacity: 0.9;
  font-size: 10px;
  line-height: 1.1;
}

.rack-status-dot {
  position: absolute;
  right: 12px;
  top: 50%;
  width: 10px;
  height: 10px;
  border: 2px solid rgba(255, 255, 255, 0.86);
  border-radius: 999px;
  background: #9ca3af;
  transform: translateY(-50%);
}

.rack-device-cell.device-type-1,
.rack-device-cell.device-type-2 {
  background: #059669;
}

.rack-device-cell.device-type-3 {
  background: #d97706;
}

.rack-device-cell.device-type-4,
.rack-device-cell.device-type-5 {
  background: #db2777;
}

.rack-device-cell.device-status-0 .rack-status-dot {
  background: #38bdf8;
}

.rack-device-cell.device-status-1 .rack-status-dot {
  background: #22c55e;
}

.rack-device-cell.device-status-2 .rack-status-dot,
.rack-device-cell.device-status-3 .rack-status-dot,
.rack-device-cell.device-status-5 .rack-status-dot {
  background: #ef4444;
}

.rack-device-cell.device-status-4 .rack-status-dot {
  background: #64748b;
}

.rack-context-menu {
  position: absolute;
  z-index: 20;
  min-width: 118px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.32);
  border-radius: 6px;
  background: #fff;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.18);
}

.rack-context-menu button {
  display: block;
  width: 100%;
  border: 0;
  background: transparent;
  color: #0f172a;
  cursor: pointer;
  padding: 9px 12px;
  text-align: left;
}

.rack-context-menu button:hover {
  background: #f1f5f9;
}

.rack-shell {
  max-width: 520px;
  margin: 16px auto 0;
  border: 1px solid #1f2937;
  border-radius: 8px;
  background:
    linear-gradient(90deg, rgba(15, 23, 42, 0.18), transparent 12%, transparent 88%, rgba(15, 23, 42, 0.2)),
    linear-gradient(180deg, #475569, #111827);
  box-shadow: 16px 18px 30px rgba(15, 23, 42, 0.18);
  padding: 18px;
}

.rack-cap {
  height: 18px;
  border-radius: 6px;
  background: linear-gradient(180deg, #64748b, #1f2937);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22);
}

.rack-cap.base {
  margin-top: 10px;
}

.rack-body {
  position: relative;
  min-height: 680px;
  margin-top: 10px;
  border: 1px solid rgba(15, 23, 42, 0.72);
  background: #020617;
  padding: 0 28px;
}

.rack-rail {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 18px;
  background:
    radial-gradient(circle at 50% 10px, rgba(255, 255, 255, 0.34) 0 2px, transparent 3px) 0 0 / 18px 30px,
    linear-gradient(180deg, #334155, #0f172a);
}

.rack-rail.left {
  left: 0;
}

.rack-rail.right {
  right: 0;
}

.rack-slots {
  position: relative;
  display: grid;
  height: 680px;
  grid-template-rows: repeat(var(--rack-units, 42), minmax(10px, 1fr));
  grid-template-columns: 64px minmax(0, 1fr);
  overflow: hidden;
  border-inline: 1px solid rgba(148, 163, 184, 0.28);
  background:
    linear-gradient(90deg, rgba(15, 23, 42, 0.42), transparent 16%, transparent 84%, rgba(15, 23, 42, 0.42)),
    #0f172a;
}

.rack-row {
  position: relative;
  grid-column: 1 / -1;
  min-height: 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
}

.rack-row span {
  position: absolute;
  left: 8px;
  top: 50%;
  z-index: 1;
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  transform: translateY(-50%);
}

.rack-row.occupied {
  background: rgba(59, 130, 246, 0.06);
}

.rack-row.conflict {
  background: rgba(239, 68, 68, 0.18);
}

.device-block {
  grid-column: 2;
  z-index: 2;
  display: flex;
  min-height: 0;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
  border: 1px solid rgba(96, 165, 250, 0.58);
  border-radius: 4px;
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.12), transparent 18%),
    linear-gradient(180deg, #2563eb, #1d4ed8);
  color: #eff6ff;
  cursor: pointer;
  align-self: stretch;
  box-sizing: border-box;
  margin: 2px 24px 2px 8px;
  padding: 1px 12px;
  text-align: left;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18), 0 8px 18px rgba(15, 23, 42, 0.32);
}

.device-block:hover {
  border-color: rgba(191, 219, 254, 0.86);
  filter: brightness(1.08);
}

.device-block strong,
.device-block span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-block strong {
  font-size: 12px;
  line-height: 1;
}

.device-block span {
  margin-top: 3px;
  opacity: 0.82;
  font-size: 10px;
  line-height: 1;
}

.device-block.compact {
  padding-block: 0;
}

.device-block.device-type-1,
.device-block.device-type-2 {
  border-color: rgba(52, 211, 153, 0.72);
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.14), transparent 18%),
    linear-gradient(180deg, #059669, #047857);
}

.device-block.device-type-3 {
  border-color: rgba(251, 191, 36, 0.78);
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.14), transparent 18%),
    linear-gradient(180deg, #d97706, #92400e);
}

.device-block.device-type-4,
.device-block.device-type-5 {
  border-color: rgba(244, 114, 182, 0.74);
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.14), transparent 18%),
    linear-gradient(180deg, #db2777, #be185d);
}

.device-block.conflict,
.device-block.device-status-2,
.device-block.device-status-3,
.device-block.device-status-5 {
  border-color: rgba(252, 165, 165, 0.82);
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.14), transparent 18%),
    linear-gradient(180deg, #dc2626, #991b1b);
}

.rack-empty {
  margin-top: 14px;
}

.detail-section {
  margin-top: 16px;
}

.detail-section h3 {
  margin: 0 0 10px;
  color: #0f172a;
  font-size: 15px;
}

.node-detail-grid,
.four-node-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.node-detail-card,
.four-node-card {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 7px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 10px;
}

.node-detail-card strong,
.four-node-card strong {
  color: #0f172a;
  font-size: 13px;
}

.four-node-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
}

.four-node-fields :deep(.n-input-number) {
  width: 100%;
}

.node-detail-card span {
  overflow: hidden;
  color: #475569;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.four-node-editor {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background: #f8fafc;
  padding: 12px;
}

.four-node-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.four-node-head h3 {
  margin: 2px 0 0;
  color: #0f172a;
  font-size: 15px;
}

.attribute-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.attribute-item {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 10px;
  border: 1px solid #eef2f7;
  border-radius: 6px;
  padding: 8px 10px;
}

.attribute-item span {
  color: #64748b;
}

.attribute-item strong {
  min-width: 0;
  overflow: hidden;
  color: #0f172a;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 1180px) {
  .region-layout,
  .cabinet-content {
    grid-template-columns: 1fr;
  }

  .region-list {
    min-height: auto;
  }

  .cabinet-list {
    display: flex;
    max-height: 88px;
    flex-direction: row;
    overflow-x: auto;
    overflow-y: hidden;
    padding-bottom: 2px;
  }

  .cabinet-card {
    min-width: 190px;
  }
}

@media (max-width: 720px) {
  .map-head,
  .stage-head,
  .rack-title {
    align-items: flex-start;
    flex-direction: column;
  }

  .cabinet-list {
    grid-template-columns: 1fr;
  }

  .world-map {
    min-height: 0;
  }
}
</style>
