<template>
  <CommonPage show-footer title="供应商比价">
    <template #action>
      <n-button :loading="loadingOptions" secondary @click="loadOptions">刷新</n-button>
    </template>

    <div class="zenlayer-page">
      <section class="quote-shell">
        <aside class="quote-form">
          <div class="panel-head">
            <span>报价参数</span>
            <strong>{{ activeServiceLabel }}</strong>
          </div>

          <n-form label-placement="top" :show-feedback="false">
            <n-form-item label="客户要询什么服务？">
              <n-select
                v-model:value="form.service"
                :options="serviceOptions"
                placeholder="请选择服务"
                @update:value="resetResult"
              />
            </n-form-item>

            <template v-if="form.service === 'datacenter_port'">
              <n-form-item label="机房">
                <n-cascader
                  v-model:value="form.dcId"
                  :options="datacenterCascaderOptions"
                  filterable
                  clearable
                  check-strategy="child"
                  placeholder="选择机房"
                />
              </n-form-item>
              <n-form-item label="端口规格">
                <n-select v-model:value="form.portType" :options="portTypeOptions" />
              </n-form-item>
            </template>

            <template v-else-if="needsEndpoints">
              <div class="endpoint-grid">
                <n-form-item label="A 点机房">
                  <n-cascader
                    v-model:value="form.endpointA"
                    :options="datacenterCascaderOptions"
                    filterable
                    clearable
                    check-strategy="child"
                    placeholder="A 点"
                  />
                </n-form-item>
                <n-form-item label="Z 点机房">
                  <n-cascader
                    v-model:value="form.endpointZ"
                    :options="datacenterCascaderOptions"
                    filterable
                    clearable
                    check-strategy="child"
                    placeholder="Z 点"
                  />
                </n-form-item>
              </div>
              <n-form-item v-if="form.service === 'private_connect'" label="端口规格">
                <n-select v-model:value="form.portType" :options="portTypeOptions" />
              </n-form-item>
              <div class="endpoint-grid">
                <n-form-item label="带宽">
                  <n-select v-model:value="form.bandwidthMbps" :options="bandwidthOptions" />
                </n-form-item>
                <n-form-item label="计费方式">
                  <n-select v-model:value="form.internetType" :options="internetTypeOptions" />
                </n-form-item>
              </div>
              <n-form-item v-if="form.service === 'private_connect_bandwidth'" label="服务等级">
                <n-select v-model:value="form.serviceLevel" :options="serviceLevelOptions" />
              </n-form-item>
            </template>

            <n-checkbox v-model:checked="form.buildCrossConnectWithAssisted">
              需要协助 Cross Connect
            </n-checkbox>
          </n-form>

          <div class="form-actions">
            <n-button type="primary" :loading="quoting" @click="generateQuote">{{ primaryActionLabel }}</n-button>
            <n-button secondary :disabled="!quote.costItems.length" @click="copyQuote">复制报价</n-button>
          </div>

          <p class="hint">
            机房列表从 Zenlayer 加载；报价使用后台保存的 API 密钥实时查询。
          </p>
        </aside>

        <main class="quote-result">
          <div class="result-head">
            <div>
              <span>报价结果</span>
              <strong>{{ quoteStatus }}</strong>
            </div>
            <n-tag :type="sourceTagType" round>{{ sourceLabel }}</n-tag>
          </div>

          <n-alert v-if="errorMessage" type="error" :bordered="false" closable @close="errorMessage = ''">
            {{ errorMessage }}
          </n-alert>

          <div class="summary-grid">
            <div v-for="item in summaryCards" :key="item.label" class="summary-card">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>

          <div class="cost-table">
            <div class="cost-row cost-row--head">
              <span>成本项</span>
              <span>供应商原价</span>
              <span>报价成本</span>
              <span>建议售价 +20%</span>
              <span>建议售价 +30%</span>
              <span>建议售价 +40%</span>
              <span>30% 毛利售价</span>
              <span>计费单位</span>
            </div>
            <div v-if="!quote.costItems.length" class="empty-state">
              生成报价后会在这里显示成本明细。
            </div>
            <div v-for="item in quote.costItems" :key="item.name" class="cost-row">
              <strong>{{ costNameMap[item.name] || item.name }}</strong>
              <span>{{ money(item.supplier_price, item.currency) }}</span>
              <span>{{ money(item.quote_cost, item.currency) }}</span>
              <span>{{ money(item.suggest_20, item.currency) }}</span>
              <span>{{ money(item.suggest_30, item.currency) }}</span>
              <span>{{ money(item.suggest_40, item.currency) }}</span>
              <span>{{ money(item.margin_30, item.currency) }}</span>
              <span>{{ item.unit || 'MONTH' }}</span>
            </div>
          </div>

          <details class="technical">
            <summary>技术详情</summary>
            <pre>{{ technicalText }}</pre>
          </details>
        </main>
      </section>
    </div>
  </CommonPage>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useMessage } from 'naive-ui'
import {
  NAlert,
  NButton,
  NCascader,
  NCheckbox,
  NForm,
  NFormItem,
  NSelect,
  NTag,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: 'ResourceZenlayerPricing' })

const message = useMessage()
const loadingOptions = ref(false)
const quoting = ref(false)
const source = ref('fallback')
const errorMessage = ref('')
const services = ref([])
const datacenters = ref([])
const portTypes = ref(['1G', '10G', '40G'])
const bandwidths = ref([10, 50, 100, 200, 500, 1000, 2000, 5000, 10000])
const internetTypes = ref([
  { label: '固定带宽', value: 'ByBandwidth' },
  { label: '95计费', value: 'ByInstanceBandwidth95' },
])

const form = reactive({
  service: 'datacenter_port',
  dcId: '',
  endpointA: '',
  endpointZ: '',
  portType: '10G',
  bandwidthMbps: 100,
  internetType: 'ByBandwidth',
  serviceLevel: 'SINGLE_UNPROTECTED',
  buildCrossConnectWithAssisted: false,
})

const quote = reactive({
  costItems: [],
  totalCost: 0,
  currency: 'USD',
  stock: '',
  action: '',
  payload: {},
  raw: null,
})

const costNameMap = {
  datacenter_port: '机房端口成本',
  cross_connect_monthly: 'Cross Connect 月费',
  cross_connect_setup: 'Cross Connect 一次性建设费',
  private_connect_bandwidth: '专线带宽成本',
  endpoint_a_access: 'A 点接入成本',
  endpoint_a_cross_connect_monthly: 'A 点 Cross Connect 月费',
  endpoint_a_cross_connect_setup: 'A 点 Cross Connect 一次性建设费',
  endpoint_z_access: 'Z 点接入成本',
  endpoint_z_cross_connect_monthly: 'Z 点 Cross Connect 月费',
  endpoint_z_cross_connect_setup: 'Z 点 Cross Connect 一次性建设费',
  quote_cost: '报价成本',
}

const serviceLevelOptions = [
  { label: 'Single Unprotected', value: 'SINGLE_UNPROTECTED' },
  { label: 'Single Protected', value: 'SINGLE_PROTECTED' },
]

const serviceOptions = computed(() => services.value
  .filter((item) => !item.disabled && item.value !== 'datacenter_lookup')
  .map((item) => ({
    label: item.label,
    value: item.value,
  })))

const datacenterCascaderOptions = computed(() => {
  const areaMap = new Map()
  datacenters.value.forEach((item) => {
    const area = item.areaName || 'Other'
    const city = item.cityName || 'Unknown City'
    if (!areaMap.has(area)) {
      areaMap.set(area, { label: area, value: `area:${area}`, children: new Map() })
    }
    const areaNode = areaMap.get(area)
    if (!areaNode.children.has(city)) {
      areaNode.children.set(city, { label: city, value: `city:${area}:${city}`, children: [] })
    }
    areaNode.children.get(city).children.push({
      label: item.dcName || item.label || item.dcId,
      value: item.dcId,
    })
  })
  return Array.from(areaMap.values())
    .sort((a, b) => a.label.localeCompare(b.label))
    .map((areaNode) => ({
      label: areaNode.label,
      value: areaNode.value,
      children: Array.from(areaNode.children.values())
        .sort((a, b) => a.label.localeCompare(b.label))
        .map((cityNode) => ({
          ...cityNode,
          children: cityNode.children.sort((a, b) => a.label.localeCompare(b.label)),
        })),
    }))
})

const portTypeOptions = computed(() => portTypes.value.map((item) => ({ label: item, value: item })))
const bandwidthOptions = computed(() => bandwidths.value.map((item) => ({ label: `${item} Mbps`, value: item })))
const internetTypeOptions = computed(() => internetTypes.value)
const activeService = computed(() => services.value.find((item) => item.value === form.service))
const activeServiceLabel = computed(() => activeService.value?.label || '机房端口')
const needsEndpoints = computed(() => ['private_connect', 'private_connect_bandwidth'].includes(form.service))
const quoteStatus = computed(() => (quote.costItems.length ? '报价生成成功。' : '等待生成报价。'))
const sourceLabel = computed(() => (source.value === 'zenlayer_api' ? 'Zenlayer API' : '本地候选机房'))
const sourceTagType = computed(() => (source.value === 'zenlayer_api' ? 'success' : 'warning'))
const primaryActionLabel = computed(() => '生成报价')

const summaryCards = computed(() => [
  { label: '服务', value: activeServiceLabel.value },
  { label: 'A 点机房', value: selectedDcShortName(form.endpointA || form.dcId) || '-' },
  { label: 'Z 点机房', value: needsEndpoints.value ? selectedDcShortName(form.endpointZ) || '-' : '-' },
  { label: '规格', value: needsEndpoints.value ? `${form.bandwidthMbps} Mbps / ${form.portType}` : form.portType },
  { label: '库存', value: quote.stock === null || quote.stock === undefined || quote.stock === '' ? '-' : quote.stock },
  { label: '成本合计', value: money(quote.totalCost, quote.currency) },
])

const technicalText = computed(() => JSON.stringify({
  action: quote.action,
  payload: quote.payload,
  raw: quote.raw,
}, null, 2))

function selectedDcName(dcId) {
  const item = datacenters.value.find((row) => row.dcId === dcId)
  return item?.label || ''
}

function selectedDcShortName(dcId) {
  const item = datacenters.value.find((row) => row.dcId === dcId)
  return item?.dcName || ''
}

function money(value, currency = 'USD') {
  return `${currency || 'USD'} ${Number(value || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

function resetResult() {
  quote.costItems = []
  quote.totalCost = 0
  quote.stock = ''
  quote.action = ''
  quote.payload = {}
  quote.raw = null
  errorMessage.value = ''
}

function applyDefaults() {
  if (!form.dcId && datacenters.value[0]?.dcId) form.dcId = datacenters.value[0].dcId
  if (!form.endpointA && datacenters.value[0]?.dcId) form.endpointA = datacenters.value[0].dcId
  if (!form.endpointZ && datacenters.value[1]?.dcId) form.endpointZ = datacenters.value[1].dcId
}

async function loadOptions() {
  loadingOptions.value = true
  try {
    const res = await api.resourceApi.zenlayerPricing()
    const data = res?.data || {}
    source.value = data.source || 'fallback'
    services.value = data.services || []
    datacenters.value = data.datacenters || []
    portTypes.value = data.portTypes || portTypes.value
    bandwidths.value = data.bandwidthOptions || bandwidths.value
    internetTypes.value = data.internetTypes || internetTypes.value
    applyDefaults()
    if (data.errors?.length) {
      message.warning('机房列表暂未从 Zenlayer 完整加载，已使用本地候选项。')
    }
  } finally {
    loadingOptions.value = false
  }
}

async function generateQuote() {
  errorMessage.value = ''
  quoting.value = true
  try {
    const res = await api.resourceApi.zenlayerQuote({ ...form })
    const data = res?.data || {}
    quote.costItems = data.costItems || []
    quote.totalCost = data.totalCost || 0
    quote.currency = data.currency || 'USD'
    quote.stock = data.stock
    quote.action = data.action || ''
    quote.payload = data.payload || {}
    quote.raw = data.raw || null
    if (!quote.costItems.length) {
      errorMessage.value = 'Zenlayer 已返回结果，但没有可展示的成本项，请展开技术详情查看原始返回。'
    }
  } catch (error) {
    errorMessage.value = error?.message || '生成报价失败'
  } finally {
    quoting.value = false
  }
}

async function copyQuote() {
  const lines = [
    `服务：${activeServiceLabel.value}`,
    `机房：${selectedDcShortName(form.endpointA || form.dcId)}`,
    needsEndpoints.value ? `Z 点：${selectedDcShortName(form.endpointZ)}` : '',
    `规格：${needsEndpoints.value ? `${form.bandwidthMbps} Mbps / ${form.portType}` : form.portType}`,
    ...quote.costItems.map((item) => `${costNameMap[item.name] || item.name}：${money(item.quote_cost, item.currency)} / ${item.unit}`),
    `成本合计：${money(quote.totalCost, quote.currency)}`,
  ].filter(Boolean)
  await navigator.clipboard.writeText(lines.join('\n'))
  message.success('报价已复制')
}

onMounted(loadOptions)
</script>

<style scoped>
.zenlayer-page {
  min-height: calc(100vh - 180px);
}

.quote-shell {
  display: grid;
  grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.quote-form,
.quote-result {
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 14px 36px rgba(15, 23, 42, 0.06);
}

.quote-form {
  padding: 18px;
}

.quote-result {
  display: grid;
  gap: 16px;
  padding: 18px;
}

.panel-head,
.result-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.panel-head span,
.result-head span,
.summary-card span,
.hint {
  color: #5b6b84;
  font-size: 13px;
}

.panel-head strong,
.result-head strong {
  display: block;
  margin-top: 4px;
  color: #111827;
  font-size: 18px;
}

.endpoint-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}

.hint {
  margin: 12px 0 0;
  line-height: 1.7;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.summary-card {
  padding: 12px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #f8fafc;
}

.summary-card strong {
  display: block;
  margin-top: 8px;
  color: #111827;
  font-size: 18px;
  word-break: break-word;
}

.cost-table {
  overflow-x: auto;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
}

.dc-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
  max-height: 520px;
  overflow: auto;
}

.dc-item {
  display: grid;
  gap: 6px;
  padding: 12px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #f8fafc;
}

.dc-item strong {
  color: #111827;
}

.dc-item span {
  color: #64748b;
  font-size: 12px;
}

.cost-row {
  display: grid;
  grid-template-columns: 1.15fr repeat(6, minmax(110px, 1fr)) 92px;
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
  font-weight: 600;
}

.empty-state {
  padding: 44px 16px;
  color: #64748b;
  text-align: center;
}

.technical {
  border-top: 1px solid #dbe3ef;
  padding-top: 12px;
  color: #475569;
}

.technical summary {
  cursor: pointer;
}

.technical pre {
  overflow: auto;
  max-height: 360px;
  margin: 12px 0 0;
  padding: 12px;
  border-radius: 8px;
  background: #0f172a;
  color: #dbeafe;
  font-size: 12px;
  line-height: 1.6;
}

@media (max-width: 1180px) {
  .quote-shell {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .summary-grid,
  .endpoint-grid {
    grid-template-columns: 1fr;
  }

  .form-actions {
    flex-direction: column;
  }
}
</style>
