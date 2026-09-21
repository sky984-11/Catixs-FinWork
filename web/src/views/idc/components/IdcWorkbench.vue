<template>
  <AppPage>
    <div class="idc-workbench">
      <section class="hero">
        <div>
          <span class="eyebrow">IDC SERVICE LIFECYCLE</span>
          <h1>{{ title }}</h1>
          <p>{{ subtitle }}</p>
        </div>
        <n-space>
          <n-button secondary :loading="loading" @click="initialize">刷新</n-button>
          <n-button
            v-if="mode === 'orders' && capabilities.create"
            type="primary"
            @click="openCreate"
            >新增IDC工单</n-button
          >
          <n-button v-if="mode === 'orders' && capabilities.accounts" secondary @click="openAccount"
            >客户账务映射</n-button
          >
          <n-button
            v-if="mode === 'services' && capabilities.delivery"
            secondary
            :loading="busy"
            @click="reconcile"
            >释放到期资源锁</n-button
          >
          <n-button
            v-if="mode === 'billing' && capabilities.billing"
            type="primary"
            @click="openBilling"
            >预览 / 生成账单</n-button
          >
          <n-button v-if="mode === 'billing' && capabilities.events" secondary @click="openEvent"
            >调整 / 预付款 / 贷项</n-button
          >
        </n-space>
      </section>
      <n-alert v-if="error" type="error" :title="error" />
      <n-alert v-if="initialized && !accounts.length" type="info"
        >尚无可访问的客户账务映射。请由财务关联CRM客户、签约主体与账单客户，并授权相关用户。</n-alert
      >
      <section class="list-panel">
        <n-select
          v-model:value="accountId"
          class="account-filter"
          clearable
          filterable
          :options="accountOptions"
          :render-label="renderAccount"
          :show-checkmark="false"
          placeholder="筛选客户"
          @update:value="resetPage"
        />
        <n-data-table
          remote
          striped
          flex-height
          class="main-table"
          :loading="loading"
          :columns="columns"
          :data="rows"
          :row-key="(row) => row.id"
          :scroll-x="scrollX"
          :pagination="false"
        >
          <template #empty
            ><n-empty :description="error ? '加载失败，请点击刷新重试' : '暂无记录'"
          /></template>
        </n-data-table>
        <div class="pagination">
          <span>共 {{ total }} 条</span
          ><n-pagination
            v-model:page="page"
            v-model:page-size="pageSize"
            :item-count="total"
            :page-sizes="[20, 50, 100]"
            show-size-picker
            @update:page="load"
            @update:page-size="resetPage"
          />
        </div>
      </section>

      <n-drawer
        v-model:show="detailVisible"
        :width="drawerWidth"
        :mask-closable="!busy"
        :close-on-esc="!busy"
      >
        <n-drawer-content :title="detailTitle" :closable="!busy">
          <n-spin :show="busy">
            <template v-if="detail && mode === 'orders'">
              <n-alert type="info" :show-icon="false"
                >{{ detail.account.customer_name }} · {{ detail.account.signing_entity_name }} ·
                {{ actionLabels[detail.action] }} · 联系人：{{ detail.contact }}</n-alert
              >
              <section v-for="line in detail.lines" :key="line.id" class="detail-section">
                <div class="section-head">
                  <h3>{{ line.name }} × {{ line.quantity }}</h3>
                  <n-tag :type="line.stage === 'accepted' ? 'success' : 'info'">{{
                    stageLabel(line.stage)
                  }}</n-tag>
                </div>
                <p class="muted">
                  明细 #{{ line.id }} · 需求版本 {{ line.revision }}
                  <span v-if="line.parent_id">· 主明细 #{{ line.parent_id }}</span
                  ><span v-if="line.service_id"> · 客户产品 #{{ line.service_id }}</span>
                </p>
                <n-collapse>
                  <n-collapse-item title="产品参数" :name="`parameters-${line.id}`"
                    ><n-descriptions :column="1" label-placement="left" bordered
                      ><n-descriptions-item
                        v-for="(value, key) in line.parameters"
                        :key="key"
                        :label="parameterLabel(line, key)"
                        >{{ parameterValue(line, key, value) }}</n-descriptions-item
                      ></n-descriptions
                    ></n-collapse-item
                  >
                  <n-collapse-item
                    v-if="line.quotes.length"
                    title="报价版本与费用"
                    :name="`quotes-${line.id}`"
                  >
                    <div v-for="quote in line.quotes" :key="quote.id" class="quote-record">
                      <strong
                        >Q{{ quote.version }} · {{ quote.currency }} · {{ quote.status }} · 有效至
                        {{ quote.valid_until }}</strong
                      >
                      <div v-for="charge in quote.charges" :key="charge.code">
                        {{ charge.name }} · {{ kindLabels[charge.kind] }} · {{ charge.amount }}
                        {{ quote.currency }} / {{ charge.unit }} ·
                        {{ treatmentLabels[charge.treatment] }}
                      </div>
                      <p>{{ quote.terms.terms }}</p>
                      <p v-if="quote.confirmation">确认依据：{{ quote.confirmation }}</p>
                    </div>
                  </n-collapse-item>
                  <n-collapse-item
                    v-if="line.delivery.evidence"
                    title="交付与验收记录"
                    :name="`delivery-${line.id}`"
                  >
                    <p>{{ line.delivery.evidence }}</p>
                    <p v-for="(value, key) in line.delivery.values" :key="key">
                      {{ key }}：{{ value }}
                    </p>
                    <p v-if="line.acceptance.evidence">
                      验收：{{ line.acceptance.evidence }} · 起租 {{ line.acceptance.starts_on }}
                    </p>
                  </n-collapse-item>
                </n-collapse>
                <div v-for="task in line.tasks" :key="task.id" class="task-row">
                  <span
                    >{{ task.department === 'procurement' ? '采购 / 接入确认' : '实施交付' }} ·
                    {{ task.status }} · {{ task.evidence }}</span
                  ><CButton
                    v-if="capabilities.delivery && ['delivery', 'acceptance'].includes(line.stage)"
                    show-save
                    save-text="处理任务"
                    :disabled="busy"
                    @save="openTask(line, task)"
                  />
                </div>
                <n-space class="line-actions">
                  <CButton
                    v-if="
                      capabilities.edit &&
                      ['draft', 'quoted', 'approved', 'rejected'].includes(line.stage)
                    "
                    show-save
                    save-text="修改需求"
                    :disabled="busy"
                    @save="openLineEdit(line)"
                  />
                  <CButton
                    v-if="
                      capabilities.quote &&
                      ['draft', 'quoted', 'approved', 'rejected'].includes(line.stage)
                    "
                    show-save
                    save-text="提交报价"
                    :disabled="busy"
                    @save="openQuote(line)"
                  />
                  <CButton
                    v-if="capabilities.quote && ['delivery', 'acceptance'].includes(line.stage)"
                    show-save
                    save-text="撤回重新报价"
                    :disabled="busy"
                    @save="openDecision(line, 'revise')"
                  />
                  <CButton
                    v-if="capabilities.quote && line.stage === 'quoted'"
                    show-save
                    save-text="批准报价"
                    :disabled="busy"
                    @save="openDecision(line, 'approve')"
                  />
                  <CButton
                    v-if="capabilities.decision && line.stage === 'approved'"
                    show-save
                    save-text="客户确认"
                    :disabled="busy"
                    @save="openDecision(line, 'confirm')"
                  />
                  <CButton
                    v-if="capabilities.quote && ['quoted', 'approved'].includes(line.stage)"
                    show-save
                    save-text="驳回报价"
                    :disabled="busy"
                    @save="openDecision(line, 'reject')"
                  />
                  <CButton
                    v-if="
                      capabilities.decision &&
                      ['draft', 'quoted', 'approved', 'rejected', 'delivery'].includes(line.stage)
                    "
                    show-save
                    save-text="取消明细"
                    :disabled="busy"
                    @save="openDecision(line, 'cancel')"
                  />
                  <CButton
                    v-if="capabilities.delivery && ['delivery', 'acceptance'].includes(line.stage)"
                    show-save
                    save-text="交付回填"
                    :disabled="busy"
                    @save="openDelivery(line)"
                  />
                  <CButton
                    v-if="capabilities.accept && line.stage === 'acceptance'"
                    show-save
                    save-text="验收 / 返工"
                    :disabled="busy"
                    @save="openAcceptance(line)"
                  />
                  <CButton
                    v-if="capabilities.delivery && line.stage === 'support'"
                    show-save
                    save-text="完成处理"
                    :disabled="busy"
                    @save="openSupport(line)"
                  />
                  <CButton
                    show-save
                    save-text="审计记录"
                    :disabled="busy"
                    @save="showAudit('line', line.id)"
                  />
                </n-space>
              </section>
            </template>
            <template v-if="detail && mode === 'services'">
              <n-alert type="info"
                >服务ID：{{ detail.service_no }} · {{ serviceState(detail.state) }} · 原始起租日
                {{ detail.anchor }}</n-alert
              >
              <n-space class="line-actions"
                ><CButton
                  v-if="capabilities.create"
                  show-save
                  save-text="变更 / 续约 / 退订"
                  @save="openServiceOrder" /><CButton
                  show-save
                  save-text="审计记录"
                  @save="showAudit('service', detail.id)"
              /></n-space>
              <section v-for="version in detail.versions" :key="version.id" class="detail-section">
                <h3>
                  {{ version.starts_on }} 至 {{ version.ends_before || '持续有效' }}（结束日不计费）
                </h3>
                <p>
                  {{ serviceState(version.state) }} · 来源明细 #{{ version.source_line_id }} ·
                  {{ version.currency }}
                </p>
                <div v-for="charge in version.charges" :key="charge.id" class="task-row">
                  <div>
                    {{ charge.name }} · {{ kindLabels[charge.kind] }} · {{ charge.unit_price }}
                    {{ version.currency }}
                    <n-tag v-if="charge.included" size="small">已含 / 免费</n-tag>
                  </div>
                  <CButton
                    v-if="capabilities.usage && charge.kind === 'usage' && !charge.included"
                    show-save
                    save-text="录入核实用量"
                    @save="openUsage(version, charge)"
                  />
                </div>
                <n-collapse
                  ><n-collapse-item title="配置与资源交付快照" :name="version.id"
                    ><p v-for="(value, key) in version.parameters" :key="key">
                      {{ key }}：{{ value }}
                    </p></n-collapse-item
                  ></n-collapse
                >
              </section>
              <h3>资源绑定</h3>
              <p v-for="resource in detail.resources" :key="resource.id">
                {{ resource.kind }} · {{ resource.resource_key }} · {{ resource.state }}
              </p>
            </template>
            <template v-if="detail && mode === 'billing'">
              <n-alert type="info"
                >{{ detail.customer_name }} · {{ detail.currency }} {{ detail.total_amount }} ·
                {{ billState(detail.status) }}</n-alert
              >
              <p>{{ detail.remark }}</p>
              <n-space
                v-if="
                  capabilities.audit_bill &&
                  ['pending_approval', 'rejected'].includes(detail.status)
                "
                class="line-actions"
                ><CButton
                  v-if="detail.status === 'pending_approval'"
                  show-save
                  save-text="审核通过"
                  @save="openBillDecision('approve')" /><CButton
                  v-if="detail.status === 'pending_approval'"
                  show-save
                  save-text="退回"
                  @save="openBillDecision('reject')" /><CButton
                  show-save
                  save-text="作废草稿"
                  @save="openBillDecision('void')"
              /></n-space>
              <section v-for="(item, index) in detail.items" :key="index" class="detail-section">
                <h3>{{ item.charge_name }}</h3>
                <p>
                  {{ item.service_no }} · {{ item.starts_on }} 至
                  {{ item.ends_before }}（结束日不计费）
                </p>
                <p>未税 {{ item.amount }} · 税额 {{ item.tax }} {{ detail.currency }}</p>
                <p v-if="item.source_line_id">
                  来源工单明细 #{{ item.source_line_id }} · 报价 Q{{ item.quote_version }}
                </p>
              </section>
            </template>
          </n-spin>
        </n-drawer-content>
      </n-drawer>

      <n-modal
        v-model:show="editor.show"
        preset="card"
        :title="editor.title"
        class="idc-modal"
        :style="modalStyle"
        :mask-closable="!busy"
        :closable="!busy"
        :close-on-esc="!busy"
      >
        <n-form label-placement="top" :disabled="busy">
          <template v-if="editor.kind === 'create'">
            <n-alert type="info" :show-icon="false"
              >一个工单对应一个客户及签约主体，可添加多个产品。未报价项目不会启动收费。</n-alert
            >
            <n-grid cols="1 680:2" responsive="self" :x-gap="16">
              <n-form-item-gi label="客户 / 签约主体" required
                ><n-select
                  v-model:value="form.account_id"
                  filterable
                  :show-checkmark="false"
                  :options="activeAccountOptions"
                  :render-label="renderAccount"
                  @update:value="loadSourceServices"
              /></n-form-item-gi>
              <n-form-item-gi label="业务动作" required
                ><n-select
                  v-model:value="form.action"
                  :options="actionOptions"
                  @update:value="onActionChange"
              /></n-form-item-gi>
              <n-form-item-gi label="工单标题" required
                ><n-input v-model:value="form.title" :maxlength="200"
              /></n-form-item-gi>
              <n-form-item-gi label="客户联系人" required
                ><n-input v-model:value="form.contact" :maxlength="200"
              /></n-form-item-gi>
              <n-form-item-gi label="期望交付日期"
                ><n-date-picker
                  v-model:formatted-value="form.requested_date"
                  value-format="yyyy-MM-dd"
                  type="date"
                  clearable
              /></n-form-item-gi>
              <n-form-item-gi label="合同 / 报价 / 原工单关联"
                ><n-input v-model:value="form.reference" :maxlength="200"
              /></n-form-item-gi>
            </n-grid>
            <section v-for="(line, index) in form.lines" :key="index" class="detail-section">
              <div class="section-head">
                <h3>产品 {{ index + 1 }}</h3>
                <CButton
                  v-if="form.lines.length > 1"
                  show-delete
                  :disabled="busy"
                  @delete="removeLine(index)"
                />
              </div>
              <n-form-item v-if="requiresService" label="已有客户产品" required
                ><n-select
                  v-model:value="line.source_service_id"
                  :options="sourceOptions"
                  filterable
                  :loading="sourceLoading"
                  @update:value="chooseSource(line)"
              /></n-form-item>
              <n-grid cols="1 680:2" responsive="self" :x-gap="16">
                <n-form-item-gi label="产品多级分类" required
                  ><n-cascader
                    v-model:value="line.product_code"
                    :options="productTree"
                    check-strategy="child"
                    :disabled="requiresService"
                    filterable
                    @update:value="line.parameters = {}"
                /></n-form-item-gi>
                <n-form-item-gi label="数量" required
                  ><n-input-number v-model:value="line.quantity" :min="0.0001" :max="1000000"
                /></n-form-item-gi>
                <n-form-item-gi v-if="index > 0" label="附加于主产品（可不选）"
                  ><n-select
                    v-model:value="line.parent_index"
                    clearable
                    :options="parentOptions(index)"
                /></n-form-item-gi>
              </n-grid>
              <n-alert v-if="line.product_code === 'NET.DIA.RETAIL'" type="warning"
                >楼宇接入必须完成覆盖勘查和询价，采用经过批准的客户价格。</n-alert
              >
              <ParameterForm
                v-if="schema(line.product_code)"
                v-model="line.parameters"
                :schema="schema(line.product_code)"
                :optional="form.action === 'quote' || requiresService"
                :disabled="busy"
              />
            </section>
            <CButton
              show-save
              save-text="添加产品 / 本地传输附加项"
              :disabled="busy || form.lines.length >= 30"
              @save="addLine"
            />
            <n-form-item label="工单说明"
              ><n-input v-model:value="form.description" type="textarea" :maxlength="10000"
            /></n-form-item>
          </template>
          <template v-else-if="editor.kind === 'account'">
            <n-alert type="info"
              >已有工单的客户、主体及账单公司不可更换；可调整授权用户。不会按名称猜测客户映射。</n-alert
            >
            <n-form-item label="已有映射（空白为新增）"
              ><n-select
                v-model:value="form.id"
                clearable
                :options="accountOptions"
                :render-label="renderAccount"
                @update:value="chooseAccount"
            /></n-form-item>
            <n-form-item label="CRM客户" required
              ><n-select
                v-model:value="form.customer_id"
                :options="mappingCustomerOptions"
                filterable
                :show-checkmark="false"
                :render-label="renderAccount"
                @update:value="
                  form.signing_entity_id = mapping.customers.find(
                    (item) => item.id === form.customer_id
                  )?.signing_entity_id
                "
            /></n-form-item>
            <n-form-item label="签约主体" required
              ><n-select
                v-model:value="form.signing_entity_id"
                :options="mapping.entities.map((item) => ({ value: item.id, label: item.name }))"
            /></n-form-item>
            <n-form-item label="账单客户公司" required
              ><n-select
                v-model:value="form.company_id"
                :options="mapping.companies.map((item) => ({ value: item.id, label: item.name }))"
                filterable
            /></n-form-item>
            <n-form-item label="允许访问此客户的用户"
              ><n-select
                v-model:value="form.user_ids"
                :options="
                  mapping.users.map((item) => ({
                    value: item.id,
                    label: item.alias || item.username,
                  }))
                "
                filterable
                multiple
            /></n-form-item>
            <n-form-item label="启用"><n-switch v-model:value="form.active" /></n-form-item>
          </template>
          <template v-else-if="editor.kind === 'quote'">
            <n-form-item label="有效客户价格 / 标准价参考"
              ><n-select
                v-model:value="candidateId"
                clearable
                :options="candidateOptions"
                @update:value="applyCandidate"
            /></n-form-item>
            <n-alert type="info"
              >引用价格后仍需核对规格、地区、单位和币种；这里保存独立报价快照，不覆盖原价格。</n-alert
            >
            <n-grid cols="1 680:2" responsive="self" :x-gap="16">
              <n-form-item-gi label="币种"
                ><n-select v-model:value="form.currency" :options="currencies"
              /></n-form-item-gi>
              <n-form-item-gi label="报价有效期" required
                ><n-date-picker
                  v-model:formatted-value="form.valid_until"
                  type="date"
                  value-format="yyyy-MM-dd"
              /></n-form-item-gi>
              <n-form-item-gi label="合同月数"
                ><n-input-number v-model:value="form.contract_months" :min="1" :max="120"
              /></n-form-item-gi>
              <n-form-item-gi label="付款期限（天）"
                ><n-input-number v-model:value="form.payment_days" :min="0" :max="365"
              /></n-form-item-gi>
            </n-grid>
            <n-form-item label="合同与计费条款" required
              ><n-input
                v-model:value="form.terms"
                type="textarea"
                :maxlength="3000"
                placeholder="起租、暂停收费、折算、费用包含关系等"
            /></n-form-item>
            <n-form-item label="勘查 / 采购询价依据（楼宇或Off-net必填）"
              ><n-input v-model:value="form.procurement_reference" :maxlength="500"
            /></n-form-item>
            <ChargeEditor v-model="form.charges" :disabled="busy" />
          </template>
          <template v-else-if="editor.kind === 'line'">
            <n-alert type="warning">修改需求会使旧报价失效，需重新报价和确认。</n-alert>
            <n-form-item label="数量"
              ><n-input-number v-model:value="form.quantity" :min="0.0001"
            /></n-form-item>
            <ParameterForm
              v-model="form.parameters"
              :schema="editor.line.schema_snapshot"
              :disabled="busy"
            />
          </template>
          <template v-else-if="editor.kind === 'delivery'">
            <n-alert type="info"
              >按已确认规格回填交付证据。资源键：设备ID或设备ID:节点名；VM为remote:vmid；IP为CIDR。</n-alert
            >
            <n-form-item
              v-for="label in editor.line.schema_snapshot.delivery_fields"
              :key="label"
              :label="label"
              required
              ><n-input v-model:value="form.values[label]" :maxlength="3000"
            /></n-form-item>
            <div v-for="(resource, index) in form.resources" :key="index" class="resource-row">
              <n-select v-model:value="resource.kind" :options="resourceKinds" /><n-input
                v-model:value="resource.key"
                placeholder="资源标识"
              /><n-checkbox v-model:checked="resource.shared">共享端口/线路/机柜</n-checkbox
              ><CButton show-delete :disabled="busy" @delete="form.resources.splice(index, 1)" />
            </div>
            <CButton
              show-save
              save-text="绑定资源"
              :disabled="busy"
              @save="form.resources.push({ kind: 'circuit', key: '', shared: false, details: {} })"
            />
            <n-form-item label="交付与测试依据" required
              ><n-input v-model:value="form.evidence" type="textarea" :maxlength="3000"
            /></n-form-item>
          </template>
          <template v-else-if="editor.kind === 'accept'">
            <n-form-item label="验收结论"
              ><n-switch v-model:value="form.accept"
                ><template #checked>通过</template><template #unchecked>返工</template></n-switch
              ></n-form-item
            >
            <n-form-item label="计费 / 变更生效日期" required
              ><n-date-picker
                v-model:formatted-value="form.starts_on"
                type="date"
                value-format="yyyy-MM-dd"
            /></n-form-item>
            <n-form-item label="计费结束边界（当天不计费，可留空）"
              ><n-date-picker
                v-model:formatted-value="form.ends_before"
                type="date"
                value-format="yyyy-MM-dd"
                clearable
            /></n-form-item>
            <n-form-item label="客户验收或返工依据" required
              ><n-input v-model:value="form.evidence" type="textarea" :maxlength="1000"
            /></n-form-item>
          </template>
          <template
            v-else-if="['decision', 'task', 'support', 'billDecision'].includes(editor.kind)"
          >
            <n-form-item v-if="editor.kind === 'task'" label="任务状态"
              ><n-select v-model:value="form.status" :options="taskStates"
            /></n-form-item>
            <n-form-item
              :label="editor.kind === 'billDecision' ? '审核意见' : '确认 / 执行依据'"
              required
              ><n-input
                v-if="editor.kind === 'billDecision'"
                v-model:value="form.comment"
                type="textarea"
                :maxlength="1000" /><n-input
                v-else
                v-model:value="form.evidence"
                type="textarea"
                :maxlength="1000"
            /></n-form-item>
          </template>
          <template v-else-if="editor.kind === 'usage'">
            <n-alert type="info"
              >填写经过核实的结算量，附上计量依据。95模式需提交完整结算区间的单一核实结果；缺数据不会按0出账。</n-alert
            >
            <n-form-item label="开始日期" required
              ><n-date-picker
                v-model:formatted-value="form.starts_on"
                type="date"
                value-format="yyyy-MM-dd"
            /></n-form-item>
            <n-form-item label="结束边界（当天不计入）" required
              ><n-date-picker
                v-model:formatted-value="form.ends_before"
                type="date"
                value-format="yyyy-MM-dd"
            /></n-form-item>
            <n-form-item label="核实用量" required
              ><n-input-number v-model:value="form.quantity" :min="0"
            /></n-form-item>
            <n-form-item label="计量证据" required
              ><n-input v-model:value="form.evidence" type="textarea" :maxlength="1000"
            /></n-form-item>
          </template>
          <template v-else-if="editor.kind === 'billing'">
            <n-form-item label="客户" required
              ><n-select
                v-model:value="form.account_id"
                :options="accountOptions"
                :render-label="renderAccount"
                :show-checkmark="false"
                filterable
                @update:value="preview = null"
            /></n-form-item>
            <n-form-item label="账单月份" required
              ><n-date-picker
                v-model:formatted-value="form.month"
                type="month"
                value-format="yyyy-MM-dd"
                @update:formatted-value="preview = null"
            /></n-form-item>
            <CButton
              show-save
              save-text="计算预览"
              :save-loading="busy"
              :disabled="busy"
              @save="previewBill"
            />
            <template v-if="preview"
              ><n-alert v-for="(problem, index) in preview.blocked" :key="index" type="error"
                >服务 #{{ problem.service_id }} / 费用 #{{ problem.charge_id }}：{{
                  problem.reason
                }}（{{ problem.starts_on }} 至 {{ problem.ends_before }}）</n-alert
              >
              <section v-for="bill in preview.previews" :key="bill.currency" class="detail-section">
                <h3>
                  {{ bill.customer_name }} · {{ bill.signing_entity_name }} · {{ bill.currency }}
                  {{ bill.total_amount }}
                </h3>
                <p v-for="item in bill.items" :key="item.key">
                  {{ item.service_no }} {{ item.charge_name }}：{{ item.amount }} + 税
                  {{ item.tax }}（{{ item.starts_on }} 至 {{ item.ends_before }}）
                </p>
              </section>
              <p v-if="!preview.previews.length && !preview.blocked.length">
                没有待生成费用，或当期已生成并锁定。
              </p>
              <p v-if="preview.skipped.length">
                跳过 {{ preview.skipped.length }} 条已出账费用。
              </p></template
            >
          </template>
          <template v-else-if="editor.kind === 'event'">
            <n-alert type="warning"
              >此操作登记待出账费用事件。调整/贷项必须关联原账单；预付款后续抵扣应登记关联贷项，避免重复收取。</n-alert
            >
            <n-form-item label="客户" required
              ><n-select
                v-model:value="form.account_id"
                :options="accountOptions"
                :render-label="renderAccount"
                :show-checkmark="false"
                filterable
            /></n-form-item>
            <n-form-item label="类型"
              ><n-select v-model:value="form.kind" :options="eventKinds"
            /></n-form-item>
            <n-form-item v-if="form.kind !== 'prepayment'" label="原账单ID" required
              ><n-input-number v-model:value="form.source_bill_id" :min="1"
            /></n-form-item>
            <n-form-item label="币种"
              ><n-select v-model:value="form.currency" :options="currencies"
            /></n-form-item>
            <n-form-item label="未税金额（贷项为负数）"
              ><n-input-number v-model:value="form.amount" :precision="2"
            /></n-form-item>
            <n-form-item label="税额"
              ><n-input-number v-model:value="form.tax" :precision="2"
            /></n-form-item>
            <n-form-item label="归属日期"
              ><n-date-picker
                v-model:formatted-value="form.due_on"
                type="date"
                value-format="yyyy-MM-dd"
            /></n-form-item>
            <n-form-item label="调整或预付依据" required
              ><n-input v-model:value="form.description" type="textarea" :maxlength="500"
            /></n-form-item>
          </template>
          <template v-else-if="editor.kind === 'audit'"
            ><n-empty v-if="!auditRows.length" description="暂无记录" />
            <div v-for="item in auditRows" :key="item.id" class="quote-record">
              <strong>{{ item.action }} · 用户 #{{ item.actor_id }} · {{ item.created_at }}</strong>
              <pre>{{ JSON.stringify(item.data, null, 2) }}</pre>
            </div></template
          >
        </n-form>
        <template #footer
          ><div class="modal-footer">
            <CButton show-cancel :disabled="busy" @cancel="editor.show = false" />
            <CButton
              :show-save="editor.kind !== 'audit'"
              :save-text="editor.kind === 'billing' ? '生成账单草稿' : '确认保存'"
              :disabled="
                busy ||
                (editor.kind === 'billing' &&
                  (!preview || preview.blocked.length > 0 || !preview.previews.length))
              "
              :save-loading="busy"
              @save="save"
            /></div
        ></template>
      </n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NTag, NTooltip } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'
import { idcApi } from '@/api/idc'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import ParameterForm from './ParameterForm.vue'
import ChargeEditor from './ChargeEditor.vue'

const props = defineProps({ mode: { type: String, default: 'orders' } })
const route = useRoute()
const router = useRouter()
const mode = computed(() => props.mode)
const title = computed(
  () => ({ orders: 'IDC工单', services: '客户产品', billing: 'IDC客户账单' }[mode.value])
)
const subtitle = computed(
  () =>
    ({
      orders: '结构化需求、版本化报价、逐产品交付验收',
      services: '服务配置、生效历史、资源绑定与费用组成',
      billing: '按实际生效区间结算，保留每笔费用的业务来源',
    }[mode.value])
)
const accounts = ref([])
const catalog = ref([])
const capabilities = ref({})
const actionLabels = ref({})
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const accountId = ref(null)
const loading = ref(false)
const initialized = ref(false)
const busy = ref(false)
const error = ref('')
const detail = ref(null)
const detailVisible = ref(false)
const drawerWidth = 'min(1100px, 96vw)'
const modalStyle = { width: 'min(900px, calc(100vw - 24px))' }
const editor = reactive({ show: false, kind: '', title: '', line: null, taskId: null })
const form = ref({})
const sourceServices = ref([])
const sourceLoading = ref(false)
const mapping = reactive({ customers: [], entities: [], companies: [], users: [] })
const candidates = ref([])
const candidateId = ref(null)
const preview = ref(null)
const auditRows = ref([])
let listSequence = 0
let sourceSequence = 0
const clone = (value) => JSON.parse(JSON.stringify(value))
const today = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate()
  ).padStart(2, '0')}`
}
const requestKey = () => {
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (x) => x.toString(16).padStart(2, '0')).join('')
}
const options = (entries) => entries.map(([value, label]) => ({ value, label }))
const currencies = ['USD', 'CNY', 'HKD', 'EUR', 'GBP', 'SGD', 'JPY'].map((value) => ({
  value,
  label: value,
}))
const resourceKinds = options([
  ['device', '物理设备 / 节点'],
  ['vm', '云主机'],
  ['cabinet', '机柜'],
  ['ip', 'IP前缀'],
  ['circuit', '线路'],
  ['port', '端口'],
])
const taskStates = options([
  ['pending', '待处理'],
  ['working', '处理中'],
  ['done', '已完成'],
  ['failed', '失败 / 返工'],
])
const eventKinds = options([
  ['adjustment', '账单调整'],
  ['prepayment', '预付款'],
  ['credit', '贷项 / 预付款抵扣'],
])
const kindLabels = { recurring: '周期费', nrc: '一次性费', usage: '用量费' }
const treatmentLabels = {
  separate: '单独计费',
  included: '已含',
  free: '免费',
  customer: '客户自备',
}
const stageLabel = (stage) =>
  ({
    draft: '待报价',
    quoted: '待审批',
    approved: '待客户确认',
    rejected: '已驳回',
    delivery: '待交付',
    acceptance: '待验收',
    accepted: '已验收',
    cancelled: '已取消',
    quote_done: '询价完成',
    support: '待处理',
    support_done: '处理完成',
  }[stage] || stage)
const serviceState = (state) =>
  ({
    active: '使用中',
    suspended: '已暂停',
    terminated: '已终止',
    scheduled: '待生效',
    expired: '已到期',
  }[state] || state)
const billState = (state) =>
  ({
    pending_approval: '待审核',
    issued: '已开账',
    rejected: '已退回',
    void: '已作废',
    paid: '已结清',
    sent: '已发送',
  }[state] || state)
const accountOptions = computed(() =>
  accounts.value.map((item) => ({
    value: item.id,
    label: item.customer_name,
    entity: item.signing_entity_name,
  }))
)
const activeAccountOptions = computed(() =>
  accountOptions.value.filter(
    (option) => accounts.value.find((item) => item.id === option.value)?.active
  )
)
const mappingCustomerOptions = computed(() =>
  mapping.customers.map((item) => ({
    value: item.id,
    label: item.name,
    entity: mapping.entities.find((entity) => entity.id === item.signing_entity_id)?.name || '',
  }))
)
const actionOptions = computed(() => options(Object.entries(actionLabels.value)))
const requiresService = computed(() =>
  ['change', 'renew', 'suspend', 'resume', 'terminate', 'incident', 'maintenance'].includes(
    form.value.action
  )
)
const sourceOptions = computed(() =>
  sourceServices.value.map((item) => ({
    value: item.id,
    label: `${item.service_no} · ${item.name} · ${serviceState(item.state)}`,
  }))
)
const candidateOptions = computed(() =>
  candidates.value.map((item) => ({
    value: item.id,
    label: `${item.price_type === 'customer' ? '客户价' : '标准价'} · ${
      item.spec_config_name || '规格待核对'
    } · ${item.currency} ${item.amount}/${item.billing_unit}`,
  }))
)
const detailTitle = computed(
  () =>
    detail.value?.ticket?.ticket_no ||
    detail.value?.service_no ||
    detail.value?.invoice_no ||
    '详情'
)
const schema = (code) => catalog.value.find((item) => item.code === code)
const productTree = computed(() => {
  const groups = []
  for (const product of catalog.value) {
    let group = groups.find((item) => item.label === product.category)
    if (!group) {
      group = { value: product.category, label: product.category, children: [] }
      groups.push(group)
    }
    if (product.code.startsWith('NET.DIA.')) {
      let dia = group.children.find((item) => item.value === 'DIA')
      if (!dia) {
        dia = { value: 'DIA', label: 'DIA', children: [] }
        group.children.push(dia)
      }
      dia.children.push({ value: product.code, label: product.name.split(' / ')[1] })
    } else group.children.push({ value: product.code, label: product.name })
  }
  return groups
})
function renderAccount(option) {
  const name = option.entity || ''
  const chinese = name.includes('科特思') || name.toLowerCase().includes('catixs-cn')
  const telecom = name.includes('77')
  return h(
    'div',
    {
      style:
        'display:flex;align-items:center;justify-content:space-between;gap:12px;width:100%;min-width:0',
    },
    [
      h(
        'span',
        { style: 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap' },
        option.label
      ),
      h(
        NTag,
        {
          size: 'small',
          type: chinese ? 'success' : telecom ? 'warning' : 'info',
          style: 'flex-shrink:0',
          title: name,
        },
        () => (chinese ? '科' : telecom ? '7' : 'C')
      ),
    ]
  )
}
function rowAction(row) {
  return h(NTooltip, null, {
    trigger: () =>
      h(
        NButton,
        { circle: true, secondary: true, size: 'small', onClick: () => view(row) },
        { icon: () => h(TheIcon, { icon: 'mdi:eye-outline', size: 16 }) }
      ),
    default: () => '查看详情',
  })
}
const columns = computed(() => {
  const config =
    mode.value === 'orders'
      ? [
          { title: '工单编号', key: 'ticket_no', width: 210 },
          { title: '客户', key: 'customer_name', width: 170 },
          { title: '工单标题', key: 'title', width: 260 },
          {
            title: '动作',
            key: 'action',
            width: 160,
            render: (row) => actionLabels.value[row.action],
          },
          {
            title: '产品阶段',
            key: 'stages',
            width: 240,
            render: (row) => [...new Set(row.stages)].map(stageLabel).join(' / '),
          },
        ]
      : mode.value === 'services'
      ? [
          { title: '服务ID', key: 'service_no', width: 240 },
          {
            title: '客户',
            key: 'account_id',
            width: 180,
            render: (row) =>
              accounts.value.find((item) => item.id === row.account_id)?.customer_name || '-',
          },
          { title: '产品', key: 'name', width: 230 },
          { title: '起租日', key: 'anchor', width: 140 },
          { title: '状态', key: 'state', width: 120, render: (row) => serviceState(row.state) },
        ]
      : [
          { title: '账单编号', key: 'invoice_no', width: 220 },
          { title: '客户', key: 'customer_name', width: 200 },
          { title: '账单月份', key: 'bill_month', width: 140 },
          { title: '币种', key: 'currency', width: 100 },
          { title: '含税金额', key: 'total_amount', width: 150 },
          { title: '状态', key: 'status', width: 140, render: (row) => billState(row.status) },
        ]
  return [
    ...config.map((column) => ({ ...column, resizable: true, minWidth: 90 })),
    { title: '操作', key: 'actions', width: 76, fixed: 'right', render: rowAction },
  ]
})
const scrollX = computed(() => columns.value.reduce((sum, column) => sum + column.width, 0))
function parameterLabel(line, key) {
  return line.schema_snapshot.fields.find((field) => field.key === key)?.label || key
}
function parameterValue(line, key, value) {
  return (
    line.schema_snapshot.fields
      .find((field) => field.key === key)
      ?.options?.find((option) => option.value === value)?.label || value
  )
}
function parentOptions(index) {
  return form.value.lines.slice(0, index).map((line, i) => ({
    value: i,
    label: `${i + 1}. ${schema(line.product_code)?.name || '待选产品'}`,
  }))
}
function newLine() {
  return {
    product_code: null,
    quantity: 1,
    parameters: {},
    source_service_id: null,
    parent_index: null,
  }
}
function addLine() {
  form.value.lines.push(newLine())
}
function removeLine(index) {
  form.value.lines.splice(index, 1)
  form.value.lines.forEach((line) => {
    if (line.parent_index === index) line.parent_index = null
    else if (line.parent_index > index) line.parent_index -= 1
  })
}
function open(kind, heading, data, line = null) {
  editor.kind = kind
  editor.title = heading
  editor.line = line
  form.value = clone(data)
  editor.show = true
}
async function load() {
  const sequence = ++listSequence
  loading.value = true
  error.value = ''
  try {
    const result = await idcApi[mode.value === 'billing' ? 'billing' : mode.value]({
      account_id: accountId.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    if (sequence !== listSequence) return
    rows.value = result.data.items
    total.value = result.data.total
  } catch (err) {
    if (sequence === listSequence) error.value = err.message || '加载失败，请重试'
  } finally {
    if (sequence === listSequence) loading.value = false
  }
}
function resetPage() {
  page.value = 1
  load()
}
async function view(row) {
  if (busy.value) return
  busy.value = true
  try {
    detail.value = mode.value === 'orders' ? (await idcApi.order(row.id)).data : row
    detailVisible.value = true
  } catch (err) {
    window.$message?.error(err.message || '读取失败')
  } finally {
    busy.value = false
  }
}
function openCreate() {
  open('create', '新增IDC工单', {
    request_key: requestKey(),
    account_id: accountId.value,
    action: 'new',
    title: '',
    contact: '',
    requested_date: null,
    reference: '',
    description: '',
    lines: [newLine()],
  })
  if (accountId.value) loadSourceServices()
}
async function loadSourceServices() {
  const sequence = ++sourceSequence
  sourceServices.value = []
  form.value.lines?.forEach((line) => {
    line.source_service_id = null
  })
  if (!form.value.account_id) return
  sourceLoading.value = true
  const selectedAccount = form.value.account_id
  try {
    const gathered = []
    let current = 1
    let count = 0
    do {
      const result = await idcApi.services({
        account_id: selectedAccount,
        page: current,
        page_size: 100,
      })
      gathered.push(...result.data.items)
      count = result.data.total
      current += 1
    } while (gathered.length < count && sequence === sourceSequence)
    if (sequence === sourceSequence) sourceServices.value = gathered
  } catch (err) {
    window.$message?.error(err.message || '客户产品加载失败')
  } finally {
    if (sequence === sourceSequence) sourceLoading.value = false
  }
}
function onActionChange() {
  form.value.lines = [newLine()]
  if (requiresService.value) loadSourceServices()
}
function chooseSource(line) {
  const service = sourceServices.value.find((item) => item.id === line.source_service_id)
  if (!service) return
  const version = service.versions[service.versions.length - 1]
  line.product_code = service.product_code
  line.parameters = clone(version?.parameters || {})
  line.quantity = Number(version?.quantity || 1)
}
async function openServiceOrder() {
  const source = clone(detail.value)
  openCreate()
  form.value.account_id = source.account_id
  form.value.action = 'change'
  form.value.title = `${source.name}变更`
  await loadSourceServices()
  form.value.lines[0].source_service_id = source.id
  chooseSource(form.value.lines[0])
}
async function openAccount() {
  try {
    Object.assign(mapping, (await idcApi.accountOptions()).data)
    open('account', '客户账务映射', {
      id: null,
      customer_id: null,
      signing_entity_id: null,
      company_id: null,
      user_ids: [],
      active: true,
    })
  } catch (err) {
    window.$message?.error(err.message || '选项读取失败')
  }
}
function chooseAccount(id) {
  const account = accounts.value.find((item) => item.id === id)
  form.value = account
    ? Object.fromEntries(
        ['id', 'customer_id', 'signing_entity_id', 'company_id', 'user_ids', 'active'].map(
          (key) => [key, clone(account[key])]
        )
      )
    : {
        id: null,
        customer_id: null,
        signing_entity_id: null,
        company_id: null,
        user_ids: [],
        active: true,
      }
}
function defaultCharge() {
  return {
    code: 'mrc',
    name: '周期费用',
    kind: 'recurring',
    amount: null,
    tax_rate: 0,
    treatment: 'separate',
    unit: '项',
    interval: 1,
    proration: 'actual_days',
    timing: 'arrears',
    usage_mode: 'quantity',
    minimum: 0,
    step: 1,
    allowance: 0,
    cap: null,
    meter_rule: '',
  }
}
async function openQuote(line) {
  candidates.value = []
  candidateId.value = null
  open(
    'quote',
    '提交报价版本',
    {
      revision: line.revision,
      currency: 'USD',
      valid_until: today(),
      contract_months: 12,
      payment_days: 15,
      terms: '',
      procurement_reference: '',
      charges: [defaultCharge()],
    },
    line
  )
  try {
    candidates.value = (await idcApi.prices(line.id)).data
  } catch (err) {
    window.$message?.error(err.message || '价格参考读取失败，可手动报价')
  }
}
function applyCandidate() {
  const candidate = candidates.value.find((item) => item.id === candidateId.value)
  if (!candidate) return
  const periods = { month: 1, quarter: 3, year: 12 }
  if (!periods[candidate.billing_unit] && candidate.billing_unit !== 'once') {
    window.$message?.warning('该价格计费单位需要人工换算，请手动填写费用组件')
    return
  }
  form.value.charges[0].kind = candidate.billing_unit === 'once' ? 'nrc' : 'recurring'
  form.value.charges[0].interval = periods[candidate.billing_unit] || 1
  form.value.currency = candidate.currency
  form.value.charges[0].amount = Number(candidate.amount)
  form.value.charges[0].name = candidate.spec_config_name || editor.line.name
}
function openLineEdit(line) {
  open(
    'line',
    '修改产品需求',
    {
      product_code: line.product_code,
      revision: line.revision,
      quantity: Number(line.quantity),
      parameters: line.parameters,
      source_service_id: line.service_id,
      parent_index: null,
    },
    line
  )
}
function openDecision(line, action) {
  open(
    'decision',
    {
      approve: '批准报价',
      confirm: '客户确认报价',
      reject: '驳回报价',
      cancel: '取消明细',
      revise: '撤回需求与报价（保留审计记录）',
    }[action],
    { version: line.quote_version, action, evidence: '' },
    line
  )
}
function openTask(line, task) {
  editor.taskId = task.id
  open(
    'task',
    '交付任务处理',
    { status: task.status, assignee_id: task.assignee_id, evidence: task.evidence },
    line
  )
}
function openSupport(line) {
  open('support', '完成故障 / 维护', { status: 'done', evidence: '' }, line)
}
function openDelivery(line) {
  open(
    'delivery',
    '实际交付回填',
    {
      revision: line.revision,
      actual_parameters: line.parameters,
      values: line.delivery.values || {},
      evidence: line.delivery.evidence || '',
      resources: (line.resources || []).map((resource) => ({
        kind: resource.kind,
        key: resource.resource_key,
        shared: !resource.exclusive_key,
        details: resource.details,
      })),
    },
    line
  )
}
function openAcceptance(line) {
  open(
    'accept',
    '客户验收与计费生效',
    {
      revision: line.revision,
      quote_version: line.quote_version,
      starts_on: today(),
      ends_before: null,
      evidence: '',
      accept: true,
    },
    line
  )
}
function openUsage(version, charge) {
  open('usage', `录入用量 · ${charge.name}`, {
    charge_id: charge.id,
    starts_on: version.starts_on,
    ends_before: version.ends_before || null,
    quantity: null,
    evidence: '',
  })
}
function openBilling() {
  preview.value = null
  open('billing', '客户账单预览与生成', {
    account_id: accountId.value,
    month: `${today().slice(0, 7)}-01`,
  })
}
function openBillDecision(action) {
  open('billDecision', '账单审核', { action, comment: '' })
}
function openEvent() {
  open('event', '登记费用事件', {
    request_key: requestKey(),
    account_id: accountId.value,
    service_id: null,
    source_bill_id: null,
    currency: 'USD',
    kind: 'adjustment',
    amount: null,
    tax: 0,
    due_on: today(),
    description: '',
  })
}
async function previewBill() {
  if (busy.value) return
  busy.value = true
  try {
    preview.value = (await idcApi.generate({ ...form.value, dry_run: true })).data
  } catch (err) {
    window.$message?.error(err.message || '预览失败')
  } finally {
    busy.value = false
  }
}
async function showAudit(objectType, id) {
  try {
    auditRows.value = (await idcApi.audit({ object_type: objectType, object_id: id })).data
    open('audit', '业务审计记录', {})
  } catch (err) {
    window.$message?.error(err.message || '审计读取失败')
  }
}
async function reconcile() {
  if (busy.value) return
  busy.value = true
  try {
    const result = await idcApi.reconcile()
    window.$message?.success(`已释放 ${result.data.released} 条到期资源锁`)
    await load()
  } catch (err) {
    window.$message?.error(err.message || '释放失败')
  } finally {
    busy.value = false
  }
}
async function save() {
  if (busy.value) return
  busy.value = true
  try {
    let response
    const payload = clone(form.value)
    const lineId = editor.line?.id
    switch (editor.kind) {
      case 'create':
        response = await idcApi.create(payload)
        break
      case 'account':
        response = await idcApi.saveAccount(payload)
        accounts.value = (await idcApi.accounts()).data
        break
      case 'line':
        response = await idcApi.updateLine(lineId, payload)
        break
      case 'quote':
        response = await idcApi.quote(lineId, payload)
        break
      case 'decision':
        response = await idcApi.decide(lineId, payload)
        break
      case 'task':
        response = await idcApi.task(editor.taskId, payload)
        break
      case 'delivery':
        response = await idcApi.delivery(lineId, payload)
        break
      case 'accept':
        response = await idcApi.accept(lineId, payload)
        break
      case 'support':
        response = await idcApi.supportComplete(lineId, payload)
        break
      case 'usage':
        response = await idcApi.usage(payload)
        break
      case 'event':
        response = await idcApi.event(payload)
        break
      case 'billing':
        response = await idcApi.generate({ ...payload, dry_run: false })
        preview.value = response.data
        if (response.data.blocked.length) return
        break
      case 'billDecision':
        response = await idcApi.billDecision(detail.value.id, payload)
        detail.value = { ...detail.value, ...response.data }
        break
      default:
        return
    }
    if (response?.data?.lines && mode.value !== 'orders') {
      editor.show = false
      detailVisible.value = false
      await router.push({ path: '/idc/orders', query: { order_id: response.data.id } })
      return
    }
    if (response?.data?.lines) {
      detail.value = response.data
      detailVisible.value = true
    }
    editor.show = false
    window.$message?.success('保存成功')
    await load()
  } catch (err) {
    window.$message?.error(err.message || '保存失败，请核对参数后重试')
  } finally {
    busy.value = false
  }
}
async function initialize() {
  try {
    const [definition, accountResult] = await Promise.all([idcApi.catalog(), idcApi.accounts()])
    catalog.value = definition.data.products
    actionLabels.value = definition.data.actions
    capabilities.value = definition.data.capabilities
    accounts.value = accountResult.data
    initialized.value = true
    await load()
    if (mode.value === 'orders' && route.query.order_id)
      await view({ id: Number(route.query.order_id) })
  } catch (err) {
    error.value = err.message || '初始化失败，请刷新重试'
  }
}
onMounted(initialize)
</script>

<style scoped>
.idc-workbench {
  padding: 20px;
  display: grid;
  gap: 18px;
}
.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 18px;
}
.hero h1 {
  margin: 4px 0;
  font-size: 26px;
}
.hero p,
.muted {
  color: #718096;
  margin: 6px 0;
}
.eyebrow {
  color: #64819b;
  font-size: 11px;
  letter-spacing: 2px;
}
.list-panel {
  background: var(--n-color, white);
  border: 1px solid #e6edf3;
  border-radius: 14px;
  padding: 20px;
}
.account-filter {
  width: min(400px, 100%);
  margin-bottom: 16px;
}
.main-table {
  height: clamp(300px, calc(100vh - 360px), 720px);
}
.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  gap: 12px;
  flex-wrap: wrap;
}
.detail-section {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 18px;
  margin: 16px 0;
}
.section-head,
.task-row,
.charge-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.section-head h3 {
  margin: 0;
}
.task-row {
  padding: 10px 0;
  border-bottom: 1px solid #edf2f7;
}
.quote-record {
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
  margin: 10px 0;
}
.line-actions {
  margin-top: 14px;
}
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
.idc-modal :deep(.n-card__content) {
  max-height: 70vh;
  overflow-y: auto;
}
.idc-modal :deep(.n-input-number),
.idc-modal :deep(.n-date-picker) {
  width: 100%;
}
.idc-modal :deep(.n-alert) {
  margin-bottom: 16px;
}
.resource-row {
  display: grid;
  grid-template-columns: 160px 1fr auto auto;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
@media (max-width: 720px) {
  .idc-workbench {
    padding: 10px;
  }
  .list-panel {
    padding: 12px;
  }
  .resource-row {
    grid-template-columns: 1fr;
  }
  .detail-section {
    padding: 12px;
  }
}
</style>
