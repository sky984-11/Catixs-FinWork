<template>
  <CommonPage show-footer :show-header="false">
    <div class="pricing-page">
      <section class="pricing-hero">
        <div>
          <span>Vendor Price Compare</span>
          <h2>Zenlayer 与 Equinix Fabric 统一比价</h2>
          <p>按产品、端点、位置、带宽和计费方式组织参数，查询后在同一屏比较供应商原价、报价成本和建议售价。</p>
        </div>
        <div class="hero-metrics">
          <article>
            <span>Zenlayer</span>
            <strong>{{ money(zenlayerQuote.totalCost, zenlayerQuote.currency) }}</strong>
          </article>
          <article>
            <span>Equinix</span>
            <strong>{{ money(equinixQuote.totalCost, equinixQuote.currency) }}</strong>
          </article>
          <article>
            <span>差额</span>
            <strong>{{ priceDiffText }}</strong>
          </article>
        </div>
      </section>

      <section class="compare-grid">
        <aside class="pricing-panel query-panel">
          <div class="panel-title">
            <span>统一参数</span>
            <strong>查询条件</strong>
          </div>

          <n-form label-placement="top" :show-feedback="false">
            <n-form-item label="产品场景">
              <n-select v-model:value="scenario" :options="scenarioOptions" @update:value="syncScenario" />
            </n-form-item>

            <div v-if="isEndpointScenario" class="form-grid">
              <n-form-item label="A 端位置">
                <n-cascader
                  v-model:value="shared.zenlayerA"
                  :options="zenlayerDatacenterOptions"
                  filterable
                  clearable
                  check-strategy="child"
                  placeholder="Zenlayer A 端"
                />
              </n-form-item>
              <n-form-item label="Z 端位置">
                <n-cascader
                  v-model:value="shared.zenlayerZ"
                  :options="zenlayerDatacenterOptions"
                  filterable
                  clearable
                  check-strategy="child"
                  placeholder="Zenlayer Z 端"
                />
              </n-form-item>
            </div>

            <div v-else-if="scenario === 'port'" class="form-grid">
              <n-form-item label="Zenlayer 机房位置">
                <n-cascader
                  v-model:value="shared.zenlayerA"
                  :options="zenlayerDatacenterOptions"
                  filterable
                  clearable
                  check-strategy="child"
                  placeholder="选择机房端口位置"
                />
              </n-form-item>
              <n-form-item label="Equinix 城市">
                <n-select
                  v-model:value="shared.eqA"
                  :options="equinixMetroOptions"
                  filterable
                  placeholder="选择 Fabric Port 城市"
                />
              </n-form-item>
            </div>

            <div v-else class="form-grid form-grid--single">
              <n-form-item label="Equinix 城市">
                <n-select
                  v-model:value="shared.eqA"
                  :options="equinixMetroOptions"
                  filterable
                  placeholder="选择 IP Block 城市"
                />
              </n-form-item>
            </div>

            <div class="form-grid">
              <n-form-item label="带宽">
                <n-select v-model:value="shared.bandwidth" :options="sharedBandwidthOptions" />
              </n-form-item>
              <n-form-item label="端口规格">
                <n-select v-model:value="shared.portType" :options="zenlayerPortOptions" />
              </n-form-item>
            </div>
          </n-form>

          <div class="hint-box">
            <strong>字段对齐</strong>
            <p>{{ sharedHintText }}</p>
          </div>
        </aside>

        <section class="pricing-panel vendor-panel">
          <div class="vendor-head">
            <div>
              <span>Zenlayer SDN</span>
              <strong>{{ zenlayerServiceLabel }}</strong>
            </div>
            <n-tag :type="zenlayerSource === 'zenlayer_api' ? 'success' : 'warning'" round>
              {{ zenlayerSource === 'zenlayer_api' ? 'API' : 'Fallback' }}
            </n-tag>
          </div>

          <n-form label-placement="top" :show-feedback="false">
            <n-form-item label="服务类型">
              <n-select v-model:value="zenlayerForm.service" :options="zenlayerServiceOptions" @update:value="resetZenlayerResult" />
            </n-form-item>

            <template v-if="zenlayerForm.service === 'datacenter_port'">
              <n-form-item label="机房">
                <n-cascader
                  v-model:value="zenlayerForm.dcId"
                  :options="zenlayerDatacenterOptions"
                  filterable
                  clearable
                  check-strategy="child"
                  placeholder="选择机房"
                />
              </n-form-item>
            </template>

            <template v-else>
              <div class="form-grid">
                <n-form-item label="A 端机房">
                  <n-cascader
                    v-model:value="zenlayerForm.endpointA"
                    :options="zenlayerDatacenterOptions"
                    filterable
                    clearable
                    check-strategy="child"
                  />
                </n-form-item>
                <n-form-item label="Z 端机房">
                  <n-cascader
                    v-model:value="zenlayerForm.endpointZ"
                    :options="zenlayerDatacenterOptions"
                    filterable
                    clearable
                    check-strategy="child"
                  />
                </n-form-item>
              </div>
              <div class="form-grid">
                <n-form-item label="计费方式">
                  <n-select v-model:value="zenlayerForm.internetType" :options="zenlayerInternetOptions" />
                </n-form-item>
                <n-form-item label="服务等级">
                  <n-select v-model:value="zenlayerForm.serviceLevel" :options="zenlayerServiceLevelOptions" />
                </n-form-item>
              </div>
            </template>

            <div class="form-grid">
              <n-form-item label="端口规格">
                <n-select v-model:value="zenlayerForm.portType" :options="zenlayerPortOptions" />
              </n-form-item>
              <n-form-item label="带宽">
                <n-select v-model:value="zenlayerForm.bandwidthMbps" :options="zenlayerBandwidthOptions" />
              </n-form-item>
            </div>

            <n-form-item>
              <template #label>
                <span class="field-help-label">
                  Cross Connect
                  <n-tooltip trigger="hover">
                    <template #trigger>
                      <span class="help-mark">?</span>
                    </template>
                    需要 Zenlayer 协助建设机房内交叉连接时开启，会把 Cross Connect 的月费或一次性建设费纳入报价；已有交叉连接或单独结算时可关闭。
                  </n-tooltip>
                </span>
              </template>
              <n-switch v-model:value="zenlayerForm.buildCrossConnectWithAssisted">
                <template #checked>需要协助</template>
                <template #unchecked>不需要</template>
              </n-switch>
            </n-form-item>
          </n-form>

          <div class="panel-actions">
            <n-button type="primary" :loading="zenlayerLoading" @click="generateZenlayerQuote">查询 Zenlayer</n-button>
            <n-button secondary :disabled="!zenlayerQuote.costItems.length" @click="copyZenlayerQuote">复制报价</n-button>
          </div>

          <n-alert v-if="zenlayerError" type="error" :bordered="false" closable @close="zenlayerError = ''">
            {{ zenlayerError }}
          </n-alert>
        </section>

        <section class="pricing-panel vendor-panel">
          <div class="vendor-head">
            <div>
              <span>Equinix Fabric</span>
              <strong>{{ equinixProductLabel }}</strong>
            </div>
            <n-tag type="info" round>{{ equinixReferenceSource }}</n-tag>
          </div>

          <n-form label-placement="top" :show-feedback="false">
            <n-form-item label="产品类型">
              <n-select v-model:value="equinixForm.type" :options="equinixProductOptions" @update:value="resetEquinixResult" />
            </n-form-item>

            <template v-if="equinixForm.type === 'VIRTUAL_CONNECTION_PRODUCT'">
              <n-form-item label="连接类型">
                <n-select v-model:value="equinixForm.connectionType" :options="equinixConnectionOptions" />
              </n-form-item>
              <div class="form-grid">
                <n-form-item label="A 端类型">
                  <n-select v-model:value="equinixForm.aSideType" :options="equinixASideOptions" />
                </n-form-item>
                <n-form-item label="Z 端类型">
                  <n-select v-model:value="equinixForm.zSideType" :options="equinixZSideOptions" />
                </n-form-item>
              </div>
              <div class="form-grid">
                <n-form-item label="A 端城市">
                  <n-select v-model:value="equinixForm.originMetro" :options="equinixMetroOptions" filterable />
                </n-form-item>
                <n-form-item label="Z 端城市">
                  <n-select v-model:value="equinixForm.destinationMetro" :options="equinixMetroOptions" filterable />
                </n-form-item>
              </div>
            </template>

            <template v-else-if="equinixForm.type === 'VIRTUAL_PORT_PRODUCT'">
              <div class="form-grid">
                <n-form-item label="城市">
                  <n-select v-model:value="equinixForm.originMetro" :options="equinixMetroOptions" filterable />
                </n-form-item>
                <n-form-item label="IBX">
                  <n-select v-model:value="equinixForm.ibxSuffix" :options="equinixIbxOptions" />
                </n-form-item>
              </div>
              <div class="form-grid">
                <n-form-item label="端口类型">
                  <n-select v-model:value="equinixForm.portType" :options="equinixPortTypeOptions" />
                </n-form-item>
                <n-form-item label="端口套餐">
                  <n-select v-model:value="equinixForm.portPackage" :options="equinixPortPackageOptions" />
                </n-form-item>
              </div>
              <div class="form-grid">
                <n-form-item label="服务类型">
                  <n-select v-model:value="equinixForm.portServiceType" :options="equinixPortServiceOptions" />
                </n-form-item>
                <n-form-item label="连接来源">
                  <n-select v-model:value="equinixForm.portConnectivitySource" :options="equinixConnectivityOptions" />
                </n-form-item>
              </div>
              <n-form-item label="LAG">
                <n-switch v-model:value="equinixForm.portLagEnabled" />
              </n-form-item>
            </template>

            <template v-else>
              <div class="form-grid">
                <n-form-item label="城市">
                  <n-select v-model:value="equinixForm.originMetro" :options="equinixMetroOptions" filterable />
                </n-form-item>
                <n-form-item label="IP 类型">
                  <n-select v-model:value="equinixForm.ipBlockType" :options="equinixIpTypeOptions" />
                </n-form-item>
              </div>
              <n-form-item label="前缀长度">
                <n-select v-model:value="equinixForm.ipBlockPrefixLength" :options="equinixPrefixOptions" />
              </n-form-item>
            </template>

            <n-form-item v-if="['VIRTUAL_CONNECTION_PRODUCT', 'VIRTUAL_PORT_PRODUCT'].includes(equinixForm.type)" label="带宽">
              <n-select v-model:value="equinixForm.bandwidth" :options="equinixBandwidthOptions" />
            </n-form-item>
          </n-form>

          <div class="panel-actions">
            <n-button type="primary" :loading="equinixLoading" @click="generateEquinixQuote">查询 Equinix</n-button>
            <n-button secondary :disabled="!equinixQuote.costItems.length" @click="copyEquinixQuote">复制报价</n-button>
          </div>

          <n-alert v-if="equinixError" type="error" :bordered="false" closable @close="equinixError = ''">
            {{ equinixError }}
          </n-alert>
        </section>
      </section>

      <section class="result-grid">
        <ResultPanel title="Zenlayer 报价结果" :items="zenlayerQuote.costItems" :total="zenlayerQuote.totalCost" :currency="zenlayerQuote.currency" />
        <ResultPanel title="Equinix 报价结果" :items="equinixQuote.costItems" :total="equinixQuote.totalCost" :currency="equinixQuote.currency" />
      </section>

    </div>
  </CommonPage>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, reactive, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NCascader,
  NForm,
  NFormItem,
  NSelect,
  NSwitch,
  NTag,
  NTooltip,
  useMessage,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: 'ResourceZenlayerPricing' })

const message = useMessage()
const loadingOptions = ref(false)
const zenlayerLoading = ref(false)
const equinixLoading = ref(false)
const zenlayerSource = ref('fallback')
const equinixReferenceSource = ref('fallback')
const zenlayerError = ref('')
const equinixError = ref('')
const scenario = ref('private_connect')

const scenarioOptions = [
  { label: '二层专线 / Virtual Connection', value: 'private_connect' },
  { label: '端口 / Fabric Port', value: 'port' },
  { label: '带宽升级 / Bandwidth Upgrade', value: 'bandwidth_upgrade' },
  { label: '仅查询 Equinix IP Block', value: 'eq_only' },
]

const shared = reactive({
  zenlayerA: '',
  zenlayerZ: '',
  eqA: 'SV',
  eqZ: 'HK',
  bandwidth: 1000,
  portType: '10G',
})

const zenlayerServices = ref([])
const zenlayerDatacenters = ref([])
const zenlayerPortTypes = ref(['1G', '10G', '40G'])
const zenlayerBandwidths = ref([10, 50, 100, 200, 500, 1000, 2000, 5000, 10000])
const zenlayerInternetTypes = ref([
  { label: '固定带宽', value: 'ByBandwidth' },
  { label: '95 计费', value: 'ByInstanceBandwidth95' },
])

const equinixReference = ref({
  productTypes: [
    { code: 'VIRTUAL_CONNECTION_PRODUCT', name: 'Virtual Connection' },
    { code: 'VIRTUAL_PORT_PRODUCT', name: 'Virtual Port' },
    { code: 'IP_BLOCK_PRODUCT', name: 'IP Block' },
  ],
  connectionTypes: [
    { code: 'EVPL_VC', name: 'EVPL Virtual Connection' },
    { code: 'EPL_VC', name: 'EPL Virtual Connection' },
    { code: 'EC_VC', name: 'EC Virtual Connection' },
    { code: 'IP_VC', name: 'IP Virtual Connection' },
    { code: 'EIA_VC', name: 'Equinix Internet Access VC' },
  ],
  sideTypes: [
    { code: 'COLO', name: 'Colocation' },
    { code: 'VD', name: 'Virtual Device' },
    { code: 'SP', name: 'Service Provider' },
    { code: 'CLOUD_ROUTER', name: 'Cloud Router' },
    { code: 'NETWORK', name: 'Network' },
  ],
  bandwidths: [50, 100, 200, 500, 1000, 2000, 5000, 10000],
  portOptions: {
    types: [{ code: 'XF_PORT', name: 'Fabric Port (XF_PORT)' }],
    packages: [{ code: 'STANDARD', name: 'Standard' }],
    serviceTypes: [{ code: 'EPL', name: 'EPL' }, { code: 'EVPL', name: 'EVPL' }],
    connectivitySources: [{ code: 'COLO', name: 'Colocation' }, { code: 'NETWORK_EDGE', name: 'Network Edge' }],
    lagOptions: [{ code: false, name: 'No' }, { code: true, name: 'Yes' }],
  },
  ipBlockOptions: {
    types: [{ code: 'IPv4', name: 'IPv4' }],
    prefixLengths: [{ code: 29, name: '/29' }],
  },
})
const equinixMetros = ref([
  { code: 'SV', name: 'Silicon Valley' },
  { code: 'HK', name: 'Hong Kong' },
  { code: 'SG', name: 'Singapore' },
  { code: 'TY', name: 'Tokyo' },
])

const zenlayerForm = reactive({
  service: 'private_connect',
  dcId: '',
  endpointA: '',
  endpointZ: '',
  portType: '10G',
  bandwidthMbps: 1000,
  internetType: 'ByBandwidth',
  serviceLevel: 'SINGLE_UNPROTECTED',
  buildCrossConnectWithAssisted: false,
})

const equinixForm = reactive({
  type: 'VIRTUAL_CONNECTION_PRODUCT',
  connectionType: 'EVPL_VC',
  bandwidth: 1000,
  aSideType: 'COLO',
  zSideType: 'COLO',
  originMetro: 'SV',
  destinationMetro: 'HK',
  ibxSuffix: '1',
  portType: 'XF_PORT',
  portPackage: 'STANDARD',
  portServiceType: 'EPL',
  portConnectivitySource: 'COLO',
  portLagEnabled: false,
  ipBlockType: 'IPv4',
  ipBlockPrefixLength: 29,
})

const zenlayerQuote = reactive(emptyQuote())
const equinixQuote = reactive(emptyQuote())

const costNameMap = {
  datacenter_port: '机房端口',
  cross_connect_monthly: 'Cross Connect 月费',
  cross_connect_setup: 'Cross Connect 一次性建设费',
  private_connect_bandwidth: '专线带宽',
  endpoint_a_access: 'A 端接入',
  endpoint_a_cross_connect_monthly: 'A 端 Cross Connect 月费',
  endpoint_a_cross_connect_setup: 'A 端 Cross Connect 一次性建设费',
  endpoint_z_access: 'Z 端接入',
  endpoint_z_cross_connect_monthly: 'Z 端 Cross Connect 月费',
  endpoint_z_cross_connect_setup: 'Z 端 Cross Connect 一次性建设费',
}

function emptyQuote() {
  return {
    costItems: [],
    totalCost: 0,
    currency: 'USD',
    stock: '',
    action: '',
    payload: {},
    raw: null,
  }
}

function resetQuote(target) {
  target.costItems = []
  target.totalCost = 0
  target.currency = 'USD'
  target.stock = ''
  target.action = ''
  target.payload = {}
  target.raw = null
}

function optionFromCode(items = []) {
  return items.map((item) => ({
    label: item.name ? `${item.name} (${item.code})` : String(item.code),
    value: item.code,
  }))
}

function filteredSideOptions(allowedCodes) {
  if (!Array.isArray(allowedCodes) || !allowedCodes.length) return equinixSideOptions.value
  const allowed = new Set(allowedCodes)
  return equinixSideOptions.value.filter((item) => allowed.has(item.value))
}

const zenlayerServiceOptions = computed(() => {
  const options = zenlayerServices.value.length
    ? zenlayerServices.value.filter((item) => !item.disabled && item.value !== 'datacenter_lookup')
    : [
        { label: '机房端口', value: 'datacenter_port' },
        { label: '二层专线', value: 'private_connect' },
        { label: '已有专线带宽升级', value: 'private_connect_bandwidth' },
      ]
  return options.map((item) => ({ label: item.label, value: item.value }))
})
const zenlayerServiceLabel = computed(() => zenlayerServiceOptions.value.find((item) => item.value === zenlayerForm.service)?.label || 'Zenlayer SDN')
const zenlayerDatacenterOptions = computed(() => {
  const areaMap = new Map()
  zenlayerDatacenters.value.forEach((item) => {
    const area = item.areaName || 'Other'
    const city = item.cityName || 'Unknown'
    if (!areaMap.has(area)) areaMap.set(area, { label: area, value: `area:${area}`, children: new Map() })
    const areaNode = areaMap.get(area)
    if (!areaNode.children.has(city)) areaNode.children.set(city, { label: city, value: `city:${area}:${city}`, children: [] })
    areaNode.children.get(city).children.push({ label: item.dcName || item.label || item.dcId, value: item.dcId })
  })
  return Array.from(areaMap.values()).map((area) => ({
    label: area.label,
    value: area.value,
    children: Array.from(area.children.values()).map((city) => ({
      ...city,
      children: city.children.sort((a, b) => a.label.localeCompare(b.label)),
    })),
  }))
})
const zenlayerPortOptions = computed(() => zenlayerPortTypes.value.map((item) => ({ label: item, value: item })))
const zenlayerBandwidthOptions = computed(() => zenlayerBandwidths.value.map((item) => ({ label: `${item} Mbps`, value: item })))
const zenlayerInternetOptions = computed(() => zenlayerInternetTypes.value)
const zenlayerServiceLevelOptions = [
  { label: 'Single Unprotected', value: 'SINGLE_UNPROTECTED' },
  { label: 'Single Protected', value: 'SINGLE_PROTECTED' },
]

const equinixProductOptions = computed(() => optionFromCode(equinixReference.value.productTypes))
const equinixConnectionOptions = computed(() => optionFromCode(equinixReference.value.connectionTypes))
const equinixSideOptions = computed(() => optionFromCode(equinixReference.value.sideTypes))
const equinixConnectionRule = computed(() => equinixReference.value.connectionTypeRules?.[equinixForm.connectionType] || {})
const equinixASideOptions = computed(() => filteredSideOptions(equinixConnectionRule.value.aSides))
const equinixZSideOptions = computed(() => filteredSideOptions(equinixConnectionRule.value.zSides))
const equinixMetroOptions = computed(() => optionFromCode(equinixMetros.value))
const equinixBandwidthOptions = computed(() => (equinixReference.value.bandwidths || []).map((item) => ({ label: `${item} Mbps`, value: item })))
const equinixIbxOptions = computed(() => ['1', '2', '3', '4', '5'].map((item) => ({ label: `${equinixForm.originMetro}${item}`, value: item })))
const equinixPortTypeOptions = computed(() => optionFromCode(equinixReference.value.portOptions?.types || []))
const equinixPortPackageOptions = computed(() => optionFromCode(equinixReference.value.portOptions?.packages || []))
const equinixPortServiceOptions = computed(() => optionFromCode(equinixReference.value.portOptions?.serviceTypes || []))
const equinixConnectivityOptions = computed(() => optionFromCode(equinixReference.value.portOptions?.connectivitySources || []))
const equinixIpTypeOptions = computed(() => optionFromCode(equinixReference.value.ipBlockOptions?.types || []))
const equinixPrefixOptions = computed(() => optionFromCode(equinixReference.value.ipBlockOptions?.prefixLengths || []))
const equinixProductLabel = computed(() => equinixProductOptions.value.find((item) => item.value === equinixForm.type)?.label || 'Equinix Fabric')
const isEndpointScenario = computed(() => ['private_connect', 'bandwidth_upgrade'].includes(scenario.value))
const sharedBandwidthOptions = computed(() => {
  const values = new Set([...zenlayerBandwidths.value, ...(equinixReference.value.bandwidths || [])])
  return Array.from(values).sort((a, b) => a - b).map((item) => ({ label: `${item} Mbps`, value: item }))
})
const sharedHintText = computed(() => {
  if (scenario.value === 'port') return '端口是单点资源，Zenlayer 机房位置和 Equinix 城市会同步到各自端口报价。带宽、端口规格保持统一。'
  if (scenario.value === 'eq_only') return 'IP Block 是单点资源，只需要选择 Equinix 城市。供应商差异项放在右侧面板单独调整。'
  return 'A/Z 端、带宽、产品场景会同步到两个供应商。供应商差异项放在各自面板里单独调整。'
})

const priceDiffText = computed(() => {
  if (!zenlayerQuote.costItems.length || !equinixQuote.costItems.length) return '-'
  if (zenlayerQuote.currency !== equinixQuote.currency) return '币种不同'
  return money(equinixQuote.totalCost - zenlayerQuote.totalCost, zenlayerQuote.currency)
})

watch(() => shared.bandwidth, (value) => {
  zenlayerForm.bandwidthMbps = value
  equinixForm.bandwidth = value
})
watch(() => shared.portType, (value) => {
  zenlayerForm.portType = value
})
watch(() => shared.zenlayerA, (value) => {
  zenlayerForm.dcId = value || zenlayerForm.dcId
  zenlayerForm.endpointA = value || zenlayerForm.endpointA
})
watch(() => shared.zenlayerZ, (value) => {
  zenlayerForm.endpointZ = value || zenlayerForm.endpointZ
})
watch(() => shared.eqA, (value) => {
  equinixForm.originMetro = value || equinixForm.originMetro
  if (scenario.value !== 'port') return
  equinixForm.destinationMetro = value || equinixForm.destinationMetro
})
watch(() => shared.eqZ, (value) => {
  equinixForm.destinationMetro = value || equinixForm.destinationMetro
})
watch(() => equinixForm.connectionType, () => {
  normalizeEquinixSideTypes()
  resetEquinixResult()
})

function normalizeEquinixSideTypes() {
  const firstASide = equinixASideOptions.value[0]?.value
  const firstZSide = equinixZSideOptions.value[0]?.value
  if (firstASide && !equinixASideOptions.value.some((item) => item.value === equinixForm.aSideType)) {
    equinixForm.aSideType = firstASide
  }
  if (firstZSide && !equinixZSideOptions.value.some((item) => item.value === equinixForm.zSideType)) {
    equinixForm.zSideType = firstZSide
  }
}

function syncScenario() {
  if (scenario.value === 'port') {
    zenlayerForm.service = 'datacenter_port'
    equinixForm.type = 'VIRTUAL_PORT_PRODUCT'
    zenlayerForm.dcId = shared.zenlayerA || zenlayerForm.dcId
    equinixForm.originMetro = shared.eqA || equinixForm.originMetro
    equinixForm.destinationMetro = shared.eqA || equinixForm.destinationMetro
  } else if (scenario.value === 'bandwidth_upgrade') {
    zenlayerForm.service = 'private_connect_bandwidth'
    equinixForm.type = 'VIRTUAL_CONNECTION_PRODUCT'
  } else if (scenario.value === 'eq_only') {
    equinixForm.type = 'IP_BLOCK_PRODUCT'
    equinixForm.originMetro = shared.eqA || equinixForm.originMetro
  } else {
    zenlayerForm.service = 'private_connect'
    equinixForm.type = 'VIRTUAL_CONNECTION_PRODUCT'
  }
  normalizeEquinixSideTypes()
  resetZenlayerResult()
  resetEquinixResult()
}

function applyZenlayerDefaults() {
  const first = zenlayerDatacenters.value[0]?.dcId
  const second = zenlayerDatacenters.value[1]?.dcId || first
  if (!shared.zenlayerA && first) shared.zenlayerA = first
  if (!shared.zenlayerZ && second) shared.zenlayerZ = second
  if (!zenlayerForm.dcId && first) zenlayerForm.dcId = first
  if (!zenlayerForm.endpointA && first) zenlayerForm.endpointA = first
  if (!zenlayerForm.endpointZ && second) zenlayerForm.endpointZ = second
}

function applyEquinixDefaults() {
  const first = equinixMetros.value[0]?.code || 'SV'
  const second = equinixMetros.value[1]?.code || 'HK'
  if (!shared.eqA) shared.eqA = first
  if (!shared.eqZ) shared.eqZ = second
  if (!equinixForm.originMetro) equinixForm.originMetro = first
  if (!equinixForm.destinationMetro) equinixForm.destinationMetro = second
}

async function loadZenlayerOptions() {
  const res = await api.resourceApi.zenlayerPricing()
  const data = res?.data || {}
  zenlayerSource.value = data.source || 'fallback'
  zenlayerServices.value = data.services || []
  zenlayerDatacenters.value = data.datacenters || []
  zenlayerPortTypes.value = data.portTypes || zenlayerPortTypes.value
  zenlayerBandwidths.value = data.bandwidthOptions || zenlayerBandwidths.value
  zenlayerInternetTypes.value = data.internetTypes || zenlayerInternetTypes.value
  applyZenlayerDefaults()
}

async function loadEquinixOptions() {
  try {
    const referenceRes = await api.resourceApi.equinixReferenceData()
    const reference = referenceRes?.data || {}
    equinixReferenceSource.value = reference.source || 'fallback'
    equinixReference.value = {
      ...equinixReference.value,
      ...reference,
      portOptions: {
        ...(equinixReference.value.portOptions || {}),
        ...(reference.portOptions || {}),
      },
      ipBlockOptions: {
        ...(equinixReference.value.ipBlockOptions || {}),
        ...(reference.ipBlockOptions || {}),
      },
    }
    normalizeEquinixSideTypes()
  } catch (error) {
    equinixError.value = error?.message || 'Equinix 参数加载失败'
  }

  try {
    const metrosRes = await api.resourceApi.equinixMetros()
    const metros = metrosRes?.data?.metros || equinixReference.value.fallbackMetros || []
    if (metros.length) equinixMetros.value = metros
    applyEquinixDefaults()
  } catch (error) {
    equinixError.value = error?.message || 'Equinix 城市加载失败'
  }
}

async function loadAllOptions() {
  loadingOptions.value = true
  try {
    await Promise.all([loadZenlayerOptions(), loadEquinixOptions()])
    syncScenario()
  } finally {
    loadingOptions.value = false
  }
}

function resetZenlayerResult() {
  resetQuote(zenlayerQuote)
  zenlayerError.value = ''
}

function resetEquinixResult() {
  resetQuote(equinixQuote)
  equinixError.value = ''
}

async function generateZenlayerQuote() {
  zenlayerError.value = ''
  zenlayerLoading.value = true
  try {
    const res = await api.resourceApi.zenlayerQuote({ ...zenlayerForm })
    const data = res?.data || {}
    zenlayerQuote.costItems = data.costItems || []
    zenlayerQuote.totalCost = data.totalCost || 0
    zenlayerQuote.currency = data.currency || 'USD'
    zenlayerQuote.stock = data.stock
    zenlayerQuote.action = data.action || ''
    zenlayerQuote.payload = data.payload || {}
    zenlayerQuote.raw = data.raw || null
    if (!zenlayerQuote.costItems.length) zenlayerError.value = 'Zenlayer 返回结果中没有可展示的成本项。'
  } catch (error) {
    zenlayerError.value = error?.message || 'Zenlayer 报价失败'
  } finally {
    zenlayerLoading.value = false
  }
}

async function generateEquinixQuote() {
  equinixError.value = ''
  equinixLoading.value = true
  try {
    normalizeEquinixSideTypes()
    const res = await api.resourceApi.equinixQuote({ ...equinixForm })
    const data = res?.data || {}
    equinixQuote.costItems = data.costItems || []
    equinixQuote.totalCost = data.totalCost || 0
    equinixQuote.currency = data.currency || 'USD'
    equinixQuote.payload = data.payload || {}
    equinixQuote.raw = data.raw || null
    if (!equinixQuote.costItems.length) equinixError.value = 'Equinix 返回结果中没有可展示的成本项。'
  } catch (error) {
    equinixError.value = error?.message || 'Equinix 报价失败'
  } finally {
    equinixLoading.value = false
  }
}

async function copyZenlayerQuote() {
  await copyQuote('Zenlayer', zenlayerServiceLabel.value, zenlayerQuote)
}

async function copyEquinixQuote() {
  await copyQuote('Equinix', equinixProductLabel.value, equinixQuote)
}

async function copyQuote(vendor, product, quote) {
  const lines = [
    `${vendor}：${product}`,
    ...quote.costItems.map((item) => `${costNameMap[item.name] || item.name}：${money(item.quote_cost, item.currency)} / ${item.unit || '-'}`),
    `成本合计：${money(quote.totalCost, quote.currency)}`,
  ]
  await navigator.clipboard.writeText(lines.join('\n'))
  message.success(`${vendor} 报价已复制`)
}

function money(value, currency = 'USD') {
  return `${currency || 'USD'} ${Number(value || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

const ResultPanel = defineComponent({
  name: 'ResultPanel',
  props: {
    title: { type: String, required: true },
    items: { type: Array, default: () => [] },
    total: { type: Number, default: 0 },
    currency: { type: String, default: 'USD' },
  },
  setup(props) {
    return () => h('section', { class: 'pricing-panel result-panel' }, [
      h('div', { class: 'result-title' }, [
        h('div', [h('span', '报价结果'), h('strong', props.title)]),
        h('b', money(props.total, props.currency)),
      ]),
      h('div', { class: 'cost-table' }, [
        h('div', { class: 'cost-row cost-row--head' }, [
          h('span', '成本项'),
          h('span', '供应商原价'),
          h('span', '报价成本'),
          h('span', '+20%'),
          h('span', '+30%'),
          h('span', '+40%'),
          h('span', '30%毛利'),
          h('span', '单位'),
        ]),
        props.items.length
          ? props.items.map((item) => h('div', { class: 'cost-row', key: `${item.name}-${item.unit}` }, [
              h('strong', costNameMap[item.name] || item.name),
              h('span', money(item.supplier_price, item.currency)),
              h('span', money(item.quote_cost, item.currency)),
              h('span', money(item.suggest_20, item.currency)),
              h('span', money(item.suggest_30, item.currency)),
              h('span', money(item.suggest_40, item.currency)),
              h('span', money(item.margin_30, item.currency)),
              h('span', item.unit || '-'),
            ]))
          : h('div', { class: 'empty-state' }, '查询后会在这里显示成本明细。'),
      ]),
    ])
  },
})

onMounted(loadAllOptions)
</script>

<style scoped>
.pricing-page {
  display: grid;
  gap: 18px;
  padding-bottom: 8px;
}

:deep(.common-page-card) {
  flex: none;
  overflow: visible;
}

:deep(.common-page-card > .n-card__content) {
  display: block;
  min-height: auto;
  overflow: visible;
  padding-bottom: 24px;
}

.pricing-hero,
.pricing-panel {
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 14px 36px rgba(15, 23, 42, 0.06);
}

.pricing-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 520px);
  gap: 18px;
  align-items: end;
  padding: 20px;
  background: linear-gradient(135deg, #f8fafc 0%, #eef6ff 48%, #f7fbf4 100%);
}

.pricing-hero span,
.panel-title span,
.vendor-head span,
.result-title span,
.summary-card span {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.pricing-hero h2 {
  margin: 6px 0 8px;
  color: #0f172a;
  font-size: 24px;
  line-height: 1.2;
}

.pricing-hero p {
  max-width: 760px;
  margin: 0;
  color: #475569;
  line-height: 1.7;
}

.hero-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.hero-metrics article,
.summary-card,
.hint-box {
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.74);
  padding: 12px;
}

.hero-metrics strong,
.summary-card strong {
  display: block;
  margin-top: 8px;
  color: #0f172a;
  font-size: 18px;
  word-break: break-word;
}

.compare-grid {
  display: grid;
  grid-template-columns: minmax(280px, 360px) repeat(2, minmax(320px, 1fr));
  gap: 18px;
  align-items: start;
}

.pricing-panel {
  padding: 18px;
}

.panel-title,
.vendor-head,
.result-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.panel-title strong,
.vendor-head strong,
.result-title strong {
  display: block;
  margin-top: 4px;
  color: #111827;
  font-size: 18px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.form-grid--single {
  grid-template-columns: 1fr;
}

.hint-box {
  margin-top: 12px;
  background: #f8fafc;
}

.hint-box strong {
  color: #0f172a;
}

.hint-box p {
  margin: 6px 0 0;
  color: #64748b;
  line-height: 1.6;
}

.panel-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.cost-table {
  overflow-x: auto;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
}

.cost-row {
  display: grid;
  grid-template-columns: 1.2fr repeat(6, minmax(110px, 1fr)) 90px;
  min-width: 980px;
  border-top: 1px solid #e7edf5;
}

.cost-row:first-child {
  border-top: 0;
}

.cost-row > * {
  padding: 12px 10px;
  color: #111827;
  font-size: 13px;
}

.cost-row--head {
  background: #f1f5fb;
}

.cost-row--head > * {
  color: #475569;
  font-weight: 700;
}

.empty-state {
  padding: 42px 16px;
  color: #64748b;
  text-align: center;
}

.field-help-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.help-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border: 1px solid #cbd5e1;
  border-radius: 50%;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  cursor: help;
}

@media (max-width: 1280px) {
  .pricing-hero,
  .compare-grid,
  .result-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .pricing-panel,
  .pricing-hero {
    padding: 14px;
  }

  .hero-metrics,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .pricing-hero h2 {
    font-size: 20px;
  }
}
</style>
