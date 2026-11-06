<template>
  <AppPage>
    <div class="billing-page">
      <div class="toolbar">
        <div>
          <h2>账单管理</h2>
          <p>从订单出账，按币种管理应收、回款与逾期。</p>
        </div>
        <CButton
          v-if="can('post', '/preview')"
          show-save
          save-text="从订单出账 / 建立计划"
          :disabled="busy || optionsLoading"
          @save="openGenerate"
        />
      </div>
      <n-alert v-if="optionsError" type="error"
        >{{ optionsError }}<CButton show-save save-text="重试加载客户" @save="loadCustomers"
      /></n-alert>
      <n-tabs v-model:value="tab" type="line" @update:value="refresh">
        <n-tab-pane name="bills" tab="账单">
          <div class="filters">
            <n-input
              v-model:value="query.keyword"
              clearable
              placeholder="账单号 / 名称"
              @keyup.enter="search"
            />
            <n-select
              v-model:value="query.customer_id"
              :options="customerOptions"
              clearable
              filterable
              placeholder="客户"
            />
            <n-select
              v-model:value="query.status"
              :options="statusOptions"
              clearable
              placeholder="账单状态"
            />
            <n-checkbox v-model:checked="query.overdue">仅逾期</n-checkbox>
            <CButton show-save save-text="查询" :disabled="loading" @save="search" />
          </div>
          <div v-if="summary.length" class="summaries">
            <div v-for="group in summary" :key="group.currency" class="summary-card">
              <strong>{{ group.currency }}</strong>
              <span>待收 {{ money(group.receivable) }}</span
              ><span>已收 {{ money(group.paid) }}</span>
              <span class="overdue">逾期 {{ money(group.overdue) }}</span>
            </div>
          </div>
          <p class="hint">汇总随筛选条件变化，仅计入已锁定账单，草稿及作废账单不计入应收。</p>
          <n-alert v-if="error" type="error"
            >{{ error }}<CButton show-save save-text="重试" @save="loadBills"
          /></n-alert>
          <n-data-table
            :columns="columns"
            :data="rows"
            :loading="loading"
            :scroll-x="1510"
            :row-key="(row) => row.id"
          />
          <n-pagination
            v-model:page="page"
            :page-size="20"
            :item-count="total"
            class="pagination"
            @update:page="loadBills"
          />
        </n-tab-pane>
        <n-tab-pane name="plans" tab="自动出账计划">
          <n-alert type="info" class="gap"
            >每日按上海时区检查到期计划，生成待审核草稿。预付在账期开始日出账，后付在账期结束次日出账。失败保留原因，可手动重试；停用后不会继续出账。</n-alert
          >
          <n-alert v-if="error" type="error"
            >{{ error }}<CButton show-save save-text="重试" @save="loadPlans"
          /></n-alert>
          <n-data-table
            :columns="planColumns"
            :data="plans"
            :loading="loading"
            :scroll-x="1160"
            :row-key="(row) => row.id"
          />
        </n-tab-pane>
      </n-tabs>
    </div>

    <n-modal
      v-model:show="editor.show"
      class="billing-editor"
      :style="editorTheme"
      preset="card"
      :title="editor.id ? '调整账单草稿' : '订单出账'"
      style="width: min(1080px, calc(100vw - 24px))"
      :closable="!busy"
      :mask-closable="!busy"
      :close-on-esc="!busy"
    >
      <div class="editor-intro">
        <span class="editor-intro-mark"
          ><TheIcon icon="mdi:file-document-outline" :size="22"
        /></span>
        <div>
          <strong>{{ editor.id ? '核对并调整账单信息' : '将订单费用整理为账单' }}</strong>
          <p>
            {{
              editor.id
                ? '保存后仍为草稿，审核锁定后进入应收。'
                : '填写出账信息 → 预览金额 → 生成草稿或建立自动计划'
            }}
          </p>
        </div>
      </div>
      <n-form label-placement="top" :disabled="busy" class="billing-editor-form">
        <section class="editor-section" aria-label="基本信息">
          <div class="section-heading">
            <span class="section-marker"></span>
            <div>
              <h3>基本信息</h3>
              <p>选择客户与订单，确认本次出账范围。</p>
            </div>
          </div>
          <div class="form-grid">
            <n-form-item label="账单名称" required
              ><template #label
                ><BillingFieldLabel label="账单名称" :help="fieldHelp.title" /></template
              ><n-input v-model:value="form.title" :maxlength="160"
            /></n-form-item>
            <n-form-item v-if="!editor.id" label="客户（正式名称）" required
              ><template #label
                ><BillingFieldLabel
                  label="客户（正式名称）"
                  :help="fieldHelp.customer_id" /></template
              ><n-select
                v-model:value="form.customer_id"
                :options="activeCustomerOptions"
                filterable
                @update:value="changeCustomer"
            /></n-form-item>
            <n-form-item v-if="!editor.id" label="关联订单" required
              ><template #label
                ><BillingFieldLabel label="关联订单" :help="fieldHelp.order_ids" /></template
              ><n-select
                v-model:value="form.order_ids"
                filterable
                multiple
                :options="orderOptions"
                :loading="ordersLoading"
                placeholder="选择同一客户的订单"
            /></n-form-item>
            <n-form-item v-if="!editor.id" label="出账币种" required
              ><template #label
                ><BillingFieldLabel label="出账币种" :help="fieldHelp.currency" /></template
              ><n-select v-model:value="form.currency" :options="currencies"
            /></n-form-item>
          </div>
        </section>
        <section v-if="!editor.id" class="editor-section" aria-label="计费规则">
          <div class="section-heading">
            <span class="section-marker"></span>
            <div>
              <h3>计费规则</h3>
              <p>设置账期与服务时间，计算实际应收费用。</p>
            </div>
          </div>
          <div class="form-grid">
            <n-form-item v-if="!editor.id" label="计费方式"
              ><template #label
                ><BillingFieldLabel label="计费方式" :help="fieldHelp.calendar_mode" /></template
              ><n-select
                v-model:value="form.calendar_mode"
                :options="[
                  { label: '自然月（按月内实际天数折算）', value: 'calendar' },
                  { label: '周年日（按服务起始日对齐）', value: 'anniversary' },
                ]"
            /></n-form-item>
            <n-form-item v-if="!editor.id" label="计费周期"
              ><template #label
                ><BillingFieldLabel label="计费周期" :help="fieldHelp.months" /></template
              ><n-select
                v-model:value="form.months"
                :options="
                  [1, 3, 6, 12, 24, 36].map((value) => ({ value, label: `${value} 个月` }))
                "
            /></n-form-item>
            <n-form-item v-if="!editor.id" label="账期开始日" required
              ><template #label
                ><BillingFieldLabel label="账期开始日" :help="fieldHelp.period_start" /></template
              ><n-date-picker
                v-model:formatted-value="form.period_start"
                value-format="yyyy-MM-dd"
                type="date"
            /></n-form-item>
            <n-form-item v-if="!editor.id" label="服务计费开始日" required
              ><template #label
                ><BillingFieldLabel
                  label="服务计费开始日"
                  :help="fieldHelp.service_start" /></template
              ><n-date-picker
                v-model:formatted-value="form.service_start"
                value-format="yyyy-MM-dd"
                type="date"
            /></n-form-item>
            <n-form-item v-if="!editor.id" label="服务结束日（可选，含当天）"
              ><template #label
                ><BillingFieldLabel
                  label="服务结束日（可选，含当天）"
                  :help="fieldHelp.service_end" /></template
              ><n-date-picker
                v-model:formatted-value="form.service_end"
                clearable
                value-format="yyyy-MM-dd"
                type="date"
            /></n-form-item>
            <n-form-item v-if="!editor.id" label="首次收取 NRC"
              ><template #label
                ><BillingFieldLabel label="首次收取 NRC" :help="fieldHelp.include_nrc" /></template
              ><n-switch v-model:value="form.include_nrc" /><span class="hint inline"
                >已计收的订单不重复收取</span
              ></n-form-item
            >
          </div>
        </section>
        <section class="editor-section" aria-label="付款安排">
          <div class="section-heading">
            <span class="section-marker"></span>
            <div>
              <h3>付款安排</h3>
              <p>明确出账时点与客户付款期限。</p>
            </div>
          </div>
          <div class="form-grid" :class="{ 'payment-grid': !editor.id }">
            <n-form-item v-if="!editor.id" label="付款安排"
              ><template #label
                ><BillingFieldLabel label="付款安排" :help="fieldHelp.payment_timing" /></template
              ><n-select
                v-model:value="form.payment_timing"
                :options="[
                  { value: 'prepaid', label: '预付' },
                  { value: 'postpaid', label: '后付' },
                ]"
            /></n-form-item>
            <n-form-item label="账单日期" required
              ><template #label
                ><BillingFieldLabel label="账单日期" :help="fieldHelp.bill_date" /></template
              ><n-date-picker
                v-model:formatted-value="form.bill_date"
                value-format="yyyy-MM-dd"
                type="date"
            /></n-form-item>
            <n-form-item label="付款到期日" required
              ><template #label
                ><BillingFieldLabel label="付款到期日" :help="fieldHelp.due_date" /></template
              ><n-date-picker
                v-model:formatted-value="form.due_date"
                value-format="yyyy-MM-dd"
                type="date"
            /></n-form-item>
          </div>
        </section>
        <section class="editor-section" aria-label="金额调整">
          <div class="section-heading">
            <span class="section-marker"></span>
            <div>
              <h3>金额调整</h3>
              <p>填写优惠、补差与税率，无调整时保持默认值。</p>
            </div>
          </div>
          <div class="form-grid">
            <n-form-item label="折扣金额"
              ><template #label
                ><BillingFieldLabel label="折扣金额" :help="fieldHelp.discount" /></template
              ><n-input v-model:value="form.discount" placeholder="0.00"
            /></n-form-item>
            <n-form-item label="变更差额（可为负）"
              ><template #label
                ><BillingFieldLabel
                  label="变更差额（可为负）"
                  :help="fieldHelp.adjustment" /></template
              ><n-input v-model:value="form.adjustment" placeholder="0.00"
            /></n-form-item>
            <n-form-item label="税率（%）"
              ><template #label
                ><BillingFieldLabel label="税率（%）" :help="fieldHelp.tax_rate" /></template
              ><n-input v-model:value="form.tax_rate" placeholder="0"
            /></n-form-item>
            <n-form-item label="折扣 / 差额原因"
              ><template #label
                ><BillingFieldLabel
                  label="折扣 / 差额原因"
                  :help="fieldHelp.adjustment_reason" /></template
              ><n-input v-model:value="form.adjustment_reason" :maxlength="500"
            /></n-form-item>
          </div>
        </section>
        <section class="editor-section" aria-label="汇率与备注">
          <div class="section-heading">
            <span class="section-marker"></span>
            <div>
              <h3>汇率与备注</h3>
              <p>记录本位币换算依据及补充说明。</p>
            </div>
          </div>
          <div class="form-grid">
            <n-form-item label="本位币"
              ><template #label
                ><BillingFieldLabel label="本位币" :help="fieldHelp.local_currency" /></template
              ><n-select v-model:value="form.local_currency" :options="currencies"
            /></n-form-item>
            <n-form-item label="汇率（1 账单币 = 本位币金额）"
              ><template #label
                ><BillingFieldLabel
                  label="汇率（1 账单币 = 本位币金额）"
                  :help="fieldHelp.fx_rate" /></template
              ><n-input v-model:value="form.fx_rate"
            /></n-form-item>
            <n-form-item label="汇率来源" required
              ><template #label
                ><BillingFieldLabel label="汇率来源" :help="fieldHelp.fx_source" /></template
              ><n-input v-model:value="form.fx_source" :maxlength="160"
            /></n-form-item>
            <n-form-item label="汇率日期" required
              ><template #label
                ><BillingFieldLabel label="汇率日期" :help="fieldHelp.fx_date" /></template
              ><n-date-picker
                v-model:formatted-value="form.fx_date"
                value-format="yyyy-MM-dd"
                type="date"
            /></n-form-item>
            <n-form-item label="备注" class="wide"
              ><template #label
                ><BillingFieldLabel label="备注" :help="fieldHelp.remark" /></template
              ><n-input v-model:value="form.remark" type="textarea" :maxlength="2000"
            /></n-form-item>
          </div>
        </section>
      </n-form>
      <div v-if="!editor.id" class="editor-notes">
        <p>
          <strong>计费说明</strong>服务日期适用于所选订单，起止日期不同请分别出账。MRC = 单价 × 数量
          × 月数折算系数；NRC = 单价 × 数量。多币种需分别出账。
        </p>
        <p>
          <strong>自动计划</strong
          >固定当前价格、折扣、税率及汇率，并沿用付款期限。变价时请停用旧计划后新建；跨币种汇率需定期复核。
        </p>
      </div>
      <div v-if="preview" class="editor-section preview">
        <h3>
          出账预览 · {{ preview.currency }} · {{ preview.period_start }} 至 {{ preview.period_end }}
        </h3>
        <n-data-table :columns="lineColumns" :data="preview.lines" :scroll-x="1140" />
        <p class="amounts">
          小计 {{ money(preview.subtotal) }} · 税额 {{ money(preview.tax_amount) }} ·
          <strong>应收 {{ money(preview.amount) }}</strong> · 本位币 {{ form.local_currency }}
          {{ money(preview.local_amount) }}
        </p>
      </div>
      <template #footer>
        <div class="editor-footer">
          <span class="editor-footer-hint">{{
            editor.id
              ? '草稿可调整，锁定后计入应收'
              : preview
              ? '请核对预览金额后再提交'
              : '先预览金额，再生成账单或建立计划'
          }}</span>
          <n-space justify="end">
            <CButton show-cancel :disabled="busy" @cancel="editor.show = false" />
            <CButton
              v-if="editor.id"
              show-save
              save-text="保存草稿"
              :disabled="busy"
              :save-loading="saving"
              @save="saveDraft"
            />
            <template v-else>
              <CButton
                show-save
                save-text="预览金额"
                :disabled="busy || ordersLoading"
                :save-loading="saving"
                @save="previewBill"
              />
              <CButton
                show-save
                save-text="生成账单草稿"
                :disabled="busy || !preview || !can('post', '/generate')"
                @save="commit(false)"
              />
              <CButton
                show-save
                save-text="建立自动出账计划"
                :disabled="busy || !preview || !can('post', '/plans')"
                @save="commit(true)"
              />
            </template>
          </n-space>
        </div>
      </template>
    </n-modal>

    <n-modal
      v-model:show="detailShow"
      preset="card"
      title="账单详情"
      style="width: min(1160px, calc(100vw - 24px))"
      :closable="!busy"
      :mask-closable="!busy"
      :close-on-esc="!busy"
    >
      <template v-if="detail">
        <div class="toolbar">
          <div>
            <h2>{{ detail.title }}</h2>
            <p>{{ detail.bill_no }} · {{ statusLabel(detail.status) }}</p>
          </div>
          <CButton show-save save-text="导出账单明细" :disabled="busy" @save="exportDetail" />
        </div>
        <div class="detail-meta">
          <div>
            <small>客户</small><strong>{{ detail.customer_name }}</strong>
          </div>
          <div>
            <small>签约主体</small><strong>{{ detail.signing_entity_name || '—' }}</strong>
          </div>
          <div>
            <small>计费期间</small
            ><strong>{{ detail.period_start }} 至 {{ detail.period_end }}</strong>
          </div>
          <div>
            <small>账单 / 到期日期</small
            ><strong>{{ detail.bill_date }} / {{ detail.due_date }}</strong>
          </div>
        </div>
        <div class="summaries">
          <div class="summary-card">
            <small>账单金额</small><strong>{{ detail.currency }} {{ money(detail.amount) }}</strong>
          </div>
          <div class="summary-card">
            <small>已收</small
            ><strong>{{ detail.currency }} {{ money(detail.paid_amount) }}</strong>
          </div>
          <div class="summary-card">
            <small>未收</small
            ><strong>{{ detail.currency }} {{ money(detail.outstanding) }}</strong>
          </div>
          <div class="summary-card">
            <small>逾期 / 催收</small
            ><strong>{{ detail.overdue_days }} 天 / {{ detail.reminder_level }} 次</strong>
          </div>
        </div>
        <n-data-table :columns="lineColumns" :data="detail.lines" :scroll-x="1140" />
        <p class="amounts">
          费用小计 {{ money(detail.subtotal) }} − 折扣 {{ money(detail.discount) }} + 变更差额
          {{ money(detail.adjustment) }} + 税额 {{ money(detail.tax_amount) }}（{{
            detail.tax_rate
          }}%）
        </p>
        <p class="hint">
          本位币 {{ detail.local_currency }} {{ money(detail.local_amount) }} · 汇率
          {{ detail.fx_rate }} · 来源 {{ detail.fx_source }} · {{ detail.fx_date }}
        </p>
        <p v-if="detail.settings.adjustment_reason">
          调整原因：{{ detail.settings.adjustment_reason }}
        </p>
        <p v-if="detail.remark">备注：{{ detail.remark }}</p>
        <n-space class="gap">
          <CButton
            v-if="detail.status === 'draft' && can('put', '/bills/{document_id}')"
            show-save
            save-text="调整草稿"
            :disabled="busy"
            @save="editDraft(detail)"
          />
          <CButton
            v-if="detail.status === 'draft' && can('post', '/bills/{document_id}/actions')"
            show-save
            save-text="审核并锁定"
            :disabled="busy"
            @save="ask('issue', detail)"
          />
          <CButton
            v-if="
              ['issued', 'partial'].includes(detail.status) &&
              can('post', '/bills/{document_id}/payments')
            "
            show-save
            save-text="登记收款"
            :disabled="busy"
            @save="openPayment(detail)"
          />
          <CButton
            v-if="detail.overdue_days > 0 && can('post', '/bills/{document_id}/actions')"
            show-save
            save-text="登记催收"
            :disabled="busy"
            @save="ask('remind', detail)"
          />
        </n-space>
        <h3 class="gap">收款流水</h3>
        <n-data-table :data="detail.payments" :columns="paymentColumns" :scroll-x="880" />
        <h3 class="gap">操作记录</h3>
        <div v-for="log in detail.audits" :key="log.id" class="audit">
          <strong>{{ actionLabels[log.action] || log.action }}</strong
          ><span>{{ log.operator_name }} · {{ log.created_at }}</span>
          <p>{{ log.comment || '—' }}</p>
          <p v-if="log.before.amount || log.after.amount" class="hint">
            账单金额 {{ log.before.amount ?? '—' }} → {{ log.after.amount ?? '—' }}；已收
            {{ log.before.paid_amount ?? '—' }} → {{ log.after.paid_amount ?? '—' }}
          </p>
        </div>
      </template>
    </n-modal>

    <n-modal
      v-model:show="paymentForm.show"
      preset="card"
      title="登记收款"
      style="width: min(600px, calc(100vw - 24px))"
      :closable="!busy"
      :mask-closable="!busy"
      :close-on-esc="!busy"
    >
      <n-form label-placement="top" :disabled="busy"
        ><div class="form-grid">
          <n-form-item label="收款流水号" required
            ><template #label
              ><BillingFieldLabel label="收款流水号" :help="fieldHelp.reference" /></template
            ><n-input v-model:value="paymentForm.reference" :maxlength="100"
          /></n-form-item>
          <n-form-item :label="`收款金额（${paymentForm.currency}）`" required
            ><template #label
              ><BillingFieldLabel
                :label="`收款金额（${paymentForm.currency}）`"
                :help="fieldHelp.amount" /></template
            ><n-input v-model:value="paymentForm.amount"
          /></n-form-item>
          <n-form-item label="收款日期" required
            ><template #label
              ><BillingFieldLabel label="收款日期" :help="fieldHelp.payment_date" /></template
            ><n-date-picker
              v-model:formatted-value="paymentForm.payment_date"
              type="date"
              value-format="yyyy-MM-dd"
          /></n-form-item>
          <n-form-item label="收款方式" required
            ><template #label
              ><BillingFieldLabel label="收款方式" :help="fieldHelp.method" /></template
            ><n-input v-model:value="paymentForm.method" :maxlength="80"
          /></n-form-item>
          <n-form-item label="备注" class="wide"
            ><template #label><BillingFieldLabel label="备注" :help="fieldHelp.remark" /></template
            ><n-input v-model:value="paymentForm.remark" type="textarea" :maxlength="500"
          /></n-form-item></div
      ></n-form>
      <template #footer
        ><CButton
          show-save
          show-cancel
          :disabled="busy"
          :save-loading="saving"
          @cancel="paymentForm.show = false"
          @save="savePayment"
      /></template>
    </n-modal>
    <n-modal
      v-model:show="confirmation.show"
      preset="card"
      :title="actionLabels[confirmation.action] || '确认操作'"
      style="width: min(520px, calc(100vw - 24px))"
      :closable="!busy"
      :mask-closable="!busy"
      :close-on-esc="!busy"
    >
      <p>
        {{
          confirmation.action === 'enable'
            ? '确认启用此计划？将沿用原价格及计费规则，从下个未出账账期继续执行，已到期的账期会自动补出草稿。'
            : confirmation.action === 'plan_delete'
            ? '确认删除此自动出账计划？删除后不再执行，已生成账单和历史关联会保留，此计划不能再启用。'
            : confirmation.action === 'delete'
            ? '确认删除此账单？删除后从默认列表移除，可筛选“已删除”查看历史。对应账期可重新出账，自动计划仍按原进度执行。'
            : confirmation.action === 'issue'
            ? '审核后锁定金额及价格快照，不能直接修改。'
            : confirmation.action === 'reverse'
            ? '冲销后恢复应收余额，原收款流水仍保留。'
            : confirmation.action === 'stop'
            ? '停用后不再自动生成账单，已生成账单保持不变。'
            : '仅登记跟进记录，不会自动向客户发送消息。'
        }}
      </p>
      <n-input
        v-if="!['stop', 'enable'].includes(confirmation.action)"
        v-model:value="confirmation.comment"
        type="textarea"
        placeholder="请填写操作原因 / 审核意见"
        :maxlength="500"
        :disabled="busy"
      />
      <template #footer
        ><CButton
          show-save
          show-cancel
          save-text="确认"
          :disabled="busy"
          :save-loading="saving"
          @cancel="confirmation.show = false"
          @save="confirmAction"
      /></template>
    </n-modal>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref, watch } from 'vue'
import { NButton, NSpace, NTag, NTooltip, useThemeVars } from 'naive-ui'
import api from '@/api'
import service from '@/api/crm-billing'
import { usePermissionStore, useUserStore } from '@/store'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import BillingFieldLabel from './components/BillingFieldLabel.vue'

const themeVars = useThemeVars()
const editorTheme = computed(() => ({
  '--editor-surface': themeVars.value.cardColor,
  '--editor-background': themeVars.value.bodyColor,
  '--editor-border': themeVars.value.dividerColor,
  '--editor-muted': themeVars.value.textColor3,
  '--editor-accent': themeVars.value.primaryColor,
}))

const fieldHelp = {
  title:
    '用于识别账单或自动计划，例如“2026 年 11 月机柜服务费”。自动计划后续生成的账单沿用此名称，不参与金额计算。',
  customer_id:
    '选择承担本次费用的客户。正式账单使用客户全称，并保存签约主体及客户资料快照。选择客户后，只能关联该客户的订单。',
  order_ids:
    '选择本次收费的订单，可选多个。金额使用订单中已确认的产品、规格、数量及 MRC/NRC 单价。服务起止日不同的订单请分别出账。',
  currency:
    '本张账单的收费币种，只计算所选订单中该币种的产品。多币种订单需要分别出账，不自动将不同币种合并。',
  calendar_mode:
    '自然月：按每月实际收费天数 ÷ 当月总天数折算。\n周年日：以服务开始日为锚点，例如 11 月 12 日至 12 月 11 日为一个完整月；月底按当月最后一天对齐。',
  period_start:
    '本次账期从哪天开始。自然月必须填每月 1 日；周年日须与服务开始日对齐。\n例如 11 月 12 日起租且按自然月收费：这里填 11 月 1 日，服务计费开始日填 11 月 12 日。',
  months:
    '一张账单覆盖的月数，例如 1 个月为月付、3 个月为季付、12 个月为年付。MRC 按数量和实际覆盖的月份计算；自动计划按此周期继续出账。',
  service_start:
    '服务实际从哪天开始收费，用于首期按天折算，并作为周年日计费的锚点。实际收费从账期开始日和此日期中较晚的一天开始。',
  service_end:
    '最后一个收费日，包含当天，用于末期折算。长期服务可留空。自动计划完成覆盖此日期的最后一期后停止继续出账。',
  payment_timing:
    '控制自动计划的出账时点：预付在账期开始日出账，后付在账期结束的次日出账。手动出账仍使用下面填写的账单日期，此选项不改变 MRC 金额。',
  include_nrc:
    'NRC 是安装、开通等一次性费用。开启时，对尚未计收的订单产品/规格收取 NRC 单价 × 数量；系统自动避免重复收取。\n关闭后本次不收；建立自动计划时，后续也不收。NRC 为 0 时不影响金额。',
  bill_date:
    '账单单据上的出账日期，不决定服务收费天数。自动计划后续按预付/后付规则填写出账日期，并沿用此日期与付款到期日之间的天数间隔。',
  due_date:
    '客户最晚应付款的日期，不得早于账单日期。已锁定账单到期后仍有未收金额，会计算逾期天数。\n例如账单日期为 11 月 6 日、到期日为 12 月 6 日，自动计划沿用 30 天付款期限。',
  discount:
    '从费用小计中扣除的金额，使用账单币种，不是折扣百分比。无优惠填 0；非零时须填写原因。自动计划每期沿用此金额。',
  adjustment:
    '对本期费用的增减金额，使用账单币种。正数补收，负数减免；非零时须填写原因，调整后金额不能为负。自动计划每期沿用此差额。',
  tax_rate:
    '输入百分比数值，例如 6 表示 6%，不收税填 0。税额按“费用小计 − 折扣 + 变更差额”计算后加到应收金额中。',
  adjustment_reason:
    '说明折扣或变更差额的依据，例如合同优惠、服务变更补差。只要折扣或差额不为 0 就必须填写，保存到记录中方便追溯。',
  local_currency:
    '财务汇总使用的本位币。账单本身仍按出账币种收费；本位币金额等于账单应收金额乘以汇率。与出账币种相同时，汇率填 1。',
  fx_rate:
    '表示 1 单位账单币可换算成多少本位币。例如账单为 USD、本位币为 CNY，填 7 表示 1 USD = 7 CNY。同币种必须填 1，不自动获取实时汇率。',
  fx_source:
    '填写汇率依据，例如“合同约定汇率”或“某银行当日牌价”；同币种填“同币种”。用于追溯，不会自动查询该来源。',
  fx_date:
    '记录所用汇率对应的日期，不参与服务费用或逾期天数计算。自动计划沿用此汇率及日期快照，财务需按约定复核。',
  remark: '补充账单或收款说明，便于后续查询，不参与费用计算。',
  reference:
    '银行或其他渠道的收款流水号。同一账单内不能重复使用；完全相同的请求重试不会重复核销，已冲销的流水号也不能重新使用。',
  amount:
    '本次实际收到的金额，必须大于 0 且不超过账单未收余额。仅接受账单币种，支持分多次登记部分收款。',
  payment_date: '实际收到款项的日期，不能晚于今天。用于保存收款流水，不改变账单原定付款到期日。',
  method: '填写实际收款渠道，例如银行转账或现金，用于对账和查询，不会发起扣款。',
}

const userStore = useUserStore()
const permissionStore = usePermissionStore()
function can(method, path) {
  return (
    userStore.isSuperUser || permissionStore.apis.includes(`${method}/api/v1/crm-billing${path}`)
  )
}

const tab = ref('bills'),
  rows = ref([]),
  plans = ref([]),
  customers = ref([]),
  orders = ref([])
const loading = ref(false),
  saving = ref(false),
  optionsLoading = ref(false),
  ordersLoading = ref(false)
const error = ref(''),
  optionsError = ref(''),
  total = ref(0),
  page = ref(1),
  summary = ref([])
const busy = computed(() => saving.value)
const query = reactive({ keyword: '', customer_id: null, status: null, overdue: false })
const editor = reactive({ show: false, id: null })
const form = reactive({}),
  preview = ref(null),
  previewPayload = ref(null)
const detail = ref(null),
  detailShow = ref(false),
  paymentForm = reactive({ show: false })
const confirmation = reactive({ show: false, action: '', row: null, comment: '' })
const currencies = ['CNY', 'USD', 'EUR', 'JPY', 'HKD'].map((value) => ({ value, label: value }))
const statusOptions = [
  { value: 'draft', label: '草稿' },
  { value: 'issued', label: '已锁定 / 未收款' },
  { value: 'partial', label: '部分收款' },
  { value: 'paid', label: '已结清' },
  { value: 'void', label: '历史作废' },
  { value: 'deleted', label: '已删除' },
]
const statusLabel = (value) => statusOptions.find((row) => row.value === value)?.label || value
const actionLabels = {
  generate: '生成草稿',
  edit: '调整草稿',
  issue: '审核锁定',
  void: '作废账单',
  delete: '删除账单',
  payment: '登记收款',
  reverse: '冲销收款',
  remind: '登记催收',
  scheduled: '自动出账',
  stop: '停用计划',
  enable: '启用计划',
  plan_delete: '删除计划',
}
const customerOptions = computed(() =>
  customers.value.map((row) => ({
    value: row.id,
    label: `${row.legal_name || row.name}${
      row.signing_entity_name ? ` · ${row.signing_entity_name}` : ''
    }`,
  }))
)
const activeCustomerOptions = computed(() =>
  customerOptions.value.filter((option) =>
    customers.value.some(
      (row) => row.id === option.value && row.status && row.lifecycle !== 'terminated'
    )
  )
)
const orderOptions = computed(() =>
  orders.value.map((row) => ({ value: row.id, label: `${row.name} · ${row.order_no}` }))
)
function money(value) {
  if (value == null) return '—'
  const [integer, fraction = ''] = String(value).split('.')
  return `${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${fraction.padEnd(2, '0')}`
}
function dateString(date = new Date()) {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' }).format(date)
}
function key() {
  return `BILL-${Date.now()}-${Math.random().toString(36).slice(2)}`
}
async function allPages(fetcher, params = {}) {
  const result = []
  for (let index = 1; ; index++) {
    const response = await fetcher({ ...params, page: index, page_size: 100 })
    result.push(...(response.data || []))
    if (!response.data?.length || result.length >= response.total) return result
  }
}
async function loadCustomers() {
  optionsLoading.value = true
  optionsError.value = ''
  try {
    customers.value = await allPages(api.customerCenterApi.listCustomers)
  } catch (e) {
    optionsError.value = e.message || '客户加载失败'
  } finally {
    optionsLoading.value = false
  }
}
async function loadBills() {
  loading.value = true
  error.value = ''
  try {
    const result = await service.list({
      ...query,
      status: query.status || '',
      page: page.value,
      page_size: 20,
    })
    rows.value = result.data
    total.value = result.total
    summary.value = result.summary || []
  } catch (e) {
    error.value = e.message || '账单加载失败'
    rows.value = []
    summary.value = []
  } finally {
    loading.value = false
  }
}
async function loadPlans() {
  loading.value = true
  error.value = ''
  try {
    plans.value = (await service.plans()).data
  } catch (e) {
    error.value = e.message || '计划加载失败'
  } finally {
    loading.value = false
  }
}
function refresh() {
  return tab.value === 'bills' ? loadBills() : loadPlans()
}
function search() {
  page.value = 1
  loadBills()
}
function openGenerate() {
  editor.id = null
  preview.value = null
  previewPayload.value = null
  orders.value = []
  const day = dateString()
  Object.keys(form).forEach((name) => delete form[name])
  Object.assign(form, {
    title: '',
    customer_id: null,
    order_ids: [],
    currency: 'USD',
    calendar_mode: 'calendar',
    period_start: `${day.slice(0, 7)}-01`,
    months: 1,
    service_start: `${day.slice(0, 7)}-01`,
    service_end: null,
    payment_timing: 'prepaid',
    include_nrc: true,
    bill_date: day,
    due_date: dateString(new Date(Date.now() + 30 * 86400000)),
    discount: '0.00',
    adjustment: '0.00',
    tax_rate: '0',
    adjustment_reason: '',
    remark: '',
    local_currency: 'USD',
    fx_rate: '1',
    fx_source: '同币种',
    fx_date: day,
    request_key: key(),
  })
  editor.show = true
}
async function changeCustomer() {
  form.order_ids = []
  orders.value = []
  ordersLoading.value = true
  const selected = form.customer_id
  try {
    const result = await allPages(api.productCenterApi.listOrders, { customer_id: selected })
    if (form.customer_id === selected) orders.value = result
  } catch {
    /* 请求封装展示错误，可重新选择客户重试 */
  } finally {
    ordersLoading.value = false
  }
}
watch(
  form,
  () => {
    preview.value = null
    previewPayload.value = null
  },
  { deep: true }
)
async function execute(callback) {
  if (busy.value) return
  saving.value = true
  try {
    await callback()
  } catch {
    /* 请求封装展示错误，保留输入以便重试 */
  } finally {
    saving.value = false
  }
}
async function previewBill() {
  if (!form.customer_id || !form.order_ids.length || !form.title.trim())
    return window.$message?.warning('请填写账单名称、客户和订单')
  await execute(async () => {
    const payload = JSON.parse(JSON.stringify(form))
    const result = await service.preview(payload)
    preview.value = result.data
    previewPayload.value = { ...payload, preview_token: result.data.preview_token }
  })
}
async function commit(plan) {
  if (!previewPayload.value) return
  await execute(async () => {
    const result = await (plan
      ? service.createPlan(previewPayload.value)
      : service.generate(previewPayload.value))
    editor.show = false
    window.$message?.success(plan ? '自动出账计划已建立' : '账单草稿已生成')
    if (plan) {
      tab.value = 'plans'
      await loadPlans()
    } else {
      detail.value = result.data
      detailShow.value = true
      tab.value = 'bills'
      await loadBills()
    }
  })
}
async function openDetail(row) {
  await execute(async () => {
    detail.value = (await service.detail(row.id)).data
    detailShow.value = true
  })
}
const termFields = [
  'title',
  'bill_date',
  'due_date',
  'discount',
  'adjustment',
  'tax_rate',
  'adjustment_reason',
  'remark',
  'local_currency',
  'fx_rate',
  'fx_source',
  'fx_date',
]
function editDraft(row) {
  Object.keys(form).forEach((name) => delete form[name])
  for (const name of termFields) form[name] = row.settings[name]
  editor.id = row.id
  editor.show = true
}
async function saveDraft() {
  await execute(async () => {
    detail.value = (await service.update(editor.id, form)).data
    editor.show = false
    await loadBills()
    window.$message?.success('草稿已更新')
  })
}
function openPayment(row) {
  Object.assign(paymentForm, {
    show: true,
    id: row.id,
    reference: '',
    amount: row.outstanding,
    currency: row.currency,
    payment_date: dateString(),
    method: '银行转账',
    remark: '',
  })
}
async function savePayment() {
  await execute(async () => {
    const { id, ...payload } = paymentForm
    delete payload.show
    detail.value = (await service.payment(id, payload)).data
    paymentForm.show = false
    await loadBills()
    window.$message?.success('收款已登记')
  })
}
function ask(action, row) {
  Object.assign(confirmation, { show: true, action, row, comment: '' })
}
async function confirmAction() {
  if (!['stop', 'enable'].includes(confirmation.action) && !confirmation.comment.trim())
    return window.$message?.warning('请填写操作原因')
  await execute(async () => {
    const { action, row, comment } = confirmation
    if (action === 'stop') {
      await service.stopPlan(row.id)
      await loadPlans()
    } else if (action === 'enable') {
      await service.enablePlan(row.id)
      await loadPlans()
    } else if (action === 'plan_delete') {
      await service.deletePlan(row.id, { reason: comment })
      await loadPlans()
    } else if (action === 'delete') {
      await service.remove(row.id, { reason: comment })
      if (detail.value?.id === row.id) detailShow.value = false
      await loadBills()
      if (!rows.value.length && page.value > 1) {
        page.value -= 1
        await loadBills()
      }
    } else {
      const result =
        action === 'reverse'
          ? await service.reverse(detail.value.id, row.id, { reason: comment })
          : await service.action(row.id, { action, comment })
      detail.value = result.data
      await loadBills()
    }
    confirmation.show = false
    window.$message?.success('操作成功')
  })
}
function action(label, icon, callback, type = 'default') {
  const paths = {
    冲销: '/bills/{document_id}/payments/{payment_id}/reverse',
    停用: '/plans/{plan_id}/stop',
    启用: '/plans/{plan_id}/enable',
    '检查 / 重试': '/plans/{plan_id}/run',
  }
  if (paths[label] && !can('post', paths[label])) return null
  return h(NTooltip, null, {
    trigger: () =>
      h(
        NButton,
        {
          size: 'small',
          circle: true,
          quaternary: true,
          type,
          'aria-label': label,
          disabled: busy.value,
          loading: busy.value,
          onClick: (event) => {
            event.stopPropagation()
            if (!busy.value) callback()
          },
        },
        { icon: () => h(TheIcon, { icon, size: 17 }) }
      ),
    default: () => label,
  })
}
function businessColumns(cols) {
  return cols.map((col) => ({ ...col, resizable: col.key !== 'actions' }))
}
const columns = businessColumns([
  { title: '账单号', key: 'bill_no', width: 240, ellipsis: { tooltip: true } },
  { title: '客户', key: 'customer_name', width: 210, ellipsis: { tooltip: true } },
  { title: '账单名称', key: 'title', width: 200, ellipsis: { tooltip: true } },
  { title: '币种', key: 'currency', width: 80 },
  { title: '应收金额', key: 'amount', width: 130, render: (row) => money(row.amount) },
  { title: '已收', key: 'paid_amount', width: 120, render: (row) => money(row.paid_amount) },
  { title: '未收', key: 'outstanding', width: 120, render: (row) => money(row.outstanding) },
  {
    title: '状态',
    key: 'status',
    width: 150,
    render: (row) =>
      h(
        NTag,
        {
          size: 'small',
          type: row.status === 'paid' ? 'success' : row.overdue_days ? 'error' : 'default',
        },
        { default: () => statusLabel(row.status) }
      ),
  },
  { title: '到期日', key: 'due_date', width: 120 },
  { title: '逾期天数', key: 'overdue_days', width: 100 },
  {
    title: '操作',
    key: 'actions',
    fixed: 'right',
    width: 100,
    render: (row) =>
      h(
        NSpace,
        { wrap: false, size: 4 },
        {
          default: () => [
            action('详情', 'mdi:eye-outline', () => openDetail(row)),
            ['draft', 'void'].includes(row.status) && can('delete', '/bills/{document_id}')
              ? action('删除', 'mdi:trash-can-outline', () => ask('delete', row), 'error')
              : null,
          ],
        }
      ),
  },
])
const lineColumns = businessColumns([
  { title: '订单', key: 'order_name', width: 180, ellipsis: { tooltip: true } },
  {
    title: '产品 / 规格',
    key: 'product_name',
    width: 210,
    ellipsis: { tooltip: true },
    render: (row) => `${row.product_name}${row.variant_name ? ` · ${row.variant_name}` : ''}`,
  },
  { title: '数量', key: 'quantity', width: 70 },
  { title: 'MRC 单价', key: 'mrc', width: 120 },
  {
    title: '折算月数',
    key: 'month_factor',
    width: 110,
    render: (row) => Number(row.month_factor).toFixed(6),
  },
  { title: 'MRC 小计', key: 'mrc_amount', width: 130, render: (row) => money(row.mrc_amount) },
  { title: 'NRC 小计', key: 'nrc_amount', width: 130, render: (row) => money(row.nrc_amount) },
  { title: '合计', key: 'amount', width: 140, render: (row) => money(row.amount) },
])
const paymentColumns = businessColumns([
  { title: '流水号', key: 'reference', width: 200 },
  { title: '日期', key: 'payment_date', width: 120 },
  {
    title: '金额',
    key: 'amount',
    width: 130,
    render: (row) => `${row.currency} ${money(row.amount)}`,
  },
  { title: '方式', key: 'method', width: 110 },
  {
    title: '状态',
    key: 'reversed',
    width: 100,
    render: (row) => (row.reversed ? '已冲销' : '已核销'),
  },
  { title: '备注', key: 'remark', width: 150, ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    fixed: 'right',
    width: 70,
    render: (row) =>
      row.reversed ? null : action('冲销', 'mdi:undo-variant', () => ask('reverse', row), 'error'),
  },
])
const planColumns = businessColumns([
  { title: '计划名称', key: 'name', width: 200, ellipsis: { tooltip: true } },
  {
    title: '币种 / 周期',
    key: 'template',
    width: 120,
    render: (row) => `${row.template.currency} / ${row.template.months} 月`,
  },
  { title: '下个账期', key: 'next_period', width: 120 },
  { title: '出账日', key: 'next_run', width: 120 },
  { title: '状态', key: 'enabled', width: 100, render: (row) => (row.enabled ? '启用' : '已停用') },
  { title: '最近失败原因', key: 'last_error', width: 330, ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    fixed: 'right',
    width: 130,
    render: (row) =>
      h(
        NSpace,
        { wrap: false, size: 4 },
        {
          default: () => [
            row.enabled
              ? action('检查 / 重试', 'mdi:refresh', () =>
                  execute(async () => {
                    const result = await service.runPlan(row.id)
                    window.$message?.success(result.msg)
                    await loadPlans()
                  })
                )
              : null,
            row.enabled
              ? action('停用', 'mdi:stop-circle-outline', () => ask('stop', row), 'error')
              : action('启用', 'mdi:play-circle-outline', () => ask('enable', row), 'success'),
            can('delete', '/plans/{plan_id}')
              ? action('删除计划', 'mdi:trash-can-outline', () => ask('plan_delete', row), 'error')
              : null,
          ],
        }
      ),
  },
])
function exportDetail() {
  const bill = detail.value
  const escape = (value) =>
    `"${String(value ?? '')
      .replace(/^[=+\-@\t\r]/, "'$&")
      .replaceAll('"', '""')}"`
  const csv = [
    ['账单号', bill.bill_no, '客户', bill.customer_name, '币种', bill.currency],
    ['账期', bill.period_start, bill.period_end],
    ['订单', '产品', '规格', '数量', 'MRC 单价', 'MRC 小计', 'NRC 小计', '合计'],
    ...bill.lines.map((row) => [
      row.order_no,
      row.product_name,
      row.variant_name,
      row.quantity,
      row.mrc,
      row.mrc_amount,
      row.nrc_amount,
      row.amount,
    ]),
    ['费用小计', bill.subtotal, '折扣', bill.discount, '变更差额', bill.adjustment],
    ['税额', bill.tax_amount, '总额', bill.amount, '已收', bill.paid_amount],
    ['本位币', bill.local_currency, '本位币金额', bill.local_amount, '汇率', bill.fx_rate],
  ]
    .map((row) => row.map(escape).join(','))
    .join('\r\n')
  const url = URL.createObjectURL(new Blob(['\ufeff', csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `${bill.bill_no}.csv`
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
onMounted(() => {
  loadCustomers()
  loadBills()
})
</script>

<style scoped>
.billing-editor {
  display: flex;
  flex-direction: column;
  max-height: calc(100dvh - 40px);
  border-radius: 16px;
  overflow: hidden;
}
.billing-editor :deep(.n-card-header) {
  flex-shrink: 0;
  padding: 20px 26px;
  border-bottom: 1px solid var(--editor-border);
}
.billing-editor :deep(.n-card__content) {
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 22px 26px;
  background: var(--editor-background);
}
.billing-editor :deep(.n-card__footer) {
  flex-shrink: 0;
  padding: 16px 26px;
  border-top: 1px solid var(--editor-border);
}
.editor-intro {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
.editor-intro-mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border-radius: 12px;
  background: var(--editor-surface);
  color: var(--editor-accent);
  border: 1px solid var(--editor-border);
}
.editor-intro strong {
  font-size: 15px;
}
.editor-intro p,
.section-heading p {
  margin: 4px 0 0;
  color: var(--editor-muted);
  font-size: 12px;
  line-height: 1.6;
}
.billing-editor-form {
  display: grid;
  gap: 16px;
}
.editor-section {
  padding: 20px;
  border: 1px solid var(--editor-border);
  border-radius: 12px;
  background: var(--editor-surface);
  min-width: 0;
}
.section-heading {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 20px;
}
.section-heading h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  line-height: 22px;
}
.section-marker {
  width: 3px;
  height: 16px;
  margin-top: 3px;
  border-radius: 3px;
  background: var(--editor-accent);
}
.billing-editor-form .form-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px 24px;
}
.billing-editor-form .payment-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.billing-editor-form :deep(.n-form-item) {
  min-width: 0;
}
.billing-editor-form :deep(.n-form-item-label) {
  font-size: 13px;
}
.editor-notes {
  margin: 16px 2px;
  color: var(--editor-muted);
  font-size: 12px;
  line-height: 1.8;
}
.editor-notes p {
  margin: 6px 0;
}
.editor-notes strong {
  margin-right: 8px;
  font-weight: 600;
}
.editor-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.editor-footer-hint {
  color: var(--editor-muted);
  font-size: 12px;
}
@media (max-width: 640px) {
  .billing-editor {
    max-height: calc(100dvh - 24px);
  }
  .billing-editor :deep(.n-card-header),
  .billing-editor :deep(.n-card__content),
  .billing-editor :deep(.n-card__footer) {
    padding: 16px;
  }
  .editor-section {
    padding: 16px 12px 8px;
  }
  .billing-editor-form .form-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .editor-footer {
    align-items: flex-start;
    flex-direction: column;
  }
}

.billing-page {
  padding: 20px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
  margin-bottom: 20px;
}
.toolbar h2 {
  margin: 0 0 6px;
  font-size: 21px;
}
.toolbar p,
.hint {
  opacity: 0.65;
  font-size: 13px;
}
.filters {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
  margin: 16px 0;
}
.filters > .n-input {
  width: 220px;
}
.filters > .n-select {
  width: 220px;
}
.summaries {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 18px 0;
}
.summary-card {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  align-items: center;
  background: var(--n-color-modal, #f6f8fb);
  border: 1px solid #e6e9ef;
  border-radius: 10px;
  padding: 16px;
}
.overdue {
  color: #d03050;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 20px;
}
.form-grid .wide {
  grid-column: 1/-1;
}
.form-grid :deep(.n-date-picker) {
  width: 100%;
}
.gap {
  margin-top: 18px;
  margin-bottom: 18px;
}
.inline {
  margin-left: 12px;
}
.pagination {
  justify-content: flex-end;
  margin-top: 18px;
}
.detail-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  margin-bottom: 18px;
}
.detail-meta small,
.detail-meta strong {
  display: block;
}
.detail-meta small {
  opacity: 0.6;
  margin-bottom: 5px;
}
.amounts {
  text-align: right;
  font-variant-numeric: tabular-nums;
  line-height: 2;
}
.audit {
  border-bottom: 1px solid #eee;
  padding: 12px 0;
}
.audit span {
  margin-left: 18px;
  opacity: 0.6;
  font-size: 12px;
}
.audit p {
  margin: 6px 0;
  overflow-wrap: anywhere;
}
@media (max-width: 640px) {
  .billing-page {
    padding: 8px;
  }
  .toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
  .form-grid,
  .detail-meta {
    grid-template-columns: 1fr;
  }
  .filters > .n-input,
  .filters > .n-select {
    width: 100%;
  }
  .summary-card {
    width: 100%;
  }
  .amounts {
    text-align: left;
  }
}
</style>
