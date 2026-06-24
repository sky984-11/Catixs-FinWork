<template>
  <AppPage :show-footer="false">
    <div class="vm-page">
      <section class="vm-layout">
        <aside class="vm-sidebar">
          <div class="panel-head">
            <div>
              <span class="eyebrow">PDM DATACENTER</span>
              <h2>节点列表</h2>
            </div>
            <n-button type="primary" secondary circle @click="openAddNodeModal">
              <template #icon>
                <TheIcon icon="mdi:server-plus" :size="18" />
              </template>
            </n-button>
          </div>

          <n-input v-model:value="filters.nodeKeyword" clearable placeholder="搜索节点 / Remote" class="side-search">
            <template #prefix>
              <TheIcon icon="mdi:magnify" :size="18" />
            </template>
          </n-input>

          <n-spin :show="loading.nodes" class="side-spin">
            <n-empty v-if="!filteredNodes.length" description="暂无节点" />
            <div v-else class="side-list">
              <n-tooltip
                v-for="node in filteredNodes"
                :key="node.value"
                trigger="hover"
                :keep-alive-on-hover="false"
              >
                <template #trigger>
                  <button
                    class="side-list-item"
                    :class="{ active: selectedNode?.value === node.value }"
                    @click="selectNode(node)"
                    @mouseenter="loadNodeTooltipRemark(node)"
                    @contextmenu.prevent.stop="openNodeContextMenu($event, node)"
                  >
                    <span>
                      <strong>{{ node.label }}</strong>
                      <em>{{ nodeStatusText(node) }}</em>
                    </span>
                    <n-tag size="small" round :type="node.status === 'online' ? 'success' : 'warning'">
                      {{ node.vm_count ?? '-' }}
                    </n-tag>
                  </button>
                </template>
                <div class="node-tooltip">
                  <span>IP：{{ nodeAddress(node) }}</span>
                  <span v-if="nodeTooltipRemark(node)">备注：{{ nodeTooltipRemark(node) }}</span>
                </div>
              </n-tooltip>
            </div>
          </n-spin>
          <n-dropdown
            placement="bottom-start"
            trigger="manual"
            :x="nodeMenu.x"
            :y="nodeMenu.y"
            :show="nodeMenu.show"
            :options="nodeMenuOptions"
            @clickoutside="nodeMenu.show = false"
            @select="handleNodeMenuSelect"
          />
        </aside>

        <main class="vm-main">
          <section class="summary-band">
            <article>
              <span class="summary-label">
                <TheIcon icon="mdi:cpu-64-bit" :size="15" />
                CPU 利用率
              </span>
              <strong>{{ formatPercent(selectedNode?.cpu_usage ?? selectedNode?.cpu) }}</strong>
            </article>
            <article>
              <span class="summary-label">
                <TheIcon icon="mdi:chip" :size="15" />
                CPU 总数
              </span>
              <strong>{{ selectedNode?.cpu_total || '-' }} 核</strong>
            </article>
            <article>
              <span class="summary-label">
                <TheIcon icon="mdi:memory" :size="15" />
                内存利用率
              </span>
              <strong>{{ formatPercent(selectedNode?.mem_usage) }}</strong>
            </article>
            <article>
              <span class="summary-label">
                <TheIcon icon="mdi:server" :size="15" />
                内存总量
              </span>
              <strong>{{ formatShortBytes(selectedNode?.maxmem) }}</strong>
            </article>
            <article>
              <span class="summary-label">
                <TheIcon icon="mdi:harddisk" :size="15" />
                磁盘利用率
              </span>
              <strong>{{ formatPercent(selectedNode?.disk_usage) }}</strong>
            </article>
            <article>
              <span class="summary-label">
                <TheIcon icon="mdi:database" :size="15" />
                磁盘总量
              </span>
              <strong>{{ formatShortBytes(selectedNode?.maxdisk) }}</strong>
            </article>
            <article class="summary-ip-card">
              <span class="summary-label">
                <TheIcon icon="mdi:lan" :size="15" />
                节点 IP
              </span>
              <strong>{{ nodeAddress(selectedNode) }}</strong>
            </article>
          </section>

          <section class="content-panel">
            <div class="panel-head">
              <div>
                <span class="eyebrow">{{ selectedNode?.label || '全部节点' }}</span>
                <h2>虚拟机列表</h2>
              </div>
              <div class="vm-list-actions">
                <n-button type="primary" round :disabled="!selectedNode" @click="openCreateModal">
                  <template #icon>
                    <TheIcon icon="mdi:server-plus" :size="18" />
                  </template>
                  添加
                </n-button>
              </div>
            </div>

            <n-data-table
              :key="tableRenderKey"
              remote
              :loading="loading.vms"
              :columns="columns"
              :data="pagedVmList"
              :pagination="false"
              :scroll-x="1440"
              :row-key="(row) => row.id"
              :row-class-name="() => 'vm-table-row'"
              :row-props="vmRowProps"
            />
            <div class="vm-list-footer">
              <div class="status-summary">
                <n-tag type="success" round>运行 {{ vmSummary.running || 0 }}</n-tag>
                <n-tag type="default" round>停止 {{ vmSummary.stopped || 0 }}</n-tag>
              </div>
              <n-pagination
                v-model:page="pagination.page"
                v-model:page-size="pagination.pageSize"
                :item-count="pagination.itemCount"
                :page-sizes="pagination.pageSizes"
                show-size-picker
                @update:page-size="handlePageSizeChange"
              />
            </div>
          </section>
        </main>
      </section>

      <n-modal
        v-model:show="createModal.show"
        preset="card"
        title="添加虚拟机"
        class="vm-create-modal"
        :style="vmCreateModalStyle"
      >
        <n-spin v-if="!createModal.created" :show="createModal.loading">
          <n-form label-placement="left" label-width="110">
            <n-grid :cols="2" :x-gap="14">
              <n-form-item-gi label="操作系统" required>
                <n-cascader
                  v-model:value="createModal.form.os_selection"
                  :options="createModal.osOptions"
                  placeholder="选择系统版本"
                  check-strategy="child"
                  @update:value="handleCreateOsChange"
                />
              </n-form-item-gi>
              <n-form-item-gi label="虚拟机名称">
                <n-input-group>
                  <n-input v-model:value="createModal.form.vm_name" placeholder="请输入虚拟机名称" />
                  <n-button class="random-addon-button" ghost type="primary" @click="refreshCreateVmName">随机</n-button>
                </n-input-group>
              </n-form-item-gi>
              <n-form-item-gi label="存储位置">
                <n-select
                  v-model:value="createModal.form.storage"
                  :options="createStorageOptions"
                  filterable
                  placeholder="选择存储"
                />
              </n-form-item-gi>
              <n-form-item-gi label="CPU 核心">
                <n-input-number v-model:value="createModal.form.cpu_cores" :min="1" :max="64" class="full-width" />
              </n-form-item-gi>
              <n-form-item-gi label="内存 GiB">
                <n-input-number v-model:value="createModal.form.memory_gb" :min="1" :max="256" class="full-width" />
              </n-form-item-gi>
              <n-form-item-gi label="磁盘 GiB">
                <n-input-number
                  v-model:value="createModal.form.disk_gb"
                  :min="10"
                  :max="2000"
                  :step="10"
                  class="full-width"
                />
              </n-form-item-gi>
              <n-form-item-gi label="root 密码">
                <n-input-group>
                  <n-input
                    v-model:value="createModal.form.password"
                    type="password"
                    show-password-on="click"
                    placeholder="请输入 root 密码"
                  />
                  <n-button class="random-addon-button" ghost type="primary" @click="refreshCreatePassword">随机</n-button>
                </n-input-group>
              </n-form-item-gi>
              <n-form-item-gi label="网络模式" required>
                <n-radio-group v-model:value="createModal.form.network.mode">
                  <n-radio-button value="dhcp">DHCP</n-radio-button>
                  <n-radio-button value="static">静态 IP</n-radio-button>
                </n-radio-group>
              </n-form-item-gi>
              <n-form-item-gi label="速率限制">
                <n-input-number
                  v-model:value="createModal.form.network.rate_limit"
                  clearable
                  :min="0"
                  placeholder="MB/s，可为空"
                  class="full-width"
                />
              </n-form-item-gi>
              <n-form-item-gi v-if="createModal.form.network.mode === 'static'" label="IP/掩码" required>
                <n-input v-model:value="createModal.form.network.ip" placeholder="例如 192.168.1.100/24" />
              </n-form-item-gi>
              <n-form-item-gi v-if="createModal.form.network.mode === 'static'" label="网关" required>
                <n-input v-model:value="createModal.form.network.gw" placeholder="例如 192.168.1.1" />
              </n-form-item-gi>
              <n-form-item-gi v-if="createModal.form.network.mode === 'static'" label="DNS" required>
                <n-input v-model:value="createModal.form.network.dns" placeholder="例如 8.8.8.8" />
              </n-form-item-gi>
              <n-form-item-gi v-if="createModal.form.network.mode === 'static'" label="VLAN" required>
                <n-input-number v-model:value="createModal.form.network.vlan" :min="1" :max="4094" class="full-width" />
              </n-form-item-gi>
              <n-form-item-gi label="描述" :span="2">
                <n-input
                  v-model:value="createModal.form.description"
                  type="textarea"
                  placeholder="请输入用途或备注"
                  :autosize="{ minRows: 2, maxRows: 4 }"
                />
              </n-form-item-gi>
            </n-grid>
          </n-form>
        </n-spin>
        <div v-else class="create-result-panel">
          <n-result status="success" title="创建任务已提交" description="请记录这台虚拟机的初始配置，root 密码只对应当前创建的机器。">
            <template #footer>
              <n-descriptions bordered :column="2" size="small">
                <n-descriptions-item label="虚拟机名称">
                  {{ createModal.createdConfig?.vm_name || '-' }}
                </n-descriptions-item>
                <n-descriptions-item label="规格">
                  {{ createModal.createdConfig?.cpu_cores || 0 }} 核 /
                  {{ createModal.createdConfig?.memory_gb || 0 }} GiB /
                  {{ createModal.createdConfig?.disk_gb || 0 }} GiB
                </n-descriptions-item>
                <n-descriptions-item label="存储位置">
                  {{ createModal.createdConfig?.storage || '-' }}
                </n-descriptions-item>
                <n-descriptions-item label="root 密码" :span="2">
                  <code class="password-code">{{ createModal.createdConfig?.password || '-' }}</code>
                  <n-button text type="primary" class="copy-password-button" @click="copyCreatePassword">复制</n-button>
                </n-descriptions-item>
                <n-descriptions-item label="网络模式">
                  {{ createModal.createdConfig?.network?.mode === 'static' ? '静态 IP' : 'DHCP' }}
                </n-descriptions-item>
                <n-descriptions-item label="速率限制">
                  {{
                    createModal.createdConfig?.network?.rate_limit
                      ? `${createModal.createdConfig.network.rate_limit} MB/s`
                      : '不限速'
                  }}
                </n-descriptions-item>
                <n-descriptions-item v-if="createModal.createdConfig?.network?.mode === 'static'" label="IP/VLAN" :span="2">
                  {{ createModal.createdConfig.network.ip || '-' }}
                  <span v-if="createModal.createdConfig.network.vlan"> / VLAN {{ createModal.createdConfig.network.vlan }}</span>
                </n-descriptions-item>
              </n-descriptions>
            </template>
          </n-result>
        </div>
        <template #footer>
          <div class="modal-footer">
            <span>{{ createModal.created ? '任务已在目标节点后台执行，请稍后刷新列表查看。' : '创建时会通过 SSH 在目标节点执行 /root/create-vm.sh。' }}</span>
            <n-space v-if="!createModal.created">
              <n-button @click="createModal.show = false">取消</n-button>
              <n-button type="primary" :loading="createModal.submitting" @click="submitCreateVm">创建</n-button>
            </n-space>
            <n-space v-else>
              <n-button @click="createModal.show = false">关闭</n-button>
              <n-button type="primary" @click="resetCreateModalForNext">继续创建</n-button>
            </n-space>
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="addNodeModal.show"
        preset="card"
        title="添加节点"
        class="vm-add-node-modal"
        :style="vmAddNodeModalStyle"
      >
        <n-steps :current="addNodeModal.step" class="add-node-steps">
          <n-step title="Probe Remote" />
          <n-step title="设置" />
          <n-step title="概要" />
        </n-steps>

        <n-form v-if="addNodeModal.step === 1" label-placement="left" label-width="104">
          <n-form-item label="服务器地址" required>
            <n-input v-model:value="addNodeModal.form.hostname" placeholder="<IP/Hostname>:Port" />
          </n-form-item>
          <n-form-item label="指纹">
            <n-input
              v-model:value="addNodeModal.form.fingerprint"
              type="textarea"
              placeholder="服务器凭证 SHA-256 指纹，自签名证书通常必填"
              :autosize="{ minRows: 2, maxRows: 3 }"
            />
          </n-form-item>
        </n-form>

        <n-form v-else-if="addNodeModal.step === 2" label-placement="left" label-width="128">
          <n-form-item label="远程 ID" required>
            <n-input v-model:value="addNodeModal.form.remote_id" placeholder="例如 HK-PVE" />
          </n-form-item>

          <n-radio-group v-model:value="addNodeModal.form.authMode" class="add-node-auth-mode">
            <n-grid :cols="2" :x-gap="24">
              <n-gi>
                <n-radio value="login">Login and create Token</n-radio>
              </n-gi>
              <n-gi>
                <n-radio value="token">Use existing Token</n-radio>
              </n-gi>
            </n-grid>
          </n-radio-group>

          <n-grid v-if="addNodeModal.form.authMode === 'login'" :cols="2" :x-gap="36">
            <n-gi>
              <n-form-item label="用户" required>
                <n-input v-model:value="addNodeModal.form.username" autocomplete="username" />
              </n-form-item>
              <n-form-item label="密码" required>
                <n-input
                  v-model:value="addNodeModal.form.password"
                  type="password"
                  show-password-on="click"
                  autocomplete="current-password"
                  placeholder="请输入密码"
                />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="领域" required>
                <n-select v-model:value="addNodeModal.form.realm" :options="addNodeRealmOptions" />
              </n-form-item>
              <n-form-item label="API Token Name" required>
                <n-input v-model:value="addNodeModal.form.create_token" />
              </n-form-item>
            </n-gi>
          </n-grid>

          <n-grid v-else :cols="2" :x-gap="36">
            <n-gi>
              <n-form-item label="令牌" required>
                <n-input v-model:value="addNodeModal.form.authid" placeholder="user@realm!token-id" />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="密钥" required>
                <n-input
                  v-model:value="addNodeModal.form.token"
                  type="password"
                  show-password-on="click"
                  autocomplete="off"
                  placeholder="API Token Secret"
                />
              </n-form-item>
            </n-gi>
          </n-grid>
        </n-form>

        <n-descriptions v-else bordered :column="1" size="small">
          <n-descriptions-item label="服务器地址">{{ addNodeModal.form.hostname || '-' }}</n-descriptions-item>
          <n-descriptions-item label="远程 ID">{{ addNodeModal.form.remote_id || '使用 PDM 探测结果' }}</n-descriptions-item>
          <n-descriptions-item label="认证方式">
            {{ addNodeModal.form.authMode === 'login' ? 'Login and create Token' : 'Use existing Token' }}
          </n-descriptions-item>
          <n-descriptions-item label="Auth ID">{{ resolvedAddNodeAuthid || '-' }}</n-descriptions-item>
        </n-descriptions>
        <template #footer>
          <div class="modal-footer">
            <span>{{ addNodeFooterText }}</span>
            <n-space>
              <n-button v-if="addNodeModal.step === 1" @click="addNodeModal.show = false">取消</n-button>
              <n-button v-else @click="addNodeModal.step -= 1">返回</n-button>
              <n-button
                v-if="addNodeModal.step < 3"
                type="primary"
                :loading="addNodeModal.probing"
                @click="nextAddNodeStep"
              >
                下一步
              </n-button>
              <n-button v-else type="primary" :loading="addNodeModal.submitting" @click="submitAddNode">添加</n-button>
            </n-space>
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="editNodeModal.show"
        preset="card"
        title="编辑节点"
        class="vm-edit-node-modal"
        :style="vmEditNodeModalStyle"
      >
        <n-spin :show="editNodeModal.loading">
          <n-form label-placement="left" label-width="104">
            <n-form-item label="节点 IP" required>
              <n-input v-model:value="editNodeModal.form.hostname" placeholder="例如 10.4.10.12" />
            </n-form-item>
            <n-form-item label="备注">
              <n-input
                v-model:value="editNodeModal.form.remark"
                type="textarea"
                placeholder="请输入节点备注"
                :autosize="{ minRows: 5, maxRows: 8 }"
              />
            </n-form-item>
          </n-form>
        </n-spin>
        <template #footer>
          <div class="modal-footer">
            <span>更新 PDM Remote 节点地址，并同步写入对应 PVE 节点备注。</span>
            <n-space>
              <n-button @click="editNodeModal.show = false">取消</n-button>
              <n-button type="primary" :loading="editNodeModal.submitting" @click="submitEditNode">更新</n-button>
            </n-space>
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="migrationModal.show"
        preset="card"
        title="迁移"
        class="vm-migration-modal"
        :style="vmMigrationModalStyle"
      >
        <n-spin :show="migrationModal.loading">
          <n-form label-placement="left" label-width="110">
            <n-grid :cols="1" :x-gap="12">
              <n-form-item-gi label="源远程">
                <n-input :value="migrationModal.row?.remote || '-'" readonly />
              </n-form-item-gi>
              <n-form-item-gi label="虚拟机">
                <n-input :value="migrationModal.row?.name || '-'" readonly />
              </n-form-item-gi>
              <n-form-item-gi label="目标远程">
                <n-select
                  v-model:value="migrationModal.form.target"
                  :options="targetRemoteOptions"
                  filterable
                  @update:value="handleMigrationTargetChange"
                />
              </n-form-item-gi>
              <n-form-item-gi label="Target VMID">
                <n-input-number v-model:value="migrationModal.form.targetVmid" :min="1" class="full-width" />
              </n-form-item-gi>
              <n-form-item-gi label="Target Endpoint">
                <n-select
                  v-model:value="migrationModal.form.targetEndpoint"
                  :options="targetEndpointOptions"
                  filterable
                />
              </n-form-item-gi>
              <n-form-item-gi label="目标存储">
                <n-select v-model:value="migrationModal.form.targetStorage" :options="targetStorageOptions" filterable />
              </n-form-item-gi>
              <n-form-item-gi label="Target Network">
                <n-select v-model:value="migrationModal.form.targetBridge" :options="targetNetworkOptions" filterable />
              </n-form-item-gi>
              <n-form-item-gi label="在线迁移">
                <n-switch v-model:value="migrationModal.form.online" :disabled="migrationModal.row?.status !== 'running'" />
              </n-form-item-gi>
              <n-form-item-gi label="Delete Source">
                <n-switch v-model:value="migrationModal.form.deleteSource" />
              </n-form-item-gi>
              <n-form-item-gi label="带宽限制">
                <n-input-number
                  v-model:value="migrationModal.form.bwlimit"
                  clearable
                  :min="0"
                  placeholder="KiB/s，可为空"
                  class="full-width"
                />
              </n-form-item-gi>
            </n-grid>
          </n-form>
        </n-spin>
        <template #footer>
          <div class="modal-footer">
            <span>存储和网络映射会按 PDM 文档的 FROM:TO 格式自动生成。</span>
            <n-space>
              <n-button @click="migrationModal.show = false">取消</n-button>
              <n-button type="primary" :loading="migrationModal.submitting" @click="submitMigration">迁移</n-button>
            </n-space>
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="taskModal.show"
        preset="card"
        title="迁移任务"
        class="vm-task-modal"
        :style="vmTaskModalStyle"
      >
        <div class="task-status-panel">
          <div>
            <span class="eyebrow">虚拟机</span>
            <h2>{{ taskModal.vmName || '-' }}</h2>
          </div>
          <n-tag round :type="taskStateType">{{ taskStatusText }}</n-tag>
        </div>
        <n-progress
          type="line"
          :percentage="taskFinished ? 100 : 60"
          :processing="!taskFinished"
          :status="taskProgressStatus"
        />
        <div class="task-detail-grid">
          <span>目标远程</span>
          <strong>{{ taskModal.remote || '-' }}</strong>
          <span>开始时间</span>
          <strong>{{ formatTimestamp(taskModal.detail?.starttime) }}</strong>
          <span>结束时间</span>
          <strong>{{ formatTimestamp(taskModal.detail?.endtime) }}</strong>
          <span>任务状态</span>
          <strong>{{ taskModal.detail?.status || taskStatusText }}</strong>
        </div>
        <template #footer>
          <div class="modal-footer">
            <span>{{ taskFinished ? '任务已结束，可以关闭此提示。' : '正在迁移中，请不要重复提交迁移。' }}</span>
            <n-space>
              <n-button :loading="taskModal.loading" @click="fetchTaskStatus({ silent: false })">刷新状态</n-button>
              <n-button v-if="!taskFinished" @click="taskModal.show = false">最小化</n-button>
              <n-button type="primary" @click="closeTaskModal">关闭</n-button>
            </n-space>
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="consoleModal.show"
        preset="card"
        :title="consoleTitle"
        class="vm-console-modal"
        :style="vmConsoleModalStyle"
        :bordered="false"
        @after-leave="resetConsoleModal"
      >
        <NoVncConsole
          v-if="consoleModal.row"
          embedded
          :remote="consoleModal.row.remote"
          :vmid="consoleModal.row.vmid"
          :node="consoleModal.row.node || ''"
          :type="consoleModal.row.type || 'pve-qemu'"
          :title="consoleModal.row.name || `VM ${consoleModal.row.vmid}`"
        />
      </n-modal>

      <n-modal
        v-model:show="monitorModal.show"
        preset="card"
        :title="monitorTitle"
        class="vm-monitor-modal"
        :style="vmMonitorModalStyle"
        :bordered="false"
      >
        <iframe v-if="monitorModal.row" class="monitor-frame" :src="monitorUrl" title="Grafana VM Monitor" />
      </n-modal>

      <button v-if="taskModal.upid && !taskModal.show" class="task-float-button" @click="taskModal.show = true">
        <TheIcon icon="mdi:progress-clock" :size="18" />
        <span>{{ taskModal.vmName || '迁移任务' }}</span>
        <n-tag size="small" round :type="taskStateType">{{ taskStatusText }}</n-tag>
      </button>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, h, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { NButton, NSpace, NTag, useDialog, useMessage } from 'naive-ui'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'
import { getToken } from '@/utils/auth'
import NoVncConsole from './NoVncConsole.vue'

const message = useMessage()
const dialog = useDialog()

const loading = reactive({
  nodes: false,
  vms: false,
})

const filters = reactive({
  nodeKeyword: '',
})

const nodeOptions = ref([])
const selectedNode = ref(null)
const vmList = ref([])
const nodeRemarkCache = reactive({})
const vmSummary = reactive({
  total: 0,
  running: 0,
  stopped: 0,
})

const createModal = reactive({
  show: false,
  created: false,
  loading: false,
  submitting: false,
  sshHost: '',
  storages: [],
  osOptions: [],
  createdConfig: null,
  form: createEmptyVmForm(),
})

const addNodeModal = reactive({
  show: false,
  step: 1,
  probing: false,
  submitting: false,
  realms: [],
  form: createEmptyAddNodeForm(),
})

const editNodeModal = reactive({
  show: false,
  loading: false,
  submitting: false,
  form: {
    remote: '',
    hostname: '',
    originalHostname: '',
    fingerprint: '',
    remark: '',
  },
})

const nodeMenu = reactive({
  show: false,
  x: 0,
  y: 0,
  node: null,
})

const migrationModal = reactive({
  show: false,
  loading: false,
  submitting: false,
  row: null,
  options: {
    source: null,
    remotes: [],
    wizard: {},
  },
  form: {
    target: '',
    targetVmid: null,
    targetStorage: '',
    targetBridge: '',
    targetEndpoint: '',
    deleteSource: true,
    online: false,
    bwlimit: null,
  },
})

const taskModal = reactive({
  show: false,
  loading: false,
  notified: false,
  upid: '',
  remote: '',
  vmName: '',
  detail: null,
})

const consoleModal = reactive({
  show: false,
  row: null,
})

const monitorModal = reactive({
  show: false,
  row: null,
})

const taskTimer = ref(null)
const tableRenderKey = ref(0)
const createOptionsCache = new Map()

const grafanaDashboardUrl = '/api/v1/pve/grafana/proxy/d/zbx-pve-vm-metrics/zabbix-pve-vm-metrics'

const vmCreateModalStyle = {
  width: '760px',
  maxWidth: 'calc(100vw - 32px)',
}

const vmAddNodeModalStyle = {
  width: '760px',
  maxWidth: 'calc(100vw - 32px)',
}

const vmEditNodeModalStyle = {
  width: '560px',
  maxWidth: 'calc(100vw - 32px)',
}

const vmMigrationModalStyle = {
  width: '640px',
  maxWidth: 'calc(100vw - 32px)',
}

const vmTaskModalStyle = {
  width: '420px',
  maxWidth: 'calc(100vw - 32px)',
}

const vmConsoleModalStyle = {
  width: 'min(1120px, calc(100vw - 32px))',
  maxWidth: 'calc(100vw - 32px)',
}

const vmMonitorModalStyle = {
  width: 'min(1240px, calc(100vw - 32px))',
  maxWidth: 'calc(100vw - 32px)',
}

const pagination = reactive({
  page: 1,
  pageSize: 10,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
})

const filteredNodes = computed(() => {
  const keyword = filters.nodeKeyword.trim().toLowerCase()
  if (!keyword) return nodeOptions.value
  return nodeOptions.value.filter((node) =>
    [node.label, node.remote, node.ip, node.address, node.status].some((value) =>
      String(value || '').toLowerCase().includes(keyword)
    )
  )
})

const nodeMenuOptions = computed(() => [
  {
    label: '编辑',
    key: 'edit',
    icon: () => h(TheIcon, { icon: 'material-symbols:edit-outline-rounded', size: 16 }),
  },
  {
    label: '删除',
    key: 'delete',
    icon: () => h(TheIcon, { icon: 'material-symbols:delete-outline-rounded', size: 16 }),
  },
])

const pagedVmList = computed(() => {
  const start = (pagination.page - 1) * pagination.pageSize
  return vmList.value.slice(start, start + pagination.pageSize)
})

const selectedTargetRemote = computed(() =>
  migrationModal.options.remotes.find((remote) => remote.remote === migrationModal.form.target)
)

const targetRemoteOptions = computed(() =>
  migrationModal.options.remotes
    .filter((remote) => remote.remote !== migrationModal.row?.remote)
    .map((remote) => ({ label: remote.remote, value: remote.remote }))
)

const targetStorageOptions = computed(() =>
  (selectedTargetRemote.value?.storages || []).map((storage) => ({ label: storage, value: storage }))
)

const targetNetworkOptions = computed(() =>
  (selectedTargetRemote.value?.networks || []).map((network) => ({ label: network, value: network }))
)

const targetEndpointOptions = computed(() => [
  { label: '自动', value: '' },
  ...(selectedTargetRemote.value?.endpoints || []).map((endpoint) => ({ label: endpoint, value: endpoint })),
])

const monitorTitle = computed(() => {
  if (!monitorModal.row) return '监控'
  return `监控 · ${monitorModal.row.name || `VM ${monitorModal.row.vmid}`}`
})

const monitorUrl = computed(() => {
  if (!monitorModal.row) return ''
  const url = new URL(grafanaDashboardUrl, window.location.origin)
  url.searchParams.set('orgId', '1')
  url.searchParams.set('from', 'now-30d')
  url.searchParams.set('to', 'now')
  url.searchParams.set('timezone', 'browser')
  url.searchParams.set('var-DS_ZABBIX', 'bflbfxqfe1vk0d')
  url.searchParams.set('var-group', 'PVE')
  url.searchParams.set('var-host', monitorModal.row.remote || '')
  url.searchParams.set('var-item_tag', `name: ${monitorModal.row.name || ''}`)
  url.searchParams.set('refresh', '1m')
  const token = getToken()
  if (token) {
    url.searchParams.set('token', token)
  }
  return url.toString()
})

const createStorageOptions = computed(() =>
  createModal.storages.map((storage) => ({
    label: storage.label || storage.value,
    value: storage.value,
  }))
)

const addNodeFooterText = computed(() => {
  if (addNodeModal.step === 1) return '先探测目标 PVE 的 TLS 指纹。'
  if (addNodeModal.step === 2) return '填写 Remote 名称，选择登录创建 Token 或使用已有 API Token。'
  return '确认后会写入 PDM Remote 配置。'
})

const addNodeRealmOptions = computed(() => {
  const realms = addNodeModal.realms.length ? addNodeModal.realms : [{ realm: 'pam', type: 'pam' }]
  return realms.map((item) => {
    const value = item.realm || item.value || item.id
    return {
      label: item.comment ? `${value} - ${item.comment}` : value,
      value,
    }
  })
})

const resolvedAddNodeAuthid = computed(() => {
  if (addNodeModal.form.authMode === 'token') return addNodeModal.form.authid
  if (!addNodeModal.form.username || !addNodeModal.form.realm) return ''
  return `${addNodeModal.form.username}@${addNodeModal.form.realm}`
})

const taskFinished = computed(() => Boolean(taskModal.detail?.finished))

const taskStateType = computed(() => {
  const state = taskModal.detail?.state
  if (state === 'success') return 'success'
  if (state === 'warning') return 'warning'
  if (state === 'error') return 'error'
  return 'info'
})

const taskProgressStatus = computed(() => {
  const state = taskModal.detail?.state
  if (state === 'error') return 'error'
  if (state === 'success' || state === 'warning') return 'success'
  return 'info'
})

const taskStatusText = computed(() => {
  const state = taskModal.detail?.state
  if (state === 'success') return '已完成'
  if (state === 'warning') return '已完成（有警告）'
  if (state === 'error') return '迁移失败'
  return '迁移中'
})

const consoleTitle = computed(() => {
  const row = consoleModal.row
  if (!row) return 'noVNC 控制台'
  return `${row.name || `VM ${row.vmid}`} 控制台`
})

const columns = [
  { title: 'VMID', key: 'vmid', width: 90 },
  {
    title: '虚拟机名称',
    key: 'name',
    minWidth: 300,
    ellipsis: { tooltip: true },
    render(row) {
      return h('div', { class: 'vm-name-cell' }, [
        h('strong', row.name || '-'),
      ])
    },
  },
  {
    title: '状态',
    key: 'status',
    width: 110,
    render(row) {
      const running = row.status === 'running'
      return h(
        NTag,
        { size: 'small', round: true, type: running ? 'success' : 'default' },
        { default: () => (running ? '运行中' : '已停止') }
      )
    },
  },
  {
    title: 'CPU',
    key: 'cpu',
    width: 150,
    render(row) {
      return `${row.cpu || 0}% / ${row.maxcpu || 0} 核`
    },
  },
  {
    title: '内存',
    key: 'mem',
    width: 260,
    render(row) {
      return `${formatBytes(row.mem)} / ${formatBytes(row.maxmem)}`
    },
  },
  {
    title: '磁盘',
    key: 'disk',
    width: 190,
    render(row) {
      const disk = formatBytes(row.disk)
      const maxdisk = formatBytes(row.maxdisk)
      if (disk === '-' && maxdisk !== '-') return maxdisk
      if (disk !== '-' && maxdisk !== '-') return `${disk} / ${maxdisk}`
      return disk
    },
  },
  {
    title: '运行时间',
    key: 'uptime',
    width: 140,
    render(row) {
      return formatUptime(row.uptime)
    },
  },
  {
    title: '备注',
    key: 'remark',
    minWidth: 140,
    ellipsis: { tooltip: true },
    render(row) {
      return row.remark || '暂无备注'
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 360,
    fixed: 'right',
    render(row) {
      return h(
        NSpace,
        { class: 'vm-row-actions', size: 6, wrap: false },
        {
          default: () => [
            actionButton('监控', 'mdi:chart-line', 'info', row, 'vm-button-monitor', openMonitor),
            powerButton(row),
            actionButton('编辑', 'material-symbols:edit-outline-rounded', 'info', row),
            actionButton('删除', 'material-symbols:delete-outline-rounded', 'error', row, '', confirmDeleteVm),
            actionButton('迁移', 'material-symbols:send-rounded', 'warning', row, 'vm-button-send', openMigration),
          ],
        }
      )
    },
  },
]

function vmRowProps(row) {
  return {
    title: '双击打开 noVNC 控制台',
    onDblclick: () => openNoVnc(row),
  }
}

async function openNoVnc(row) {
  if (!row?.remote || !row?.vmid) {
    message.warning('缺少虚拟机远程或 VMID 信息')
    return
  }

  consoleModal.row = { ...row }
  consoleModal.show = true
}

function resetConsoleModal() {
  consoleModal.row = null
}

function openMonitor(row) {
  if (!row?.remote || !row?.name) {
    message.warning('缺少 Grafana 监控所需的节点或虚拟机名称')
    return
  }
  monitorModal.row = { ...row }
  monitorModal.show = true
}

function actionButton(label, icon, type, row, className = '', handler = null) {
  return h(
    NButton,
    {
      class: className,
      size: 'tiny',
      round: true,
      secondary: true,
      type,
      onClick: (event) => {
        event.stopPropagation()
        if (handler) {
          handler(row)
          return
        }
        message.info(`${label}功能后续实现：${row.name}`)
      },
    },
    {
      icon: () => h(TheIcon, { icon, size: 14 }),
      default: () => label,
    }
  )
}

function powerButton(row) {
  const isRunning = row.status === 'running'
  return actionButton(
    isRunning ? '关机' : '开机',
    isRunning ? 'mdi:power' : 'mdi:play-circle-outline',
    isRunning ? 'warning' : 'success',
    row
  )
}

function confirmDeleteVm(row) {
  if (!row?.remote || !row?.vmid) {
    message.warning('缺少虚拟机远程或 VMID 信息')
    return
  }
  if (row.status === 'running') {
    message.warning('请先关机后再删除虚拟机')
    return
  }

  dialog.warning({
    title: '删除虚拟机',
    content: `确认删除 ${row.name || `VM ${row.vmid}`} 吗？该操作不可恢复。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: () => {
      const payload = {
        remote: row.remote,
        vmid: row.vmid,
        type: row.type,
        node: row.node || undefined,
        status: row.status,
      }
      message.success('删除请求已发送，请稍后刷新列表查看')
      api.virtualMachineApi
        .deleteVm(payload)
        .then(() => fetchVms())
        .catch((error) => {
          message.error(error.message || '删除虚拟机失败')
        })
    },
  })
}

function createEmptyVmForm() {
  return {
    region: '',
    storage: '',
    vm_name: generateRandomVmName(),
    description: '',
    os_selection: null,
    os_type: '',
    os_version: '',
    cpu_cores: 2,
    memory_gb: 4,
    disk_gb: 20,
    password: generateRandomPassword(),
    network: {
      mode: 'dhcp',
      ip: '',
      mask: '255.255.255.0',
      dns: '8.8.8.8',
      gw: '',
      vlan: 1,
      rate_limit: 5,
    },
  }
}

function createEmptyAddNodeForm() {
  return {
    hostname: '',
    fingerprint: '',
    authMode: 'login',
    username: 'root',
    realm: 'pam',
    password: '',
    authid: '',
    token: '',
    remote_id: '',
    create_token: 'pdm-admin-HK-datacenter',
    web_url: '',
  }
}

function extractProbeFingerprint(data) {
  if (!data || typeof data !== 'object') return ''
  if (data.fingerprint) return data.fingerprint
  if (data.UntrustedCertificate?.fingerprint) return data.UntrustedCertificate.fingerprint
  if (data.TrustedCertificate?.fingerprint) return data.TrustedCertificate.fingerprint
  return ''
}

function generateRandomVmName() {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
  let randomStr = ''
  for (let i = 0; i < 6; i += 1) {
    randomStr += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return `vm-${randomStr}`
}

function generateRandomPassword() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  let password = ''
  for (let i = 0; i < 12; i += 1) {
    password += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return password
}

function refreshCreateVmName() {
  createModal.form.vm_name = generateRandomVmName()
}

function refreshCreatePassword() {
  createModal.form.password = generateRandomPassword()
}

async function copyCreatePassword() {
  const password = createModal.createdConfig?.password
  if (!password) return
  try {
    await navigator.clipboard.writeText(password)
    message.success('root 密码已复制')
  } catch (error) {
    message.error('复制失败，请手动复制')
  }
}

function normalizeOsOptions(options = []) {
  return options.map((group) => ({
    label: group.label,
    value: group.value,
    children: (group.children || []).map((child) => ({
      label: child.label,
      value: `${group.value}:${child.value}`,
    })),
  }))
}

function handleCreateOsChange(value) {
  if (!value || !String(value).includes(':')) {
    createModal.form.os_type = ''
    createModal.form.os_version = ''
    return
  }
  const [type, version] = String(value).split(':')
  createModal.form.os_type = type
  createModal.form.os_version = version
}

function applyCreateOptions(options) {
  createModal.storages = options?.storages || []
  createModal.osOptions = options?.osOptions || []
  createModal.sshHost = options?.sshHost || ''
  createModal.form.storage = createModal.form.storage || createModal.storages[0]?.value || ''
}

async function preloadCreateOptions(nodeValue, { silent = true } = {}) {
  if (!nodeValue) return null

  const cached = createOptionsCache.get(nodeValue)
  if (cached?.data) return cached.data
  if (cached?.promise) return cached.promise

  const entry = { data: null, error: null, promise: null }
  entry.promise = api.virtualMachineApi
    .createOptions({ node_ip: nodeValue })
    .then((res) => {
      const data = {
        storages: res.data?.storages || [],
        osOptions: normalizeOsOptions(res.data?.os_options || []),
        sshHost: res.data?.ssh_host || '',
      }
      entry.data = data
      entry.error = null
      return data
    })
    .catch((error) => {
      entry.error = error
      if (!silent) throw error
      return null
    })
    .finally(() => {
      entry.promise = null
    })

  createOptionsCache.set(nodeValue, entry)
  return entry.promise
}

async function openCreateModal() {
  if (!selectedNode.value?.value) {
    message.warning('请先选择节点')
    return
  }

  createModal.show = true
  createModal.created = false
  createModal.createdConfig = null
  createModal.sshHost = ''
  createModal.storages = []
  createModal.osOptions = []
  createModal.form = {
    ...createEmptyVmForm(),
    region: selectedNode.value.value,
  }
  const cached = createOptionsCache.get(createModal.form.region)
  if (cached?.data) {
    applyCreateOptions(cached.data)
  } else if (cached?.promise) {
    cached.promise.then((options) => {
      if (createModal.show && createModal.form.region === selectedNode.value?.value && options) {
        applyCreateOptions(options)
      }
    })
  } else {
    message.info('创建选项正在后台加载，请稍后选择系统和存储')
  }
  createModal.loading = false
}

function validateCreateForm() {
  if (!createModal.form.vm_name) return '请输入虚拟机名称'
  if (!createModal.form.os_type || !createModal.form.os_version) return '请选择操作系统'
  if (!createModal.form.storage) return '请选择存储位置'
  if (!createModal.form.password || createModal.form.password.length < 6) return 'root 密码不能少于 6 位'
  if (createModal.form.network.mode === 'static') {
    if (!createModal.form.network.ip) return '请输入静态 IP/掩码'
    if (!createModal.form.network.gw) return '请输入网关'
    if (!createModal.form.network.dns) return '请输入 DNS'
  }
  return ''
}

async function submitCreateVm() {
  const error = validateCreateForm()
  if (error) {
    message.warning(error)
    return
  }

  createModal.submitting = true
  try {
    const res = await api.virtualMachineApi.createVm(createModal.form)
    createModal.createdConfig = JSON.parse(JSON.stringify(res.data?.config || createModal.form))
    createModal.created = true
    message.success(res.msg || '创建任务已提交')
    await refreshNodes()
  } catch (err) {
    message.error(err.message || '创建虚拟机失败')
  } finally {
    createModal.submitting = false
  }
}

function resetCreateModalForNext() {
  const region = createModal.form.region
  const storage = createModal.form.storage
  const osOptions = createModal.osOptions
  const storages = createModal.storages
  const sshHost = createModal.sshHost

  createModal.created = false
  createModal.createdConfig = null
  createModal.osOptions = osOptions
  createModal.storages = storages
  createModal.sshHost = sshHost
  createModal.form = {
    ...createEmptyVmForm(),
    region,
    storage,
  }
}

function openAddNodeModal() {
  addNodeModal.form = createEmptyAddNodeForm()
  addNodeModal.realms = []
  addNodeModal.step = 1
  addNodeModal.show = true
}

function openNodeContextMenu(event, node) {
  nodeMenu.node = node
  nodeMenu.x = event.clientX
  nodeMenu.y = event.clientY
  nodeMenu.show = true
}

function handleNodeMenuSelect(key) {
  const node = nodeMenu.node
  nodeMenu.show = false
  if (!node) return
  if (key === 'edit') {
    openEditNodeModal(node)
    return
  }
  if (key === 'delete') {
    confirmDeleteNode(node)
  }
}

async function openEditNodeModal(node) {
  const remote = node.remote || node.value || ''
  const host = nodeAddress(node) === '-' ? '' : nodeAddress(node)
  editNodeModal.form = {
    remote,
    hostname: host,
    originalHostname: host,
    fingerprint: node.fingerprint || '',
    remark: '',
  }
  editNodeModal.show = true
  if (!remote) return

  editNodeModal.loading = true
  try {
    const res = await api.virtualMachineApi.nodeRemark(remote, {
      host: host || undefined,
    })
    editNodeModal.form.remark = res.data?.remark || ''
  } catch (error) {
    message.error(error.message || '读取节点备注失败')
  } finally {
    editNodeModal.loading = false
  }
}

async function submitEditNode() {
  if (!editNodeModal.form.remote) return
  if (!editNodeModal.form.hostname) {
    message.warning('请输入节点 IP')
    return
  }

  editNodeModal.submitting = true
  try {
    const res = await api.virtualMachineApi.updateNode(editNodeModal.form.remote, {
      hostname: editNodeModal.form.hostname,
      original_hostname: editNodeModal.form.originalHostname,
      fingerprint: editNodeModal.form.fingerprint || undefined,
    })
    await api.virtualMachineApi.updateNodeRemark(editNodeModal.form.remote, {
      remark: editNodeModal.form.remark || '',
      host: editNodeModal.form.hostname || editNodeModal.form.originalHostname || undefined,
    })
    nodeRemarkCache[editNodeModal.form.remote] = { loading: false, remark: editNodeModal.form.remark || '' }
    message.success(res.msg || 'PVE 节点已更新')
    editNodeModal.show = false
    await refreshNodes()
  } catch (error) {
    message.error(error.message || '编辑 PVE 节点失败')
  } finally {
    editNodeModal.submitting = false
  }
}

function confirmDeleteNode(node) {
  const remote = node.remote || node.value
  if (!remote) return
  dialog.warning({
    title: '删除节点',
    content: `确认删除 ${remote} 吗？该操作会删除 PDM Remote 配置。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await api.virtualMachineApi.deleteNode(remote)
        message.success(res.msg || 'PVE 节点已删除')
        if (selectedNode.value?.value === remote) {
          selectedNode.value = null
        }
        await refreshNodes()
      } catch (error) {
        message.error(error.message || '删除 PVE 节点失败')
      }
    },
  })
}

function validateAddNodeForm() {
  if (!addNodeModal.form.hostname) return '请输入服务器地址'
  if (!addNodeModal.form.remote_id) return '请输入远程 ID'
  if (addNodeModal.form.authMode === 'login') {
    if (!addNodeModal.form.username) return '请输入用户'
    if (!addNodeModal.form.password) return '请输入密码'
    if (!addNodeModal.form.realm) return '请选择领域'
    if (!addNodeModal.form.create_token) return '请输入 API Token Name'
    return ''
  }
  if (!addNodeModal.form.authid) return '请输入令牌'
  if (!addNodeModal.form.token) return '请输入密钥'
  return ''
}

async function nextAddNodeStep() {
  if (addNodeModal.step === 1) {
    if (!addNodeModal.form.hostname) {
      message.warning('请输入服务器地址')
      return
    }
    addNodeModal.probing = true
    try {
      const probeRes = await api.virtualMachineApi.probeNode({
        hostname: addNodeModal.form.hostname,
        fingerprint: addNodeModal.form.fingerprint || undefined,
      })
      const probedFingerprint = extractProbeFingerprint(probeRes.data)
      if (probedFingerprint) {
        addNodeModal.form.fingerprint = probedFingerprint
      }
      const realmsRes = await api.virtualMachineApi.nodeRealms({
        hostname: addNodeModal.form.hostname,
        fingerprint: addNodeModal.form.fingerprint || undefined,
      })
      addNodeModal.realms = realmsRes.data || []
      if (
        addNodeModal.realms.length &&
        !addNodeModal.realms.some((item) => (item.realm || item.value || item.id) === addNodeModal.form.realm)
      ) {
        addNodeModal.form.realm = addNodeModal.realms[0].realm || addNodeModal.realms[0].value || 'pam'
      }
      addNodeModal.step = 2
    } catch (error) {
      message.error(error.message || '探测 PVE 节点失败')
    } finally {
      addNodeModal.probing = false
    }
    return
  }

  const error = validateAddNodeForm()
  if (error) {
    message.warning(error)
    return
  }
  addNodeModal.step = 3
}

function buildAddNodePayload() {
  const payload = {
    hostname: addNodeModal.form.hostname,
    fingerprint: addNodeModal.form.fingerprint || undefined,
    remote_id: addNodeModal.form.remote_id,
    web_url: addNodeModal.form.web_url || undefined,
  }
  if (addNodeModal.form.authMode === 'login') {
    return {
      ...payload,
      authid: resolvedAddNodeAuthid.value,
      token: addNodeModal.form.password,
      create_token: addNodeModal.form.create_token,
    }
  }
  return {
    ...payload,
    authid: addNodeModal.form.authid,
    token: addNodeModal.form.token,
  }
}

async function submitAddNode() {
  const error = validateAddNodeForm()
  if (error) {
    message.warning(error)
    return
  }

  addNodeModal.submitting = true
  try {
    const res = await api.virtualMachineApi.addNode(buildAddNodePayload())
    const zabbixSync = res.data?.zabbix_sync
    if (zabbixSync?.enabled && zabbixSync?.synced) {
      message.success(`${res.msg || 'PVE 节点已添加'}，Zabbix 已同步`)
    } else if (zabbixSync?.enabled && !zabbixSync?.synced) {
      message.warning(`${res.msg || 'PVE 节点已添加'}，Zabbix 同步失败：${zabbixSync.message || '请检查后端日志'}`)
    } else {
      message.success(res.msg || 'PVE 节点已添加')
    }
    addNodeModal.show = false
    createOptionsCache.clear()
    await refreshNodes()
  } catch (error) {
    message.error(error.message || '添加 PVE 节点失败')
  } finally {
    addNodeModal.submitting = false
  }
}

function resetMigrationDefaults() {
  const target = selectedTargetRemote.value
  migrationModal.form.targetStorage = target?.storages?.[0] || ''
  migrationModal.form.targetBridge = target?.networks?.[0] || ''
  migrationModal.form.targetEndpoint = ''
}

function handleMigrationTargetChange() {
  resetMigrationDefaults()
}

function clearTaskPolling() {
  if (!taskTimer.value) return
  clearInterval(taskTimer.value)
  taskTimer.value = null
}

function openTaskModal({ upid, remote, vmName }) {
  clearTaskPolling()
  Object.assign(taskModal, {
    show: true,
    loading: false,
    notified: false,
    upid,
    remote,
    vmName,
    detail: { upid, remote, state: 'running', finished: false, success: false },
  })
  fetchTaskStatus({ silent: true })
  taskTimer.value = setInterval(() => fetchTaskStatus({ silent: true }), 5000)
}

function closeTaskModal() {
  taskModal.show = false
  if (!taskFinished.value) return
  Object.assign(taskModal, {
    loading: false,
    notified: false,
    upid: '',
    remote: '',
    vmName: '',
    detail: null,
  })
}

async function fetchTaskStatus({ silent = true } = {}) {
  if (!taskModal.upid) return
  taskModal.loading = true
  try {
    const res = await api.virtualMachineApi.taskStatus({
      upid: taskModal.upid,
      remote: taskModal.remote,
    })
    taskModal.detail = res.data || taskModal.detail
    if (taskModal.detail?.finished) {
      clearTaskPolling()
      if (!taskModal.notified) {
        taskModal.notified = true
        if (taskModal.detail.state === 'error') {
          message.error(`迁移任务失败：${taskModal.detail.status || '请查看 PDM 任务日志'}`)
        } else if (taskModal.detail.state === 'warning') {
          message.warning(`迁移任务完成但有警告：${taskModal.detail.status || ''}`)
          await refreshNodes()
        } else {
          message.success('迁移任务已完成')
          await refreshNodes()
        }
      }
    }
  } catch (error) {
    if (!silent) {
      message.error(error.message || '读取迁移任务状态失败')
    }
  } finally {
    taskModal.loading = false
  }
}

async function openMigration(row) {
  migrationModal.show = true
  migrationModal.loading = true
  migrationModal.row = row
  migrationModal.options = { source: null, remotes: [], wizard: {} }
  Object.assign(migrationModal.form, {
    target: '',
    targetVmid: Number(row.vmid) || null,
    targetStorage: '',
    targetBridge: '',
    targetEndpoint: '',
    deleteSource: true,
    online: row.status === 'running',
    bwlimit: null,
  })

  try {
    const res = await api.virtualMachineApi.migrationOptions({
      remote: row.remote,
      vmid: row.vmid,
      type: row.type,
    })
    migrationModal.options = res.data || { source: null, remotes: [], wizard: {} }
    migrationModal.form.target = targetRemoteOptions.value[0]?.value || ''
    resetMigrationDefaults()
  } catch (error) {
    message.error(error.message || '读取迁移选项失败')
  } finally {
    migrationModal.loading = false
  }
}

async function submitMigration() {
  if (!migrationModal.row) return
  if (!migrationModal.form.target) {
    message.warning('请选择目标远程')
    return
  }
  if (!migrationModal.form.targetStorage) {
    message.warning('请选择目标存储')
    return
  }
  if (!migrationModal.form.targetBridge) {
    message.warning('请选择 Target Network')
    return
  }

  migrationModal.submitting = true
  try {
    const res = await api.virtualMachineApi.migrateVm({
      remote: migrationModal.row.remote,
      vmid: migrationModal.row.vmid,
      type: migrationModal.row.type,
      target: migrationModal.form.target,
      target_vmid: migrationModal.form.targetVmid,
      target_storage: migrationModal.form.targetStorage,
      target_bridge: migrationModal.form.targetBridge,
      target_endpoint: migrationModal.form.targetEndpoint || undefined,
      delete_source: migrationModal.form.deleteSource,
      online: migrationModal.form.online,
      bwlimit: migrationModal.form.bwlimit,
    })
    migrationModal.show = false
    message.success(res.msg || '迁移任务已发起')
    openTaskModal({
      upid: res.data?.upid,
      remote: res.data?.source_remote || migrationModal.row.remote,
      vmName: migrationModal.row.name,
    })
  } catch (error) {
    message.error(error.message || '发起迁移失败')
  } finally {
    migrationModal.submitting = false
  }
}

async function fetchNodes() {
  loading.nodes = true
  try {
    const res = await api.virtualMachineApi.pveNodes()
    nodeOptions.value = res.data || []
    if (!selectedNode.value && nodeOptions.value.length) {
      selectedNode.value = nodeOptions.value[0]
    }
    if (selectedNode.value?.value && !selectedNode.value.error) {
      preloadCreateOptions(selectedNode.value.value)
    }
  } catch (error) {
    nodeOptions.value = []
    message.error(error.message || '读取 PDM 节点列表失败')
  } finally {
    loading.nodes = false
  }
}

async function refreshNodes() {
  await fetchNodes()
  if (selectedNode.value && !nodeOptions.value.some((node) => node.value === selectedNode.value.value)) {
    selectedNode.value = nodeOptions.value[0] || null
  }
  await fetchVms()
}

async function fetchVms() {
  if (!selectedNode.value?.value) {
    vmList.value = []
    Object.assign(vmSummary, { total: 0, running: 0, stopped: 0 })
    pagination.itemCount = 0
    pagination.page = 1
    return
  }

  loading.vms = true
  try {
    const res = await api.virtualMachineApi.pveVms({
      node: selectedNode.value.value,
    })
    vmList.value = res.data?.items || []
    Object.assign(vmSummary, res.data?.summary || { total: 0, running: 0, stopped: 0 })
    syncSelectedNodeSummary(vmSummary)
    pagination.itemCount = vmList.value.length
    pagination.page = 1
    await nextTick()
    tableRenderKey.value += 1
  } catch (error) {
    vmList.value = []
    Object.assign(vmSummary, { total: 0, running: 0, stopped: 0 })
    syncSelectedNodeSummary(vmSummary)
    pagination.itemCount = 0
    message.error(error.message || '读取 PDM 虚拟机失败')
  } finally {
    loading.vms = false
  }
}

function selectNode(node) {
  selectedNode.value = node
  if (node.error) {
    vmList.value = []
    Object.assign(vmSummary, { total: 0, running: 0, stopped: 0 })
    pagination.itemCount = 0
    pagination.page = 1
    return
  }
  preloadCreateOptions(node.value)
  fetchVms()
}

function nodeStatusText(node) {
  if (node.error) {
    return String(node.error).includes('timeout') ? '连接超时' : '连接失败'
  }
  if (!Number(node.node_count || 0)) {
    return node.vm_count == null ? '等待查询' : '已查询'
  }
  return `${node.online_node_count || 0}/${node.node_count || 0} 节点在线`
}

function nodeAddress(node) {
  if (!node) return '-'
  return node.ip || node.address || node.host || node.endpoint || node.remote || node.label || '-'
}

function nodeCacheKey(node) {
  return node?.remote || node?.value || ''
}

function nodeTooltipRemark(node) {
  const key = nodeCacheKey(node)
  const cached = key ? nodeRemarkCache[key] : null
  return String(cached?.remark || '').trim()
}

async function loadNodeTooltipRemark(node) {
  const remote = nodeCacheKey(node)
  if (!remote || nodeRemarkCache[remote]) return
  nodeRemarkCache[remote] = { loading: true, remark: '' }
  try {
    const host = nodeAddress(node) === '-' ? '' : nodeAddress(node)
    const res = await api.virtualMachineApi.nodeRemark(remote, {
      host: host || undefined,
    })
    nodeRemarkCache[remote] = { loading: false, remark: res.data?.remark || '' }
  } catch {
    nodeRemarkCache[remote] = { loading: false, remark: '' }
  }
}

function formatPercent(value) {
  const number = Number(value || 0)
  return `${Number.isInteger(number) ? number : number.toFixed(2).replace(/\.?0+$/, '')}%`
}

function nodeCpuSummary(node) {
  if (!node) return '-'
  const total = Number(node.cpu_total || 0)
  return `${formatPercent(node.cpu_usage ?? node.cpu)} / ${total || '-'} 核`
}

function nodeMemorySummary(node) {
  if (!node) return '-'
  return `${formatPercent(node.mem_usage)} / ${formatBytes(node.maxmem)}`
}

function nodeDiskSummary(node) {
  if (!node) return '-'
  return `${formatPercent(node.disk_usage)} / ${formatBytes(node.maxdisk)}`
}

function syncSelectedNodeSummary(summary) {
  if (!selectedNode.value?.value) return
  const target = nodeOptions.value.find((node) => node.value === selectedNode.value.value)
  if (!target) return
  target.vm_count = summary?.total ?? vmList.value.length
  target.status = (summary?.total ?? 0) > 0 ? 'online' : target.status || 'unknown'
  selectedNode.value = target
}

function handlePageSizeChange(pageSize) {
  pagination.pageSize = pageSize
  pagination.page = 1
}

function formatBytes(value) {
  const bytes = Number(value || 0)
  if (!bytes) return '-'
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
  let size = bytes
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size.toFixed(index === 0 ? 0 : 2)} ${units[index]}`
}

function formatShortBytes(value) {
  const bytes = Number(value || 0)
  if (!bytes) return '-'
  const units = ['B', 'K', 'M', 'G', 'T']
  let size = bytes
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size.toFixed(index === 0 ? 0 : 2)} ${units[index]}`
}

function formatUptime(value) {
  const seconds = Number(value || 0)
  if (!seconds) return '-'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (days) return `${days}天 ${hours}小时`
  if (hours) return `${hours}小时 ${minutes}分钟`
  return `${minutes}分钟`
}

function formatTimestamp(value) {
  const timestamp = Number(value || 0)
  if (!timestamp) return '-'
  return new Date(timestamp * 1000).toLocaleString()
}

onMounted(async () => {
  await fetchNodes()
  await fetchVms()
})

onBeforeUnmount(() => {
  clearTaskPolling()
})
</script>

<style scoped>
.vm-page {
  box-sizing: border-box;
  min-height: 100%;
  background: #f5f7fb;
  padding: 16px;
}

.vm-layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 16px;
}

.vm-sidebar,
.content-panel,
.summary-band article {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.04);
}

.vm-sidebar {
  display: flex;
  height: calc(100vh - 150px);
  max-height: calc(100vh - 150px);
  flex-direction: column;
  overflow: hidden;
  padding: 16px;
}

.vm-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 16px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.panel-head h2 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 18px;
  line-height: 1.25;
}

.eyebrow {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.side-search {
  margin-bottom: 12px;
}

.side-spin {
  min-height: 0;
  flex: 1;
}

.side-spin :deep(.n-spin-container),
.side-spin :deep(.n-spin-content) {
  display: flex;
  min-height: 0;
  height: 100%;
  flex-direction: column;
}

.side-list {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  padding-right: 2px;
  scrollbar-gutter: stable;
}

.side-list-item {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  color: #0f172a;
  cursor: pointer;
  padding: 10px 12px;
  text-align: left;
}

.side-list-item:hover,
.side-list-item.active {
  border-color: #fb5b2f;
  background: #fff7ed;
}

.side-list-item span {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.side-list-item strong,
.side-list-item em {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.side-list-item em {
  color: #64748b;
  font-size: 12px;
  font-style: normal;
}

.node-tooltip {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 260px;
  line-height: 1.45;
  white-space: normal;
}

.summary-band {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr)) minmax(150px, 1.25fr);
  gap: 10px;
}

.summary-band article {
  min-width: 0;
  padding: 14px 16px;
}

.summary-label {
  display: inline-flex !important;
  align-items: center;
  gap: 6px;
  color: #8c939d;
  font-size: 12px;
  line-height: 1.2;
}

.summary-label :deep(svg) {
  color: #9aa3af;
}

.summary-band strong {
  display: block;
  overflow: hidden;
  margin-top: 9px;
  color: #303133;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.2;
  text-overflow: clip;
  white-space: nowrap;
}

.summary-ip-card strong {
  font-size: 16px;
  letter-spacing: 0;
}

.content-panel {
  padding: 16px;
}

.content-panel :deep(.vm-row-actions) {
  display: flex;
  align-items: center;
  flex-flow: row nowrap !important;
  flex-wrap: nowrap;
  gap: 6px !important;
}

.content-panel :deep(.vm-button-monitor) {
  --n-text-color: #4f46e5 !important;
  --n-text-color-hover: #4338ca !important;
  --n-text-color-pressed: #3730a3 !important;
  --n-text-color-focus: #4f46e5 !important;
  --n-color: rgba(99, 102, 241, 0.13) !important;
  --n-color-hover: rgba(99, 102, 241, 0.2) !important;
  --n-color-pressed: rgba(99, 102, 241, 0.26) !important;
  --n-color-focus: rgba(99, 102, 241, 0.2) !important;
  --n-border: 1px solid rgba(99, 102, 241, 0.28) !important;
  --n-border-hover: 1px solid rgba(99, 102, 241, 0.42) !important;
  --n-border-pressed: 1px solid rgba(99, 102, 241, 0.5) !important;
  --n-border-focus: 1px solid rgba(99, 102, 241, 0.42) !important;
}

.content-panel :deep(.vm-button-send) {
  --n-text-color: #d4380d !important;
  --n-text-color-hover: #d4380d !important;
  --n-text-color-pressed: #ad2b08 !important;
  --n-text-color-focus: #d4380d !important;
  --n-color: rgba(250, 140, 22, 0.12) !important;
  --n-color-hover: rgba(250, 140, 22, 0.18) !important;
  --n-color-pressed: rgba(250, 140, 22, 0.24) !important;
  --n-color-focus: rgba(250, 140, 22, 0.18) !important;
  --n-border: 1px solid rgba(250, 140, 22, 0.28) !important;
  --n-border-hover: 1px solid rgba(250, 140, 22, 0.4) !important;
  --n-border-pressed: 1px solid rgba(250, 140, 22, 0.48) !important;
  --n-border-focus: 1px solid rgba(250, 140, 22, 0.4) !important;
}

.monitor-frame {
  width: 100%;
  height: min(82vh, 880px);
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #0b0f19;
}

.vm-list-actions {
  display: flex;
  margin-left: auto;
  justify-content: flex-end;
}

.vm-list-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 12px;
}

.status-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.vm-name-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
}

.vm-name-cell strong,
.vm-name-cell span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.vm-name-cell span {
  color: #64748b;
  font-size: 12px;
}

.vm-migration-modal {
  width: min(760px, calc(100vw - 32px));
}

.vm-task-modal {
  width: min(480px, calc(100vw - 32px));
}

.vm-console-modal {
  overflow: hidden;
}

.vm-console-modal :deep(.n-card__content) {
  padding: 0;
}

.add-node-steps {
  margin-bottom: 22px;
}

.create-result-panel {
  padding: 4px 0 8px;
}

.add-node-hint {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.add-node-auth-mode {
  display: block;
  margin-bottom: 18px;
}

.password-code {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  background: #f1f5f9;
  color: #0f172a;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.copy-password-button {
  margin-left: 8px;
}

.full-width {
  width: 100%;
}

.random-addon-button {
  min-width: 64px;
  --n-border: 1px solid #ff4d22 !important;
  --n-border-hover: 1px solid #ff4d22 !important;
  --n-border-pressed: 1px solid #d83a0f !important;
  --n-border-focus: 1px solid #ff4d22 !important;
  --n-text-color: #ff4d22 !important;
  --n-text-color-hover: #ff4d22 !important;
  --n-text-color-pressed: #d83a0f !important;
  --n-text-color-focus: #ff4d22 !important;
}

.task-status-panel {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.task-status-panel h2 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 18px;
  line-height: 1.3;
}

.task-detail-grid {
  display: grid;
  grid-template-columns: 84px minmax(0, 1fr);
  gap: 8px 12px;
  margin-top: 14px;
}

.task-detail-grid span {
  color: #64748b;
}

.task-detail-grid strong {
  min-width: 0;
  color: #0f172a;
  font-weight: 500;
}

.task-float-button {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 50;
  display: flex;
  max-width: min(420px, calc(100vw - 48px));
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid rgba(251, 91, 47, 0.22);
  border-radius: 999px;
  background: #fff;
  box-shadow: 0 14px 35px rgba(15, 23, 42, 0.18);
  color: #0f172a;
  cursor: pointer;
}

.task-float-button span {
  overflow: hidden;
  max-width: 180px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-float-button:hover {
  border-color: #fb5b2f;
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.modal-footer span {
  color: #64748b;
  font-size: 12px;
}

html.dark .vm-page {
  background: #0f172a;
}

html.dark .vm-sidebar,
html.dark .content-panel,
html.dark .summary-band article,
html.dark .side-list-item {
  border-color: rgba(148, 163, 184, 0.2);
  background: rgba(17, 24, 39, 0.86);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.2);
}

html.dark .side-list-item:hover,
html.dark .side-list-item.active {
  border-color: #fb5b2f;
  background: rgba(124, 45, 18, 0.36);
}

html.dark .panel-head h2,
html.dark .summary-band strong,
html.dark .side-list-item {
  color: #e5e7eb;
}

html.dark .eyebrow,
html.dark .summary-band span,
html.dark .side-list-item em,
html.dark .vm-name-cell span {
  color: #94a3b8;
}

html.dark .content-panel :deep(.n-data-table-th) {
  background: #111827;
  color: #cbd5e1;
}

html.dark .content-panel :deep(.n-data-table-td) {
  color: #e5e7eb;
}

html.dark .content-panel :deep(.vm-table-row .n-data-table-td) {
  border-bottom-color: rgba(148, 163, 184, 0.16);
}

html.dark .content-panel :deep(.vm-table-row:hover .n-data-table-td) {
  background: rgba(30, 41, 59, 0.72);
}

html.dark .task-status-panel h2,
html.dark .task-detail-grid strong {
  color: #e5e7eb;
}

html.dark .password-code {
  background: #1f2937;
  color: #e5e7eb;
}

html.dark .task-float-button {
  border-color: rgba(251, 91, 47, 0.32);
  background: #111827;
  color: #e5e7eb;
}

@media (max-width: 1280px) {
  .summary-band {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .vm-layout {
    grid-template-columns: 1fr;
  }

  .summary-band {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .vm-sidebar {
    min-height: auto;
  }

  .side-list {
    max-height: 360px;
  }
}

@media (max-width: 520px) {
  .summary-band {
    grid-template-columns: 1fr;
  }
}
</style>
