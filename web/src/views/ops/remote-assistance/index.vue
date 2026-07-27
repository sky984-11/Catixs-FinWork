<template>
  <AppPage :show-footer="false">
    <div class="collaboration-page">
      <section class="summary-grid">
        <article>
          <span class="summary-icon orange"><TheIcon icon="mdi:clipboard-clock-outline" :size="21" /></span>
          <div><small>未到场</small><strong>{{ statusCount.scheduled }}</strong></div>
        </article>
        <article>
          <span class="summary-icon blue"><TheIcon icon="mdi:account-clock-outline" :size="21" /></span>
          <div><small>现场处理中</small><strong>{{ statusCount.arrived }}</strong></div>
        </article>
        <article>
          <span class="summary-icon green"><TheIcon icon="mdi:check-circle-outline" :size="21" /></span>
          <div><small>已完成</small><strong>{{ statusCount.done }}</strong></div>
        </article>
        <article>
          <span class="summary-icon gray"><TheIcon icon="mdi:account-hard-hat-outline" :size="21" /></span>
          <div><small>启用工程师</small><strong>{{ activeEngineerCount }}</strong></div>
        </article>
      </section>

      <section class="workspace-panel">
        <n-tabs v-model:value="activeTab" type="line" animated>
          <n-tab-pane name="remote" tab="运维记录">
            <div class="table-toolbar">
              <div class="filter-row">
                <n-select
                  v-model:value="remoteFilters.engineer_id"
                  clearable
                  filterable
                  placeholder="按工程师筛选"
                  :options="remoteEngineerOptions"
                />
                <n-select
                  v-model:value="remoteFilters.site"
                  clearable
                  filterable
                  placeholder="按机房筛选"
                  :options="remoteSiteFilterOptions"
                />
                <n-select
                  v-model:value="remoteFilters.status"
                  clearable
                  placeholder="任务状态"
                  :options="statusOptions"
                />
              </div>
              <n-space>
                <n-button secondary circle :loading="loading" title="刷新" @click="fetchOverview">
                  <template #icon><TheIcon icon="mdi:refresh" :size="18" /></template>
                </n-button>
                <n-button type="primary" round @click="openRemoteEditor()">
                  <template #icon><TheIcon icon="mdi:plus" :size="18" /></template>
                  新增运维记录
                </n-button>
              </n-space>
            </div>
            <n-data-table
              :loading="loading"
              :columns="remoteColumns"
              :data="filteredRemoteHands"
              :pagination="remotePagination"
              :row-key="(row) => row.id"
              flex-height
              :scroll-x="1740"
              striped
            >
              <template #empty><n-empty description="暂无运维记录" /></template>
            </n-data-table>
          </n-tab-pane>

          <n-tab-pane name="engineers" tab="工程师">
            <div class="table-toolbar">
              <div class="filter-row engineer-search">
                <n-input v-model:value="engineerKeyword" clearable placeholder="搜索姓名、联系方式、微信或地区">
                  <template #prefix><TheIcon icon="mdi:magnify" :size="17" /></template>
                </n-input>
              </div>
              <n-space>
                <n-button secondary circle :loading="loading" title="刷新" @click="fetchOverview">
                  <template #icon><TheIcon icon="mdi:refresh" :size="18" /></template>
                </n-button>
                <n-button type="primary" round @click="openEngineerEditor()">
                  <template #icon><TheIcon icon="mdi:account-plus-outline" :size="18" /></template>
                  新增工程师
                </n-button>
              </n-space>
            </div>
            <n-data-table
              :loading="loading"
              :columns="engineerColumns"
              :data="filteredEngineers"
              :pagination="engineerPagination"
              :row-key="(row) => row.id"
              flex-height
              :scroll-x="1100"
              striped
            >
              <template #empty><n-empty description="暂无工程师" /></template>
            </n-data-table>
          </n-tab-pane>
        </n-tabs>
      </section>
      <n-modal
        v-model:show="remoteEditor.show"
        preset="card"
        :title="remoteEditor.form.id ? '编辑运维记录' : '新增运维记录'"
        class="editor-modal remote-editor-modal"
        :bordered="false"
      >
        <n-form label-placement="left" label-width="92" :model="remoteEditor.form">
          <div class="form-grid">
            <n-form-item label="客户" required>
              <n-input v-model:value="remoteEditor.form.customer" placeholder="客户名称" />
            </n-form-item>
            <n-form-item label="工单号">
              <n-input v-model:value="remoteEditor.form.ticket" placeholder="关联工单号" />
            </n-form-item>
            <n-form-item label="机房" required>
              <n-cascader
                v-model:value="remoteEditor.form.site_key"
                filterable
                clearable
                show-path
                :options="siteCascaderOptions"
                placeholder="选择地区 / 机房"
                @update:value="handleRemoteSiteCascaderChange"
              />
            </n-form-item>
            <n-form-item label="工程师" required>
              <n-select
                v-model:value="remoteEditor.form.engineer_id"
                filterable
                clearable
                :options="assignableEngineerOptions"
                :disabled="!remoteEditor.form.region"
                :placeholder="remoteEditor.form.region ? '选择启用工程师' : '请先选择地区'"
                @update:value="handleEngineerSelected"
              />
            </n-form-item>
            <n-form-item label="任务状态">
              <n-select v-model:value="remoteEditor.form.status" :options="statusOptions" />
            </n-form-item>
            <n-form-item label="运维结算">
              <n-select
                v-model:value="remoteEditor.form.ops_settlement_status"
                :options="settlementOptions"
              />
            </n-form-item>
            <n-form-item label="客户结算">
              <n-select
                v-model:value="remoteEditor.form.customer_settlement_status"
                :options="settlementOptions"
              />
            </n-form-item>
            <n-form-item label="到场时间">
              <n-date-picker
                v-model:formatted-value="remoteEditor.form.arrived_at"
                type="datetime"
                format="yyyy-MM-dd HH:mm"
                value-format="yyyy-MM-dd'T'HH:mm"
                :actions="datePickerActions"
                :time-picker-props="minuteTimePickerProps"
                clearable
                style="width: 100%"
              />
            </n-form-item>
            <n-form-item label="离场时间">
              <n-date-picker
                v-model:formatted-value="remoteEditor.form.left_at"
                type="datetime"
                format="yyyy-MM-dd HH:mm"
                value-format="yyyy-MM-dd'T'HH:mm"
                :actions="datePickerActions"
                :time-picker-props="minuteTimePickerProps"
                clearable
                style="width: 100%"
                @update:formatted-value="updateWorkMinutes"
              />
            </n-form-item>
          </div>
          <n-form-item label="备注">
            <n-input
              v-model:value="remoteEditor.form.note"
              type="textarea"
              placeholder="工作内容、交接信息或其他说明"
              :autosize="{ minRows: 3, maxRows: 6 }"
            />
          </n-form-item>
        </n-form>
        <template #footer>
          <div class="modal-actions">
            <n-button round @click="remoteEditor.show = false">取消</n-button>
            <n-button type="primary" round :loading="remoteEditor.saving" @click="saveRemoteHands">保存</n-button>
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="engineerEditor.show"
        preset="card"
        :title="engineerEditor.form.id ? '编辑工程师' : '新增工程师'"
        class="editor-modal engineer-editor-modal"
        :bordered="false"
      >
        <n-form label-placement="left" label-width="92" :model="engineerEditor.form">
          <div class="form-grid">
            <n-form-item label="姓名" required>
              <n-input v-model:value="engineerEditor.form.name" placeholder="工程师姓名" />
            </n-form-item>
            <n-form-item label="联系方式">
              <n-input v-model:value="engineerEditor.form.contact" placeholder="电话或其他联系方式" />
            </n-form-item>
            <n-form-item label="微信号">
              <n-input v-model:value="engineerEditor.form.wechat_id" placeholder="微信号" />
            </n-form-item>
            <n-form-item label="联系群">
              <n-input v-model:value="engineerEditor.form.wechat_group" placeholder="微信群或工作群" />
            </n-form-item>
            <n-form-item label="负责地区">
              <n-select
                v-model:value="engineerEditor.form.regions"
                multiple
                filterable
                tag
                :options="regionOptions"
                placeholder="选择一个或多个地区"
              />
            </n-form-item>
            <n-form-item label="状态">
              <n-select v-model:value="engineerEditor.form.is_active" :options="engineerStatusOptions" />
            </n-form-item>
          </div>
          <n-form-item label="备注">
            <n-input
              v-model:value="engineerEditor.form.note"
              type="textarea"
              placeholder="技能、值班时间或其他说明"
              :autosize="{ minRows: 3, maxRows: 6 }"
            />
          </n-form-item>
        </n-form>
        <template #footer>
          <div class="modal-actions">
            <n-button round @click="engineerEditor.show = false">取消</n-button>
            <n-button type="primary" round :loading="engineerEditor.saving" @click="saveEngineer">保存</n-button>
          </div>
        </template>
      </n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NPopconfirm, NSpace, NTag, NTooltip, useMessage } from 'naive-ui'
import api from '@/api'
import { translateCity, translateCountry, translateLocationPath } from '@/utils/location-i18n'

const message = useMessage()
const loading = ref(false)
const activeTab = ref('remote')
const remoteHands = ref([])
const engineers = ref([])
const datacenters = ref([])
const engineerKeyword = ref('')

const remoteFilters = reactive({ engineer_id: null, site: null, status: null })
const datePickerActions = ['clear', 'now', 'confirm']
const minuteTimePickerProps = { format: 'HH:mm' }
const remotePagination = reactive({
  page: 1,
  pageSize: 10,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
  onUpdatePage: (page) => {
    remotePagination.page = page
  },
  onUpdatePageSize: (pageSize) => {
    remotePagination.pageSize = pageSize
    remotePagination.page = 1
  },
})
const engineerPagination = reactive({
  page: 1,
  pageSize: 10,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
  onUpdatePage: (page) => {
    engineerPagination.page = page
  },
  onUpdatePageSize: (pageSize) => {
    engineerPagination.pageSize = pageSize
    engineerPagination.page = 1
  },
})

const statusOptions = [
  { label: '未到场', value: 'scheduled' },
  { label: '已到场', value: 'arrived' },
  { label: '已完成', value: 'done' },
  { label: '已取消', value: 'cancelled' },
]

const settlementOptions = [
  { label: '未计费', value: 'unbilled' },
  { label: '已计费', value: 'billed' },
  { label: '已结算', value: 'settled' },
]

const engineerStatusOptions = [
  { label: '启用', value: 1 },
  { label: '停用', value: 0 },
]

const remoteEditor = reactive({ show: false, saving: false, form: createRemoteForm() })
const engineerEditor = reactive({ show: false, saving: false, form: createEngineerForm() })

const statusCount = computed(() => ({
  scheduled: remoteHands.value.filter((item) => item.status === 'scheduled').length,
  arrived: remoteHands.value.filter((item) => item.status === 'arrived').length,
  done: remoteHands.value.filter((item) => item.status === 'done').length,
}))

const activeEngineerCount = computed(
  () => engineers.value.filter((item) => Number(item.is_active) === 1).length
)

const regionOptions = computed(() => {
  const values = new Set()
  datacenters.value.forEach((item) => {
    const value = displayRegion(datacenterRegion(item))
    if (value) values.add(value)
  })
  engineers.value.forEach((item) => engineerRegions(item).forEach((value) => values.add(displayRegion(value))))
  remoteHands.value.forEach((item) => {
    const value = displayRegion(item.region)
    if (value) values.add(value)
  })
  return [...values].sort().map((value) => ({ label: value, value }))
})

const siteCascaderOptions = computed(() => {
  const groups = new Map()
  const addSite = ({ region, site, label, timezone }) => {
    const regionLabel = displayRegion(region)
    const siteValue = fieldText(site)
    if (!regionLabel || !siteValue) return
    if (!groups.has(regionLabel)) {
      groups.set(regionLabel, {
        label: regionLabel,
        value: siteCascaderRegionValue(regionLabel),
        children: [],
      })
    }
    const group = groups.get(regionLabel)
    const value = siteCascaderValue(regionLabel, siteValue)
    if (group.children.some((item) => item.value === value)) return
    group.children.push({
      label: fieldText(label) || siteValue,
      value,
      region: regionLabel,
      site: siteValue,
      timezone,
    })
  }

  datacenters.value.forEach((item) => {
    const siteValue = datacenterValue(item)
    const siteName = fieldText(item.name)
    addSite({
      region: datacenterRegion(item),
      site: siteValue,
      label: siteName && siteName !== siteValue ? `${siteValue} / ${siteName}` : siteValue,
      timezone: item.timezone,
    })
  })
  remoteHands.value.forEach((item) => addSite({
    region: item.region,
    site: item.site,
    label: item.site,
    timezone: item.timezone,
  }))

  return [...groups.values()]
    .sort((left, right) => left.label.localeCompare(right.label, 'zh-Hans-CN'))
    .map((group) => ({
      ...group,
      children: group.children.sort((left, right) => left.label.localeCompare(right.label, 'zh-Hans-CN')),
    }))
})

const assignableEngineerOptions = computed(() => {
  if (!remoteEditor.form.region) return []
  return engineers.value
    .filter((item) => Number(item.is_active) === 1)
    .filter((item) => regionMatches(engineerRegions(item), remoteEditor.form.region))
    .map((item) => ({
      label: [item.name, item.wechat_id || item.contact].filter(Boolean).join(' · '),
      value: item.id,
    }))
})

const remoteEngineerOptions = computed(() => uniqueOptions(
  remoteHands.value
    .map((item) => ({
      label: item.engineer_name || engineers.value.find((engineer) => String(engineer.id) === String(item.engineer_id))?.name,
      value: item.engineer_id || item.engineer_name,
    }))
    .filter((item) => item.label && item.value)
))

const remoteSiteFilterOptions = computed(() => uniqueOptions(
  [
    ...datacenters.value.map((item) => ({ label: datacenterLabel(item), value: datacenterValue(item) })),
    ...remoteHands.value.map((item) => ({ label: fieldText(item.site), value: fieldText(item.site) })),
  ].filter((item) => item.value)
))

const filteredRemoteHands = computed(() => {
  return remoteHands.value.filter((item) => {
    if (remoteFilters.status && item.status !== remoteFilters.status) return false
    if (remoteFilters.engineer_id) {
      const selectedEngineer = String(remoteFilters.engineer_id)
      const currentEngineer = String(item.engineer_id || item.engineer_name || '')
      if (currentEngineer !== selectedEngineer) return false
    }
    if (remoteFilters.site && !valuesMatch(item.site, remoteFilters.site)) return false
    return true
  })
})

const filteredEngineers = computed(() => {
  const keyword = engineerKeyword.value.trim().toLowerCase()
  if (!keyword) return engineers.value
  return engineers.value.filter((item) => ['name', 'contact', 'wechat_id', 'wechat_group', 'region', 'note']
    .some((key) => String(item[key] || '').toLowerCase().includes(keyword)))
})

const remoteColumns = [
  {
    title: '客户 / 工单', key: 'customer', width: 180,
    render: (row) => h('div', { class: 'primary-cell' }, [
      h('strong', row.customer || '-'), h('small', row.ticket || '无工单号'),
    ]),
  },
  {
    title: '工程师', key: 'engineer_name', width: 190,
    render: (row) => h('div', { class: 'primary-cell' }, [
      h('strong', row.engineer_name || '-'),
      h('small', row.engineer_wechat || row.engineer_contact || '-'),
    ]),
  },
  {
    title: '地区 / 机房', key: 'site', width: 190,
    render: (row) => h('div', { class: 'primary-cell' }, [
      h('strong', displayRegion(row.region) || '-'), h('small', row.site || '-'),
    ]),
  },
  { title: '日期', key: 'date', width: 110, render: (row) => formatDate(row.arrived_at || row.left_at) },
  { title: '到场', key: 'arrived_at', width: 105, render: (row) => formatTime(row.arrived_at) },
  { title: '离场', key: 'left_at', width: 105, render: (row) => formatTime(row.left_at) },
  { title: '工时', key: 'work_minutes', width: 95, render: (row) => formatDuration(row.work_minutes) },
  {
    title: '状态', key: 'status', width: 100,
    render: (row) => h(NTag, { type: statusTagType(row.status), bordered: false, size: 'small' },
      { default: () => statusLabel(row.status) }),
  },
  {
    title: '运维结算', key: 'ops_settlement_status', width: 110,
    render: (row) => renderSettlementTag(readSettlementStatus(row, 'ops')),
  },
  {
    title: '客户结算', key: 'customer_settlement_status', width: 110,
    render: (row) => renderSettlementTag(readSettlementStatus(row, 'customer')),
  },
  {
    title: '备注', key: 'note', width: 360,
    render: (row) => renderNoteCell(row.note),
  },
  {
    title: '操作', key: 'actions', width: 290, fixed: 'right',
    render: (row) => h(NSpace, { size: 6, wrap: false }, {
      default: () => [
        row.status === 'scheduled' && !row.left_at
          ? h(NButton, { size: 'small', type: 'success', secondary: true, onClick: () => updateRemoteStatus(row, 'arrived') }, { default: () => '到场' })
          : null,
        row.status === 'arrived' && row.arrived_at && !row.left_at
          ? h(NButton, { size: 'small', type: 'warning', secondary: true, onClick: () => updateRemoteStatus(row, 'done') }, { default: () => '离场' })
          : null,
        h(NButton, { size: 'small', type: 'primary', secondary: true, onClick: () => openRemoteEditor(row) }, { default: () => '编辑' }),
        renderDeleteConfirm({
          title: `确认删除 ${row.customer || row.ticket || '这条运维记录'}？`,
          actionText: '删除',
          onConfirm: () => deleteRemoteHands(row),
        }),
      ].filter(Boolean),
    }),
  },
]

const engineerColumns = [
  { title: '姓名', key: 'name', width: 150, render: (row) => h('strong', row.name || '-') },
  { title: '联系方式', key: 'contact', width: 180, render: (row) => row.contact || '-' },
  {
    title: '微信', key: 'wechat_id', width: 200,
    render: (row) => h('div', { class: 'primary-cell' }, [
      h('strong', row.wechat_id || '-'), h('small', row.wechat_group || '无联系群'),
    ]),
  },
  { title: '负责地区', key: 'region', minWidth: 220, ellipsis: { tooltip: true } },
  {
    title: '状态', key: 'is_active', width: 100,
    render: (row) => h(NTag, { type: Number(row.is_active) === 1 ? 'success' : 'default', bordered: false, size: 'small' },
      { default: () => (Number(row.is_active) === 1 ? '启用' : '停用') }),
  },
  {
    title: '备注', key: 'note', width: 360,
    render: (row) => renderNoteCell(row.note),
  },
  {
    title: '操作', key: 'actions', width: 170, fixed: 'right',
    render: (row) => h(NSpace, { size: 6, wrap: false }, {
      default: () => [
        h(NButton, { size: 'small', type: 'primary', secondary: true, onClick: () => openEngineerEditor(row) }, { default: () => '编辑' }),
        renderDeleteConfirm({
          title: `确认删除工程师 ${row.name || ''}？`,
          actionText: '删除',
          onConfirm: () => deleteEngineer(row),
        }),
      ],
    }),
  },
]

function createRemoteForm(source = {}) {
  return {
    id: source.id || null,
    customer: source.customer || '',
    ticket: source.ticket || '',
    engineer_id: source.engineer_id || null,
    engineer_name: source.engineer_name || '',
    engineer_contact: source.engineer_contact || '',
    engineer_wechat: source.engineer_wechat || '',
    engineer_group: source.engineer_group || '',
    region: displayRegion(source.region),
    site: source.site || '',
    site_key: findSiteCascaderValue(source),
    rack: '',
    timezone: source.timezone || 'Asia/Shanghai',
    arrived_at: normalizeDateTime(source.arrived_at),
    left_at: normalizeDateTime(source.left_at),
    work_minutes: Number(source.work_minutes || 0),
    status: source.status || 'scheduled',
    ops_settlement_status: readSettlementStatus(source, 'ops'),
    customer_settlement_status: readSettlementStatus(source, 'customer'),
    note: source.note || '',
  }
}

function createEngineerForm(source = {}) {
  return {
    id: source.id || null,
    name: source.name || '',
    contact: source.contact || '',
    wechat_id: source.wechat_id || '',
    wechat_group: source.wechat_group || '',
    regions: splitRegions(source.region),
    is_active: Number(source.is_active ?? 1),
    note: source.note || '',
  }
}

function datacenterValue(item) {
  return String(item.code || item.name || item.id || '')
}

function datacenterLabel(item) {
  const value = datacenterValue(item)
  const name = item.name && item.name !== value ? `${value} / ${item.name}` : value
  const region = displayRegion(datacenterRegion(item))
  return region ? `${region} / ${name}` : name
}

function siteCascaderRegionValue(region) {
  return `region:${displayRegion(region)}`
}

function siteCascaderValue(region, site) {
  return `${siteCascaderRegionValue(region)}|site:${fieldText(site)}`
}

function findSiteCascaderValue(source = {}) {
  const site = fieldText(source.site)
  if (!site) return null
  const sourceRegion = displayRegion(source.region)
  const datacenter = datacenters.value.find((item) => {
    if (!valuesMatch(datacenterValue(item), site)) return false
    return !sourceRegion || datacenterMatchesRegion(item, sourceRegion)
  })
  if (datacenter) return siteCascaderValue(datacenterRegion(datacenter), datacenterValue(datacenter))
  const record = remoteHands.value.find((item) => {
    if (!valuesMatch(item.site, site)) return false
    return !sourceRegion || valuesMatch(item.region, sourceRegion)
  })
  return siteCascaderValue(sourceRegion || record?.region, site)
}

function datacenterRegion(item) {
  const region = displayRegion(fieldText(item.region) || fieldText(item.region_name))
  const country = translateCountry(fieldText(item.country) || fieldText(item.country_name))
  const city = translateCity(fieldText(item.city) || fieldText(item.city_name))
  const location = fieldText(item.location) || fieldText(item.location_name)
  if (region && city && !normalizeRegion(region).includes(normalizeRegion(city))) return `${region} / ${city}`
  if (country && city) return `${country} / ${city}`
  return region || location || city || country || fieldText(item.continent) || fieldText(item.continent_name)
}

function displayRegion(value) {
  const text = fieldText(value)
  if (!text) return ''
  return translateLocationPath(text) || translateCountry(text) || translateCity(text) || text
}

function engineerRegions(item) {
  if (!item) return []
  const country = fieldText(item.country) || fieldText(item.country_name)
  const city = fieldText(item.city) || fieldText(item.city_name)
  const location = fieldText(item.location) || fieldText(item.location_name)
  return uniqueValues([
    fieldText(item.region),
    fieldText(item.region_name),
    ...splitRegions(item.regions),
    ...splitRegions(item.region),
    location,
    city,
    country,
    country && city ? `${country} / ${city}` : '',
    country && location ? `${country} / ${location}` : '',
  ])
}

function datacenterRegions(item) {
  const region = fieldText(item.region) || fieldText(item.region_name)
  const country = fieldText(item.country) || fieldText(item.country_name)
  const city = fieldText(item.city) || fieldText(item.city_name)
  const location = fieldText(item.location) || fieldText(item.location_name)
  const continent = fieldText(item.continent) || fieldText(item.continent_name)
  return uniqueValues([
    datacenterRegion(item),
    region,
    location,
    city,
    country,
    country && city ? `${country} / ${city}` : '',
    country && location ? `${country} / ${location}` : '',
    region && city ? `${region} / ${city}` : '',
    continent && country ? `${continent} / ${country}` : '',
  ])
}

function datacenterMatchesRegion(item, region) {
  if (!region) return false
  return datacenterRegions(item).some((value) => valuesMatch(value, region))
}

function regionMatches(regionValue, selectedRegion) {
  if (!selectedRegion) return false
  return splitRegions(regionValue).some((value) => valuesMatch(value, selectedRegion))
}

function valuesMatch(left, right) {
  const normalizedLeft = normalizeRegion(displayRegion(left))
  const normalizedRight = normalizeRegion(displayRegion(right))
  return Boolean(normalizedLeft && normalizedRight) && normalizedLeft === normalizedRight
}

function normalizeRegion(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[\s　]+/g, '')
    .replace(/[，、|]+/g, ',')
    .replace(/[／\\]+/g, '/')
    .replace(/\/+/g, '/')
    .trim()
}

function uniqueValues(values) {
  return [...new Set(values.map((value) => String(value || '').trim()).filter(Boolean))]
}

function uniqueOptions(options) {
  const values = new Map()
  options.forEach((option) => {
    const value = fieldText(option?.value)
    if (value && !values.has(value)) values.set(value, { label: fieldText(option.label) || value, value })
  })
  return [...values.values()]
}

function fieldText(value) {
  if (value == null) return ''
  if (typeof value === 'object') {
    return String(value.name || value.label || value.title || value.value || value.code || value.id || '').trim()
  }
  return String(value).trim()
}

function splitRegions(value) {
  if (Array.isArray(value)) return value.filter(Boolean)
  return String(value || '').split(/[,，;；|]+/).map((item) => item.trim()).filter(Boolean)
}

function openRemoteEditor(row = null) {
  remoteEditor.form = createRemoteForm(row || {})
  remoteEditor.show = true
}

function openEngineerEditor(row = null) {
  engineerEditor.form = createEngineerForm(row || {})
  engineerEditor.show = true
}

function handleRemoteSiteCascaderChange(value, option) {
  if (!value) {
    remoteEditor.form.region = ''
    remoteEditor.form.site = ''
    handleEngineerSelected(null)
    return
  }
  if (!option?.site) {
    remoteEditor.form.region = displayRegion(option?.label)
    remoteEditor.form.site = ''
    handleEngineerSelected(null)
    return
  }
  remoteEditor.form.region = displayRegion(option.region)
  remoteEditor.form.site = option.site
  if (option.timezone) remoteEditor.form.timezone = option.timezone
  const validEngineers = assignableEngineerOptions.value.map((item) => item.value)
  if (!validEngineers.includes(remoteEditor.form.engineer_id)) handleEngineerSelected(null)
}

function handleEngineerSelected(value) {
  const engineer = engineers.value.find((item) => String(item.id) === String(value))
  remoteEditor.form.engineer_id = engineer?.id || null
  remoteEditor.form.engineer_name = engineer?.name || ''
  remoteEditor.form.engineer_contact = engineer?.contact || ''
  remoteEditor.form.engineer_wechat = engineer?.wechat_id || ''
  remoteEditor.form.engineer_group = engineer?.wechat_group || ''
}

function updateWorkMinutes() {
  remoteEditor.form.work_minutes = minutesBetween(remoteEditor.form.arrived_at, remoteEditor.form.left_at)
}

function minutesBetween(start, end) {
  if (!start || !end) return 0
  const value = Math.round((new Date(end).getTime() - new Date(start).getTime()) / 60000)
  return Number.isFinite(value) ? Math.max(0, value) : 0
}

async function saveRemoteHands() {
  const form = remoteEditor.form
  if (!form.customer.trim()) return message.warning('请输入客户名称')
  if (!fieldText(form.region)) return message.warning('请选择或输入地区')
  if (!form.site) return message.warning('请选择机房')
  if (!form.engineer_id) return message.warning('请选择工程师')
  remoteEditor.saving = true
  try {
    const payload = { ...form }
    delete payload.id
    delete payload.site_key
    if (form.id) await api.remoteAssistanceApi.updateRemoteHands(form.id, payload)
    else await api.remoteAssistanceApi.createRemoteHands(payload)
    message.success(form.id ? '运维记录已更新' : '运维记录已创建')
    remoteEditor.show = false
    await fetchOverview()
  } finally {
    remoteEditor.saving = false
  }
}

async function saveEngineer() {
  const form = engineerEditor.form
  if (!form.name.trim()) return message.warning('请输入工程师姓名')
  engineerEditor.saving = true
  try {
    const payload = {
      name: form.name,
      contact: form.contact,
      wechat_id: form.wechat_id,
      wechat_group: form.wechat_group,
      region: form.regions.join(', '),
      is_active: form.is_active,
      note: form.note,
    }
    if (form.id) await api.remoteAssistanceApi.updateEngineer(form.id, payload)
    else await api.remoteAssistanceApi.createEngineer(payload)
    message.success(form.id ? '工程师信息已更新' : '工程师已创建')
    engineerEditor.show = false
    await fetchOverview()
  } finally {
    engineerEditor.saving = false
  }
}

async function deleteRemoteHands(row) {
  await api.remoteAssistanceApi.deleteRemoteHands(row.id)
  message.success('运维记录已删除')
  await fetchOverview()
}

async function deleteEngineer(row) {
  await api.remoteAssistanceApi.deleteEngineer(row.id)
  message.success('工程师已删除')
  await fetchOverview()
}

async function updateRemoteStatus(row, nextStatus) {
  const now = localDateTime()
  const payload = { ...createRemoteForm(row) }
  delete payload.id
  if (nextStatus === 'arrived') {
    payload.arrived_at = now
    payload.status = 'arrived'
  } else {
    payload.left_at = now
    payload.status = 'done'
    payload.work_minutes = minutesBetween(payload.arrived_at, now)
  }
  await api.remoteAssistanceApi.updateRemoteHands(row.id, payload)
  message.success(nextStatus === 'arrived' ? '已记录到场' : '已记录离场')
  await fetchOverview()
}

async function fetchOverview() {
  loading.value = true
  try {
    const res = await api.remoteAssistanceApi.overview()
    remoteHands.value = Array.isArray(res.data?.remote_hands) ? res.data.remote_hands : []
    engineers.value = Array.isArray(res.data?.engineers) ? res.data.engineers : []
    datacenters.value = Array.isArray(res.data?.datacenters) ? res.data.datacenters : []
  } finally {
    loading.value = false
  }
}

function normalizeDateTime(value) {
  return value ? String(value).slice(0, 16) : null
}

function localDateTime() {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 16)
}

function formatDate(value) {
  return value ? String(value).slice(0, 10) : '-'
}

function formatTime(value) {
  return value ? String(value).slice(11, 16) || '-' : '-'
}

function formatDuration(value) {
  const minutes = Number(value || 0)
  if (!minutes) return '-'
  if (minutes < 60) return `${minutes} 分钟`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours}小时${rest}分钟` : `${hours} 小时`
}

function statusLabel(status) {
  return statusOptions.find((item) => item.value === status)?.label || status || '未知'
}

function statusTagType(status) {
  return { scheduled: 'warning', arrived: 'info', done: 'success', cancelled: 'default' }[status] || 'default'
}

function normalizeSettlementStatus(value) {
  const aliases = {
    unbilled: 'unbilled',
    unpaid: 'unbilled',
    pending: 'unbilled',
    '未计费': 'unbilled',
    billed: 'billed',
    invoiced: 'billed',
    '已计费': 'billed',
    settled: 'settled',
    paid: 'settled',
    completed: 'settled',
    '已结算': 'settled',
  }
  return aliases[String(value || '').trim().toLowerCase()] || 'unbilled'
}

function readSettlementStatus(source, type) {
  if (!source) return 'unbilled'
  const value = type === 'ops'
    ? source.ops_settlement_status ?? source.operation_settlement_status ?? source.ops_billing_status
    : source.customer_settlement_status ?? source.customer_billing_status
  return normalizeSettlementStatus(value)
}

function renderSettlementTag(value) {
  const normalized = normalizeSettlementStatus(value)
  const type = { unbilled: 'warning', billed: 'info', settled: 'success' }[normalized]
  const label = settlementOptions.find((item) => item.value === normalized)?.label || '未计费'
  return h(NTag, { type, bordered: false, size: 'small' }, { default: () => label })
}

function renderDeleteConfirm({ title, actionText, onConfirm }) {
  return h(NPopconfirm, {
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: onConfirm,
  }, {
    trigger: () => h(NButton, { size: 'small', type: 'error', secondary: true }, { default: () => actionText }),
    default: () => title,
  })
}

function renderNoteCell(note) {
  const content = String(note || '').trim()
  if (!content) return h('span', { class: 'muted-text' }, '无备注')
  return h(NTooltip, {
    trigger: 'hover',
    placement: 'top',
    style: { maxWidth: '520px', whiteSpace: 'pre-wrap', lineHeight: '1.6' },
  }, {
    trigger: () => h('div', { class: 'note-cell' }, content),
    default: () => content,
  })
}

onMounted(fetchOverview)
</script>

<style scoped>
.collaboration-page {
  display: flex;
  height: calc(100vh - 132px);
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.summary-grid article,
.workspace-panel {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
}

.summary-grid article {
  display: flex;
  min-height: 94px;
  align-items: center;
  gap: 14px;
  padding: 18px;
}

.summary-grid small {
  display: block;
  margin-bottom: 5px;
  color: #7b8798;
  font-size: 13px;
}

.summary-grid strong {
  color: #172033;
  font-size: 25px;
  line-height: 1;
}

.summary-icon {
  display: grid;
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  place-items: center;
  border-radius: 8px;
}

.summary-icon.orange { background: #fff1eb; color: #f4511e; }
.summary-icon.blue { background: #eaf3ff; color: #2775d7; }
.summary-icon.green { background: #e8f7ef; color: #15945c; }
.summary-icon.gray { background: #f0f2f5; color: #5c6878; }

.workspace-panel {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  overflow: hidden;
  padding: 20px;
}

.workspace-panel :deep(.n-tabs),
.workspace-panel :deep(.n-tabs-pane-wrapper),
.workspace-panel :deep(.n-tab-pane) {
  min-height: 0;
  flex: 1;
}

.workspace-panel :deep(.n-tabs-pane-wrapper) {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.workspace-panel :deep(.n-tab-pane) {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.workspace-panel :deep(.n-data-table) {
  flex: 1;
  min-height: 0;
}

.table-toolbar,
.modal-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.table-toolbar {
  padding: 8px 0 16px;
}

.filter-row {
  display: grid;
  width: min(780px, 72%);
  grid-template-columns: minmax(180px, 1fr) minmax(180px, 1fr) 160px;
  gap: 10px;
}

.engineer-search { grid-template-columns: minmax(280px, 520px); }

:deep(.primary-cell) {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

:deep(.primary-cell strong) { color: #172033; }
:deep(.primary-cell small) { overflow: hidden; color: #7b8798; text-overflow: ellipsis; white-space: nowrap; }
:deep(.note-cell) {
  display: -webkit-box;
  overflow: hidden;
  color: #1f2937;
  line-height: 1.55;
  white-space: normal;
  word-break: break-word;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
:deep(.muted-text) { color: #9ca3af; }

.editor-modal { width: min(900px, calc(100vw - 32px)); }
.engineer-editor-modal { width: min(760px, calc(100vw - 32px)); }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; column-gap: 22px; }
.modal-actions { justify-content: flex-end; }

@media (max-width: 900px) {
  .summary-grid { grid-template-columns: 1fr 1fr; }
  .table-toolbar { align-items: stretch; flex-direction: column; }
  .filter-row { width: 100%; }
  .form-grid { grid-template-columns: 1fr; }
}

@media (max-width: 560px) {
  .summary-grid { grid-template-columns: 1fr; }
  .filter-row { grid-template-columns: 1fr; }
  .workspace-panel { padding: 14px; }
}
</style>
