<template>
  <AppPage :show-footer="false">
    <div class="collaboration-page">
      <section class="workspace-panel">
        <n-tabs v-model:value="activeTab" type="line" animated>
          <n-tab-pane name="plans" tab="运维计划">
            <div class="table-toolbar">
              <div class="filter-row">
                <n-select
                  v-model:value="planFilters.customer"
                  clearable
                  filterable
                  placeholder="按客户筛选"
                  :show-checkmark="false"
                  :loading="remoteCustomersLoading"
                  :options="planCustomerFilterOptions"
                  :render-label="renderRemoteCustomerOption"
                  :filter="filterRemoteCustomer"
                  @focus="loadRemoteCustomers()"
                  @update:value="planPagination.page = 1"
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
              :scroll-x="tableWidth(planColumns)"
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
                <n-button secondary :disabled="loading || !filteredRemoteHands.length" @click="exportRemoteHands">
                  <template #icon><TheIcon icon="mdi:download" :size="18" /></template>
                  导出记录
                </n-button>
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
              :scroll-x="tableWidth(remoteColumns)"
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
              :scroll-x="tableWidth(engineerColumns)"
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
        :closable="!remoteUploading && !remoteEditor.saving"
        :mask-closable="!remoteUploading && !remoteEditor.saving"
        :close-on-esc="!remoteUploading && !remoteEditor.saving"
        class="record-editor-modal"
        style="width: 760px; max-width: calc(100vw - 32px)"
        :bordered="false"
      >
        <div class="record-editor-intro">
          <span class="record-editor-icon"
            ><TheIcon icon="mdi:clipboard-text-clock-outline" :size="24"
          /></span>
          <div>
            <strong>{{ remoteEditor.form.id ? '完善本次运维记录' : '记录一次现场运维' }}</strong>
            <p>关联客户与工程师，核对作业时间、费用及现场交接资料。</p>
          </div>
        </div>
        <n-form
          class="record-editor-form"
          label-placement="top"
          :model="remoteEditor.form"
          :disabled="remoteUploading || remoteEditor.saving"
        >
          <section class="record-form-section" aria-labelledby="record-basic-title">
            <div class="record-section-head">
              <span id="record-basic-title">基本信息</span><small>客户归属与执行人员</small>
            </div>
            <div class="record-form-grid">
              <n-form-item label="客户" required>
                <n-select
                  v-model:value="remoteCustomerValue"
                  filterable
                  :show-checkmark="false"
                  :loading="remoteCustomersLoading"
                  :options="remoteCustomerOptions"
                  :render-label="renderRemoteCustomerOption"
                  :filter="filterRemoteCustomer"
                  placeholder="请选择客户"
                  @focus="loadRemoteCustomers()"
                />
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
              <n-form-item label="是否结算">
                <n-switch v-model:value="remoteEditor.form.is_settled">
                  <template #checked>已结算</template>
                  <template #unchecked>未结算</template>
                </n-switch>
              </n-form-item>
            </div>
          </section>
          <section class="record-form-section" aria-labelledby="record-time-title">
            <div class="record-section-head">
              <span id="record-time-title">作业时间</span><small>到场与离场均按北京时间填写</small>
            </div>
            <div class="record-form-grid">
              <n-form-item label="到场(北京)">
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
              <n-form-item label="离场(北京)">
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
              <div class="record-duration">
                <span>实际工时</span>
                <strong>{{ formatDuration(remoteEditor.form.work_minutes) }}</strong>
                <small>夜班按所选地区的当地时间计算</small>
              </div>
            </div>
          </section>
          <section class="record-form-section" aria-labelledby="record-billing-title">
            <div class="record-section-head">
              <span id="record-billing-title">费用结算</span><small>按本次规则自动试算</small>
            </div>
            <div v-if="remoteEditor.form.id" class="record-billing-toolbar">
              <CButton
                show-save
                size="small"
                :save-text="
                  remoteEditor.form.refresh_billing_rules
                    ? '已更新规则'
                    : '更新工程师规则'
                "
                :disabled="
                  remoteEditor.saving || remoteUploading || remoteEditor.form.refresh_billing_rules
                "
                @save="remoteEditor.form.refresh_billing_rules = true"
              ><template #save-icon><TheIcon icon="mdi:refresh" :size="18" /></template></CButton>
            </div>
            <MaintenancePriceEditor v-model="remoteEditor.form.customer_pricing" allow-custom :engineer-rules="remoteBillingRules" :disabled="remoteEditor.saving || remoteUploading" />
            <BillingQuote
              v-model="remoteEditor.form.billing_context"
              :customer-pricing="remoteEditor.form.customer_pricing"
              record-expenses
              :rules="remoteBillingRules"
              :arrived-at="remoteEditor.form.arrived_at"
              :left-at="remoteEditor.form.left_at"
              :timezone="remoteEditor.form.timezone"
              :region="remoteEditor.form.region"
              :disabled="remoteEditor.saving || remoteUploading"
            />
          </section>
          <section class="record-form-section" aria-labelledby="record-notes-title">
            <div class="record-section-head">
              <span id="record-notes-title">工作说明与附件</span
              ><small>工作内容、交接信息与现场资料</small>
            </div>
            <n-form-item label="备注">
              <n-input
                v-model:value="remoteEditor.form.note"
                type="textarea"
                placeholder="工作内容、交接信息或其他说明"
                :autosize="{ minRows: 3, maxRows: 6 }"
              />
            </n-form-item>
            <n-form-item label="附件">
              <div class="plan-attachments">
                <label
                  class="plan-upload-zone"
                  :class="{
                    'is-dragging': remoteDragging,
                    'is-disabled': remoteUploading || remoteEditor.saving,
                  }"
                  @dragover.prevent="remoteDragging = !remoteUploading && !remoteEditor.saving"
                  @dragleave.prevent="remoteDragging = false"
                  @drop.prevent="handleRemoteAttachmentDrop"
                >
                  <input
                    class="plan-upload-input"
                    type="file"
                    multiple
                    aria-label="上传运维记录附件，支持选择多个文件"
                    :disabled="remoteUploading || remoteEditor.saving"
                    @change="handleRemoteAttachmentSelect"
                  />
                  <n-spin :show="remoteUploading" size="small">
                    <div class="plan-upload-content">
                      <svg class="plan-upload-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path
                          d="M12 16V4m-4 4 4-4 4 4M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"
                          stroke="currentColor"
                          stroke-width="1.6"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        />
                      </svg>
                      <span class="plan-upload-title">{{
                        remoteUploading ? '附件上传中，请稍候…' : '点击或拖拽文件到此处上传'
                      }}</span>
                      <n-text depth="3" class="plan-upload-tip"
                        >支持多文件上传 · 单个最大20MB · 最多50个</n-text
                      >
                    </div>
                  </n-spin>
                </label>
                <div
                  v-for="attachment in remoteEditor.form.attachments"
                  :key="attachment.url"
                  class="plan-attachment"
                >
                  <a :href="attachment.url" :download="attachment.name">{{ attachment.name }}</a>
                  <CButton
                    show-delete
                    size="tiny"
                    :disabled="remoteUploading || remoteEditor.saving"
                    @delete="deleteAttachment(remoteEditor, attachment)"
                  />
                </div>
              </div>
            </n-form-item>
          </section>
        </n-form>
        <template #footer>
          <div class="record-editor-footer">
            <span class="record-footer-hint">{{
              remoteUploading ? '正在处理附件，请稍候…' : '确认工时与费用后保存'
            }}</span>
            <CButton
              show-cancel
              show-save
              :save-loading="remoteEditor.saving"
              :disabled="remoteUploading || remoteEditor.saving"
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
        :closable="!planUploading && !planEditor.saving"
        :mask-closable="!planUploading && !planEditor.saving"
        :close-on-esc="!planUploading && !planEditor.saving"
        class="editor-modal remote-editor-modal"
        style="width: min(680px, calc(100vw - 40px))"
        :bordered="false"
      >
        <n-form class="remote-form" label-placement="left" label-width="90" size="small" :model="planEditor.form">
          <div class="remote-form-grid">
            <n-form-item label="客户" required>
              <n-select
                v-model:value="planCustomerValue"
                filterable
                :show-checkmark="false"
                :loading="remoteCustomersLoading"
                :options="planCustomerOptions"
                :render-label="renderRemoteCustomerOption"
                :filter="filterRemoteCustomer"
                placeholder="请选择客户"
                @focus="loadRemoteCustomers()"
              />
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
          <MaintenancePriceEditor v-model="planEditor.form.customer_pricing" :disabled="planEditor.saving || planUploading" />
          <n-form-item label="计划说明">
            <n-input
              v-model:value="planEditor.form.note"
              type="textarea"
              placeholder="计划内容、到场要求、交接信息"
              :autosize="{ minRows: 3, maxRows: 6 }"
            />
          </n-form-item>
          <n-form-item label="附件">
            <div class="plan-attachments">
              <label
                class="plan-upload-zone"
                :class="{ 'is-dragging': planDragging, 'is-disabled': planUploading || planEditor.saving }"
                @dragover.prevent="planDragging = !planUploading && !planEditor.saving"
                @dragleave.prevent="planDragging = false"
                @drop.prevent="handlePlanAttachmentDrop"
              >
                <input
                  class="plan-upload-input"
                  type="file"
                  multiple
                  aria-label="上传运维计划附件，支持选择多个文件"
                  :disabled="planUploading || planEditor.saving"
                  @change="handlePlanAttachmentSelect"
                />
                <n-spin :show="planUploading" size="small">
                  <div class="plan-upload-content">
                    <svg class="plan-upload-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path
                        d="M12 16V4m-4 4 4-4 4 4M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"
                        stroke="currentColor"
                        stroke-width="1.6"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                    </svg>
                    <span class="plan-upload-title">{{ planUploading ? '附件上传中，请稍候…' : '点击或拖拽文件到此处上传' }}</span>
                    <n-text depth="3" class="plan-upload-tip">支持多文件上传 · 单个最大20MB · 最多50个</n-text>
                  </div>
                </n-spin>
              </label>
              <div v-for="attachment in planEditor.form.attachments" :key="attachment.url" class="plan-attachment">
                <a :href="attachment.url" :download="attachment.name">{{ attachment.name }}</a>
                <CButton
                  show-delete
                  size="tiny"
                  :disabled="planUploading || planEditor.saving"
                  @delete="deleteAttachment(planEditor, attachment)"
                />
              </div>
            </div>
          </n-form-item>
          <n-checkbox v-if="!planEditor.form.id" v-model:checked="planEditor.form.notify">创建后立即发送飞书通知</n-checkbox>
        </n-form>
        <template #footer>
          <div class="modal-actions compact-modal-actions">
            <CButton
              show-cancel
              show-save
              size="small"
              :save-loading="planEditor.saving"
              :disabled="planUploading || planEditor.saving"
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
          <n-form-item label="到场(北京)" required>
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
          <n-form-item label="离场(北京)" required>
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
          <n-form-item label="运维时区">
            <n-select v-model:value="planEditor.form.timezone" filterable tag :options="timezoneOptions" />
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
        class="record-editor-modal engineer-profile-modal"
        style="width: 760px; max-width: calc(100vw - 32px)"
        :bordered="false"
        :mask-closable="!engineerEditor.saving"
        :close-on-esc="!engineerEditor.saving"
        :closable="!engineerEditor.saving"
      >
        <div class="record-editor-intro">
          <span class="record-editor-icon"
            ><TheIcon icon="mdi:account-hard-hat-outline" :size="24"
          /></span>
          <div>
            <strong>维护工程师档案</strong>
            <p>管理联系信息、服务地区与本次适用的计费规则。</p>
          </div>
        </div>
        <n-form
          class="record-editor-form"
          label-placement="top"
          :model="engineerEditor.form"
          :disabled="engineerEditor.saving"
        >
          <section class="record-form-section">
            <div class="record-section-head">
              <span>基本信息</span><small>联系方式与负责地区</small>
            </div>
            <div class="record-form-grid">
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
                <n-input
                  v-model:value="engineerEditor.form.wechat_group"
                  placeholder="微信群或工作群"
                />
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
          </section>
          <section class="record-form-section">
            <div class="record-section-head">
              <span>计费规则</span><small>基础人工与附加费用</small>
            </div>
            <n-form-item label="启用计费">
              <n-switch v-model:value="engineerEditor.form.billing_enabled" />
            </n-form-item>
            <EngineerBillingEditor
              v-if="engineerEditor.form.billing_enabled"
              v-model="engineerEditor.form.billing_rules"
              :disabled="engineerEditor.saving"
            />
          </section>
          <section class="record-form-section">
            <n-form-item label="备注">
              <n-input
                v-model:value="engineerEditor.form.note"
                type="textarea"
                placeholder="技能、值班时间或其他说明"
                :autosize="{ minRows: 3, maxRows: 6 }"
              />
            </n-form-item>
          </section>
        </n-form>
        <template #footer>
          <div class="record-editor-footer">
            <CButton
              show-cancel
              show-save
              :save-loading="engineerEditor.saving"
              :disabled="engineerEditor.saving"
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
import { NButton, NPopconfirm, NSpace, NSelect, NSwitch, NTag, NTooltip, useMessage } from 'naive-ui'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'
import { recordsCsv } from './export.mjs'
import { buildCustomerOptions, buildPlanCustomerOptions, matchesPlanCustomer, selectedCustomerValue } from './customers.mjs'
import { billingTotalLabel, billingSummary, editableBillingRules, validateBillingRules, timezoneOptions, beijingDateTime, beijingTimestamp } from './billing.mjs'
import BillingQuote from './BillingQuote.vue'
import MaintenancePriceEditor from './MaintenancePriceEditor.vue'
import EngineerBillingEditor from './EngineerBillingEditor.vue'
import CButton from '@/components/public/CButton.vue'
import { translateCity, translateCountry, translateLocationPath } from '@/utils/location-i18n'

const message = useMessage()
const loading = ref(false)
const planDragging = ref(false)
const remoteUploading = ref(false)
const remoteDragging = ref(false)
const planUploading = ref(false)
const remoteSettlementSaving = ref(new Set())
const activeTab = ref('plans')
const remoteHands = ref([])
const plans = ref([])
const engineers = ref([])
const users = ref([])
const datacenters = ref([])
const popRegions = ref([])
const remoteCustomers = ref([])
const remoteCustomersLoading = ref(false)
const remoteCustomersLoaded = ref(false)
const remoteCustomerSelection = ref(null)
const planCustomerSelection = ref(null)
const remoteCustomerOptions = computed(() =>
  buildCustomerOptions(remoteCustomers.value, remoteEditor.form.customer)
)
const planCustomerOptions = computed(() =>
  buildCustomerOptions(remoteCustomers.value, planEditor.form.customer)
)
const remoteCustomerValue = computed({
  get: () =>
    selectedCustomerValue(
      remoteCustomerOptions.value,
      remoteEditor.form.customer,
      remoteCustomerSelection.value ||
        (remoteEditor.form.customer_id ? `customer:${remoteEditor.form.customer_id}` : null)
    ),
  set: (value) => {
    const option = remoteCustomerOptions.value.find((item) => item.value === value)
    remoteCustomerSelection.value = value
    remoteEditor.form.customer = option?.customerName || ''
    remoteEditor.form.customer_id = option?.customerId || null
    remoteEditor.form.customer_pricing = { kind: 'internal' }
  },
})
const planCustomerValue = computed({
  get: () =>
    selectedCustomerValue(
      planCustomerOptions.value,
      planEditor.form.customer,
      planCustomerSelection.value ||
        (planEditor.form.customer_id ? `customer:${planEditor.form.customer_id}` : null)
    ),
  set: (value) => {
    const option = planCustomerOptions.value.find((item) => item.value === value)
    planCustomerSelection.value = value
    planEditor.form.customer = option?.customerName || ''
    planEditor.form.customer_id = option?.customerId || null
    planEditor.form.customer_pricing = { kind: 'internal' }
  },
})

const engineerKeyword = ref('')

const remoteFilters = reactive({ engineer_id: null, site: null, site_key: null, status: null })
const planFilters = reactive({ customer: null, site: null, site_key: null, status: null })
const datePickerActions = ['clear', 'confirm']
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


const planStatusOptions = [
  { label: '待执行', value: 'pending' },
  { label: '已完成', value: 'done' },
  { label: '已取消', value: 'cancelled' },
]

const remoteEditor = reactive({ show: false, saving: false, form: createRemoteForm() })
const remoteBillingRules = computed(() => {
  const form = remoteEditor.form
  if (!form.refresh_billing_rules && form.engineer_id === form.billing_engineer_id && form.billing_rules_snapshot) return form.billing_rules_snapshot
  return engineers.value.find((item) => item.id === form.engineer_id)?.billing_rules || null
})
const planEditor = reactive({ show: false, saving: false, form: createPlanForm() })
const completeEditor = reactive({ show: false, saving: false, form: createCompleteForm() })
const engineerEditor = reactive({ show: false, saving: false, form: createEngineerForm() })

const activeEngineerCount = computed(
  () => engineers.value.filter((item) => Number(item.is_active) === 1).length
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

const planCustomerFilterOptions = computed(() => buildPlanCustomerOptions(remoteCustomers.value, plans.value))

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
    if (planFilters.customer) {
      const option = planCustomerFilterOptions.value.find((customer) => customer.value === planFilters.customer)
      if (!matchesPlanCustomer(item, option)) return false
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
      h('strong', canonicalRegion(row.region) || '-'), h('small', row.site || '-'),
    ]),
  },
  { title: '日期', key: 'date', width: 135, render: (row) => formatRemoteDateRange(row) },
  { title: '到场（北京）', key: 'arrived_at', width: 125, render: (row) => formatTime(row.arrived_at) },
  { title: '离场（北京）', key: 'left_at', width: 145, render: (row) => formatRemoteEndTime(row) },
  { title: '工时', key: 'work_minutes', width: 95, render: (row) => formatDuration(row.work_minutes) },
  {
    title: '费用',
    key: 'billing_result',
    width: 200,
    render: (row) =>
      h(NTooltip, null, {
        trigger: () =>
          h('div', { class: 'primary-cell' }, [
            h('strong', billingTotalLabel(row.billing_result)),
            h(
              'small',
              row.customer_pricing_snapshot?.kind === 'fixed'
                ? '自定义 · 一口价'
                : row.customer_pricing_snapshot?.kind === 'hourly'
                ? `自定义 · ${row.customer_pricing_snapshot.hourly_rate ?? '待确认'} ${
                    row.customer_pricing_snapshot.currency || 'USD'
                  }/小时`
                : '工程师规则'
            ),
            row.billing_result?.status !== 'calculated' && row.billing_result?.notices?.length
              ? h(
                  'small',
                  { style: 'color: #d97706; white-space: normal' },
                  row.billing_result.notices[0]
                )
              : null,
          ]),
        default: () =>
          h('div', [
            h(
              'div',
              row.billing_result?.basis === 'current_rules'
                ? '按当前规则试算（历史记录未保存费用）'
                : '本次计费结果'
            ),
            ...(row.billing_result?.lines || []).map((line) =>
              h(
                'div',
                `${line.label}：${line.amount} ${line.currency || row.billing_result.currency}`
              )
            ),
            ...(row.billing_result?.notices || []).map((line) => h('div', line)),
          ]),
      }),
  },
  {
    title: '状态', key: 'status', width: 100,
    render: (row) => h(NTag, { type: statusTagType(row.status), bordered: false, size: 'small' },
      { default: () => statusLabel(row.status) }),
  },
  {
    title: '是否结算', key: 'is_settled', width: 120,
    render: (row) => renderSettlementSwitch(row),
  },
  {
    title: '备注', key: 'note', width: 360,
    render: (row) => renderNoteCell(row.note),
  },
  {
    title: '操作', key: 'actions', width: 124, fixed: 'right',
    render: (row) => h(NSpace, { size: 6, wrap: false }, {
      default: () => [
        row.status === 'scheduled' && !row.left_at
          ? renderActionButton('到场', 'mdi:login', 'success', () => updateRemoteStatus(row, 'arrived'))
          : null,
        row.status === 'arrived' && row.arrived_at && !row.left_at
          ? renderActionButton('离场', 'mdi:logout', 'warning', () => updateRemoteStatus(row, 'done'))
          : null,
        renderActionButton('编辑', 'mdi:pencil-outline', 'primary', () => openRemoteEditor(row)),
        renderDeleteConfirm({
          title: `确认删除 ${row.customer || row.ticket || '这条运维记录'}？`,
          actionText: '删除',
          onConfirm: () => deleteRemoteHands(row),
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
      h('strong', canonicalRegion(row.region) || '-'), h('small', row.site || '-'),
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
    render: (row) => h('div', { class: 'plan-attachments' }, [
      renderNoteCell(row.note),
      ...(row.attachments || []).map((item) => h('a', {
        href: item.url,
        download: item.name,
        style: { overflowWrap: 'anywhere' },
      }, item.name)),
    ]),
  },
  {
    title: '操作', key: 'actions', width: 124, fixed: 'right',
    render: (row) => h(NSpace, { size: 6, wrap: false }, {
      default: () => [
        row.status === 'pending'
          ? renderActionButton('完成', 'mdi:check-circle-outline', 'success', () => openCompleteEditor(row))
          : null,
        row.status === 'pending'
          ? renderActionButton('变更', 'mdi:pencil-outline', 'primary', () => openPlanEditor(row))
          : null,
        row.status === 'pending'
          ? renderDeleteConfirm({
            title: `确认取消 ${row.customer || row.ticket || '这条运维计划'}？`,
            actionText: '取消',
            onConfirm: () => cancelPlan(row),
          })
          : null,
        row.remote_hands_id
          ? renderActionButton('查看记录', 'mdi:clipboard-text-outline', 'default', () => { activeTab.value = 'remote' })
          : null,
        ['done', 'cancelled'].includes(row.status)
          ? renderDeleteConfirm({
            title: `确认删除 ${row.customer || row.ticket || '这条运维计划'}？`,
            actionText: '删除',
            onConfirm: () => deletePlan(row),
          })
          : null,
      ].filter(Boolean),
    }),
  },
]

const engineerColumns = [
  { title: '姓名', key: 'name', width: 150, render: (row) => h('strong', row.name || '-') },
  {
    title: '计费规则', key: 'billing_rules', width: 280,
    render: (row) => h('div', { class: 'primary-cell' }, billingSummary(row.billing_rules).map((line) => h('small', line))),
  },
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
    title: '操作', key: 'actions', width: 90, fixed: 'right',
    render: (row) => h(NSpace, { size: 6, wrap: false }, {
      default: () => [
        renderActionButton('编辑', 'mdi:pencil-outline', 'primary', () => openEngineerEditor(row)),
        renderDeleteConfirm({
          title: `确认删除工程师 ${row.name || ''}？`,
          actionText: '删除',
          onConfirm: () => deleteEngineer(row),
        }),
      ],
    }),
  },
]

for (const columns of [remoteColumns, planColumns, engineerColumns]) {
  columns.forEach((column) => { column.resizable = column.key !== 'actions' })
}

function tableWidth(columns) {
  return columns.reduce((total, column) => total + Number(column.width || column.minWidth || 100), 0)
}

function exportRemoteHands() {
  const rows = filteredRemoteHands.value
  if (!rows.length) return message.warning('暂无可导出的运维记录')
  try {
    const content = recordsCsv([
      ['客户', '工单', '工程师', '联系方式', '微信', '联系群', '地区', '机房', '机柜', '时区', '到场时间（北京时间）', '离场时间（北京时间）', '工时（分钟）', '状态', '是否结算', '备注', '费用', '币种', '计费说明'],
      ...rows.map((row) => [row.customer, row.ticket, row.engineer_name, row.engineer_contact,
        row.engineer_wechat, row.engineer_group, displayRegion(row.region), row.site, row.rack,
        row.timezone, row.arrived_at, row.left_at, row.work_minutes, statusLabel(row.status),
        readSettledFlag(row) ? '已结算' : '未结算', row.note, billingTotalLabel(row.billing_result), row.billing_result?.currency ?? '',
        [row.billing_result?.basis === 'current_rules' ? '按现行规则试算' : '本次计费结果', ...(row.billing_result?.notices || [])].join('；')]),
    ])
    const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8;' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `运维记录-${localDateTime().slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    message.success(`已导出 ${rows.length} 条运维记录`)
  } catch {
    message.error('导出失败，请重试')
  }
}

function createRemoteForm(source = {}) {
  return {
    id: source.id || null,
    customer: source.customer || '',
    customer_id: source.customer_id || null,
    customer_pricing: { ...(source.customer_pricing || source.customer_pricing_snapshot || { kind: 'internal' }) },
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
    is_settled: readSettledFlag(source),
    attachments: (source.attachments || []).map((item) => ({ ...item })),
    billing_engineer_id: source.engineer_id || null,
    billing_rules_snapshot: source.billing_rules_snapshot || null,
    billing_context: { ...(source.billing_context || {}) },
    refresh_billing_rules: false,
    note: source.note || '',
  }
}

function createPlanForm(source = {}) {
  return {
    id: source.id || null,
    customer: source.customer || '',
    customer_id: source.customer_id || null,
    customer_pricing: { ...(source.customer_pricing || source.customer_pricing_snapshot || { kind: 'internal' }) },
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
    attachments: (source.attachments || []).map((item) => ({ ...item })),
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
    billing_enabled: Boolean(source.billing_rules),
    billing_rules: editableBillingRules(source.billing_rules),
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
  remoteCustomerSelection.value = null
  remoteEditor.form = createRemoteForm(row || {})
  remoteEditor.show = true
  loadRemoteCustomers(true)
}

async function loadRemoteCustomers(force = false) {
  if ((!force && remoteCustomersLoaded.value) || remoteCustomersLoading.value) return
  remoteCustomersLoading.value = true
  try {
    const res = await api.customerCenterApi.options()
    remoteCustomers.value = res.data?.customers || []
    remoteCustomersLoaded.value = true
  } catch (error) {
    message.error(error.message || '读取客户列表失败，请重新点击客户下拉框重试')
  } finally {
    remoteCustomersLoading.value = false
  }
}

function filterRemoteCustomer(pattern, option) {
  return `${option.label} ${option.searchText || ''} ${option.value}`
    .toLowerCase()
    .includes(pattern.trim().toLowerCase())
}

function renderRemoteCustomerOption(option) {
  const entity = String(option.signing_entity_name || '')
  const normalized = entity.toLowerCase()
  const tag = entity.includes('科特思')
    ? { text: '科', type: 'success' }
    : normalized.includes('77')
    ? { text: '7', type: 'warning' }
    : normalized.includes('catixs')
    ? { text: 'C', type: 'info' }
    : null
  return h(
    'span',
    {
      style: {
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1fr) auto',
        alignItems: 'center',
        width: '100%',
        minWidth: 0,
        flex: '1 1 auto',
        columnGap: '12px',
      },
    },
    [
      h(
        'span',
        { style: 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;' },
        option.label
      ),
      tag
        ? h(NTag, { size: 'small', round: true, type: tag.type }, { default: () => tag.text })
        : null,
    ]
  )
}

function openPlanEditor(row = null) {
  planCustomerSelection.value = null
  planEditor.form = createPlanForm(row || {})
  planEditor.show = true
  loadRemoteCustomers(true)
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
  remoteEditor.form.timezone = option.timezone || 'Asia/Shanghai'
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
  const value = Math.floor((beijingTimestamp(end) - beijingTimestamp(start)) / 60000)
  return Number.isFinite(value) ? Math.max(0, value) : 0
}

function isEndBeforeStart(start, end) {
  if (!start || !end) return false
  const startTime = beijingTimestamp(start)
  const endTime = beijingTimestamp(end)
  return Number.isFinite(startTime) && Number.isFinite(endTime) && endTime < startTime
}

async function saveRemoteHands() {
  if (remoteUploading.value || remoteEditor.saving) return
  const form = remoteEditor.form
  if (!form.customer.trim()) return message.warning('请选择客户')
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

function handlePlanAttachmentSelect(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  uploadPlanAttachments(files)
}

function handlePlanAttachmentDrop(event) {
  planDragging.value = false
  uploadPlanAttachments(Array.from(event.dataTransfer?.files || []))
}

function handleRemoteAttachmentSelect(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  uploadAttachments(files, remoteEditor, remoteUploading)
}

function handleRemoteAttachmentDrop(event) {
  remoteDragging.value = false
  uploadAttachments(Array.from(event.dataTransfer?.files || []), remoteEditor, remoteUploading)
}

function uploadPlanAttachments(files) {
  return uploadAttachments(files, planEditor, planUploading)
}

async function deleteAttachment(editor, attachment) {
  const busy = editor === planEditor ? planUploading : remoteUploading
  if (busy.value || editor.saving) return
  busy.value = true
  try {
    await api.remoteAssistanceApi.deleteAttachment(attachment.url)
    // Deletion is immediate, including when editing is later cancelled.
    for (const item of [...plans.value, ...remoteHands.value, editor.form]) {
      if (item.attachments) item.attachments = item.attachments.filter((value) => value.url !== attachment.url)
    }
    message.success('附件已删除')
  } catch (error) {
    message.error(error.message || '附件删除失败，请重试')
  } finally {
    busy.value = false
  }
}

async function uploadAttachments(files, editor, busy) {
  if (!files.length || busy.value || editor.saving) return
  const form = editor.form
  if (form.attachments.length + files.length > 50) return message.warning('最多添加50个附件')
  if (files.some((file) => !file.size || file.size > 20 * 1024 * 1024)) {
    return message.warning('请选择非空文件，单个附件不能超过20MB')
  }
  busy.value = true
  let failed = 0
  try {
    for (const file of files) {
      try {
        const result = await api.remoteAssistanceApi.uploadPlanAttachment(file)
        form.attachments.push(result.data)
      } catch (error) {
        failed += 1
        message.error(`${file.name} 上传失败：${error.message || '请重新添加'}`)
      }
    }
    if (!failed) message.success(`已上传${files.length}个附件`)
  } finally {
    busy.value = false
  }
}

async function savePlan() {
  if (planUploading.value || planEditor.saving) return
  const form = planEditor.form
  if (!form.customer.trim()) return message.warning('请选择客户')
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
  if (engineerEditor.saving) return
  const form = engineerEditor.form
  if (!form.name.trim()) return message.warning('请输入工程师姓名')
  const billingRules = form.billing_enabled ? form.billing_rules : null
  const billingError = validateBillingRules(billingRules)
  if (billingError) return message.warning(billingError)
  engineerEditor.saving = true
  try {
    const payload = {
      name: form.name,
      billing_rules: billingRules,
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

async function updateRemoteSettled(row, value) {
  const nextValue = Boolean(value)
  if (nextValue === readSettledFlag(row)) return
  const key = `${row.id}:settled`
  remoteSettlementSaving.value = new Set([...remoteSettlementSaving.value, key])
  try {
    const payload = { ...createRemoteForm(row) }
    delete payload.id
    payload.is_settled = nextValue
    payload.ops_settlement_status = nextValue ? 'settled' : 'unbilled'
    payload.customer_settlement_status = nextValue ? 'settled' : 'unbilled'
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
  if (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(text)) {
    const date = new Date(text)
    return Number.isFinite(date.getTime()) ? beijingDateTime(date) : null
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
  return beijingDateTime(date)
}

function localDateTime() {
  const now = new Date()
  return formatLocalDateTime(now)
}

function addHoursToDateTime(value, hours = 1) {
  if (!value) return null
  const timestamp = beijingTimestamp(value)
  return Number.isFinite(timestamp) ? beijingDateTime(new Date(timestamp + hours * 3600000)) : null
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

function readSettledFlag(source) {
  if (!source) return false
  if (source.is_settled !== undefined && source.is_settled !== null) {
    return Boolean(source.is_settled)
  }
  return readSettlementStatus(source, 'ops') === 'settled'
    && readSettlementStatus(source, 'customer') === 'settled'
}

function renderSettlementSwitch(row) {
  const key = `${row.id}:settled`
  const saving = remoteSettlementSaving.value.has(key)
  return h(NSwitch, {
    value: readSettledFlag(row),
    size: 'small',
    loading: saving,
    disabled: saving,
    onUpdateValue: (value) => updateRemoteSettled(row, value),
  }, {
    checked: () => '已结算',
    unchecked: () => '未结算',
  })
}

function renderActionButton(label, icon, type, onClick) {
  return h(NTooltip, null, {
    trigger: () => h(NButton, {
      size: 'small', circle: true, quaternary: true, type, 'aria-label': label, onClick,
    }, { icon: () => h(TheIcon, { icon, size: 17 }) }),
    default: () => label,
  })
}

function renderDeleteConfirm({ title, actionText, onConfirm }) {
  return h(NPopconfirm, {
    positiveText: actionText,
    negativeText: '取消',
    onPositiveClick: onConfirm,
  }, {
    trigger: () => renderActionButton(actionText, actionText === '取消' ? 'mdi:close-circle-outline' : 'mdi:delete-outline', actionText === '取消' ? 'warning' : 'error'),
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
.plan-attachments {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  min-width: 0;
}

.plan-upload-zone {
  position: relative;
  display: block;
  padding: 24px 16px;
  border: 1px dashed #b8c5d6;
  border-radius: 10px;
  background: rgba(32, 128, 240, 0.03);
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background-color 0.2s;
}

.plan-upload-zone:not(.is-disabled):hover,
.plan-upload-zone:focus-within,
.plan-upload-zone.is-dragging {
  border-color: var(--primary-color, #2080f0);
  background: rgba(32, 128, 240, 0.08);
}

.plan-upload-zone.is-disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.plan-upload-input {
  position: absolute;
  inset: 0;
  z-index: 1;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: inherit;
}

.plan-upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  pointer-events: none;
}

.plan-upload-icon {
  width: 36px;
  height: 36px;
  margin-bottom: 4px;
  color: var(--primary-color, #2080f0);
}

.plan-upload-title {
  font-size: 14px;
  font-weight: 500;
}

.plan-upload-tip {
  font-size: 12px;
}

.plan-attachment {
  display: flex;
  align-items: center;
  gap: 12px;
}

.plan-attachment a {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--primary-color, #2080f0);
}

.collaboration-page {
  display: flex;
  height: calc(100vh - 132px);
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
}

.workspace-panel {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
}

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
.engineer-form { max-height: min(70vh, 720px); overflow-y: auto; padding-right: 8px; }
.engineer-form :deep(.n-form-item) { margin-bottom: 12px; }
.engineer-form :deep(.n-input),
.engineer-form :deep(.n-base-selection) { min-height: 30px; }
.modal-actions { justify-content: flex-end; }
.compact-modal-actions,
.engineer-modal-actions { gap: 8px; }

@media (max-width: 900px) {
  .table-toolbar { align-items: stretch; flex-direction: column; }
  .filter-row { width: 100%; }
  .form-grid { grid-template-columns: 1fr; }
  .remote-form-grid { grid-template-columns: 1fr; }
}

@media (max-width: 560px) {
  .filter-row { grid-template-columns: 1fr; }
  .workspace-panel { padding: 14px; }
}
.record-editor-modal :deep(.n-card__content) {
  max-height: calc(100vh - 180px);
  overflow-y: auto;
}
:global(.n-base-select-option.remote-customer-option .n-base-select-option__content) {
  display: flex;
  width: 100%;
}
:global(.n-base-select-option.remote-customer-option .n-base-select-option__content > span) {
  flex: 1 1 auto;
  min-width: 0;
}
.record-editor-intro {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 14px 16px;
  border: 1px solid #dceafe;
  border-radius: 8px;
  background: #f8fbff;
}
.record-editor-icon {
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
.record-editor-intro strong {
  font-size: 16px;
  color: #0f172a;
}
.record-editor-intro p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}
.record-editor-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.record-form-section {
  padding: 14px 16px 2px;
  border: 1px solid #e8edf3;
  border-radius: 8px;
}
.record-section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #edf2f7;
}
.record-section-head > span {
  font-size: 15px;
  font-weight: 700;
}
.record-section-head > small {
  font-size: 12px;
  color: #94a3b8;
}
.record-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 16px;
}
.record-editor-form :deep(.n-form-item) {
  min-width: 0;
}
.record-editor-form :deep(.n-date-picker),
.record-editor-form :deep(.n-input-number) {
  width: 100%;
}
.record-editor-form :deep(.n-form-item-blank) {
  min-width: 0;
}
.record-duration {
  display: flex;
  align-self: start;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin: 2px 0 18px;
  padding: 12px 14px;
  background: #f8fbff;
  border: 1px solid #e8edf3;
  border-radius: 8px;
}
.record-duration > span {
  color: #64748b;
  font-size: 13px;
}
.record-duration > strong {
  color: #0f766e;
  font-size: 18px;
}
.record-duration > small {
  flex-basis: 100%;
  color: #94a3b8;
}
.record-billing-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 14px;
}
.record-billing-toolbar :deep(.n-button) {
  min-height: 34px;
  padding: 0 14px;
  border-radius: 8px;
  font-weight: 500;
}
.record-editor-form :deep(.billing-quote) {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 16px;
  padding: 0;
  background: transparent;
}
.record-editor-form :deep(.billing-quote > .n-spin-container) {
  grid-column: 1 / -1;
  margin-bottom: 14px;
  padding: 12px 14px;
  background: #f8fbff;
  border: 1px solid #e8edf3;
  border-radius: 8px;
}
.record-editor-form :deep(.billing-quote p) {
  margin: 6px 0 10px;
  font-size: 13px;
}
.record-editor-form :deep(.fee-line) {
  padding: 8px 0;
  border-bottom: 1px dashed #e8edf3;
  font-size: 13px;
}
.record-editor-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.record-footer-hint {
  font-size: 12px;
  color: #94a3b8;
}
@media (max-width: 600px) {
  .record-editor-modal {
    width: calc(100vw - 16px) !important;
    max-width: calc(100vw - 16px) !important;
  }
  .record-editor-modal :deep(.n-card-header) {
    padding: 14px 16px 8px;
  }
  .record-editor-modal :deep(.n-card__content) {
    max-height: calc(100vh - 152px);
    padding: 10px 16px;
  }
  .record-editor-modal :deep(.n-card__footer) {
    padding: 10px 16px 14px;
  }
  .record-form-grid,
  .record-editor-form :deep(.billing-quote) {
    grid-template-columns: minmax(0, 1fr);
  }
  .record-form-section {
    padding: 12px 12px 2px;
  }
  .record-editor-footer {
    flex-wrap: wrap;
    justify-content: flex-end;
  }
  .record-footer-hint {
    flex-basis: 100%;
  }
  .record-billing-toolbar {
    justify-content: flex-start;
  }
}
</style>
