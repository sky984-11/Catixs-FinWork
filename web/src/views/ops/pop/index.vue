<template>
  <AppPage :show-footer="false">
    <div class="pop-page">
      <section class="pop-summary">
        <article>
          <span class="summary-icon blue"><TheIcon icon="mdi:earth" :size="21" /></span>
          <div><small>国家/城市</small><strong>{{ regions.length }}</strong></div>
        </article>
        <article>
          <span class="summary-icon green"><TheIcon icon="mdi:office-building-marker-outline" :size="21" /></span>
          <div><small>机房</small><strong>{{ roomLocations.length }}</strong></div>
        </article>
        <article>
          <span class="summary-icon orange"><TheIcon icon="mdi:server-network" :size="21" /></span>
          <div><small>机柜</small><strong>{{ cabinets.length }}</strong></div>
        </article>
      </section>

      <section class="pop-panel">
        <n-tabs v-model:value="activeTab" type="line" animated>
          <n-tab-pane name="region" tab="国家 / 城市">
            <div class="table-toolbar">
              <n-input v-model:value="regionKeyword" clearable placeholder="搜索国家、城市、POP名称或代码">
                <template #prefix><TheIcon icon="mdi:magnify" :size="17" /></template>
              </n-input>
              <n-space>
                <n-button secondary circle :loading="loading" title="刷新" @click="loadData">
                  <template #icon><TheIcon icon="mdi:refresh" :size="18" /></template>
                </n-button>
                <n-button type="primary" round @click="openRegionEditor()">
                  <template #icon><TheIcon icon="mdi:plus" :size="18" /></template>
                  新增国家/城市
                </n-button>
              </n-space>
            </div>
            <n-data-table
              :loading="loading"
              :columns="regionColumns"
              :data="regionTableData"
              :pagination="regionPagination"
              :row-key="(row) => row.id"
              striped
            />
          </n-tab-pane>

          <n-tab-pane name="location" tab="机房">
            <div class="table-toolbar">
              <div class="filter-row">
                <n-cascader
                  v-model:value="locationRegionFilter"
                  clearable
                  filterable
                  check-strategy="child"
                  :show-path="true"
                  :options="regionCascaderOptions"
                  placeholder="按国家 / 城市筛选"
                />
                <n-input v-model:value="locationKeyword" clearable placeholder="搜索机房名称、地址或备注">
                  <template #prefix><TheIcon icon="mdi:magnify" :size="17" /></template>
                </n-input>
              </div>
              <n-space>
                <n-button secondary circle :loading="loading" title="刷新" @click="loadData">
                  <template #icon><TheIcon icon="mdi:refresh" :size="18" /></template>
                </n-button>
                <n-button type="primary" round @click="openLocationEditor()">
                  <template #icon><TheIcon icon="mdi:plus" :size="18" /></template>
                  新增机房
                </n-button>
              </n-space>
            </div>
            <n-data-table
              :loading="loading"
              :columns="locationColumns"
              :data="locationTableData"
              :pagination="locationPagination"
              :row-key="(row) => row.id"
              striped
            />
          </n-tab-pane>
        </n-tabs>
      </section>

      <n-modal
        v-model:show="regionEditor.show"
        preset="card"
        :title="regionEditor.form.id ? '编辑国家/城市' : '新增国家/城市'"
        class="editor-modal"
        :bordered="false"
      >
        <n-form label-placement="top" :model="regionEditor.form">
          <div class="form-grid">
            <n-form-item label="国家" required>
              <n-input v-model:value="regionEditor.form.country" placeholder="例如 United Kingdom" />
            </n-form-item>
            <n-form-item label="城市" required>
              <n-input v-model:value="regionEditor.form.city" placeholder="例如 香港" />
            </n-form-item>
            <n-form-item label="城市代码" required>
              <n-input
                v-model:value="regionEditor.form.code"
                placeholder="例如 HK"
                maxlength="50"
                @update:value="(value) => (regionEditor.form.code = normalizeRegionCode(value))"
              />
            </n-form-item>
          </div>
          <n-checkbox v-model:checked="regionEditor.form.status">启用</n-checkbox>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="regionEditor.show = false">取消</n-button>
            <n-button type="primary" :loading="regionEditor.submitting" @click="submitRegion">保存</n-button>
          </n-space>
        </template>
      </n-modal>

      <n-modal
        v-model:show="locationEditor.show"
        preset="card"
        :title="locationEditor.form.id ? '编辑机房' : '新增机房'"
        class="editor-modal"
        :bordered="false"
      >
        <n-form label-placement="top" :model="locationEditor.form">
          <n-form-item label="所属国家/城市" required>
            <n-cascader
              v-model:value="locationEditor.form.region_id"
              clearable
              filterable
              check-strategy="child"
              :show-path="true"
              :options="regionCascaderOptions"
              placeholder="选择国家 / 城市"
            />
          </n-form-item>
          <div class="form-grid">
            <n-form-item label="机房名称" required>
              <n-input v-model:value="locationEditor.form.name" placeholder="例如 LD8" />
            </n-form-item>
            <n-form-item label="状态">
              <n-checkbox v-model:checked="locationEditor.form.status">启用</n-checkbox>
            </n-form-item>
          </div>
          <n-form-item label="地址">
            <n-input v-model:value="locationEditor.form.address" placeholder="机房地址" />
          </n-form-item>
          <n-form-item label="备注">
            <n-input v-model:value="locationEditor.form.remark" type="textarea" />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="locationEditor.show = false">取消</n-button>
            <n-button type="primary" :loading="locationEditor.submitting" @click="submitLocation">保存</n-button>
          </n-space>
        </template>
      </n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NPopconfirm, NSpace, NTag, useMessage } from 'naive-ui'
import api from '@/api'

const message = useMessage()
const loading = ref(false)
const activeTab = ref('region')
const regions = ref([])
const locations = ref([])
const cabinets = ref([])
const regionKeyword = ref('')
const locationKeyword = ref('')
const locationRegionFilter = ref(null)

const regionPagination = reactive({
  pageSize: 20,
  showSizePicker: true,
  pageSizes: [20, 50, 100],
})

const locationPagination = reactive({
  pageSize: 20,
  showSizePicker: true,
  pageSizes: [20, 50, 100],
})

const regionEditor = reactive({
  show: false,
  submitting: false,
  form: createRegionForm(),
})

const locationEditor = reactive({
  show: false,
  submitting: false,
  form: createLocationForm(),
})

const roomLocations = computed(() => locations.value.filter((item) => Number(item.type) === 1))

const regionCascaderOptions = computed(() => {
  const countryMap = new Map()
  regions.value.forEach((region) => {
    const country = String(region.country || '未分组').trim() || '未分组'
    if (!countryMap.has(country)) {
      countryMap.set(country, {
        label: country,
        value: `country:${country}`,
        children: [],
      })
    }
    countryMap.get(country).children.push({
      label: cityOptionLabel(region),
      value: region.id,
    })
  })

  return [...countryMap.values()]
    .map((country) => ({
      ...country,
      children: country.children.sort((a, b) => String(a.label).localeCompare(String(b.label), 'zh-Hans-CN')),
    }))
    .sort((a, b) => String(a.label).localeCompare(String(b.label), 'zh-Hans-CN'))
})

const filteredRegions = computed(() => {
  const keyword = normalize(regionKeyword.value)
  if (!keyword) return regions.value
  return regions.value.filter((item) =>
    [item.country, item.city, item.name, item.code, item.remark].some((value) => normalize(value).includes(keyword))
  )
})

const filteredLocations = computed(() => {
  const keyword = normalize(locationKeyword.value)
  return roomLocations.value.filter((item) => {
    const regionMatched = isLocationRegionMatched(item, locationRegionFilter.value)
    const keywordMatched =
      !keyword ||
      [item.name, item.address, item.remark, regionLabel(regionById(item.region_id))].some((value) =>
        normalize(value).includes(keyword)
      )
    return regionMatched && keywordMatched
  })
})

const regionTableData = computed(() => filteredRegions.value.slice())
const locationTableData = computed(() => filteredLocations.value.slice())

const regionColumns = [
  {
    title: '国家 / 城市',
    key: 'country',
    minWidth: 220,
    render: (row) =>
        h('div', { class: 'primary-cell' }, [
          h('strong', [row.country, row.city].filter(Boolean).join(' / ') || row.name || '-'),
          h('small', row.code || '-'),
        ]),
  },
  { title: '机房数', key: 'room_count', width: 100, render: (row) => locationCount(row.id) },
  { title: '机柜数', key: 'cabinet_count', width: 100, render: (row) => cabinetCountByRegion(row.id) },
  {
    title: '状态',
    key: 'status',
    width: 90,
    render: (row) =>
      h(NTag, { type: row.status ? 'success' : 'default', bordered: false, size: 'small' }, {
        default: () => (row.status ? '启用' : '停用'),
      }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 210,
    fixed: 'right',
    render: (row) =>
      h(NSpace, { size: 6, wrap: false }, {
        default: () => [
          h(NButton, { size: 'small', type: 'primary', secondary: true, onClick: () => openRegionEditor(row) }, { default: () => '编辑' }),
          h(NButton, { size: 'small', secondary: true, onClick: () => openLocationEditor({ region_id: row.id }) }, { default: () => '加机房' }),
          renderDeleteConfirm({
            title: `确认删除 ${row.name || row.code || '该POP'}？`,
            disabled: locationCount(row.id) > 0,
            disabledTip: '该国家/城市下还有机房，不能删除',
            onConfirm: () => deleteRegion(row),
          }),
        ],
      }),
  },
]

const locationColumns = [
  {
    title: '机房',
    key: 'name',
    minWidth: 210,
    render: (row) =>
      h('div', { class: 'primary-cell' }, [
        h('strong', row.name || '-'),
        h('small', regionLabel(regionById(row.region_id))),
      ]),
  },
  { title: '地址', key: 'address', minWidth: 240, ellipsis: { tooltip: true } },
  { title: '机柜数', key: 'cabinet_count', width: 100, render: (row) => cabinetCountByLocation(row.id) },
  {
    title: '状态',
    key: 'status',
    width: 90,
    render: (row) =>
      h(NTag, { type: row.status ? 'success' : 'default', bordered: false, size: 'small' }, {
        default: () => (row.status ? '启用' : '停用'),
      }),
  },
  { title: '备注', key: 'remark', minWidth: 180, ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    fixed: 'right',
    render: (row) =>
      h(NSpace, { size: 6, wrap: false }, {
        default: () => [
          h(NButton, { size: 'small', type: 'primary', secondary: true, onClick: () => openLocationEditor(row) }, { default: () => '编辑' }),
          renderDeleteConfirm({
            title: `确认删除机房 ${row.name || ''}？`,
            disabled: cabinetCountByLocation(row.id) > 0,
            disabledTip: '该机房下还有机柜，不能删除',
            onConfirm: () => deleteLocation(row),
          }),
        ],
      }),
  },
]

function createRegionForm(row = {}) {
  return {
    id: row.id,
    country: row.country || '',
    city: row.city || '',
    name: row.name || '',
    code: row.code || '',
    remark: row.remark || '',
    status: row.status ?? true,
  }
}

function normalizeRegionRow(row = {}) {
  const country = String(row.country || '').trim()
  const city = String(row.city || '').trim()
  const name = String(row.name || [country, city].filter(Boolean).join(' / ')).trim()
  return {
    ...row,
    country: country || inferCountryFromName(name),
    city: city || inferCityFromName(name),
    name: name || [country, city].filter(Boolean).join(' / '),
  }
}

function createLocationForm(row = {}) {
  return {
    id: row.id,
    region_id: row.region_id || null,
    name: row.name || '',
    type: 1,
    address: row.address || '',
    remark: row.remark || '',
    status: row.status ?? true,
  }
}

async function loadData() {
  loading.value = true
  try {
    const [regionRes, locationRes, cabinetRes] = await Promise.all([
      api.assetApi.regions({ page_size: 1000 }),
      api.assetApi.locations({ page_size: 1000 }),
      api.assetApi.cabinets({ page_size: 1000 }),
    ])
    regions.value = (regionRes.data || []).map(normalizeRegionRow)
    locations.value = locationRes.data || []
    cabinets.value = cabinetRes.data || []
  } finally {
    loading.value = false
  }
}

function openRegionEditor(row = null) {
  regionEditor.form = createRegionForm(row || {})
  regionEditor.show = true
}

async function submitRegion() {
  const form = regionEditor.form
  const country = String(form.country || '').trim()
  const city = String(form.city || '').trim()
  const code = normalizeRegionCode(form.code)
  if (!country || !city || !code) {
    message.warning('请填写国家、城市和城市代码')
    return
  }
  regionEditor.submitting = true
  try {
    const finalCode = makeRegionCode(code, country, city, form.id)
    const payload = {
      ...form,
      country,
      city,
      name: `${country} / ${city}`,
      code: finalCode,
      remark: '',
      status: Boolean(form.status),
    }
    const res = payload.id ? await api.assetApi.updateRegion(payload) : await api.assetApi.createRegion(payload)
    const savedRegion = normalizeRegionRow({
      ...payload,
      ...(res.data || {}),
    })
    upsertRegion(savedRegion)
    regionKeyword.value = ''
    locationRegionFilter.value = savedRegion.id || locationRegionFilter.value
    regionEditor.show = false
    await loadData()
    if (savedRegion.id && !regions.value.some((item) => item.id === savedRegion.id)) {
      upsertRegion(savedRegion)
    }
    message.success('国家/城市已保存')
  } finally {
    regionEditor.submitting = false
  }
}

function openLocationEditor(row = null) {
  locationEditor.form = createLocationForm({
    ...(row || {}),
    region_id: row?.region_id || row?.id || locationRegionFilter.value || regions.value[0]?.id || null,
  })
  locationEditor.show = true
}

async function submitLocation() {
  const form = locationEditor.form
  const name = String(form.name || '').trim()
  const regionId = Number(form.region_id)
  if (!regionById(regionId) || !name) {
    message.warning('请选择国家/城市并填写机房名称')
    return
  }
  locationEditor.submitting = true
  try {
    const payload = {
      ...form,
      region_id: regionId,
      name,
      type: 1,
      address: String(form.address || '').trim(),
      remark: String(form.remark || '').trim(),
      status: Boolean(form.status),
    }
    if (payload.id) await api.assetApi.updateLocation(payload)
    else await api.assetApi.createLocation(payload)
    locationEditor.show = false
    await loadData()
    message.success('机房已保存')
  } finally {
    locationEditor.submitting = false
  }
}

async function deleteRegion(row) {
  await api.assetApi.deleteRegion({ region_id: row.id })
  await loadData()
  message.success('国家/城市已删除')
}

async function deleteLocation(row) {
  await api.assetApi.deleteLocation({ location_id: row.id })
  await loadData()
  message.success('机房已删除')
}

function regionById(id) {
  return regions.value.find((item) => item.id === id) || null
}

function isLocationRegionMatched(location, selectedValue) {
  if (!selectedValue) return true
  if (typeof selectedValue === 'string' && selectedValue.startsWith('country:')) {
    const country = selectedValue.slice('country:'.length)
    return regionById(location.region_id)?.country === country
  }
  return location.region_id === Number(selectedValue)
}

function upsertRegion(region) {
  if (!region?.id) return
  const index = regions.value.findIndex((item) => item.id === region.id)
  if (index >= 0) regions.value.splice(index, 1, region)
  else regions.value.unshift(region)
}

function regionLabel(region) {
  if (!region) return '-'
  const place = [region.country, region.city].filter(Boolean).join(' / ')
  return place || region.name || '-'
}

function cityOptionLabel(region) {
  const city = region.city || region.name || '-'
  return region.code ? `${city} (${region.code})` : city
}

function locationCount(regionId) {
  return roomLocations.value.filter((item) => item.region_id === regionId).length
}

function cabinetCountByRegion(regionId) {
  const locationIds = new Set(roomLocations.value.filter((item) => item.region_id === regionId).map((item) => item.id))
  return cabinets.value.filter((item) => locationIds.has(item.location_id)).length
}

function cabinetCountByLocation(locationId) {
  return cabinets.value.filter((item) => item.location_id === locationId).length
}

function normalize(value) {
  return String(value || '').trim().toLowerCase()
}

function inferCountryFromName(name) {
  const parts = String(name || '').split('/').map((item) => item.trim()).filter(Boolean)
  return parts.length > 1 ? parts[0] : ''
}

function inferCityFromName(name) {
  const parts = String(name || '').split('/').map((item) => item.trim()).filter(Boolean)
  return parts.length > 1 ? parts[1] : ''
}

function normalizeRegionCode(value) {
  return String(value || '')
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9-]+/g, '')
    .slice(0, 50)
}

function makeRegionCode(rawCode, country, city, currentId) {
  const base = normalizeRegionCode(rawCode) || String(city || country || 'POP')
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 24) || 'POP'
  const countryPart = String(country || '')
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 12)

  let nextCode = base
  const usedByOther = (value) => regions.value.some((item) => item.code === value && item.id !== currentId)
  if (usedByOther(nextCode) && countryPart) nextCode = `${countryPart}-${base}`.slice(0, 50)
  let index = 2
  while (usedByOther(nextCode)) {
    const suffix = `-${index}`
    nextCode = `${base.slice(0, 50 - suffix.length)}${suffix}`
    index += 1
  }
  return nextCode
}

function renderDeleteConfirm({ title, disabled, disabledTip, onConfirm }) {
  if (disabled) {
    return h(NButton, { size: 'small', type: 'error', secondary: true, disabled: true, title: disabledTip }, { default: () => '删除' })
  }
  return h(NPopconfirm, {
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: onConfirm,
  }, {
    trigger: () => h(NButton, { size: 'small', type: 'error', secondary: true }, { default: () => '删除' }),
    default: () => title,
  })
}

onMounted(loadData)
</script>

<style scoped>
.pop-page {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  gap: 10px;
  background: #f5f7fb;
  padding: 10px;
}

.pop-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.pop-summary article {
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background: #fff;
  padding: 12px 14px;
}

.summary-icon {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 8px;
}

.summary-icon.blue {
  background: #e0f2fe;
  color: #0369a1;
}

.summary-icon.green {
  background: #dcfce7;
  color: #15803d;
}

.summary-icon.orange {
  background: #ffedd5;
  color: #c2410c;
}

.pop-summary small {
  display: block;
  color: #64748b;
  font-size: 12px;
}

.pop-summary strong {
  color: #0f172a;
  font-size: 22px;
  line-height: 1.1;
}

.pop-panel {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background: #fff;
  padding: 10px;
}

.pop-panel :deep(.n-tabs),
.pop-panel :deep(.n-tab-pane),
.pop-panel :deep(.n-data-table) {
  min-height: 0;
}

.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.table-toolbar > .n-input {
  max-width: 420px;
}

.filter-row {
  display: grid;
  width: min(680px, 100%);
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 8px;
}

.primary-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.primary-cell strong,
.primary-cell small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.primary-cell strong {
  color: #0f172a;
  font-weight: 700;
}

.primary-cell small {
  color: #64748b;
  font-size: 12px;
}

.editor-modal {
  width: min(680px, calc(100vw - 32px));
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 12px;
}

@media (max-width: 760px) {
  .pop-summary,
  .filter-row,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .table-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .table-toolbar > .n-input {
    max-width: none;
  }
}
</style>
