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
          <div><small>待执行计划</small><strong>{{ pendingPlanCount }}</strong></div>
        </article>
      </section>

      <section class="workspace-panel">
        <n-tabs v-model:value="activeTab" type="line" animated>
          <n-tab-pane name="plans" tab="运维计划">
            <div class="table-toolbar">
              <div class="filter-row">
                <n-select
                  v-model:value="planFilters.assignee_id"
                  clearable
                  filterable
                  placeholder="按负责人筛选"
                  :options="planAssigneeOptions"
                />
                <n-cascader
                  v-model:value="planFilters.site_key"
                  clearable
                  filterable
                  show-path
                  check-strategy="child"
                  placeholder="按地区 / 机房筛选"
                  :options="siteCascaderOptions"
                  :filter="siteCascaderFilter"
                  @update:value="handlePlanFilterSiteChange"
                />
                <n-select
                  v-model:value="planFilters.status"
                  clearable
                  placeholder="计划状态"
                  :options="planStatusOptions"
                />
              </div>
              <n-space>
                <n-button secondary circle :loading="loading" title="刷新" @click="fetchOverview">
                  <template #icon><TheIcon icon="mdi:refresh" :size="18" /></template>
                </n-button>
                <n-button type="primary" round @click="openPlanEditor()">
                  <template #icon><TheIcon icon="mdi:calendar-plus" :size="18" /></template>
                  新增运维计划
                </n-button>
              </n-space>
            </div>
            <n-data-table
              :loading="loading"
              :columns="planColumns"
              :data="filteredPlans"
              :pagination="planPagination"
              :row-key="(row) => row.id"
              flex-height
              :scroll-x="1600"
              striped
            >
              <template #empty><n-empty description="暂无运维计划" /></template>
            </n-data-table>
          </n-tab-pane>

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
                <n-cascader
                  v-model:value="remoteFilters.site_key"
                  clearable
                  filterable
                  show-path
                  check-strategy="child"
                  placeholder="按地区 / 机房筛选"
                  :options="siteCascaderOptions"
                  :filter="siteCascaderFilter"
                  @update:value="handleRemoteFilterSiteChange"
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
        style="width: min(640px, calc(100vw - 40px))"
        :bordered="false"
      >
        <n-form class="remote-form" label-placement="left" label-width="76" size="small" :model="remoteEditor.form">
          <div class="remote-form-grid">
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
                :filter="siteCascaderFilter"
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
                @update:formatted-value="updateWorkMinutes"
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
          <div class="modal-actions compact-modal-actions">
            <CButton
              show-cancel
              show-save
              size="small"
              :save-loading="remoteEditor.saving"
              @cancel="remoteEditor.show = false"
              @save="saveRemoteHands"
            />
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="planEditor.show"
        preset="card"
        :title="planEditor.form.id ? '变更运维计划' : '新增运维计划'"
        class="editor-modal remote-editor-modal"
        style="width: min(680px, calc(100vw - 40px))"
        :bordered="false"
      >
        <n-form class="remote-form" label-placement="left" label-width="90" size="small" :model="planEditor.form">
          <div class="remote-form-grid">
            <n-form-item label="客户" required>
              <n-input v-model:value="planEditor.form.customer" placeholder="客户名称" />
            </n-form-item>
            <n-form-item label="工单号">
              <n-input v-model:value="planEditor.form.ticket" placeholder="关联工单号" />
            </n-form-item>
            <n-form-item label="机房" required>
              <n-cascader
                v-model:value="planEditor.form.site_key"
                filterable
                clearable
                show-path
                :options="siteCascaderOptions"
                :filter="siteCascaderFilter"
                placeholder="选择地区 / 机房"
                @update:value="handlePlanSiteCascaderChange"
              />
            </n-form-item>
            <n-form-item label="工程师">
              <n-select
                v-model:value="planEditor.form.engineer_id"
                filterable
                clearable
                :options="assignablePlanEngineerOptions"
                :disabled="!planEditor.form.region"
                :placeholder="planEditor.form.region ? '选择启用工程师' : '请先选择地区'"
                @update:value="handlePlanEngineerSelected"
              />
            </n-form-item>
            <n-form-item label="计划时间" required>
              <n-date-picker
                v-model:formatted-value="planEditor.form.planned_at"
                type="datetime"
                format="yyyy-MM-dd HH:mm"
                value-format="yyyy-MM-dd'T'HH:mm"
                :actions="datePickerActions"
                :time-picker-props="minuteTimePickerProps"
                clearable
                style="width: 100%"
              />
            </n-form-item>
            <n-form-item label="通知负责人">
              <n-select
                v-model:value="planEditor.form.assignee_ids"
                multiple
                filterable
                clearable
                max-tag-count="responsive"
                :options="userOptions"
                placeholder="选择飞书通知接收人"
              />
            </n-form-item>
          </div>
          <n-form-item label="计划说明">
            <n-input
              v-model:value="planEditor.form.note"
              type="textarea"
              placeholder="计划内容、到场要求、交接信息"
              :autosize="{ minRows: 3, maxRows: 6 }"
            />
          </n-form-item>
          <n-checkbox v-model:checked="planEditor.form.notify">{{ planEditor.form.id ? '保存后发送飞书通知' : '创建后立即发送飞书通知' }}</n-checkbox>
        </n-form>
        <template #footer>
          <div class="modal-actions compact-modal-actions">
            <CButton
              show-cancel
              show-save
              size="small"
              :save-loading="planEditor.saving"
              @cancel="planEditor.show = false"
              @save="savePlan"
            />
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="completeEditor.show"
        preset="card"
        title="完成运维计划"
        class="editor-modal engineer-editor-modal"
        style="width: min(460px, calc(100vw - 40px))"
        :bordered="false"
      >
        <n-form class="remote-form" label-placement="left" label-width="82" size="small" :model="completeEditor.form">
          <n-form-item label="到场时间" required>
            <n-date-picker
              v-model:formatted-value="completeEditor.form.arrived_at"
              type="datetime"
              format="yyyy-MM-dd HH:mm"
              value-format="yyyy-MM-dd'T'HH:mm"
              :actions="datePickerActions"
              :time-picker-props="minuteTimePickerProps"
              @update:formatted-value="handleCompleteArrivedAtChange"
              clearable
              style="width: 100%"
            />
          </n-form-item>
          <n-form-item label="离场时间" required>
            <n-date-picker
              v-model:formatted-value="completeEditor.form.left_at"
              type="datetime"
              format="yyyy-MM-dd HH:mm"
              value-format="yyyy-MM-dd'T'HH:mm"
              :actions="datePickerActions"
              :time-picker-props="minuteTimePickerProps"
              clearable
              style="width: 100%"
            />
          </n-form-item>
          <n-form-item label="备注">
            <n-input
              v-model:value="completeEditor.form.note"
              type="textarea"
              placeholder="完成情况、交接信息或其他说明"
              :autosize="{ minRows: 3, maxRows: 5 }"
            />
          </n-form-item>
        </n-form>
        <template #footer>
          <div class="modal-actions compact-modal-actions">
            <CButton
              show-cancel
              show-save
              size="small"
              save-text="完成"
              :save-loading="completeEditor.saving"
              @cancel="completeEditor.show = false"
              @save="submitCompletePlan"
            />
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="engineerEditor.show"
        preset="card"
        :title="engineerEditor.form.id ? '编辑工程师' : '新增工程师'"
        class="editor-modal engineer-editor-modal"
        style="width: min(420px, calc(100vw - 40px))"
        :bordered="false"
      >
        <n-form class="engineer-form" label-placement="left" label-width="76" size="small" :model="engineerEditor.form">
          <div class="engineer-form-grid">
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
              <n-cascader
                v-model:value="engineerEditor.form.regions"
                multiple
                filterable
                clearable
                :show-path="false"
                check-strategy="child"
                max-tag-count="responsive"
                :options="regionCascaderOptions"
                :filter="regionCascaderFilter"
                placeholder="选择一个或多个地区"
              />
            </n-form-item>
            <n-form-item label="状态">
              <n-switch
                v-model:value="engineerEditor.form.is_active"
                :checked-value="1"
                :unchecked-value="0"
              >
                <template #checked>启用</template>
                <template #unchecked>停用</template>
              </n-switch>
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
          <div class="modal-actions engineer-modal-actions">
            <CButton
              show-cancel
              show-save
              size="small"
              :save-loading="engineerEditor.saving"
              @cancel="engineerEditor.show = false"
              @save="saveEngineer"
            />
          </div>
        </template>
      </n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NPopconfirm, NSpace, NSelect, NTag, NTooltip, useMessage } from 'naive-ui'
import api from '@/api'
import CButton from '@/components/public/CButton.vue'
import { translateCity, translateCountry, translateLocationPath } from '@/utils/location-i18n'

const message = useMessage()
const loading = ref(false)
const remoteSettlementSaving = ref(new Set())
const activeTab = ref('plans')
const remoteHands = ref([])
const plans = ref([])
const engineers = ref([])
const users = ref([])
const datacenters = ref([])
const popRegions = ref([])
const engineerKeyword = ref('')

const remoteFilters = reactive({ engineer_id: null, site: null, site_key: null, status: null })
const planFilters = reactive({ assignee_id: null, site: null, site_key: null, status: null })
const datePickerActions = ['clear', 'now', 'confirm']
const minuteTimePickerProps = { format: 'HH:mm' }
const regionAliasMap = new Map([
  ['hk', '香港'],
  ['hongkong', '香港'],
  ['hong kong', '香港'],
  ['newyork', '纽约'],
  ['new york', '纽约'],
  ['ny', '纽约'],
  ['ny2', '纽约'],
  ['secaucus', '纽约'],
  ['secaucus usa', '纽约'],
  ['losangeles', '洛杉矶'],
  ['los angeles', '洛杉矶'],
  ['la', '洛杉矶'],
  ['la3', '洛杉矶'],
  ['london', '伦敦'],
  ['lon', '伦敦'],
  ['ashburn', '阿什本'],
  ['frankfurt', '法兰克福'],
  ['frankfurtammain', '法兰克福'],
  ['frankfurt am main', '法兰克福'],
  ['fra', '法兰克福'],
  ['tokyo', '东京'],
  ['singapore', '新加坡'],
  ['taipei', '台北'],
  ['seoul', '首尔'],
])
const pinyinCharMap = {
  中: 'zhong', 国: 'guo', 香: 'xiang', 港: 'gang', 德: 'de', 法: 'fa', 兰: 'lan', 克: 'ke', 福: 'fu',
  美: 'mei', 纽: 'niu', 约: 'yue', 洛: 'luo', 杉: 'shan', 矶: 'ji', 伦: 'lun', 敦: 'dun',
  阿: 'a', 什: 'shi', 本: 'ben', 日: 'ri', 东: 'dong', 京: 'jing', 新: 'xin', 加: 'jia', 坡: 'po',
  台: 'tai', 北: 'bei', 首: 'shou', 尔: 'er', 荷: 'he', 斯: 'si', 特: 'te', 丹: 'dan',
  曼: 'man', 谷: 'gu', 迪: 'di', 拜: 'bai', 芝: 'zhi', 哥: 'ge', 达: 'da', 拉: 'la',
  布: 'bu', 宜: 'yi', 诺: 'nuo', 艾: 'ai', 利: 'li', 塔: 'ta', 贝: 'bei', 卡: 'ka',
  西: 'xi', 机: 'ji', 房: 'fang', 数: 'shu', 据: 'ju', 心: 'xin',
}
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
const planPagination = reactive({
  page: 1,
  pageSize: 10,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
  onUpdatePage: (page) => {
    planPagination.page = page
  },
  onUpdatePageSize: (pageSize) => {
    planPagination.pageSize = pageSize
    planPagination.page = 1
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

const planStatusOptions = [
  { label: '待执行', value: 'pending' },
  { label: '已完成', value: 'done' },
  { label: '已取消', value: 'cancelled' },
]

const remoteEditor = reactive({ show: false, saving: false, form: createRemoteForm() })
const planEditor = reactive({ show: false, saving: false, form: createPlanForm() })
const completeEditor = reactive({ show: false, saving: false, form: createCompleteForm() })
const engineerEditor = reactive({ show: false, saving: false, form: createEngineerForm() })

const statusCount = computed(() => ({
  scheduled: remoteHands.value.filter((item) => item.status === 'scheduled').length,
  arrived: remoteHands.value.filter((item) => item.status === 'arrived').length,
  done: remoteHands.value.filter((item) => item.status === 'done').length,
}))

const activeEngineerCount = computed(
  () => engineers.value.filter((item) => Number(item.is_active) === 1).length
)

const pendingPlanCount = computed(
  () => plans.value.filter((item) => item.status === 'pending').length
)

const userOptions = computed(() => users.value
  .filter((item) => item.id && item.is_active !== false && Number(item.is_active) !== 0)
  .map((item) => ({
    label: item.label || item.nick_name || item.username || `用户 ${item.id}`,
    value: item.id,
  })))

const regionCascaderOptions = computed(() => {
  const roots = []
  popRegions.value.forEach((item) => ensureRegionPath(roots, popRegionPathParts(item)))
  return sortCascaderTree(roots)
})

const siteCascaderOptions = computed(() => {
  const roots = []
  const addSite = ({ region, site, label, timezone, searchText }) => {
    const regionLabel = displayRegion(region)
    const siteValue = fieldText(site)
    if (!regionLabel || !siteValue) return
    const value = siteCascaderValue(regionLabel, siteValue)
    const parent = ensureCascaderPath(roots, regionPathParts(regionLabel), 'region')
    if (parent.children.some((item) => item.value === value)) return
    parent.children.push({
      label: fieldText(label) || siteValue,
      value,
      region: regionLabel,
      site: siteValue,
      timezone,
      searchText: uniqueValues([regionLabel, siteValue, label, searchText]).join(' '),
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
      searchText: datacenterSearchText(item),
    })
  })
  remoteHands.value.forEach((item) => addSite({
    region: item.region,
    site: item.site,
    label: item.site,
    timezone: item.timezone,
    searchText: [item.region, item.site].filter(Boolean).join(' '),
  }))

  return sortCascaderTree(roots)
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

const assignablePlanEngineerOptions = computed(() => {
  if (!planEditor.form.region) return []
  return engineers.value
    .filter((item) => Number(item.is_active) === 1)
    .filter((item) => regionMatches(engineerRegions(item), planEditor.form.region))
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

const planAssigneeOptions = computed(() => userOptions.value)

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

const filteredPlans = computed(() => {
  return plans.value.filter((item) => {
    if (planFilters.status && item.status !== planFilters.status) return false
    if (planFilters.site && !valuesMatch(item.site, planFilters.site)) return false
    if (planFilters.assignee_id) {
      const ids = Array.isArray(item.assignee_ids) ? item.assignee_ids.map(String) : []
      if (!ids.includes(String(planFilters.assignee_id))) return false
    }
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
  { title: '日期', key: 'date', width: 135, render: (row) => formatRemoteDateRange(row) },
  { title: '到场', key: 'arrived_at', width: 105, render: (row) => formatTime(row.arrived_at) },
  { title: '离场', key: 'left_at', width: 125, render: (row) => formatRemoteEndTime(row) },
  { title: '工时', key: 'work_minutes', width: 95, render: (row) => formatDuration(row.work_minutes) },
  {
    title: '状态', key: 'status', width: 100,
    render: (row) => h(NTag, { type: statusTagType(row.status), bordered: false, size: 'small' },
      { default: () => statusLabel(row.status) }),
  },
  {
    title: '运维结算', key: 'ops_settlement_status', width: 130,
    render: (row) => renderSettlementSelect(row, 'ops'),
  },
  {
    title: '客户结算', key: 'customer_settlement_status', width: 130,
    render: (row) => renderSettlementSelect(row, 'customer'),
  },
  {
    title: '备注', key: 'note', width: 360,
    render: (row) => renderNoteCell(row.note),
  },
  {
    title: '操作', key: 'actions', width: 260, fixed: 'right',
    render: (row) => h(NSpace, { size: 6, wrap: false }, {
      default: () => [
        row.status === 'scheduled' && !row.left_at
          ? h(NButton, { size: 'tiny', type: 'success', secondary: true, round: true, onClick: () => updateRemoteStatus(row, 'arrived') }, { default: () => '到场' })
          : null,
        row.status === 'arrived' && row.arrived_at && !row.left_at
          ? h(NButton, { size: 'tiny', type: 'warning', secondary: true, round: true, onClick: () => updateRemoteStatus(row, 'done') }, { default: () => '离场' })
          : null,
        h(NButton, { size: 'tiny', type: 'primary', secondary: true, round: true, onClick: () => openRemoteEditor(row) }, { default: () => '编辑' }),
        renderDeleteConfirm({
          title: `确认删除 ${row.customer || row.ticket || '这条运维记录'}？`,
          actionText: '删除',
          onConfirm: () => deleteRemoteHands(row),
          buttonProps: { size: 'tiny', round: true },
        }),
      ].filter(Boolean),
    }),
  },
]

const planColumns = [
  {
    title: '客户 / 工单', key: 'customer', width: 180,
    render: (row) => h('div', { class: 'primary-cell' }, [
      h('strong', row.customer || '-'), h('small', row.ticket || '无工单号'),
    ]),
  },
  {
    title: '工程师', key: 'engineer_name', width: 180,
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
  {
    title: '计划时间', key: 'planned_at', width: 160, sorter: 'default',
    render: (row) => formatDateTime(row.planned_at),
  },
  { title: '通知负责人', key: 'assignee_names', width: 180, ellipsis: { tooltip: true }, render: (row) => row.assignee_names || '-' },
  {
    title: '计划状态', key: 'status', width: 110,
    render: (row) => h(NTag, { type: planStatusTagType(row.status), bordered: false, size: 'small' },
      { default: () => planStatusLabel(row.status) }),
  },
  {
    title: '通知状态', key: 'notify_status', width: 120,
    render: (row) => h(NTag, { type: notifyStatusTagType(row.notify_status), bordered: false, size: 'small' },
      { default: () => notifyStatusLabel(row.notify_status) }),
  },
  {
    title: '备注', key: 'note', width: 320,
    render: (row) => renderNoteCell(row.note),
  },
  {
    title: '操作', key: 'actions', width: 310, fixed: 'right',
    render: (row) => h(NSpace, { size: 6, wrap: false }, {
      default: () => [
        row.status === 'pending'
          ? h(NButton, { size: 'tiny', type: 'success', secondary: true, round: true, onClick: () => openCompleteEditor(row) }, { default: () => '完成' })
          : null,
        row.status === 'pending'
          ? h(NButton, { size: 'tiny', type: 'primary', secondary: true, round: true, onClick: () => openPlanEditor(row) }, { default: () => '变更' })
          : null,
        row.status === 'pending'
          ? h(NButton, { size: 'tiny', type: 'warning', secondary: true, round: true, onClick: () => cancelPlan(row) }, { default: () => '取消' })
          : null,
        row.remote_hands_id
          ? h(NButton, { size: 'tiny', secondary: true, round: true, onClick: () => { activeTab.value = 'remote' } }, { default: () => '查看记录' })
          : null,
        ['done', 'cancelled'].includes(row.status)
          ? renderDeleteConfirm({
            title: `确认删除 ${row.customer || row.ticket || '这条运维计划'}？`,
            actionText: '删除',
            buttonProps: { size: 'tiny', type: 'error', secondary: true, round: true },
            onConfirm: () => deletePlan(row),
          })
          : null,
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
  {
    title: '负责地区',
    key: 'region',
    minWidth: 240,
    render: (row) => renderRegionTags(row.region),
  },
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

function createPlanForm(source = {}) {
  return {
    id: source.id || null,
    customer: source.customer || '',
    ticket: source.ticket || '',
    engineer_id: source.engineer_id || null,
    engineer_name: source.engineer_name || '',
    engineer_contact: source.engineer_contact || '',
    engineer_wechat: source.engineer_wechat || '',
    engineer_group: source.engineer_group || '',
    assignee_ids: Array.isArray(source.assignee_ids) ? source.assignee_ids : [],
    region: displayRegion(source.region),
    site: source.site || '',
    site_key: findSiteCascaderValue(source),
    rack: source.rack || '',
    timezone: source.timezone || 'Asia/Shanghai',
    planned_at: normalizeDateTime(source.planned_at),
    status: source.status || 'pending',
    note: source.note || '',
    notify: !source.id,
  }
}

function createCompleteForm(source = {}) {
  const arrivedAt = normalizeDateTime(source.planned_at) || localDateTime()
  return {
    id: source.id || null,
    arrived_at: arrivedAt,
    left_at: addHoursToDateTime(arrivedAt, 1),
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
    regions: uniqueRegionValues(splitRegions(source.region)),
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

function datacenterSearchText(item) {
  return uniqueValues([
    datacenterLabel(item),
    datacenterValue(item),
    item.code,
    item.name,
    item.location,
    item.location_name,
    item.region,
    item.region_name,
    item.country,
    item.country_name,
    item.city,
    item.city_name,
    datacenterRegion(item),
  ]).join(' ')
}

function regionPathParts(value) {
  const parts = displayRegion(value)
    .split(/[\/／\\]+/)
    .map((item) => translateRegionAlias(item.trim()) || item.trim())
    .filter(Boolean)
  return parts.length ? parts : [canonicalRegion(value)].filter(Boolean)
}

function popRegionPathParts(item = {}) {
  const country = translateCountry(fieldText(item.country) || fieldText(item.country_name))
  const city = translateCity(fieldText(item.city) || fieldText(item.city_name))
  const regionParts = regionPathParts(fieldText(item.name) || fieldText(item.region_name))
  const values = [country, city]
  if (!city) {
    regionParts.forEach((part) => {
      const label = translateRegionAlias(part) || fieldText(part)
      if (!label) return
      const key = normalizeRegion(label)
      if (!key || values.some((value) => normalizeRegion(value) === key)) return
      values.push(label)
    })
  }
  const parts = []
  values.forEach((value) => {
    const label = translateRegionAlias(value) || fieldText(value)
    if (!label) return
    const key = normalizeRegion(label)
    if (!key || parts.some((part) => normalizeRegion(part) === key)) return
    parts.push(label)
  })
  return parts
}

function ensureCascaderPath(roots, parts, valuePrefix) {
  let children = roots
  let current = null
  const path = []
  parts.forEach((part) => {
    path.push(part)
    const value = `${valuePrefix}:${path.join('/')}`
    let node = children.find((item) => item.value === value)
    if (!node) {
      node = {
        label: part,
        value,
        searchText: path.join(' '),
        children: [],
      }
      children.push(node)
    }
    current = node
    children = node.children
  })
  return current || { children: roots }
}

function ensureRegionPath(roots, parts) {
  let children = roots
  let current = null
  const path = []
  parts.forEach((part) => {
    const label = translateRegionAlias(part) || part
    const key = normalizeRegion(label)
    if (!key) return
    path.push(label)
    const value = canonicalRegion(path.join(' / ')) || label
    let node = children.find((item) => normalizeRegion(item.label) === key || normalizeRegion(item.value) === normalizeRegion(value))
    if (!node) {
      node = {
        label,
        value,
        region: value,
        searchText: uniqueValues([path.join(' '), value, displayRegion(value)]).join(' '),
        children: [],
      }
      children.push(node)
    } else {
      node.searchText = uniqueValues([node.searchText, path.join(' '), value, displayRegion(value)]).join(' ')
      if (!node.region) node.region = value
    }
    current = node
    children = node.children
  })
  return current
}

function sortCascaderTree(nodes) {
  return nodes
    .sort((left, right) => String(left.label || '').localeCompare(String(right.label || ''), 'zh-Hans-CN'))
    .map((node) => ({
      ...node,
      children: node.children?.length ? sortCascaderTree(node.children) : undefined,
    }))
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

function canonicalRegion(value) {
  const text = displayRegion(value)
  if (!text) return ''
  const commaParts = text
    .split(/[,，、|;；]+/)
    .map((item) => item.trim())
    .filter(Boolean)
  const source = commaParts.find((item) => item.includes('/')) || commaParts[0] || text
  const pathParts = source
    .split('/')
    .map((item) => item.trim())
    .filter(Boolean)
  return translateRegionAlias(pathParts[pathParts.length - 1] || source)
}

function translateRegionAlias(value) {
  const text = fieldText(value)
  if (!text) return ''
  const translated = translateCity(text) || translateCountry(text)
  const normalized = text
    .toLowerCase()
    .replace(/[,，]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return regionAliasMap.get(normalized) || regionAliasMap.get(normalized.replace(/\s+/g, '')) || translated || text
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
  const regions = splitRegions(regionValue)
  return regions.some((value) => valuesMatch(value, selectedRegion))
}

function valuesMatch(left, right) {
  const normalizedLeft = normalizeRegion(displayRegion(left))
  const normalizedRight = normalizeRegion(displayRegion(right))
  if (!normalizedLeft || !normalizedRight) return false
  if (normalizedLeft === normalizedRight) return true
  const leftTokens = regionMatchTokens(left)
  const rightTokens = regionMatchTokens(right)
  return leftTokens.some((value) => rightTokens.includes(value))
}

function regionMatchTokens(value) {
  const text = displayRegion(value)
  const tokens = new Set()
  const addToken = (source) => {
    const translated = translateRegionAlias(source)
    const normalized = normalizeRegion(translated || source)
    if (normalized) tokens.add(normalized)
  }
  addToken(text)
  addToken(canonicalRegion(text))
  text
    .split(/[,，、|;；/／\\]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .forEach(addToken)
  return [...tokens]
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

function uniqueRegionValues(values) {
  const result = new Map()
  values.forEach((source) => {
    const value = canonicalRegion(source)
    const key = normalizeRegion(value)
    if (value && key && !result.has(key)) result.set(key, value)
  })
  return [...result.values()]
}

function uniqueOptions(options) {
  const values = new Map()
  options.forEach((option) => {
    const value = fieldText(option?.value)
    const key = normalizeRegion(value)
    if (!value || !key) return
    const current = values.get(key)
    const searchText = uniqueValues([current?.searchText, option.searchText, option.label, value]).join(' ')
    if (current) {
      current.searchText = searchText
    } else {
      values.set(key, { label: fieldText(option.label) || value, value, searchText })
    }
  })
  return [...values.values()]
}

function siteOptionFilter(pattern, option) {
  const keyword = normalizeSearchText(pattern)
  if (!keyword) return true
  return siteSearchTokens([option?.label, option?.value, option?.searchText].filter(Boolean).join(' '))
    .some((token) => token.includes(keyword))
}

function siteCascaderFilter(pattern, option, path = []) {
  const options = Array.isArray(path) && path.length ? path : [option]
  const text = options
    .flatMap((item) => [item?.label, item?.value, item?.region, item?.site, item?.searchText])
    .filter(Boolean)
    .join(' ')
  return siteOptionFilter(pattern, { label: text, value: text, searchText: text })
}

function regionCascaderFilter(pattern, option, path = []) {
  const options = Array.isArray(path) && path.length ? path : [option]
  const text = options
    .flatMap((item) => [item?.label, item?.value, item?.region, item?.searchText])
    .filter(Boolean)
    .join(' ')
  return siteOptionFilter(pattern, { label: text, value: text, searchText: text })
}

function siteSearchTokens(value) {
  const text = String(value || '')
  const normalized = normalizeSearchText(text)
  const pinyin = toPinyinText(text)
  const normalizedPinyin = normalizeSearchText(pinyin)
  const pinyinInitials = pinyin
    .split(/\s+/)
    .map((item) => item[0] || '')
    .join('')
  return uniqueValues([
    normalized,
    normalized.replace(/[\/,，、|;；.-]+/g, ''),
    normalizedPinyin,
    normalizedPinyin.replace(/[\/,，、|;；.-]+/g, ''),
    normalizeSearchText(pinyinInitials),
  ])
}

function normalizeSearchText(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[\s　]+/g, '')
    .replace(/[\/,，、|;；._-]+/g, '')
    .trim()
}

function toPinyinText(value) {
  return String(value || '')
    .split('')
    .map((char) => pinyinCharMap[char] || char)
    .join(' ')
}

function fieldText(value) {
  if (value == null) return ''
  if (typeof value === 'object') {
    return String(value.name || value.label || value.title || value.value || value.code || value.id || '').trim()
  }
  return String(value).trim()
}

function splitRegions(value) {
  if (Array.isArray(value)) return value.flatMap(splitRegions)
  const text = String(value || '').trim()
  if (!text) return []
  const normalized = /[\u4e00-\u9fa5]/.test(text)
    ? text.replace(/[\s　]+/g, ',')
    : text
  return normalized
    .split(/[,，、;；|\r\n\t]+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function openRemoteEditor(row = null) {
  remoteEditor.form = createRemoteForm(row || {})
  remoteEditor.show = true
}

function openPlanEditor(row = null) {
  planEditor.form = createPlanForm(row || {})
  planEditor.show = true
}

function openCompleteEditor(row) {
  completeEditor.form = createCompleteForm(row || {})
  completeEditor.show = true
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

function handleRemoteFilterSiteChange(value, option) {
  remoteFilters.site = value && option?.site ? option.site : null
}

function handleEngineerSelected(value) {
  const engineer = engineers.value.find((item) => String(item.id) === String(value))
  remoteEditor.form.engineer_id = engineer?.id || null
  remoteEditor.form.engineer_name = engineer?.name || ''
  remoteEditor.form.engineer_contact = engineer?.contact || ''
  remoteEditor.form.engineer_wechat = engineer?.wechat_id || ''
  remoteEditor.form.engineer_group = engineer?.wechat_group || ''
}

function handlePlanSiteCascaderChange(value, option) {
  if (!value) {
    planEditor.form.region = ''
    planEditor.form.site = ''
    handlePlanEngineerSelected(null)
    return
  }
  if (!option?.site) {
    planEditor.form.region = displayRegion(option?.label)
    planEditor.form.site = ''
    handlePlanEngineerSelected(null)
    return
  }
  planEditor.form.region = displayRegion(option.region)
  planEditor.form.site = option.site
  if (option.timezone) planEditor.form.timezone = option.timezone
  const validEngineers = assignablePlanEngineerOptions.value.map((item) => item.value)
  if (!validEngineers.includes(planEditor.form.engineer_id)) handlePlanEngineerSelected(null)
}

function handlePlanFilterSiteChange(value, option) {
  planFilters.site = value && option?.site ? option.site : null
}

function handlePlanEngineerSelected(value) {
  const engineer = engineers.value.find((item) => String(item.id) === String(value))
  planEditor.form.engineer_id = engineer?.id || null
  planEditor.form.engineer_name = engineer?.name || ''
  planEditor.form.engineer_contact = engineer?.contact || ''
  planEditor.form.engineer_wechat = engineer?.wechat_id || ''
  planEditor.form.engineer_group = engineer?.wechat_group || ''
}

function updateWorkMinutes() {
  remoteEditor.form.arrived_at = normalizeDateTime(remoteEditor.form.arrived_at)
  remoteEditor.form.left_at = normalizeDateTime(remoteEditor.form.left_at)
  remoteEditor.form.work_minutes = minutesBetween(remoteEditor.form.arrived_at, remoteEditor.form.left_at)
}

function handleCompleteArrivedAtChange(value) {
  const nextLeftAt = addHoursToDateTime(value, 1)
  if (nextLeftAt) completeEditor.form.left_at = nextLeftAt
}

function minutesBetween(start, end) {
  if (!start || !end) return 0
  const value = Math.round((new Date(end).getTime() - new Date(start).getTime()) / 60000)
  return Number.isFinite(value) ? Math.max(0, value) : 0
}

function isEndBeforeStart(start, end) {
  if (!start || !end) return false
  const startTime = new Date(start).getTime()
  const endTime = new Date(end).getTime()
  return Number.isFinite(startTime) && Number.isFinite(endTime) && endTime < startTime
}

async function saveRemoteHands() {
  const form = remoteEditor.form
  if (!form.customer.trim()) return message.warning('请输入客户名称')
  if (!fieldText(form.region)) return message.warning('请选择或输入地区')
  if (!form.site) return message.warning('请选择机房')
  if (!form.engineer_id) return message.warning('请选择工程师')
  form.arrived_at = normalizeDateTime(form.arrived_at)
  form.left_at = normalizeDateTime(form.left_at)
  if (isEndBeforeStart(form.arrived_at, form.left_at)) return message.warning('离场时间不能早于到场时间')
  remoteEditor.saving = true
  try {
    const payload = { ...form }
    payload.work_minutes = minutesBetween(payload.arrived_at, payload.left_at)
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

async function savePlan() {
  const form = planEditor.form
  if (!form.customer.trim()) return message.warning('请输入客户名称')
  if (!fieldText(form.region)) return message.warning('请选择地区')
  if (!form.site) return message.warning('请选择机房')
  form.planned_at = normalizeDateTime(form.planned_at)
  if (!form.planned_at) return message.warning('请选择计划时间')
  planEditor.saving = true
  try {
    const payload = { ...form }
    payload.planned_at = normalizeDateTime(payload.planned_at)
    delete payload.id
    delete payload.site_key
    if (form.id) await api.remoteAssistanceApi.updatePlan(form.id, payload)
    else await api.remoteAssistanceApi.createPlan(payload)
    message.success(form.id ? '运维计划已变更' : '运维计划已创建')
    planEditor.show = false
    activeTab.value = 'plans'
    await fetchOverview()
  } finally {
    planEditor.saving = false
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

async function notifyPlan(row) {
  await api.remoteAssistanceApi.notifyPlan(row.id)
  message.success('运维计划通知已发送')
  await fetchOverview()
}

async function cancelPlan(row) {
  await api.remoteAssistanceApi.cancelPlan(row.id)
  message.success('运维计划已取消')
  await fetchOverview()
}

async function deletePlan(row) {
  await api.remoteAssistanceApi.deletePlan(row.id)
  message.success('运维计划已删除')
  await fetchOverview()
}

async function submitCompletePlan() {
  const form = completeEditor.form
  if (!form.id) return
  if (!form.arrived_at) return message.warning('请选择到场时间')
  if (!form.left_at) return message.warning('请选择离场时间')
  if (isEndBeforeStart(form.arrived_at, form.left_at)) return message.warning('离场时间不能早于到场时间')
  completeEditor.saving = true
  try {
    await api.remoteAssistanceApi.completePlan(form.id, {
      arrived_at: form.arrived_at,
      left_at: form.left_at,
      note: form.note,
    })
    message.success('运维计划已完成，并已写入运维记录')
    completeEditor.show = false
    await fetchOverview()
  } finally {
    completeEditor.saving = false
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

async function updateRemoteSettlement(row, type, value) {
  const normalized = normalizeSettlementStatus(value)
  if (normalized === readSettlementStatus(row, type)) return
  const key = `${row.id}:${type}`
  remoteSettlementSaving.value = new Set([...remoteSettlementSaving.value, key])
  try {
    const payload = { ...createRemoteForm(row) }
    delete payload.id
    payload.ops_settlement_status = readSettlementStatus(row, 'ops')
    payload.customer_settlement_status = readSettlementStatus(row, 'customer')
    if (type === 'ops') payload.ops_settlement_status = normalized
    else payload.customer_settlement_status = normalized
    await api.remoteAssistanceApi.updateRemoteHands(row.id, payload)
    message.success('结算状态已更新')
    await fetchOverview()
  } finally {
    const next = new Set(remoteSettlementSaving.value)
    next.delete(key)
    remoteSettlementSaving.value = next
  }
}

async function fetchOverview() {
  loading.value = true
  try {
    const [overviewRes, userRes, regionRes] = await Promise.all([
      api.remoteAssistanceApi.overview(),
      api.getUserList({ page: 1, page_size: 1000 }).catch(() => null),
      api.assetApi.regions({ page: 1, page_size: 1000, status: true }).catch(() => null),
    ])
    const data = overviewRes.data || {}
    const listUsers = normalizeUserRows(userRes?.data)
    remoteHands.value = Array.isArray(data.remote_hands) ? data.remote_hands : []
    plans.value = Array.isArray(data.plans) ? data.plans : []
    engineers.value = Array.isArray(data.engineers) ? data.engineers : []
    users.value = listUsers.length ? listUsers : normalizeUserRows(data.users)
    datacenters.value = Array.isArray(data.datacenters) ? data.datacenters : []
    popRegions.value = Array.isArray(regionRes?.data) ? regionRes.data : []
  } finally {
    loading.value = false
  }
}

function normalizeUserRows(rows) {
  if (!Array.isArray(rows)) return []
  return rows
    .filter((item) => item?.id)
    .map((item) => ({
      id: item.id,
      label: item.label || item.alias || item.username || `用户 ${item.id}`,
      username: item.username || '',
      alias: item.alias || '',
      email: item.email || '',
      phone: item.phone || '',
      is_active: item.is_active,
    }))
}

function normalizeDateTime(value) {
  if (!value) return null
  if (value instanceof Date && Number.isFinite(value.getTime())) return formatLocalDateTime(value)
  const text = String(value).trim()
  if (!text) return null
  const numeric = Number(text)
  if (Number.isFinite(numeric) && text.length >= 10) {
    const date = new Date(text.length === 10 ? numeric * 1000 : numeric)
    if (Number.isFinite(date.getTime())) return formatLocalDateTime(date)
  }
  const match = text.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[T\s](\d{1,2})(?::(\d{1,2}))?)?/)
  if (match) {
    const [, year, month, day, hour = '00', minute = '00'] = match
    return `${year}-${padDatePart(month)}-${padDatePart(day)}T${padDatePart(hour)}:${padDatePart(minute)}`
  }
  const date = new Date(text)
  return Number.isFinite(date.getTime()) ? formatLocalDateTime(date) : null
}

function padDatePart(value) {
  return String(value || '0').padStart(2, '0')
}

function formatLocalDateTime(date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 16)
}

function localDateTime() {
  const now = new Date()
  return formatLocalDateTime(now)
}

function addHoursToDateTime(value, hours = 1) {
  if (!value) return null
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return null
  date.setHours(date.getHours() + hours)
  return formatLocalDateTime(date)
}

function formatDate(value) {
  return value ? String(value).slice(0, 10) : '-'
}

function shortDate(value) {
  return value ? String(value).slice(5, 10) : ''
}

function formatRemoteDateRange(row) {
  const startDate = formatDate(row.arrived_at || row.left_at)
  const endDate = formatDate(row.left_at)
  if (startDate === '-' || endDate === '-' || startDate === endDate) return startDate
  return `${shortDate(row.arrived_at)} ~ ${shortDate(row.left_at)}`
}

function formatTime(value) {
  return value ? String(value).slice(11, 16) || '-' : '-'
}

function formatRemoteEndTime(row) {
  if (!row.left_at) return '-'
  if (!row.arrived_at || formatDate(row.arrived_at) === formatDate(row.left_at)) return formatTime(row.left_at)
  return formatDateTime(row.left_at).slice(5)
}

function formatDateTime(value) {
  if (!value) return '-'
  const text = String(value).replace('T', ' ')
  return text.slice(0, 16)
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

function planStatusLabel(status) {
  return planStatusOptions.find((item) => item.value === status)?.label || status || '未知'
}

function planStatusTagType(status) {
  return { pending: 'warning', done: 'success', cancelled: 'default' }[status] || 'default'
}

function notifyStatusLabel(status) {
  return { pending: '待通知', sent: '已发送', failed: '发送失败' }[status] || status || '待通知'
}

function notifyStatusTagType(status) {
  return { pending: 'default', sent: 'success', failed: 'error' }[status] || 'default'
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

function renderSettlementSelect(row, type) {
  const key = `${row.id}:${type}`
  return h(NSelect, {
    value: readSettlementStatus(row, type),
    options: settlementOptions,
    size: 'tiny',
    consistentMenuWidth: false,
    loading: remoteSettlementSaving.value.has(key),
    disabled: remoteSettlementSaving.value.has(key),
    style: { width: '108px' },
    onUpdateValue: (value) => updateRemoteSettlement(row, type, value),
  })
}

function renderSettlementTag(value) {
  const normalized = normalizeSettlementStatus(value)
  const type = { unbilled: 'warning', billed: 'info', settled: 'success' }[normalized]
  const label = settlementOptions.find((item) => item.value === normalized)?.label || '未计费'
  return h(NTag, { type, bordered: false, size: 'small' }, { default: () => label })
}

function renderDeleteConfirm({ title, actionText, onConfirm, buttonProps = {} }) {
  return h(NPopconfirm, {
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: onConfirm,
  }, {
    trigger: () => h(NButton, { size: 'small', type: 'error', secondary: true, ...buttonProps }, { default: () => actionText }),
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

function renderRegionTags(value) {
  const regions = uniqueRegionValues(splitRegions(value))
  if (!regions.length) return h('span', { class: 'muted-text' }, '未设置')
  const visible = regions.slice(0, 4)
  const hiddenCount = regions.length - visible.length
  return h('div', { class: 'region-tags' }, [
    ...visible.map((region) =>
      h(NTag, { size: 'small', type: 'info', bordered: false, round: true }, { default: () => region })
    ),
    hiddenCount > 0
      ? h(NTooltip, { trigger: 'hover' }, {
        trigger: () => h(NTag, { size: 'small', bordered: false, round: true }, { default: () => `+${hiddenCount}` }),
        default: () => regions.slice(4).join('、'),
      })
      : null,
  ].filter(Boolean))
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
:deep(.region-tags) {
  display: flex;
  max-width: 100%;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 2px 0;
}

.editor-modal { width: min(900px, calc(100vw - 32px)); }
.engineer-editor-modal { width: min(560px, calc(100vw - 32px)); }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; column-gap: 22px; }
.remote-form-grid { display: grid; grid-template-columns: 1fr 1fr; column-gap: 14px; }
.remote-form :deep(.n-form-item) { margin-bottom: 12px; }
.remote-form :deep(.n-input),
.remote-form :deep(.n-base-selection),
.remote-form :deep(.n-date-picker) { min-height: 30px; }
.engineer-form-grid { display: grid; grid-template-columns: 1fr; }
.engineer-form :deep(.n-form-item) { margin-bottom: 12px; }
.engineer-form :deep(.n-input),
.engineer-form :deep(.n-base-selection) { min-height: 30px; }
.modal-actions { justify-content: flex-end; }
.compact-modal-actions,
.engineer-modal-actions { gap: 8px; }

@media (max-width: 900px) {
  .summary-grid { grid-template-columns: 1fr 1fr; }
  .table-toolbar { align-items: stretch; flex-direction: column; }
  .filter-row { width: 100%; }
  .form-grid { grid-template-columns: 1fr; }
  .remote-form-grid { grid-template-columns: 1fr; }
}

@media (max-width: 560px) {
  .summary-grid { grid-template-columns: 1fr; }
  .filter-row { grid-template-columns: 1fr; }
  .workspace-panel { padding: 14px; }
}
</style>
