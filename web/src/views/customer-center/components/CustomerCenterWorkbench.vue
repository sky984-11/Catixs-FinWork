<template>
  <AppPage :show-footer="false">
    <div class="crm-page">
      <section v-if="mode === 'customers'" class="crm-summary">
        <article v-for="card in summaryCards" :key="card.label">
          <span :class="['crm-summary__icon', card.tone]"><TheIcon :icon="card.icon" :size="22" /></span>
          <div>
            <small>{{ card.label }}</small>
            <strong>{{ card.value }}</strong>
          </div>
        </article>
      </section>

      <section class="crm-panel">
        <div class="crm-panel__head">
          <div>
            <span class="eyebrow">CUSTOMER CENTER</span>
            <h2>{{ pageTitle }}</h2>
          </div>
          <n-space>
            <n-button secondary circle :loading="loading" title="刷新" @click="loadPage">
              <template #icon><TheIcon icon="mdi:refresh" :size="18" /></template>
            </n-button>
            <n-button v-if="mode === 'customers'" type="primary" @click="openCustomerModal()">
              <template #icon><TheIcon icon="mdi:account-plus-outline" :size="18" /></template>
              新增客户
            </n-button>
            <n-button v-if="mode === 'contracts'" type="primary" @click="openContractModal()">
              <template #icon><TheIcon icon="mdi:file-sign" :size="18" /></template>
              新增合同
            </n-button>
            <n-button v-if="mode === 'contacts'" type="primary" @click="openContactModal()">
              <template #icon><TheIcon icon="mdi:card-account-phone-outline" :size="18" /></template>
              新增联系人
            </n-button>
          </n-space>
        </div>

        <div :class="['crm-filter', { 'crm-filter--compact': mode === 'contacts' }]">
          <n-input v-if="mode !== 'contacts'" v-model:value="query.keyword" clearable :placeholder="keywordPlaceholder" @keyup.enter="loadPage" />
          <n-select v-if="mode === 'customers'" v-model:value="query.lifecycle" clearable :options="options.lifecycles" placeholder="生命周期" />
          <n-select v-if="mode === 'customers'" v-model:value="query.customer_level" clearable :options="options.levels" placeholder="客户等级" />
          <n-select v-if="mode === 'customers'" v-model:value="query.entity_type" clearable :options="options.entityTypes" placeholder="主体类型" />
          <n-select v-if="mode === 'customers'" v-model:value="query.signing_entity_id" clearable filterable :options="options.signingEntities" placeholder="签约主体" />
          <n-select v-if="mode !== 'customers'" v-model:value="query.customer_id" clearable filterable :options="options.customers" placeholder="签约客户" />
          <n-select v-if="mode === 'contracts'" v-model:value="query.status" clearable :options="options.contractStatuses" placeholder="合同状态" />
          <n-select v-if="mode === 'contacts'" v-model:value="query.role" clearable :options="options.contactRoles" placeholder="联系人角色" />
          <n-button secondary @click="resetQuery">重置</n-button>
          <n-button type="primary" @click="loadPage">搜索</n-button>
        </div>

        <n-data-table
          remote
          striped
          :loading="loading"
          :columns="columns"
          :data="rows"
          :pagination="false"
          :row-key="(row) => row.id"
          :row-props="mode === 'customers' ? customerRowProps : undefined"
          :scroll-x="scrollX"
        >
          <template #empty><n-empty description="暂无数据" /></template>
        </n-data-table>
        <div class="crm-pagination">
          <span>共 {{ pagination.itemCount }} 条</span>
          <n-pagination
            v-model:page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :item-count="pagination.itemCount"
            :page-sizes="pagination.pageSizes"
            show-size-picker
            @update:page="loadPage"
            @update:page-size="handlePageSizeChange"
          />
        </div>
      </section>

      <n-drawer v-model:show="detailVisible" :width="detailWidth" placement="right">
        <n-drawer-content :native-scrollbar="false">
          <template #header>
            <div class="detail-title">
              <div>
                <span class="eyebrow">客户详情</span>
                <strong>{{ detail?.legal_name || detail?.name || '-' }}</strong>
              </div>
              <n-button size="small" secondary @click="openCustomerModal(detail)">编辑客户</n-button>
            </div>
          </template>
          <n-spin :show="detailLoading">
            <div v-if="detail" class="detail-body">
              <section class="detail-metrics">
                <article><span>客户等级</span><strong>{{ detail.customer_level_label }}</strong></article>
                <article><span>生命周期</span><strong>{{ detail.lifecycle_label }}</strong></article>
                <article><span>签约主体</span><strong>{{ detail.signing_entity_name || '-' }}</strong></article>
                <article><span>所属销售</span><strong>{{ detail.sales_owner || '-' }}</strong></article>
              </section>
              <n-tabs type="line" animated>
                <n-tab-pane name="base" tab="基本信息">
                  <div class="info-grid">
                    <article><span>客户简称</span><strong>{{ detail.name || '-' }}</strong></article>
                    <article><span>客户全称</span><strong>{{ detail.legal_name || '-' }}</strong></article>
                    <article><span>主体类型</span><strong>{{ detail.entity_type_label }}</strong></article>
                    <article><span>所属地区</span><strong>{{ detail.region || '-' }}</strong></article>
                    <article><span>联系地址</span><strong>{{ detail.address || '-' }}</strong></article>
                  </div>
                  <div class="text-block"><b>开票信息</b><p>{{ formatInvoiceInfo(detail.invoice_info) }}</p></div>
                  <div class="text-block"><b>财务信息</b><p>{{ formatFinanceInfo(detail.finance_info) }}</p></div>
                  <div class="text-block"><b>备注</b><p>{{ detail.remark || '-' }}</p></div>
                </n-tab-pane>
                <n-tab-pane name="contacts" tab="客户联系人">
                  <SubTable title="客户联系人" :columns="contactColumns" :data="detail.contacts || []" @add="openContactModal()" />
                </n-tab-pane>
                <n-tab-pane name="contracts" tab="客户合同">
                  <SubTable title="客户合同" :columns="contractColumns" :data="detail.contracts || []" @add="openContractModal()" />
                </n-tab-pane>
                <n-tab-pane name="bills" tab="客户账单">
                  <SubTable title="客户账单" :columns="billColumns" :data="detail.bills || []" @add="openBillModal()" />
                </n-tab-pane>
              </n-tabs>
            </div>
          </n-spin>
        </n-drawer-content>
      </n-drawer>

      <n-modal v-model:show="customerModal.show" preset="card" :title="customerModal.form.id ? '编辑客户' : '新增客户'" class="crm-modal customer-modal">
        <div class="customer-modal__intro">
          <span class="customer-modal__icon">
            <TheIcon icon="mdi:office-building-outline" :size="24" />
          </span>
          <div>
            <strong>{{ customerModal.form.id ? '维护客户档案' : '创建客户档案' }}</strong>
            <p>统一维护客户主体、签约归属、销售负责人和财务备注。</p>
          </div>
        </div>
        <n-form :model="customerModal.form" label-placement="top" class="customer-form">
          <section class="form-section">
            <div class="form-section__head">
              <span>基本信息</span>
              <small>客户识别与主体资料</small>
            </div>
            <n-grid :cols="2" :x-gap="16" :y-gap="2">
              <n-form-item-gi label="客户简称" required><n-input v-model:value="customerModal.form.name" placeholder="请输入客户简称" /></n-form-item-gi>
              <n-form-item-gi label="客户全称"><n-input v-model:value="customerModal.form.legal_name" placeholder="请输入工商或证件主体名称" /></n-form-item-gi>
              <n-form-item-gi label="联系地址" :span="2"><n-input v-model:value="customerModal.form.address" placeholder="请输入客户联系地址" /></n-form-item-gi>
            </n-grid>
          </section>

          <section class="form-section">
            <div class="form-section__head">
              <span>客户属性</span>
              <small>签约、分级与生命周期</small>
            </div>
            <n-grid :cols="2" :x-gap="16" :y-gap="2">
              <n-form-item-gi label="主体类型"><n-select v-model:value="customerModal.form.entity_type" :options="options.entityTypes" placeholder="请选择主体类型" /></n-form-item-gi>
              <n-form-item-gi label="签约主体"><n-select v-model:value="customerModal.form.signing_entity_id" clearable filterable :options="options.signingEntities" placeholder="请选择签约主体" /></n-form-item-gi>
              <n-form-item-gi label="客户等级"><n-select v-model:value="customerModal.form.customer_level" :options="options.levels" placeholder="请选择客户等级" /></n-form-item-gi>
              <n-form-item-gi label="客户生命周期"><n-select v-model:value="customerModal.form.lifecycle" :options="options.lifecycles" placeholder="请选择生命周期" /></n-form-item-gi>
              <n-form-item-gi label="所属销售">
                <n-select
                  v-model:value="customerModal.form.sales_owner"
                  clearable
                  filterable
                  :loading="salesUserLoading"
                  :options="salesOwnerOptions"
                  placeholder="请选择用户"
                />
              </n-form-item-gi>
              <n-form-item-gi label="所属地区"><n-input v-model:value="customerModal.form.region" placeholder="如：中国大陆 / 香港 / 欧洲" /></n-form-item-gi>
            </n-grid>
          </section>

          <section class="form-section">
            <div class="form-section__head">
              <span>财务与备注</span>
              <small>按国家/地区维护开票、结算与风控信息</small>
            </div>
            <n-grid :cols="2" :x-gap="16" :y-gap="2">
              <n-form-item-gi label="开票地区"><n-select v-model:value="customerModal.form.invoice_profile.invoice_region" :options="invoiceRegionOptions" /></n-form-item-gi>
              <n-form-item-gi label="发票/账单类型"><n-select v-model:value="customerModal.form.invoice_profile.invoice_type" :options="invoiceTypeOptions" /></n-form-item-gi>
              <n-form-item-gi label="发票抬头"><n-input v-model:value="customerModal.form.invoice_profile.invoice_title" placeholder="通常为客户全称" /></n-form-item-gi>
              <n-form-item-gi label="税号 / VAT / GST"><n-input v-model:value="customerModal.form.invoice_profile.tax_id" placeholder="按当地税务规则填写" /></n-form-item-gi>
              <n-form-item-gi label="注册号 / BR / UEN"><n-input v-model:value="customerModal.form.invoice_profile.registration_no" placeholder="香港 BR、新加坡 UEN、海外注册号等" /></n-form-item-gi>
              <n-form-item-gi label="开票邮箱"><n-input v-model:value="customerModal.form.invoice_profile.invoice_email" placeholder="用于发送发票或 Invoice" /></n-form-item-gi>
              <n-form-item-gi v-if="customerModal.form.invoice_profile.invoice_region === 'CN'" label="开户银行"><n-input v-model:value="customerModal.form.invoice_profile.bank_name" placeholder="专票常用" /></n-form-item-gi>
              <n-form-item-gi v-if="customerModal.form.invoice_profile.invoice_region === 'CN'" label="银行账号"><n-input v-model:value="customerModal.form.invoice_profile.bank_account" placeholder="专票常用" /></n-form-item-gi>
              <n-form-item-gi v-if="['HK', 'SG', 'EU', 'US', 'OTHER'].includes(customerModal.form.invoice_profile.invoice_region)" label="SWIFT / Routing"><n-input v-model:value="customerModal.form.invoice_profile.swift_code" placeholder="跨境收付款识别码" /></n-form-item-gi>
              <n-form-item-gi v-if="customerModal.form.invoice_profile.invoice_region === 'EU'" label="IBAN"><n-input v-model:value="customerModal.form.invoice_profile.iban" placeholder="欧盟/欧洲客户常用" /></n-form-item-gi>
              <n-form-item-gi label="开票地址" :span="2"><n-input v-model:value="customerModal.form.invoice_profile.invoice_address" placeholder="注册地址或税务地址" /></n-form-item-gi>

              <n-form-item-gi label="结算币种"><n-select v-model:value="customerModal.form.finance_profile.settlement_currency" :options="options.currencies" /></n-form-item-gi>
              <n-form-item-gi label="结算周期"><n-select v-model:value="customerModal.form.finance_profile.billing_cycle" :options="billingCycleOptions" /></n-form-item-gi>
              <n-form-item-gi label="账期"><n-select v-model:value="customerModal.form.finance_profile.payment_terms" :options="paymentTermOptions" /></n-form-item-gi>
              <n-form-item-gi label="付款方式"><n-select v-model:value="customerModal.form.finance_profile.payment_method" :options="paymentMethodOptions" /></n-form-item-gi>
              <n-form-item-gi label="信用额度"><n-input-number v-model:value="customerModal.form.finance_profile.credit_limit" :min="0" placeholder="0 表示未授信" /></n-form-item-gi>
              <n-form-item-gi label="允许欠款"><n-switch v-model:value="customerModal.form.finance_profile.allow_arrears" /></n-form-item-gi>
              <n-form-item-gi label="对账日"><n-input-number v-model:value="customerModal.form.finance_profile.reconciliation_day" :min="1" :max="31" placeholder="每月几号" /></n-form-item-gi>
              <n-form-item-gi label="财务联系人"><n-input v-model:value="customerModal.form.finance_profile.finance_contact" placeholder="姓名 / 邮箱 / 电话" /></n-form-item-gi>
              <n-form-item-gi label="地区特殊说明" :span="2"><n-input v-model:value="customerModal.form.invoice_profile.local_requirement" type="textarea" placeholder="例如：中国大陆专票要求、香港 BR 要求、EU VAT reverse charge、美国 W-9 等" /></n-form-item-gi>
              <n-form-item-gi label="财务备注" :span="2"><n-input v-model:value="customerModal.form.finance_profile.finance_remark" type="textarea" placeholder="结算习惯、信用风险、历史付款情况等" /></n-form-item-gi>
              <n-form-item-gi label="备注" :span="2"><n-input v-model:value="customerModal.form.remark" type="textarea" placeholder="内部备注、风险提示、历史沟通记录等" /></n-form-item-gi>
            </n-grid>
          </section>
        </n-form>
        <template #footer><ModalFooter :loading="customerModal.loading" @cancel="customerModal.show = false" @save="saveCustomer" /></template>
      </n-modal>

      <n-modal v-model:show="contractModal.show" preset="card" :title="contractModal.form.id ? '编辑合同' : '新增合同'" class="crm-modal">
        <n-form :model="contractModal.form" label-placement="top">
          <n-grid :cols="2" :x-gap="14">
            <n-form-item-gi label="签约客户" required><n-select v-model:value="contractModal.form.customer_id" filterable :options="options.customers" /></n-form-item-gi>
            <n-form-item-gi label="签约主体"><n-select v-model:value="contractModal.form.signing_entity_id" clearable filterable :options="options.signingEntities" /></n-form-item-gi>
            <n-form-item-gi label="合同编号"><n-input v-model:value="contractModal.form.contract_no" /></n-form-item-gi>
            <n-form-item-gi label="合同名称" required><n-input v-model:value="contractModal.form.name" /></n-form-item-gi>
            <n-form-item-gi label="合同状态"><n-select v-model:value="contractModal.form.status" :options="options.contractStatuses" /></n-form-item-gi>
            <n-form-item-gi label="币种"><n-select v-model:value="contractModal.form.currency" :options="options.currencies" /></n-form-item-gi>
            <n-form-item-gi label="生效日期"><n-date-picker v-model:formatted-value="contractModal.form.effective_date" value-format="yyyy-MM-dd" type="date" clearable /></n-form-item-gi>
            <n-form-item-gi label="到期日期"><n-date-picker v-model:formatted-value="contractModal.form.expiry_date" value-format="yyyy-MM-dd" type="date" clearable /></n-form-item-gi>
            <n-form-item-gi label="合同金额"><n-input-number v-model:value="contractModal.form.amount" :min="0" /></n-form-item-gi>
            <n-form-item-gi label="到期提醒天数"><n-input-number v-model:value="contractModal.form.reminder_days" :min="0" /></n-form-item-gi>
            <n-form-item-gi label="合同附件" :span="2"><n-input v-model:value="contractModal.form.attachment_url" /></n-form-item-gi>
            <n-form-item-gi label="备注" :span="2"><n-input v-model:value="contractModal.form.remark" type="textarea" /></n-form-item-gi>
          </n-grid>
        </n-form>
        <template #footer><ModalFooter :loading="contractModal.loading" @cancel="contractModal.show = false" @save="saveContract" /></template>
      </n-modal>

      <n-modal
        v-model:show="contactModal.show"
        preset="card"
        :title="contactModal.form.id ? '编辑联系人' : '新增联系人'"
        class="crm-modal contact-modal"
        style="width: min(720px, calc(100vw - 32px))"
      >
        <div class="contact-modal__intro">
          <span class="contact-modal__icon">
            <TheIcon icon="mdi:card-account-phone-outline" :size="24" />
          </span>
          <div>
            <strong>{{ contactModal.form.contact_type === 'group' ? '维护组邮箱' : '维护客户联系人' }}</strong>
            <p>用于记录客户侧商务、技术、财务、运维或紧急沟通入口。</p>
          </div>
        </div>
        <n-form :model="contactModal.form" label-placement="top" class="contact-form">
          <section class="form-section">
            <div class="form-section__head">
              <span>归属与身份</span>
              <small>确认联系人归属客户、类型和沟通角色</small>
            </div>
            <n-grid :cols="2" :x-gap="16" :y-gap="2" responsive="screen">
              <n-form-item-gi label="所属客户" required :span="2"><n-select v-model:value="contactModal.form.customer_id" filterable :options="options.customers" placeholder="请选择客户" /></n-form-item-gi>
              <n-form-item-gi label="联系人类型"><n-select v-model:value="contactModal.form.contact_type" :options="options.contactTypes" /></n-form-item-gi>
              <n-form-item-gi label="联系人角色"><n-select v-model:value="contactModal.form.role" :options="options.contactRoles" /></n-form-item-gi>
              <n-form-item-gi :label="contactModal.form.contact_type === 'group' ? '组名 / 部门名' : '联系人姓名'" :span="2"><n-input v-model:value="contactModal.form.name" :placeholder="contactModal.form.contact_type === 'group' ? '如：NOC / Accounting / Billing' : '请输入联系人姓名'" /></n-form-item-gi>
            </n-grid>
          </section>

          <section class="form-section">
            <div class="form-section__head">
              <span>联系方式</span>
              <small>组邮箱可只维护邮箱，个人联系人可补充电话和地址</small>
            </div>
            <n-grid :cols="2" :x-gap="16" :y-gap="2" responsive="screen">
              <n-form-item-gi label="邮箱"><n-input v-model:value="contactModal.form.email" placeholder="name@example.com" /></n-form-item-gi>
              <n-form-item-gi label="电话"><n-input v-model:value="contactModal.form.phone" placeholder="国家码 + 电话号码" /></n-form-item-gi>
              <n-form-item-gi label="联系地址" :span="2"><n-input v-model:value="contactModal.form.address" placeholder="可填写办公地址、邮寄地址或所在地" /></n-form-item-gi>
              <n-form-item-gi label="备注" :span="2"><n-input v-model:value="contactModal.form.remark" type="textarea" placeholder="内部备注、沟通偏好、账单抄送说明等" /></n-form-item-gi>
            </n-grid>
          </section>
        </n-form>
        <template #footer><ModalFooter :loading="contactModal.loading" @cancel="contactModal.show = false" @save="saveContact" /></template>
      </n-modal>

      <n-modal v-model:show="billModal.show" preset="card" :title="billModal.form.id ? '编辑账单' : '新增账单'" class="crm-modal">
        <n-form :model="billModal.form" label-placement="top">
          <n-grid :cols="2" :x-gap="14">
            <n-form-item-gi label="所属客户" required><n-select v-model:value="billModal.form.customer_id" filterable :options="options.customers" /></n-form-item-gi>
            <n-form-item-gi label="账单编号"><n-input v-model:value="billModal.form.bill_no" /></n-form-item-gi>
            <n-form-item-gi label="账单名称" required><n-input v-model:value="billModal.form.title" /></n-form-item-gi>
            <n-form-item-gi label="状态"><n-select v-model:value="billModal.form.status" :options="options.billStatuses" /></n-form-item-gi>
            <n-form-item-gi label="金额"><n-input-number v-model:value="billModal.form.amount" :min="0" /></n-form-item-gi>
            <n-form-item-gi label="币种"><n-select v-model:value="billModal.form.currency" :options="options.currencies" /></n-form-item-gi>
            <n-form-item-gi label="账单日期"><n-date-picker v-model:formatted-value="billModal.form.bill_date" value-format="yyyy-MM-dd" type="date" clearable /></n-form-item-gi>
            <n-form-item-gi label="到期日期"><n-date-picker v-model:formatted-value="billModal.form.due_date" value-format="yyyy-MM-dd" type="date" clearable /></n-form-item-gi>
            <n-form-item-gi label="已完成结算"><n-switch v-model:value="billModal.form.is_settled" /></n-form-item-gi>
            <n-form-item-gi label="无后续业务往来"><n-switch v-model:value="billModal.form.business_closed" /></n-form-item-gi>
            <n-form-item-gi label="备注" :span="2"><n-input v-model:value="billModal.form.remark" type="textarea" /></n-form-item-gi>
          </n-grid>
        </n-form>
        <template #footer><ModalFooter :loading="billModal.loading" @cancel="billModal.show = false" @save="saveBill" /></template>
      </n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NDataTable,
  NDatePicker,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NForm,
  NFormItemGi,
  NGrid,
  NInput,
  NInputNumber,
  NModal,
  NPagination,
  NPopconfirm,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  NTabPane,
  NTabs,
  NTag,
} from 'naive-ui'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

const props = defineProps({ mode: { type: String, default: 'customers' } })

const labelMap = {
  customers: { title: '客户管理', keyword: '搜索客户简称 / 客户全称 / 销售 / 地区' },
  contracts: { title: '客户合同', keyword: '搜索合同编号 / 合同名称 / 客户' },
  contacts: { title: '客户联系人', keyword: '搜索联系人 / 邮箱 / 电话 / 客户' },
}

const pageTitle = computed(() => labelMap[props.mode]?.title || '客户中心')
const keywordPlaceholder = computed(() => labelMap[props.mode]?.keyword || '搜索')
const scrollX = computed(() => (props.mode === 'customers' ? 1320 : props.mode === 'contracts' ? 1320 : 940))
const detailWidth = computed(() => Math.min(1040, Math.max(760, Math.floor(window.innerWidth * 0.66))))

const loading = ref(false)
const detailLoading = ref(false)
const salesUserLoading = ref(false)
const rows = ref([])
const detail = ref(null)
const detailVisible = ref(false)
const dashboard = reactive({ customers: 0, active_customers: 0, contracts: 0, expiring_contracts: 0, contacts: 0, unsettled_bills: 0 })
const pagination = reactive({ page: 1, pageSize: 20, itemCount: 0, pageSizes: [20, 50, 100] })
const query = reactive({ keyword: '', lifecycle: null, customer_level: null, entity_type: null, signing_entity_id: null, customer_id: null, status: null, role: null })
const options = reactive({
  signingEntities: [],
  customers: [],
  entityTypes: [],
  lifecycles: [],
  levels: [],
  contactRoles: [],
  contactTypes: [
    { label: '个人', value: 'person' },
    { label: '组邮箱', value: 'group' },
  ],
  contractStatuses: [],
  billStatuses: [],
  currencies: [],
})

const customerModal = reactive({ show: false, loading: false, form: emptyCustomer() })
const contractModal = reactive({ show: false, loading: false, form: emptyContract() })
const contactModal = reactive({ show: false, loading: false, form: emptyContact() })
const billModal = reactive({ show: false, loading: false, form: emptyBill() })
const salesUsers = ref([])

const salesOwnerOptions = computed(() => {
  const options = salesUsers.value.map((user) => {
    const label = getUserDisplayName(user)
    return { label, value: label }
  }).filter((item) => item.label)
  const current = String(customerModal.form.sales_owner || '').trim()
  if (current && !options.some((item) => item.value === current)) {
    options.unshift({ label: current, value: current })
  }
  return options
})

const invoiceRegionOptions = [
  { label: '中国大陆', value: 'CN' },
  { label: '中国香港', value: 'HK' },
  { label: '中国台湾', value: 'TW' },
  { label: '新加坡', value: 'SG' },
  { label: '欧盟 / 欧洲', value: 'EU' },
  { label: '美国', value: 'US' },
  { label: '其他国家/地区', value: 'OTHER' },
]
const invoiceTypeOptions = [
  { label: '增值税专用发票', value: 'cn_vat_special' },
  { label: '增值税普通发票', value: 'cn_vat_normal' },
  { label: 'Commercial Invoice', value: 'commercial_invoice' },
  { label: 'Tax Invoice', value: 'tax_invoice' },
  { label: 'Receipt', value: 'receipt' },
]
const billingCycleOptions = [
  { label: '月结', value: 'monthly' },
  { label: '季度结算', value: 'quarterly' },
  { label: '半年结算', value: 'semi_annual' },
  { label: '年付', value: 'annual' },
  { label: '一次性', value: 'one_time' },
]
const paymentTermOptions = [
  { label: '预付', value: 'prepaid' },
  { label: 'Net 7', value: 'net_7' },
  { label: 'Net 15', value: 'net_15' },
  { label: 'Net 30', value: 'net_30' },
  { label: 'Net 45', value: 'net_45' },
  { label: 'Net 60', value: 'net_60' },
]
const paymentMethodOptions = [
  { label: '银行转账', value: 'bank_transfer' },
  { label: '电汇 / TT', value: 'telegraphic_transfer' },
  { label: 'PayPal', value: 'paypal' },
  { label: 'Wise', value: 'wise' },
  { label: '信用卡', value: 'credit_card' },
  { label: '其他', value: 'other' },
]

const summaryCards = computed(() => [
  { label: '客户总数', value: dashboard.customers, icon: 'mdi:account-group-outline', tone: 'blue' },
  { label: '正式客户', value: dashboard.active_customers, icon: 'mdi:account-check-outline', tone: 'green' },
  { label: '合同总数', value: dashboard.contracts, icon: 'mdi:file-sign', tone: 'purple' },
  { label: '即将到期', value: dashboard.expiring_contracts, icon: 'mdi:calendar-alert-outline', tone: 'orange' },
  { label: '联系人', value: dashboard.contacts, icon: 'mdi:card-account-phone-outline', tone: 'cyan' },
  { label: '未结算账单', value: dashboard.unsettled_bills, icon: 'mdi:receipt-clock-outline', tone: 'red' },
])

const ModalFooter = defineComponent({
  props: { loading: Boolean },
  emits: ['cancel', 'save'],
  setup(componentProps, { emit }) {
    return () => h(NSpace, { justify: 'end' }, () => [
      h(NButton, { onClick: () => emit('cancel') }, () => '取消'),
      h(NButton, { type: 'primary', loading: componentProps.loading, onClick: () => emit('save') }, () => '保存'),
    ])
  },
})

const SubTable = defineComponent({
  props: { title: String, columns: Array, data: Array },
  emits: ['add'],
  setup(componentProps, { emit }) {
    return () => h('div', { class: 'sub-table' }, [
      h('div', { class: 'sub-table__head' }, [
        h('strong', componentProps.title),
        h(NButton, { size: 'small', type: 'primary', onClick: () => emit('add') }, () => '新增'),
      ]),
      h(NDataTable, { columns: componentProps.columns, data: componentProps.data, pagination: false, scrollX: 940 }),
    ])
  },
})

function optionize(rows = []) {
  return rows.map((item) => ({ label: item.legal_name || item.name, value: item.id }))
}

function optionLabel(options, value) {
  return options.find((item) => item.value === value)?.label || value || '-'
}

function safeJsonParse(value) {
  if (!value || typeof value !== 'string') return null
  try {
    const data = JSON.parse(value)
    return data && typeof data === 'object' ? data : null
  } catch {
    return null
  }
}

function defaultInvoiceProfile() {
  return {
    invoice_region: 'CN',
    invoice_type: 'cn_vat_special',
    invoice_title: '',
    tax_id: '',
    registration_no: '',
    invoice_email: '',
    bank_name: '',
    bank_account: '',
    swift_code: '',
    iban: '',
    invoice_address: '',
    local_requirement: '',
  }
}

function defaultFinanceProfile() {
  return {
    settlement_currency: 'USD',
    billing_cycle: 'monthly',
    payment_terms: 'net_30',
    payment_method: 'bank_transfer',
    credit_limit: 0,
    allow_arrears: false,
    reconciliation_day: null,
    finance_contact: '',
    finance_remark: '',
  }
}

function parseInvoiceProfile(value) {
  const data = safeJsonParse(value)
  if (data?.version === 1 && data.type === 'invoice_profile') {
    return { ...defaultInvoiceProfile(), ...(data.data || {}) }
  }
  const profile = defaultInvoiceProfile()
  profile.local_requirement = value || ''
  return profile
}

function parseFinanceProfile(value) {
  const data = safeJsonParse(value)
  if (data?.version === 1 && data.type === 'finance_profile') {
    return { ...defaultFinanceProfile(), ...(data.data || {}) }
  }
  const profile = defaultFinanceProfile()
  profile.finance_remark = value || ''
  return profile
}

function serializeProfile(type, data) {
  return JSON.stringify({ version: 1, type, data })
}

function formatInvoiceInfo(value) {
  const profile = parseInvoiceProfile(value)
  const lines = [
    `开票地区：${optionLabel(invoiceRegionOptions, profile.invoice_region)}`,
    `发票/账单类型：${optionLabel(invoiceTypeOptions, profile.invoice_type)}`,
    `发票抬头：${profile.invoice_title || '-'}`,
    `税号 / VAT / GST：${profile.tax_id || '-'}`,
    `注册号 / BR / UEN：${profile.registration_no || '-'}`,
    `开票邮箱：${profile.invoice_email || '-'}`,
    `开票地址：${profile.invoice_address || '-'}`,
  ]
  if (profile.bank_name || profile.bank_account) {
    lines.push(`开户银行：${profile.bank_name || '-'}`, `银行账号：${profile.bank_account || '-'}`)
  }
  if (profile.swift_code) lines.push(`SWIFT / Routing：${profile.swift_code}`)
  if (profile.iban) lines.push(`IBAN：${profile.iban}`)
  if (profile.local_requirement) lines.push(`地区特殊说明：${profile.local_requirement}`)
  return lines.join('\n')
}

function formatFinanceInfo(value) {
  const profile = parseFinanceProfile(value)
  return [
    `结算币种：${profile.settlement_currency || '-'}`,
    `结算周期：${optionLabel(billingCycleOptions, profile.billing_cycle)}`,
    `账期：${optionLabel(paymentTermOptions, profile.payment_terms)}`,
    `付款方式：${optionLabel(paymentMethodOptions, profile.payment_method)}`,
    `信用额度：${Number(profile.credit_limit || 0).toLocaleString()}`,
    `允许欠款：${profile.allow_arrears ? '是' : '否'}`,
    `对账日：${profile.reconciliation_day ? `每月 ${profile.reconciliation_day} 日` : '-'}`,
    `财务联系人：${profile.finance_contact || '-'}`,
    `财务备注：${profile.finance_remark || '-'}`,
  ].join('\n')
}

function getUserDisplayName(user) {
  return user?.alias || user?.username || user?.email || ''
}

async function loadSalesUsers() {
  salesUserLoading.value = true
  try {
    const res = await api.getUserList({ page: 1, page_size: 9999 })
    salesUsers.value = (res?.data || []).filter((item) => item.is_active !== false)
  } finally {
    salesUserLoading.value = false
  }
}

async function loadOptions() {
  const res = await api.customerCenterApi.options()
  const data = res.data || {}
  options.signingEntities = optionize(data.signing_entities || [])
  options.customers = data.customers || []
  options.entityTypes = data.entity_types || []
  options.lifecycles = data.lifecycles || []
  options.levels = data.levels || []
  options.contactRoles = data.contact_roles || []
  options.contactTypes = data.contact_types || options.contactTypes
  options.contractStatuses = data.contract_statuses || []
  options.billStatuses = data.bill_statuses || []
  options.currencies = data.currencies || []
}

async function loadDashboard() {
  const res = await api.customerCenterApi.dashboard()
  Object.assign(dashboard, res.data || {})
}

function pageParams(extra = {}) {
  return { page: pagination.page, page_size: pagination.pageSize, ...extra }
}

async function loadPage() {
  loading.value = true
  try {
    let res
    if (props.mode === 'customers') {
      res = await api.customerCenterApi.listCustomers(pageParams({
        keyword: query.keyword,
        lifecycle: query.lifecycle || '',
        customer_level: query.customer_level || '',
        entity_type: query.entity_type || '',
        signing_entity_id: query.signing_entity_id || undefined,
      }))
    } else if (props.mode === 'contracts') {
      res = await api.customerCenterApi.listContracts(pageParams({ keyword: query.keyword, customer_id: query.customer_id || undefined, status: query.status || '' }))
    } else {
      res = await api.customerCenterApi.listContacts(pageParams({ keyword: query.keyword, customer_id: query.customer_id || undefined, role: query.role || '' }))
    }
    rows.value = res.data || []
    pagination.itemCount = res.total || 0
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  Object.assign(query, { keyword: '', lifecycle: null, customer_level: null, entity_type: null, signing_entity_id: null, customer_id: null, status: null, role: null })
  pagination.page = 1
  loadPage()
}

function handlePageSizeChange(size) {
  pagination.pageSize = size
  pagination.page = 1
  loadPage()
}

async function refreshAll() {
  await Promise.all([loadOptions(), loadSalesUsers(), loadDashboard(), loadPage()])
}

function rowActions(row, edit, remove) {
  return h(NSpace, { size: 6 }, () => [
    h(NButton, { size: 'small', secondary: true, type: 'info', onClick: () => edit(row) }, { icon: () => h(TheIcon, { icon: 'mdi:pencil', size: 15 }), default: () => '编辑' }),
    h(NPopconfirm, { onPositiveClick: () => remove(row) }, { trigger: () => h(NButton, { size: 'small', secondary: true, type: 'error' }, { icon: () => h(TheIcon, { icon: 'mdi:trash-can-outline', size: 15 }), default: () => '删除' }), default: () => '确认删除？' }),
  ])
}

const customerColumns = [
  { title: '客户简称', key: 'name', width: 170, fixed: 'left', ellipsis: { tooltip: true } },
  { title: '客户全称', key: 'legal_name', width: 260, ellipsis: { tooltip: true } },
  { title: '主体类型', key: 'entity_type_label', width: 110 },
  { title: '签约主体', key: 'signing_entity_name', width: 190, ellipsis: { tooltip: true } },
  { title: '等级', key: 'customer_level_label', width: 120, render: (row) => renderTag(row.customer_level_label, levelType(row.customer_level)) },
  { title: '生命周期', key: 'lifecycle_label', width: 120, render: (row) => renderTag(row.lifecycle_label, lifecycleType(row.lifecycle)) },
  { title: '所属销售', key: 'sales_owner', width: 130 },
  { title: '所属地区', key: 'region', width: 130 },
  { title: '联系人', key: 'contact_count', width: 90 },
  { title: '合同', key: 'contract_count', width: 80 },
  { title: '账单', key: 'bill_count', width: 80 },
  { title: '操作', key: 'actions', width: 150, fixed: 'right', render: (row) => rowActions(row, openCustomerModal, removeCustomer) },
]
const contractColumns = [
  { title: '合同编号', key: 'contract_no', width: 150, fixed: 'left', ellipsis: { tooltip: true } },
  { title: '合同名称', key: 'name', width: 260, ellipsis: { tooltip: true } },
  { title: '签约客户', key: 'customer_name', width: 180, ellipsis: { tooltip: true } },
  { title: '签约主体', key: 'signing_entity_name', width: 190, ellipsis: { tooltip: true } },
  { title: '状态', key: 'status_label', width: 110, render: (row) => renderTag(row.status_label, contractType(row.status)) },
  { title: '生效日期', key: 'effective_date', width: 120 },
  { title: '到期日期', key: 'expiry_date', width: 120 },
  { title: '金额', key: 'amount', width: 120, render: (row) => `${row.currency || ''} ${Number(row.amount || 0).toLocaleString()}` },
  { title: '提醒', key: 'reminder_days', width: 100, render: (row) => (row.reminder_enabled ? `${row.reminder_days || 0}天` : '关闭') },
  { title: '操作', key: 'actions', width: 150, fixed: 'right', render: (row) => rowActions(row, openContractModal, removeContract) },
]
const contactColumns = [
  { title: '联系人', key: 'name', width: 150, fixed: 'left' },
  { title: '类型', key: 'contact_type_label', width: 90, render: (row) => renderTag(row.contact_type_label, row.contact_type === 'group' ? 'warning' : 'default') },
  { title: '所属客户', key: 'customer_name', width: 200, ellipsis: { tooltip: true } },
  { title: '角色', key: 'role_label', width: 120, render: (row) => renderTag(row.role_label, 'info') },
  { title: '邮箱', key: 'email', width: 190, ellipsis: { tooltip: true } },
  { title: '电话', key: 'phone', width: 130 },
  { title: '操作', key: 'actions', width: 150, fixed: 'right', render: (row) => rowActions(row, openContactModal, removeContact) },
]
const billColumns = [
  { title: '账单编号', key: 'bill_no', width: 140 },
  { title: '账单名称', key: 'title', width: 200, ellipsis: { tooltip: true } },
  { title: '状态', key: 'status_label', width: 100, render: (row) => renderTag(row.status_label, row.is_settled ? 'success' : 'warning') },
  { title: '金额', key: 'amount', width: 120, render: (row) => `${row.currency || ''} ${Number(row.amount || 0).toLocaleString()}` },
  { title: '账单日期', key: 'bill_date', width: 120 },
  { title: '到期日期', key: 'due_date', width: 120 },
  { title: '无后续业务', key: 'business_closed', width: 110, render: (row) => (row.business_closed ? renderTag('是', 'success') : '-') },
  { title: '操作', key: 'actions', width: 150, render: (row) => rowActions(row, openBillModal, removeBill) },
]
const columns = computed(() => (props.mode === 'customers' ? customerColumns : props.mode === 'contracts' ? contractColumns : contactColumns))

function renderTag(text, type = 'default') {
  return h(NTag, { size: 'small', round: true, type }, () => text || '-')
}

function levelType(value) {
  return value === 'S' || value === 'A' ? 'success' : value === 'D' ? 'error' : 'info'
}

function lifecycleType(value) {
  return value === 'active' ? 'success' : value === 'paused' ? 'warning' : value === 'terminated' ? 'error' : 'info'
}

function contractType(value) {
  return value === 'active' ? 'success' : value === 'expiring' ? 'warning' : value === 'expired' || value === 'terminated' ? 'error' : 'info'
}

function customerRowProps(row) {
  return { style: 'cursor:pointer;', onDblclick: () => openDetail(row.id) }
}

async function openDetail(id) {
  detailVisible.value = true
  detailLoading.value = true
  try {
    const res = await api.customerCenterApi.getCustomer(id)
    detail.value = res.data
  } finally {
    detailLoading.value = false
  }
}

function emptyCustomer() {
  return { id: null, customer_code: '', name: '', legal_name: '', alias: '', entity_type: 'enterprise', signing_entity_id: null, customer_level: 'C', lifecycle: 'active', sales_owner: '', region: '', address: '', invoice_info: '', finance_info: '', invoice_profile: defaultInvoiceProfile(), finance_profile: defaultFinanceProfile(), remark: '', status: true }
}
function emptyContract() {
  return { id: null, customer_id: detail.value?.id || null, signing_entity_id: null, contract_no: '', name: '', status: 'draft', effective_date: null, expiry_date: null, amount: 0, currency: 'USD', attachment_url: '', reminder_days: 30, reminder_enabled: true, remark: '' }
}
function emptyContact() {
  return { id: null, customer_id: detail.value?.id || null, contact_type: 'person', name: '', role: 'business', title: '', email: '', phone: '', address: '', remark: '', status: true }
}
function emptyBill() {
  return { id: null, customer_id: detail.value?.id || null, bill_no: '', title: '', status: 'draft', amount: 0, currency: 'USD', bill_date: null, due_date: null, is_settled: false, business_closed: false, remark: '' }
}

function openCustomerModal(row = null) {
  const form = row ? { ...emptyCustomer(), ...row } : emptyCustomer()
  form.invoice_profile = parseInvoiceProfile(form.invoice_info)
  form.finance_profile = parseFinanceProfile(form.finance_info)
  if (!form.invoice_profile.invoice_title) form.invoice_profile.invoice_title = form.legal_name || form.name || ''
  customerModal.form = form
  customerModal.show = true
}
function openContractModal(row = null) {
  contractModal.form = row ? { ...emptyContract(), ...row } : emptyContract()
  contractModal.show = true
}
function openContactModal(row = null) {
  const form = row ? { ...emptyContact(), ...row } : emptyContact()
  form.contact_type = normalizeContactType(form)
  if (form.contact_type === 'group') form.title = ''
  contactModal.form = form
  contactModal.show = true
}
function openBillModal(row = null) {
  billModal.form = row ? { ...emptyBill(), ...row } : emptyBill()
  billModal.show = true
}

async function saveCustomer() {
  if (!customerModal.form.name) return window.$message?.warning('请填写客户简称')
  customerModal.loading = true
  try {
    const payload = { ...customerModal.form }
    payload.alias = payload.name
    payload.invoice_info = serializeProfile('invoice_profile', payload.invoice_profile)
    payload.finance_info = serializeProfile('finance_profile', payload.finance_profile)
    delete payload.invoice_profile
    delete payload.finance_profile
    if (!payload.id) delete payload.customer_code
    if (payload.id) await api.customerCenterApi.updateCustomer(payload.id, payload)
    else await api.customerCenterApi.createCustomer(payload)
    customerModal.show = false
    window.$message?.success('客户已保存')
    await refreshAfterEdit()
  } finally {
    customerModal.loading = false
  }
}

async function saveContract() {
  if (!contractModal.form.customer_id || !contractModal.form.name) return window.$message?.warning('请选择客户并填写合同名称')
  contractModal.loading = true
  try {
    const payload = { ...contractModal.form }
    if (payload.id) await api.customerCenterApi.updateContract(payload.id, payload)
    else await api.customerCenterApi.createContract(payload)
    contractModal.show = false
    window.$message?.success('合同已保存')
    await refreshAfterEdit()
  } finally {
    contractModal.loading = false
  }
}

async function saveContact() {
  if (!contactModal.form.customer_id || (!contactModal.form.name && !contactModal.form.email)) return window.$message?.warning('请选择客户，并填写联系人姓名/组名或邮箱')
  contactModal.loading = true
  try {
    const payload = { ...contactModal.form }
    payload.contact_type = normalizeContactType(payload)
    if (payload.contact_type === 'group') payload.title = ''
    if (payload.id) await api.customerCenterApi.updateContact(payload.id, payload)
    else await api.customerCenterApi.createContact(payload)
    contactModal.show = false
    window.$message?.success('联系人已保存')
    await refreshAfterEdit()
  } finally {
    contactModal.loading = false
  }
}

function normalizeContactType(row = {}) {
  if (row.contact_type === 'group' || row.contact_type === 'person') return row.contact_type
  if (row.contact_type_label === '组邮箱') return 'group'
  return 'person'
}

async function saveBill() {
  if (!billModal.form.customer_id || !billModal.form.title) return window.$message?.warning('请选择客户并填写账单名称')
  billModal.loading = true
  try {
    const payload = { ...billModal.form }
    if (payload.id) await api.customerCenterApi.updateBill(payload.id, payload)
    else await api.customerCenterApi.createBill(payload)
    billModal.show = false
    window.$message?.success('账单已保存')
    await refreshAfterEdit()
  } finally {
    billModal.loading = false
  }
}

async function removeCustomer(row) {
  await api.customerCenterApi.deleteCustomer(row.id)
  window.$message?.success('客户已删除')
  await refreshAfterEdit()
}
async function removeContract(row) {
  await api.customerCenterApi.deleteContract(row.id)
  window.$message?.success('合同已删除')
  await refreshAfterEdit()
}
async function removeContact(row) {
  await api.customerCenterApi.deleteContact(row.id)
  window.$message?.success('联系人已删除')
  await refreshAfterEdit()
}
async function removeBill(row) {
  await api.customerCenterApi.deleteBill(row.id)
  window.$message?.success('账单已删除')
  await refreshAfterEdit()
}

async function refreshAfterEdit() {
  await loadOptions()
  await loadDashboard()
  await loadPage()
  if (detail.value?.id) await openDetail(detail.value.id)
}

onMounted(refreshAll)
</script>

<style scoped>
.crm-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: calc(100vh - 120px);
}
.crm-summary {
  display: grid;
  grid-template-columns: repeat(6, minmax(120px, 1fr));
  gap: 12px;
}
.crm-summary article {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 76px;
  padding: 14px 16px;
  border: 1px solid #e7edf4;
  border-radius: 8px;
  background: #fff;
}
.crm-summary small,
.eyebrow {
  color: #607089;
  font-size: 12px;
  font-weight: 700;
}
.crm-summary strong {
  display: block;
  color: #111827;
  font-size: 26px;
  line-height: 1.1;
}
.crm-summary__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 8px;
}
.blue { color: #2563eb; background: #eaf1ff; }
.green { color: #16a34a; background: #e9f8ef; }
.purple { color: #6d28d9; background: #f1ebff; }
.orange { color: #ea580c; background: #fff1e8; }
.cyan { color: #0891b2; background: #e8f8fb; }
.red { color: #e11d48; background: #fff0f3; }
.crm-panel {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 680px;
  padding: 18px;
  border: 1px solid #e7edf4;
  border-radius: 8px;
  background: #fff;
}
.crm-panel__head,
.sub-table__head,
.detail-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.crm-panel__head h2 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 22px;
}
.crm-filter {
  display: grid;
  grid-template-columns: minmax(260px, 1.5fr) repeat(4, minmax(130px, 1fr)) 78px 78px;
  gap: 10px;
  margin: 16px 0;
}
.crm-filter--compact {
  grid-template-columns: minmax(180px, 1fr) minmax(160px, 1fr) 78px 78px;
}
.crm-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 14px;
}
.detail-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.detail-metrics,
.info-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(140px, 1fr));
  gap: 10px;
}
.detail-metrics article,
.info-grid article {
  padding: 12px;
  border: 1px solid #e7edf4;
  border-radius: 8px;
  background: #f8fafc;
}
.detail-metrics span,
.info-grid span {
  display: block;
  color: #64748b;
  font-size: 12px;
}
.detail-metrics strong,
.info-grid strong {
  display: block;
  margin-top: 4px;
  color: #0f172a;
}
.text-block {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid #e7edf4;
  border-radius: 8px;
  background: #fff;
}
.text-block p {
  margin: 8px 0 0;
  white-space: pre-wrap;
}
.sub-table {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
:deep(.crm-modal) {
  width: min(920px, 92vw);
}
:deep(.customer-modal) {
  width: min(960px, 94vw);
}
:deep(.customer-modal .n-card-header) {
  padding: 20px 24px 12px;
}
:deep(.contact-modal .n-card-header) {
  padding: 20px 24px 12px;
}
:deep(.customer-modal .n-card__content) {
  padding: 0 24px 8px;
}
:deep(.contact-modal .n-card__content) {
  padding: 0 24px 8px;
}
:deep(.customer-modal .n-card__footer) {
  padding: 14px 24px 20px;
  border-top: 1px solid #e8edf3;
  background: #fbfdff;
}
:deep(.contact-modal .n-card__footer) {
  padding: 14px 24px 20px;
  border-top: 1px solid #e8edf3;
  background: #fbfdff;
}
.customer-modal__intro {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 14px 16px;
  border: 1px solid #dceafe;
  border-radius: 8px;
  background: linear-gradient(135deg, #f8fbff 0%, #eef8f5 100%);
}
.customer-modal__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  border-radius: 8px;
  color: #0f766e;
  background: #dff7f1;
}
.customer-modal__intro strong {
  display: block;
  color: #0f172a;
  font-size: 16px;
}
.customer-modal__intro p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}
.contact-modal__intro {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 14px 16px;
  border: 1px solid #dceafe;
  border-radius: 8px;
  background: #f8fbff;
}
.contact-modal__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  border-radius: 8px;
  color: #0891b2;
  background: #e8f8fb;
}
.contact-modal__intro strong {
  display: block;
  color: #0f172a;
  font-size: 16px;
}
.contact-modal__intro p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}
.customer-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.contact-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.form-section {
  padding: 14px 16px 2px;
  border: 1px solid #e8edf3;
  border-radius: 8px;
  background: #fff;
}
.form-section__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #edf2f7;
}
.form-section__head span {
  color: #0f172a;
  font-size: 15px;
  font-weight: 700;
}
.form-section__head small {
  color: #94a3b8;
  font-size: 12px;
}
@media (max-width: 1280px) {
  .crm-summary { grid-template-columns: repeat(3, 1fr); }
  .crm-filter { grid-template-columns: 1fr 1fr; }
  .detail-metrics,
  .info-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 720px) {
  :deep(.customer-modal),
  :deep(.contact-modal) {
    width: 96vw;
  }
  .customer-modal__intro,
  .contact-modal__intro {
    align-items: flex-start;
  }
  .form-section {
    padding: 12px 12px 0;
  }
  .form-section__head {
    align-items: flex-start;
    flex-direction: column;
    gap: 2px;
  }
}
</style>
