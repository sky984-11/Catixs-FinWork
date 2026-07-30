<template>
  <AppPage :show-footer="false">
    <div class="cabinet-world-page" :class="{ 'is-map-home': viewMode === 'map' }">
      <section v-if="viewMode === 'map'" class="map-panel map-only">
        <div class="map-head">
          <div>
            <span class="eyebrow">Global Cabinet Map</span>
            <h2>机柜节点分布</h2>
          </div>
          <n-space>
            <n-tag round type="info">{{ mapRegionNodes.length }} 个地区</n-tag>
            <n-tag round type="success">{{ cabinets.length }} 个机柜</n-tag>
            <n-tag round type="warning">{{ totalDeviceCount }} 台设备</n-tag>
            <n-button secondary round :loading="loading" @click="loadData">刷新</n-button>
          </n-space>
        </div>

        <n-spin :show="loading" class="map-spin">
          <div ref="mapEl" class="world-map"></div>
        </n-spin>
      </section>

      <section v-else class="region-layout">
        <main class="cabinet-stage">
          <div class="cabinet-content">
            <n-spin :show="deviceLoading" class="rack-spin">
              <div v-if="selectedCabinet" class="rack-board">
                <div class="rack-title">
                  <div>
                    <span class="eyebrow">Rack Diagram</span>
                    <h3>{{ selectedCabinet.name }}</h3>
                  </div>
                  <n-space align="center">
                    <n-tag round :type="rackConflictCount ? 'error' : 'success'">
                      {{ rackConflictCount ? `${rackConflictCount} 个U位冲突` : 'U位正常' }}
                    </n-tag>
                    <n-button type="primary" round @click="openDeviceModal()">新增设备</n-button>
                  </n-space>
                </div>

                <div
                  class="rack-table-shell"
                  :style="{ '--rack-units': rackVisibleUnitCount }"
                  @click="closeRackContextMenu"
                >
                  <table class="rack-table">
                    <thead>
                      <tr>
                        <th class="rack-u-head">U</th>
                        <th>{{ selectedCabinet.name }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in rackTableRows" :key="row.u">
                        <td class="rack-u-cell">{{ row.u }}</td>
                        <td
                          v-if="row.block"
                          class="rack-device-cell"
                          :class="[
                            `device-type-${Number(row.block.device.type)}`,
                            `device-status-${Number(row.block.device.status)}`,
                            { conflict: row.block.conflict },
                          ]"
                          :rowspan="row.block.height"
                          :title="row.block.device.remark || row.block.device.name"
                          @click.stop="openDeviceDetail(row.block.device)"
                          @contextmenu.prevent.stop="openRackContextMenu($event, row.u, row.block.device)"
                        >
                          <div class="rack-device-main">
                            <strong>{{ row.block.device.name || '-' }}</strong>
                            <span>{{ formatDeviceUPosition(row.block.device) }}</span>
                          </div>
                          <i class="rack-status-dot"></i>
                        </td>
                        <td
                          v-else-if="!row.hidden"
                          class="rack-empty-cell"
                          @dblclick="openDeviceModal(null, row.u)"
                          @contextmenu.prevent.stop="openRackContextMenu($event, row.u)"
                        ></td>
                      </tr>
                    </tbody>
                  </table>

                  <div
                    v-if="rackContextMenu.show"
                    class="rack-context-menu"
                    :style="{ left: `${rackContextMenu.x}px`, top: `${rackContextMenu.y}px` }"
                    @click.stop
                  >
                    <button v-if="!rackContextMenu.device" @click="handleRackMenuAdd">新增设备</button>
                    <button v-if="rackContextMenu.device" @click="handleRackMenuEdit">编辑设备</button>
                    <button v-if="rackContextMenu.device" @click="handleRackMenuClone">克隆设备</button>
                    <button v-if="rackContextMenu.device && !isFourNodeAttributes(rackContextMenu.device.attributes)" @click="handleRackMenuConsole">
                      {{ deviceConsoleLabel(rackContextMenu.device) }}
                    </button>
                    <button v-if="rackContextMenu.device" @click="handleRackMenuDelete">删除设备</button>
                  </div>
                </div>

                <n-empty
                  v-if="!rackBlocks.length"
                  class="rack-empty"
                  description="当前机柜暂无配置 U 位的设备"
                />
              </div>
              <n-empty v-else description="请选择一个机柜" />
            </n-spin>

            <aside class="cabinet-side">
              <div class="stage-head">
                <div>
                  <span class="eyebrow">{{ selectedRegion?.code || '-' }}</span>
                  <h2>{{ selectedRegionLabel || '请选择地区' }}</h2>
                  <div class="region-meta">
                    <span>{{ selectedRegionNode?.locations.length || 0 }} 机房</span>
                    <span>{{ selectedRegionNode?.cabinetCount || 0 }} 机柜</span>
                    <span>{{ selectedRegionNode?.deviceCount || 0 }} 设备</span>
                    <span>{{ rackUsedUnits }}/{{ rackVisibleUnitCount }}U</span>
                  </div>
                </div>
                <n-space class="stage-actions" align="center">
                  <n-button type="primary" round @click="openCabinetModal()">新增机柜</n-button>
                  <n-button secondary round @click="backToMap">返回地图</n-button>
                </n-space>
              </div>

              <div class="cabinet-list">
                <div class="side-section-title">
                  <span>Cabinets</span>
                  <strong>{{ selectedCabinets.length }}</strong>
                </div>
                <article
                  v-for="cabinet in selectedCabinets"
                  :key="cabinet.id"
                  class="cabinet-card"
                  :class="{ active: selectedCabinetId === cabinet.id }"
                  @click="selectCabinet(cabinet.id)"
                >
                  <i v-if="selectedCabinetId === cabinet.id" class="cabinet-active-mark"></i>
                  <div class="cabinet-card-head">
                    <strong>{{ cabinet.name }}</strong>
                    <span class="cabinet-card-actions">
                      <button title="编辑机柜" @click.stop="openCabinetModal(cabinet)">编辑</button>
                      <button title="删除机柜" @click.stop="deleteCabinet(cabinet)">删除</button>
                    </span>
                  </div>
                  <span class="cabinet-location">{{ cabinetLocationName(cabinet) }}</span>
                  <div class="cabinet-card-metrics">
                    <em>{{ cabinetDeviceCount(cabinet.id) }} 台设备</em>
                    <em>{{ formatCabinetURange(cabinet) }}</em>
                  </div>
                  <div class="cabinet-card-foot">
                    <span>{{ formatCabinetSize(cabinet) }}</span>
                    <span>{{ formatCabinetPower(cabinet) }}</span>
                  </div>
                </article>
              </div>
            </aside>
          </div>
        </main>
      </section>

      <n-drawer v-model:show="deviceDrawer.show" :width="deviceDrawerWidth">
        <n-drawer-content :title="deviceDrawer.row?.name || '设备详情'" closable>
          <template v-if="deviceDrawer.row">
            <n-descriptions bordered :column="1" label-placement="left" size="small">
              <n-descriptions-item label="设备类型">{{ getDeviceType(deviceDrawer.row.type) }}</n-descriptions-item>
              <n-descriptions-item label="设备状态">{{ getDeviceStatus(deviceDrawer.row.status) }}</n-descriptions-item>
              <n-descriptions-item label="所在位置">
                {{ deviceDrawer.row.region_name || '-' }} / {{ deviceDrawer.row.location_name || '-' }} /
                {{ deviceDrawer.row.cabinet_name || selectedCabinet?.name || '-' }}
              </n-descriptions-item>
              <n-descriptions-item label="U位">{{ formatDeviceUPosition(deviceDrawer.row) }}</n-descriptions-item>
              <n-descriptions-item label="厂商型号">
                {{ [deviceDrawer.row.brand, deviceDrawer.row.model].filter(Boolean).join(' / ') || '-' }}
              </n-descriptions-item>
              <n-descriptions-item label="序列号">{{ deviceDrawer.row.serial_no || '-' }}</n-descriptions-item>
              <n-descriptions-item label="备注">{{ deviceDrawer.row.remark || '-' }}</n-descriptions-item>
            </n-descriptions>

            <n-space class="detail-actions">
              <n-button
                type="primary"
                secondary
                :loading="vncModal.loading"
                @click="openDeviceConsole(deviceDrawer.row)"
              >
                {{ deviceConsoleButtonLabel(deviceDrawer.row) }}
              </n-button>
              <n-popconfirm
                v-for="action in devicePowerActions"
                :key="action.value"
                :positive-button-props="{ type: action.type }"
                @positive-click="controlDevicePower(deviceDrawer.row, action.value)"
              >
                <template #trigger>
                  <n-button
                    secondary
                    :type="action.type"
                    :disabled="!hasDevicePowerConfig(deviceDrawer.row)"
                    :loading="powerLoadingKey === devicePowerKey(deviceDrawer.row, action.value)"
                  >
                    {{ action.label }}
                  </n-button>
                </template>
                确认对 {{ deviceDrawer.row.name || '该设备' }} 执行{{ action.label }}操作？
              </n-popconfirm>
            </n-space>

            <div v-if="!isFourNodeDrawerDevice && (deviceIpmiDetail.ipmi_host || deviceIpmiDetail.ipmi_user)" class="detail-section">
              <div class="detail-section-head">
                <h3>IPMI 信息</h3>
                <n-button
                  size="small"
                  secondary
                  :disabled="!hasDevicePowerConfig(deviceDrawer.row)"
                  :loading="ipmiLogLoadingKey === deviceIpmiLogKey(deviceDrawer.row)"
                  @click="loadDeviceIpmiLogs(deviceDrawer.row)"
                >
                  查看日志
                </n-button>
              </div>
              <div class="attribute-grid">
                <div v-if="deviceIpmiDetail.ipmi_host" class="attribute-item">
                  <span>IPMI地址</span>
                  <strong>{{ deviceIpmiDetail.ipmi_host }}</strong>
                </div>
                <div v-if="deviceIpmiDetail.ipmi_user" class="attribute-item">
                  <span>IPMI用户</span>
                  <strong>{{ deviceIpmiDetail.ipmi_user }}</strong>
                </div>
                <div v-if="deviceIpmiDetail.ipmi_password" class="attribute-item">
                  <span>IPMI密码</span>
                  <strong>{{ deviceIpmiDetail.ipmi_password }}</strong>
                </div>
              </div>
              <div v-if="ipmiLogTarget === deviceIpmiLogKey(deviceDrawer.row)" class="ipmi-log-panel">
                <n-empty v-if="!ipmiLogs.length && !ipmiLogLoadingKey" description="暂无日志" />
                <div v-else class="ipmi-log-list">
                  <article v-for="item in ipmiLogs" :key="`${item.service}-${item.id}-${item.created}-${item.message}`" class="ipmi-log-row">
                    <div>
                      <strong>{{ item.message || item.message_id || '-' }}</strong>
                      <span>{{ [item.service, item.entry_type, item.sensor].filter(Boolean).join(' / ') || '-' }}</span>
                    </div>
                    <em :class="severityClass(item.severity)">{{ item.severity || '-' }}</em>
                    <time>{{ item.created || '-' }}</time>
                  </article>
                </div>
              </div>
            </div>

            <div v-if="!isFourNodeDrawerDevice" class="detail-section">
              <h3>设备配置</h3>
              <n-empty v-if="!attributeRows.length" description="暂无配置" />
              <div v-else class="attribute-grid">
                <div v-for="item in attributeRows" :key="item.key" class="attribute-item">
                  <span>{{ item.key }}</span>
                  <strong>{{ item.value || '-' }}</strong>
                </div>
              </div>
            </div>

            <div v-if="fourNodeDetailNodes.length" class="detail-section">
              <h3>四节点服务器</h3>
              <div class="node-detail-grid">
                <article v-for="node in fourNodeDetailNodes" :key="node.name" class="node-detail-card">
                  <div class="node-detail-head">
                    <strong>{{ node.device_name || node.name }}</strong>
                    <n-space size="small">
                      <n-button
                        size="tiny"
                        secondary
                        type="primary"
                        :disabled="!hasNodeVncConfig(node)"
                        :loading="vncModal.loading"
                        @click="openDeviceVnc(deviceDrawer.row, node)"
                      >
                        VNC
                      </n-button>
                      <n-popconfirm
                        v-for="action in devicePowerActions"
                        :key="`${node.name}-${action.value}`"
                        :positive-button-props="{ type: action.type }"
                        @positive-click="controlDevicePower(deviceDrawer.row, action.value, node)"
                      >
                        <template #trigger>
                          <n-button
                            size="tiny"
                            secondary
                            :type="action.type"
                            :disabled="!hasNodePowerConfig(node)"
                            :loading="powerLoadingKey === devicePowerKey(deviceDrawer.row, action.value, node)"
                          >
                            {{ action.shortLabel }}
                          </n-button>
                        </template>
                        确认对 {{ node.device_name || node.name }} 执行{{ action.label }}操作？
                      </n-popconfirm>
                      <n-button
                        size="tiny"
                        secondary
                        :disabled="!hasNodePowerConfig(node)"
                        :loading="ipmiLogLoadingKey === deviceIpmiLogKey(deviceDrawer.row, node)"
                        @click="loadDeviceIpmiLogs(deviceDrawer.row, node)"
                      >
                        日志
                      </n-button>
                    </n-space>
                  </div>
                  <div class="node-detail-fields">
                    <span><b>状态</b><em>{{ getDeviceStatus(node.status) }}</em></span>
                    <span><b>序列号</b><em>{{ node.serial_no || '-' }}</em></span>
                    <span class="wide"><b>CPU</b><em>{{ formatFourNodeCpu(node) }}</em></span>
                    <span><b>内存</b><em>{{ node.memory || '-' }}</em></span>
                    <span><b>磁盘</b><em>{{ node.disk || '-' }}</em></span>
                    <span><b>IPMI地址</b><em>{{ node.ipmi_host || '-' }}</em></span>
                    <span><b>IPMI用户</b><em>{{ node.ipmi_user || '-' }}</em></span>
                    <span><b>IPMI密码</b><em>{{ node.ipmi_password || '-' }}</em></span>
                    <span class="wide"><b>备注</b><em>{{ node.remark || '-' }}</em></span>
                  </div>
                  <div v-if="ipmiLogTarget === deviceIpmiLogKey(deviceDrawer.row, node)" class="ipmi-log-panel node-log-panel">
                    <n-empty v-if="!ipmiLogs.length && !ipmiLogLoadingKey" description="暂无日志" />
                    <div v-else class="ipmi-log-list">
                      <article v-for="item in ipmiLogs" :key="`${item.service}-${item.id}-${item.created}-${item.message}`" class="ipmi-log-row">
                        <div>
                          <strong>{{ item.message || item.message_id || '-' }}</strong>
                          <span>{{ [item.service, item.entry_type, item.sensor].filter(Boolean).join(' / ') || '-' }}</span>
                        </div>
                        <em :class="severityClass(item.severity)">{{ item.severity || '-' }}</em>
                        <time>{{ item.created || '-' }}</time>
                      </article>
                    </div>
                  </div>
                </article>
              </div>
            </div>
          </template>
        </n-drawer-content>
      </n-drawer>

      <n-modal
        v-model:show="vncModal.show"
        class="device-vnc-modal"
        style="width: min(1180px, 94vw)"
        @after-leave="resetDeviceVnc"
      >
        <div class="device-vnc-shell">
          <DeviceVncConsole
            v-if="vncModal.wsUrl"
            :title="vncModal.deviceName"
            subtitle="设备 VNC 控制台"
            :ws-url="vncModal.wsUrl"
            :password="vncModal.password"
            :target="vncModal.target"
            :profile="vncModal.profile"
            @close="closeDeviceVnc"
          />
        </div>
      </n-modal>

      <n-modal v-model:show="cabinetModal.show" preset="dialog" :title="cabinetModalTitle" style="width: 760px">
        <n-form label-placement="top">
          <n-form-item label="机房位置" required>
            <n-select
              v-model:value="cabinetModal.form.location_id"
              :options="selectedRegionLocationOptions"
              placeholder="选择机房"
            />
          </n-form-item>
          <n-grid :cols="2" :x-gap="12">
            <n-form-item-gi label="机柜名称" required>
              <n-input v-model:value="cabinetModal.form.name" placeholder="例如 A01" />
            </n-form-item-gi>
            <n-form-item-gi label="租用起始 U">
              <n-input-number v-model:value="cabinetModal.form.rental_start_u" :min="1" />
            </n-form-item-gi>
            <n-form-item-gi label="租用结束 U">
              <n-input-number v-model:value="cabinetModal.form.rental_end_u" :min="cabinetModal.form.rental_start_u || 1" />
            </n-form-item-gi>
            <n-form-item-gi label="租用容量">
              <n-input :value="`${cabinetRentalUnitCount}U`" readonly />
            </n-form-item-gi>
            <n-form-item-gi label="宽度 mm">
              <n-input-number v-model:value="cabinetModal.form.width_mm" :min="0" />
            </n-form-item-gi>
            <n-form-item-gi label="深度 mm">
              <n-input-number v-model:value="cabinetModal.form.depth_mm" :min="0" />
            </n-form-item-gi>
            <n-form-item-gi label="电力分配 kW">
              <n-input-number v-model:value="cabinetModal.form.power_allocation_kw" :min="0" :precision="1" />
            </n-form-item-gi>
            <n-form-item-gi label="超额电力计费">
              <n-input v-model:value="cabinetModal.form.power_overage_rate" placeholder="例如 RM180/0.1kW" />
            </n-form-item-gi>
            <n-form-item-gi label="PDU插槽类型">
              <n-input v-model:value="cabinetModal.form.pdu_socket_types" placeholder="例如 C13, C19" />
            </n-form-item-gi>
            <n-form-item-gi label="托盘">
              <n-input v-model:value="cabinetModal.form.rack_tray" placeholder="例如 2x rack tray" />
            </n-form-item-gi>
          </n-grid>
          <n-form-item label="rPDU配置">
            <n-input
              v-model:value="cabinetModal.form.pdu_spec"
              type="textarea"
              placeholder="例如 2x 24 ways SPN rPDU c/w 20 C13 & 4 C19 Power Socket"
            />
          </n-form-item>
          <n-form-item label="电源插座">
            <n-input
              v-model:value="cabinetModal.form.power_socket_spec"
              type="textarea"
              placeholder="例如 2x 32A single phase 220V-240V IEC 60309 commando socket"
            />
          </n-form-item>
          <n-form-item label="备注">
            <n-input v-model:value="cabinetModal.form.remark" type="textarea" />
          </n-form-item>
        </n-form>
        <template #action>
          <n-button @click="cabinetModal.show = false">取消</n-button>
          <n-button type="primary" :loading="cabinetModal.submitting" @click="submitCabinet">保存</n-button>
        </template>
      </n-modal>

      <n-modal v-model:show="deviceModal.show" preset="dialog" :title="deviceModalTitle" style="width: 760px">
        <n-form label-placement="top">
          <n-grid :cols="2" :x-gap="12">
            <n-form-item-gi label="设备名称" required>
              <n-input v-model:value="deviceModal.form.name" placeholder="例如 Server-01" />
            </n-form-item-gi>
            <n-form-item-gi label="设备类型">
              <n-select v-model:value="deviceModal.form.type" :options="deviceTypeOptions" />
            </n-form-item-gi>
            <n-form-item-gi label="设备形态">
              <n-select
                v-model:value="deviceModal.form.form_factor"
                :options="deviceFormFactorOptions"
                @update:value="handleDeviceFormFactorChange"
              />
            </n-form-item-gi>
            <n-form-item-gi label="占用 U 数">
              <n-input-number v-model:value="deviceModal.form.u_height" :min="1" :max="rackVisibleUnitCount" />
            </n-form-item-gi>
            <n-form-item-gi label="起始 U 位">
              <n-input-number v-model:value="deviceModal.form.u_position" :min="rackStartU" :max="rackEndU" />
            </n-form-item-gi>
            <n-form-item-gi label="状态">
              <n-select v-model:value="deviceModal.form.status" :options="deviceStatusOptions" />
            </n-form-item-gi>
            <n-form-item-gi label="厂商">
              <n-select
                v-model:value="deviceModal.form.brand"
                clearable
                filterable
                tag
                :options="platformOptions"
                placeholder="选择厂商"
                @update:value="handlePlatformChange"
              />
            </n-form-item-gi>
            <n-form-item-gi label="型号">
              <n-select
                v-model:value="deviceModal.form.model"
                clearable
                filterable
                tag
                :options="modelOptions"
                placeholder="选择型号"
                @update:value="handleModelChange"
              />
            </n-form-item-gi>
            <n-form-item-gi label="序列号">
              <n-input v-model:value="deviceModal.form.serial_no" />
            </n-form-item-gi>
          </n-grid>
          <n-form-item label="备注">
            <n-input v-model:value="deviceModal.form.remark" type="textarea" />
          </n-form-item>

          <div v-if="deviceModal.form.form_factor !== 'four_node'" class="device-ipmi-editor">
            <div class="four-node-head">
              <div>
                <span class="eyebrow">IPMI / Redfish</span>
                <h3>IPMI 信息</h3>
              </div>
              <n-button
                size="small"
                secondary
                type="primary"
                :loading="redfishLoading"
                :disabled="!deviceModal.form.ipmi_host"
                @click="probeDeviceRedfish"
              >
                Redfish 获取配置
              </n-button>
            </div>
            <n-grid :cols="3" :x-gap="8">
              <n-form-item-gi label="IPMI 地址">
                <n-input v-model:value="deviceModal.form.ipmi_host" placeholder="例如 192.168.1.10" />
              </n-form-item-gi>
              <n-form-item-gi label="IPMI 用户">
                <n-input v-model:value="deviceModal.form.ipmi_user" placeholder="ADMIN" />
              </n-form-item-gi>
              <n-form-item-gi label="IPMI 密码">
                <n-input v-model:value="deviceModal.form.ipmi_password" type="password" show-password-on="click" />
              </n-form-item-gi>
            </n-grid>
          </div>

          <div v-if="deviceModal.form.form_factor !== 'four_node'" class="device-attribute-editor">
            <div class="four-node-head">
              <div>
                <span class="eyebrow">Device Config</span>
                <h3>设备配置</h3>
              </div>
              <n-button size="small" secondary @click="addDeviceAttribute">添加配置</n-button>
            </div>
            <n-empty v-if="!deviceModal.form.attributeList.length" description="暂无配置" />
            <div v-else class="attribute-editor-list">
              <div v-for="(attr, index) in deviceModal.form.attributeList" :key="index" class="attribute-editor-row">
                <n-input v-model:value="attr.key" size="small" placeholder="配置项，例如 IPMI密码" />
                <n-input
                  v-model:value="attr.value"
                  size="small"
                  :type="isSecretAttributeKey(attr.key) ? 'password' : 'text'"
                  placeholder="配置值"
                  show-password-on="click"
                />
                <n-button size="small" quaternary type="error" @click="removeDeviceAttribute(index)">删除</n-button>
              </div>
            </div>
          </div>

          <div v-if="deviceModal.form.form_factor === 'four_node'" class="four-node-editor">
            <div class="four-node-head">
              <div>
                <span class="eyebrow">Four Node Server</span>
                <h3>四节点配置</h3>
              </div>
              <n-tag round type="info">2U / N1-N4</n-tag>
            </div>
            <div class="four-node-grid">
              <article v-for="node in deviceModal.form.nodeList" :key="node.name" class="four-node-card">
                <strong>{{ node.name }}</strong>
                <div class="four-node-fields">
                  <n-input v-model:value="node.device_name" size="small" placeholder="设备名称" />
                  <n-input v-model:value="node.serial_no" size="small" placeholder="设备序号" />
                  <n-select v-model:value="node.status" size="small" :options="deviceStatusOptions" placeholder="节点状态" />
                  <n-input-number v-model:value="node.cpu_count" size="small" placeholder="CPU数量" :min="0" />
                  <n-input v-model:value="node.cpu_model" size="small" placeholder="CPU型号" />
                  <n-input-number v-model:value="node.cpu_cores" size="small" placeholder="CPU核心数" :min="0" />
                  <n-input v-model:value="node.memory" size="small" placeholder="内存" />
                  <n-input v-model:value="node.disk" size="small" placeholder="磁盘" />
                  <n-input v-model:value="node.ipmi_host" size="small" placeholder="IPMI 地址" />
                  <n-input v-model:value="node.ipmi_user" size="small" placeholder="IPMI User" />
                  <n-input v-model:value="node.ipmi_password" size="small" placeholder="IPMI Password" type="password" show-password-on="click" />
                  <n-input v-model:value="node.remark" size="small" placeholder="备注" />
                </div>
              </article>
            </div>
          </div>
        </n-form>
        <template #action>
          <n-button @click="deviceModal.show = false">取消</n-button>
          <n-button type="primary" :loading="deviceModal.submitting" @click="submitDevice">保存</n-button>
        </template>
      </n-modal>

    </div>
  </AppPage>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import { translateRegion } from '@/utils/location-i18n'
import DeviceVncConsole from './DeviceVncConsole.vue'

defineOptions({ name: 'AssetCabinetWorldMap' })

const loading = ref(false)
const deviceLoading = ref(false)
const redfishLoading = ref(false)
const powerLoadingKey = ref('')
const ipmiLogLoadingKey = ref('')
const ipmiLogTarget = ref('')
const ipmiLogs = ref([])
const regions = ref([])
const locations = ref([])
const cabinets = ref([])
const rackDevices = ref([])
const devicePlatformTree = ref([])
const viewMode = ref('map')
const selectedRegionId = ref(null)
const selectedCabinetId = ref(null)
const mapEl = ref(null)
const route = useRoute()
const router = useRouter()
const deviceDrawer = reactive({ show: false, row: null })
const vncModal = reactive({
  show: false,
  loading: false,
  title: '设备 VNC 控制台',
  deviceName: '',
  wsUrl: '',
  password: '',
  target: '',
  profile: 'default',
})
const cabinetModal = reactive({
  show: false,
  submitting: false,
  form: createCabinetForm(),
})
const deviceModal = reactive({
  show: false,
  submitting: false,
  form: createDeviceForm(),
})
const rackContextMenu = reactive({
  show: false,
  x: 0,
  y: 0,
  u: null,
  device: null,
})
let mapInstance = null
let mapTileLayer = null
let mapMarkerLayer = null

const deviceTypeOptions = [
  { label: '服务器', value: 0 },
  { label: '交换机', value: 1 },
  { label: '路由器', value: 2 },
  { label: '防火墙', value: 3 },
  { label: 'PDU', value: 4 },
  { label: '配件', value: 5 },
  { label: '其他', value: 99 },
]

const deviceStatusOptions = [
  { label: '空闲', value: 0 },
  { label: '故障', value: 3 },
  { label: '使用', value: 1 },
  { label: '下架', value: 4 },
]

const devicePowerActions = [
  { value: 'on', label: '开机', shortLabel: '开机', type: 'success' },
  { value: 'off', label: '关机', shortLabel: '关机', type: 'warning' },
  { value: 'restart', label: '重启', shortLabel: '重启', type: 'error' },
]

const legacyDeviceStatusLabels = {
  2: '故障',
  5: '下架',
}

const deviceFormFactorOptions = [
  { label: '标准设备', value: 'standard' },
  { label: '四节点服务器', value: 'four_node' },
]

const knownRegionPoints = [
  { keys: ['HK', 'HONG KONG', '香港'], lat: 22.3193, lng: 114.1694 },
  { keys: ['SG', 'SINGAPORE', '新加坡'], lat: 1.3521, lng: 103.8198 },
  { keys: ['JP', 'JAPAN', '东京', '日本'], lat: 35.6762, lng: 139.6503 },
  { keys: ['TW', 'TAIWAN', '台湾'], lat: 25.033, lng: 121.5654 },
  { keys: ['SH', 'SHA', 'SHANGHAI', 'SHANG HAI', '上海'], lat: 31.2304, lng: 121.4737 },
  { keys: ['SZ', 'SHENZHEN', '深圳'], lat: 22.5431, lng: 114.0579 },
  { keys: ['DE', 'GERMANY', '德国', 'FRANKFURT'], lat: 50.1109, lng: 8.6821 },
  { keys: ['LON', 'LONDON', 'UK', 'GB', '英国', '伦敦'], lat: 51.5072, lng: -0.1276 },
  { keys: ['LA', 'LA3', 'LOS ANGELES', 'US', 'USA', '美国'], lat: 34.0522, lng: -118.2437 },
  { keys: ['NY', 'NY2', 'NEW YORK', 'NEWYORK', '纽约'], lat: 40.7128, lng: -74.006 },
]

const regionNodes = computed(() =>
  regions.value
    .map((region, index) => {
      const regionLocations = locations.value.filter((item) => item.region_id === region.id && item.type === 1)
      const regionCabinets = cabinets.value.filter((cabinet) =>
        regionLocations.some((location) => location.id === cabinet.location_id)
      )
      return {
        region,
        locations: regionLocations,
        cabinets: regionCabinets,
        cabinetCount: regionCabinets.length,
        deviceCount: regionCabinets.reduce((total, cabinet) => total + cabinetDeviceCount(cabinet.id), 0),
        point: regionPoint(region, index),
      }
    })
)
const mapRegionNodes = computed(() => regionNodes.value.filter((node) => node.cabinetCount > 0))
const totalDeviceCount = computed(() =>
  cabinets.value.reduce((total, cabinet) => total + cabinetDeviceCount(cabinet.id), 0)
)

const selectedRegion = computed(() => regions.value.find((item) => item.id === selectedRegionId.value) || null)
const selectedRegionLabel = computed(() => translateRegion(selectedRegion.value) || selectedRegion.value?.name || '')
const selectedRegionNode = computed(
  () => regionNodes.value.find((node) => node.region.id === selectedRegionId.value) || null
)
const selectedCabinets = computed(() => selectedRegionNode.value?.cabinets || [])
const selectedCabinet = computed(() => cabinets.value.find((item) => item.id === selectedCabinetId.value) || null)
const selectedRegionLocationOptions = computed(() =>
  (selectedRegionNode.value?.locations || []).map((location) => ({
    label: location.name,
    value: location.id,
  }))
)
const platformOptions = computed(() =>
  devicePlatformTree.value.map((platform) => ({
    label: platform.label,
    value: platform.value,
  }))
)
const modelOptions = computed(() => {
  const platform = devicePlatformTree.value.find((item) => item.value === deviceModal.form.brand)
  return (platform?.models || []).map((model) => ({
    label: model.label,
    value: model.value,
  }))
})

const cabinetStoredCapacity = computed(() => Math.max(Number(selectedCabinet.value?.capacity_u) || 42, 1))
const rackStartU = computed(() => Math.max(Number(selectedCabinet.value?.rental_start_u) || 1, 1))
const rackEndU = computed(() => {
  const fallbackEnd = rackStartU.value + cabinetStoredCapacity.value - 1
  const end = Number(selectedCabinet.value?.rental_end_u) || fallbackEnd
  return Math.max(end, rackStartU.value)
})
const rackVisibleUnitCount = computed(() => Math.max(rackEndU.value - rackStartU.value + 1, 1))
const rackCapacity = computed(() => rackVisibleUnitCount.value)
const rackPlacedDevices = computed(() =>
  rackDevices.value
    .map((device) => {
      const start = Number(device.u_position || 0)
      const height = Math.max(Number(device.u_height || 1), 1)
      const end = start + height - 1
      if (!start || start < rackStartU.value || end > rackEndU.value) return null
      return {
        ...device,
        start,
        end,
        height,
      }
    })
    .filter(Boolean)
)
const rackUnits = computed(() => {
  const units = []
  for (let no = rackEndU.value; no >= rackStartU.value; no -= 1) {
    const occupants = rackPlacedDevices.value.filter((item) => item.start <= no && item.end >= no)
    units.push({ no, occupied: Boolean(occupants.length), conflict: occupants.length > 1 })
  }
  return units
})
const rackConflictCount = computed(() => rackUnits.value.filter((unit) => unit.conflict).length)
const rackUsedUnits = computed(() => rackUnits.value.filter((unit) => unit.occupied).length)
const rackBlocks = computed(() =>
  rackPlacedDevices.value.map((device) => ({
    device,
    start: device.start,
    end: device.end,
    height: device.height,
    conflict: rackPlacedDevices.value.some(
      (other) => other.id !== device.id && other.start <= device.end && other.end >= device.start
    ),
  }))
)
const rackTableRows = computed(() => {
  const rows = []
  for (let u = rackEndU.value; u >= rackStartU.value; u -= 1) {
    const block = rackBlocks.value.find((item) => item.end === u)
    const covered = rackBlocks.value.some((item) => item.start <= u && item.end >= u)
    rows.push({
      u,
      block,
      hidden: covered && !block,
    })
  }
  return rows
})
const structuredAttributeKeys = new Set([
  'nodes',
  'form_factor',
  'node_count',
  '节点数量',
  '设备形态',
  'ipmi_host',
  'ipmi_user',
  'ipmi_password',
  'IPMI地址',
  'IPMI用户',
  'IPMI密码',
])
const vncAttributeKeys = ['vnc_host', 'vnc_address', 'VNC地址', 'VNC主机', 'ipmi_host', 'IPMI地址']
const webConsoleUrlKeys = [
  'ilo_console_url',
  'bmc_console_url',
  'web_console_url',
  'iLO控制台地址',
  'ILO控制台地址',
  'BMC控制台地址',
  'WEB控制台地址',
  'Web控制台地址',
  'remote_console_url',
  '远程控制台地址',
]
const attributeRows = computed(() =>
  attributesToList(deviceDrawer.row?.attributes).filter((item) => !structuredAttributeKeys.has(item.key))
)
const deviceIpmiDetail = computed(() => extractIpmiInfo(deviceDrawer.row?.attributes || {}))
const cabinetModalTitle = computed(() => (cabinetModal.form.id ? '编辑机柜' : '新增机柜'))
const cabinetRentalUnitCount = computed(() => {
  const start = Number(cabinetModal.form.rental_start_u || 0)
  const end = Number(cabinetModal.form.rental_end_u || 0)
  return Math.max(end - start + 1, 0)
})
const deviceModalTitle = computed(() => (deviceModal.form.id ? '编辑设备' : '新增设备'))
const isFourNodeDrawerDevice = computed(() => isFourNodeAttributes(deviceDrawer.row?.attributes))
const fourNodeDetailNodes = computed(() =>
  isFourNodeDrawerDevice.value ? normalizeFourNodeList(deviceDrawer.row?.attributes?.nodes || []) : []
)
const deviceDrawerWidth = computed(() => (fourNodeDetailNodes.value.length ? 'min(920px, 92vw)' : 620))

function isFourNodeAttributes(attributes) {
  return attributes?.form_factor === 'four_node' || attributes?.设备形态 === '四节点服务器'
}

function createCabinetForm() {
  return {
    id: null,
    location_id: null,
    name: '',
    code: '',
    row: '',
    column: '',
    capacity_u: 42,
    rental_start_u: 1,
    rental_end_u: 42,
    width_mm: 600,
    depth_mm: 1000,
    power_allocation_kw: 0,
    power_overage_rate: '',
    pdu_spec: '',
    power_socket_spec: '',
    rack_tray: '',
    pdu_socket_types: '',
    remark: '',
    status: true,
  }
}

function createDeviceForm() {
  return {
    cabinet_id: null,
    asset_no: '',
    name: '',
    type: 0,
    brand: '',
    model: '',
    serial_no: '',
    u_position: null,
    u_height: 1,
    status: 0,
    ipmi_host: '',
    ipmi_user: '',
    ipmi_password: '',
    purchase_date: null,
    warranty_expire: null,
    attributes: {},
    attributeList: [],
    remark: '',
    form_factor: 'standard',
    nodeList: createFourNodeList(),
  }
}

function createFourNodeList() {
  return ['N1', 'N2', 'N3', 'N4'].map((name, index) => ({
    name,
    device_name: '',
    serial_no: '',
    status: 0,
    cpu_count: null,
    cpu_model: '',
    cpu_cores: null,
    memory: '',
    disk: '',
    ipmi_host: '',
    ipmi_user: '',
    ipmi_password: '',
    remark: '',
    legacy_ip: '',
    legacy_cpu: '',
    sort: index + 1,
  }))
}

function normalizeFourNodeList(nodes) {
  const source = Array.isArray(nodes) ? nodes : []
  return createFourNodeList().map((fallback) => {
    const matched = source.find((item) => item?.name === fallback.name) || {}
    return {
      ...fallback,
      device_name: String(matched.device_name || matched.deviceName || matched.name || ''),
      serial_no: String(matched.serial_no || matched.serialNo || ''),
      status: normalizeDeviceStatusValue(matched.status, fallback.status),
      cpu_count: matched.cpu_count ?? matched.cpuCount ?? null,
      cpu_model: String(matched.cpu_model || matched.cpuModel || matched.cpu || ''),
      cpu_cores: matched.cpu_cores ?? matched.cpuCores ?? null,
      memory: String(matched.memory || ''),
      disk: String(matched.disk || ''),
      ipmi_host: String(matched.ipmi_host || matched.ipmiHost || ''),
      ipmi_user: String(matched.ipmi_user || matched.ipmiUser || ''),
      ipmi_password: String(matched.ipmi_password || matched.ipmiPassword || ''),
      remark: String(matched.remark || ''),
      legacy_ip: String(matched.ip || ''),
      legacy_cpu: String(matched.cpu || ''),
      sort: Number(matched.sort || fallback.sort),
    }
  })
}

function formatFourNodeCpu(node) {
  return [node.cpu_count ? `${node.cpu_count}颗` : '', node.cpu_model, node.cpu_cores ? `${node.cpu_cores}核` : '']
    .filter(Boolean)
    .join(' / ') || '-'
}

function normalizeDeviceStatusValue(value, fallback = 0) {
  const status = Number(value)
  return deviceStatusOptions.some((item) => item.value === status) ? status : fallback
}

function aggregateFourNodeStatus(nodes) {
  const statuses = normalizeFourNodeList(nodes).map((node) => normalizeDeviceStatusValue(node.status, 0))
  if (!statuses.length) return 0
  if (statuses.every((status) => status === 4)) return 4
  if (statuses.some((status) => status === 3)) return 3
  if (statuses.some((status) => status === 1)) return 1
  if (statuses.some((status) => status === 0)) return 0
  return statuses[0] ?? 0
}

function serializeFourNodeList(nodes) {
  return normalizeFourNodeList(nodes).map((node) => ({
    name: node.name,
    device_name: String(node.device_name || '').trim(),
    serial_no: String(node.serial_no || '').trim(),
    status: normalizeDeviceStatusValue(node.status, 0),
    cpu_count: node.cpu_count === null || node.cpu_count === '' ? null : Number(node.cpu_count),
    cpu_model: String(node.cpu_model || '').trim(),
    cpu_cores: node.cpu_cores === null || node.cpu_cores === '' ? null : Number(node.cpu_cores),
    memory: String(node.memory || '').trim(),
    disk: String(node.disk || '').trim(),
    ipmi_host: String(node.ipmi_host || '').trim(),
    ipmi_user: String(node.ipmi_user || '').trim(),
    ipmi_password: String(node.ipmi_password || '').trim(),
    remark: String(node.remark || '').trim(),
  }))
}

function createAttributeList(attributes) {
  if (!attributes || typeof attributes !== 'object') return []
  return Object.entries(attributes)
    .filter(([key]) => !structuredAttributeKeys.has(key))
    .map(([key, value]) => ({
      key,
      value: value === null || value === undefined ? '' : String(value),
    }))
}

function normalizeDevicePlatformTree(value) {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => {
      const label = String(item?.label || item?.name || item?.value || '').trim()
      const itemValue = String(item?.value || item?.name || label).trim()
      if (!label || !itemValue) return null
      const models = Array.isArray(item.models)
        ? item.models
            .map((model) => {
              const modelLabel = String(model?.label || model?.name || model?.value || '').trim()
              const modelValue = String(model?.value || model?.name || modelLabel).trim()
              if (!modelLabel || !modelValue) return null
              return { ...model, label: modelLabel, value: modelValue }
            })
            .filter(Boolean)
        : []
      return { ...item, label, value: itemValue, models }
    })
    .filter(Boolean)
}

function buildAttributesFromList(list) {
  return (Array.isArray(list) ? list : []).reduce((result, item) => {
    const key = String(item?.key || '').trim()
    if (!key || structuredAttributeKeys.has(key)) return result
    result[key] = item?.value === null || item?.value === undefined ? '' : String(item.value).trim()
    return result
  }, {})
}

function extractIpmiInfo(attributes = {}) {
  return {
    ipmi_host: String(attributes.ipmi_host || attributes.IPMI地址 || '').trim(),
    ipmi_user: String(attributes.ipmi_user || attributes.IPMI用户 || '').trim(),
    ipmi_password: String(attributes.ipmi_password || attributes.IPMI密码 || '').trim(),
  }
}

function applyIpmiInfoToAttributes(attributes = {}) {
  const result = { ...attributes }
  result.ipmi_host = String(deviceModal.form.ipmi_host || '').trim()
  result.ipmi_user = String(deviceModal.form.ipmi_user || '').trim()
  if (deviceModal.form.ipmi_password) {
    result.ipmi_password = String(deviceModal.form.ipmi_password || '').trim()
  }
  return result
}

function mergeAttributeRows(values = {}) {
  const current = new Map((deviceModal.form.attributeList || []).map((item) => [String(item.key || '').trim(), item]))
  Object.entries(values || {}).forEach(([key, value]) => {
    const attrKey = String(key || '').trim()
    if (!attrKey || structuredAttributeKeys.has(attrKey) || value === null || value === undefined || value === '') return
    if (current.has(attrKey)) {
      current.get(attrKey).value = String(value)
    } else {
      const item = { key: attrKey, value: String(value) }
      deviceModal.form.attributeList.push(item)
      current.set(attrKey, item)
    }
  })
}

function applyRedfishResult(data = {}) {
  mergeAttributeRows(data.attributes || {})
}

async function probeDeviceRedfish() {
  if (!deviceModal.form.ipmi_host) {
    window.$message?.warning('请先填写 IPMI 地址')
    return
  }
  redfishLoading.value = true
  try {
    const res = await api.assetApi.redfishProbeDevice({
      ipmi_host: deviceModal.form.ipmi_host,
      ipmi_user: deviceModal.form.ipmi_user,
      ipmi_password: deviceModal.form.ipmi_password,
    })
    applyRedfishResult(res.data || {})
    window.$message?.success('Redfish 信息已回填')
  } catch (error) {
    window.$message?.error(error.message || 'Redfish 获取失败')
  } finally {
    redfishLoading.value = false
  }
}

function addDeviceAttribute() {
  deviceModal.form.attributeList.push({ key: '', value: '' })
}

function removeDeviceAttribute(index) {
  deviceModal.form.attributeList.splice(index, 1)
}

function isSecretAttributeKey(key) {
  const normalizedKey = String(key || '').toLowerCase()
  return ['password', '密码', 'secret', 'token', 'ipmi'].some((item) => normalizedKey.includes(item.toLowerCase()))
}

function regionPoint(region, index) {
  const text = `${region.code || ''} ${region.name || ''} ${region.remark || ''}`.toUpperCase()
  const matched = knownRegionPoints.find((item) => item.keys.some((key) => text.includes(key.toUpperCase())))
  if (matched) return { lat: matched.lat, lng: matched.lng }
  return { lat: 38 - Math.floor(index / 8) * 12, lng: -145 + (index % 8) * 42 }
}

async function ensureMap() {
  if (viewMode.value !== 'map') return
  await nextTick()
  await new Promise((resolve) => requestAnimationFrame(resolve))
  if (!mapEl.value) return
  if (mapInstance && mapInstance.getContainer() !== mapEl.value) {
    destroyMap()
  }
  if (!mapInstance) {
    mapInstance = L.map(mapEl.value, {
      attributionControl: true,
      maxBoundsViscosity: 0.8,
      minZoom: 2,
      worldCopyJump: true,
      zoomControl: true,
    }).setView([24, 18], 2)
    mapInstance.setMaxBounds([
      [-85, -180],
      [85, 180],
    ])
    mapTileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 8,
      minZoom: 2,
    }).addTo(mapInstance)
    mapMarkerLayer = L.layerGroup().addTo(mapInstance)
    mapInstance.on('zoomend', () => renderMapMarkers())
  }
  mapInstance.invalidateSize()
  renderMapMarkers(true)
  setTimeout(() => {
    mapInstance?.invalidateSize()
    renderMapMarkers()
  }, 120)
}

function destroyMap() {
  mapMarkerLayer?.clearLayers()
  mapTileLayer?.remove()
  mapInstance?.remove()
  mapMarkerLayer = null
  mapTileLayer = null
  mapInstance = null
}

function layoutMapMarkerNodes(nodes) {
  if (!mapInstance) return []
  const zoom = mapInstance.getZoom()
  const placed = []
  const minGap = 52
  return nodes.map((node) => {
    const basePoint = mapInstance.project([node.point.lat, node.point.lng], zoom)
    let markerPoint = basePoint
    for (let attempt = 0; attempt < 18; attempt += 1) {
      const distanceOk = placed.every((point) => markerPoint.distanceTo(point) >= minGap)
      if (distanceOk) break
      const angle = (Math.PI * 2 * attempt) / 8
      const radius = 32 + Math.floor(attempt / 8) * 24
      markerPoint = L.point(basePoint.x + Math.cos(angle) * radius, basePoint.y + Math.sin(angle) * radius)
    }
    placed.push(markerPoint)
    const visualPoint = mapInstance.unproject(markerPoint, zoom)
    return {
      ...node,
      visualPoint: {
        lat: visualPoint.lat,
        lng: visualPoint.lng,
      },
    }
  })
}

function renderMapMarkers(fitBounds = false) {
  if (!mapInstance || !mapMarkerLayer) return
  mapMarkerLayer.clearLayers()
  const bounds = []
  mapRegionNodes.value.forEach((node) => {
    bounds.push([node.point.lat, node.point.lng])
  })
  if (fitBounds && bounds.length) {
    mapInstance.fitBounds(bounds, { maxZoom: 4, padding: [80, 80] })
  }
  layoutMapMarkerNodes(mapRegionNodes.value).forEach((node) => {
    const marker = L.marker([node.visualPoint.lat, node.visualPoint.lng], {
      icon: L.divIcon({
        className: 'cabinet-map-marker',
        html: mapMarkerHtml(node),
        iconAnchor: [22, 22],
        iconSize: [44, 44],
      }),
      title: node.region.name || node.region.code || '',
    })
    marker.on('click', () => navigateToRegion(node.region.id))
    marker.addTo(mapMarkerLayer)
  })
}

function mapMarkerHtml(node) {
  const label = node.region.code || translateRegion(node.region) || node.region.name || ''
  const count = node.cabinetCount || 0
  return `
    <div class="cabinet-marker-wrap">
      <span class="cabinet-marker-count">${count}</span>
      <span class="cabinet-marker-label">${label}</span>
    </div>
  `
}

async function loadData() {
  loading.value = true
  try {
    const [regionRes, locationRes, cabinetRes, brandRes] = await Promise.all([
      api.assetApi.regions({ page_size: 1000 }),
      api.assetApi.locations({ page_size: 1000 }),
      api.assetApi.cabinets({ page_size: 1000 }),
      api.assetApi.deviceBrands(),
    ])
    regions.value = regionRes.data || []
    locations.value = locationRes.data || []
    cabinets.value = cabinetRes.data || []
    devicePlatformTree.value = normalizeDevicePlatformTree(brandRes.data || [])
    applyRouteSelection()
  } finally {
    loading.value = false
  }
}

function handlePlatformChange(value) {
  const normalizedValue = String(value || '').trim()
  if (normalizedValue && !devicePlatformTree.value.some((item) => item.value === normalizedValue)) {
    devicePlatformTree.value.push({
      label: normalizedValue,
      value: normalizedValue,
      name: normalizedValue,
      models: [],
      _local: true,
    })
  }
  const platform = devicePlatformTree.value.find((item) => item.value === normalizedValue)
  if (!platform?.models?.some((model) => model.value === deviceModal.form.model)) {
    deviceModal.form.model = ''
  }
}

function handleModelChange(value) {
  const normalizedValue = String(value || '').trim()
  const brandValue = String(deviceModal.form.brand || '').trim()
  if (!normalizedValue || !brandValue) return
  const platform = ensureLocalPlatformOption(brandValue)
  if (!platform.models.some((model) => model.value === normalizedValue)) {
    platform.models.push({
      label: normalizedValue,
      value: normalizedValue,
      name: normalizedValue,
      _local: true,
    })
  }
}

function ensureLocalPlatformOption(value) {
  const normalizedValue = String(value || '').trim()
  let platform = devicePlatformTree.value.find((item) => item.value === normalizedValue)
  if (!platform && normalizedValue) {
    platform = {
      label: normalizedValue,
      value: normalizedValue,
      name: normalizedValue,
      models: [],
      _local: true,
    }
    devicePlatformTree.value.push(platform)
  }
  if (platform && !Array.isArray(platform.models)) platform.models = []
  return platform
}

async function ensureDeviceBrandAndModel() {
  const brandName = String(deviceModal.form.brand || '').trim()
  const modelName = String(deviceModal.form.model || '').trim()
  if (!brandName) return

  let platform = devicePlatformTree.value.find((item) => item.value === brandName || item.name === brandName)
  if (!platform?.id) {
    const res = await api.assetApi.createDeviceBrand({ name: brandName, status: true })
    devicePlatformTree.value = normalizeDevicePlatformTree(res.data || [])
    platform = devicePlatformTree.value.find((item) => item.value === brandName || item.name === brandName)
  }

  if (!modelName || !platform?.id) return
  const existedModel = (platform.models || []).find((model) => model.value === modelName || model.name === modelName)
  if (!existedModel?.id) {
    const res = await api.assetApi.createDeviceModel({ brand_id: platform.id, name: modelName, status: true })
    devicePlatformTree.value = normalizeDevicePlatformTree(res.data || [])
  }
}

function numberQueryValue(value) {
  const source = Array.isArray(value) ? value[0] : value
  const parsed = Number(source)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

function regionIdByCabinetId(cabinetId) {
  const cabinet = cabinets.value.find((item) => item.id === Number(cabinetId))
  const location = locations.value.find((item) => item.id === cabinet?.location_id)
  return location?.region_id || null
}

function firstCabinetIdInRegion(regionId) {
  const node = regionNodes.value.find((item) => item.region.id === Number(regionId))
  return node?.cabinets?.[0]?.id || null
}

function routeToMap() {
  router.push({ path: route.path, query: {} })
}

function routeToCabinet(regionId, cabinetId = null) {
  if (!regionId) return
  const query = {
    region_id: String(regionId),
  }
  if (cabinetId) query.cabinet_id = String(cabinetId)
  router.push({ path: route.path, query })
}

function applyRouteSelection() {
  const queryRegionId = numberQueryValue(route.query.region_id)
  const queryCabinetId = numberQueryValue(route.query.cabinet_id)
  if (!queryRegionId && !queryCabinetId) {
    viewMode.value = 'map'
    rackDevices.value = []
    deviceDrawer.show = false
    ensureMap()
    return
  }

  const nextRegionId = queryRegionId || regionIdByCabinetId(queryCabinetId)
  if (!nextRegionId || !regionNodes.value.some((node) => node.region.id === nextRegionId)) {
    routeToMap()
    return
  }

  selectedRegionId.value = nextRegionId
  const nextCabinetId = selectedCabinets.value.some((cabinet) => cabinet.id === queryCabinetId)
    ? queryCabinetId
    : firstCabinetIdInRegion(nextRegionId)
  selectedCabinetId.value = nextCabinetId
  viewMode.value = 'region'
  if (nextCabinetId) loadCabinetDevices()
  else rackDevices.value = []
}

function navigateToRegion(regionId) {
  routeToCabinet(regionId, firstCabinetIdInRegion(regionId))
}

function backToMap() {
  routeToMap()
}

function selectCabinet(cabinetId) {
  const regionId = selectedRegionId.value || regionIdByCabinetId(cabinetId)
  if (!regionId) return
  routeToCabinet(regionId, cabinetId)
}

async function loadCabinetDevices() {
  if (!selectedCabinetId.value) {
    rackDevices.value = []
    return
  }
  deviceLoading.value = true
  try {
    const res = await api.assetApi.devices({
      page: 1,
      page_size: 1000,
      cabinet_id: selectedCabinetId.value,
    })
    rackDevices.value = res.data || []
    updateCabinetDeviceCount(selectedCabinetId.value, rackDevices.value.length)
  } finally {
    deviceLoading.value = false
  }
}

function openCabinetModal(cabinet = null) {
  if (!selectedRegionId.value) {
    window.$message?.warning('请先选择地区')
    return
  }
  if (!selectedRegionLocationOptions.value.length) {
    window.$message?.warning('当前地区暂无机房，请先到 POP点管理 创建机房')
    return
  }
  if (cabinet) {
    const rentalStart = Number(cabinet.rental_start_u || 1)
    const fallbackEnd = rentalStart + Number(cabinet.capacity_u || 42) - 1
    cabinetModal.form = {
      ...createCabinetForm(),
      ...cabinet,
      code: cabinet.code || cabinet.name || '',
      capacity_u: Number(cabinet.capacity_u || 42),
      rental_start_u: rentalStart,
      rental_end_u: Number(cabinet.rental_end_u || fallbackEnd),
      width_mm: Number(cabinet.width_mm || 600),
      depth_mm: Number(cabinet.depth_mm || 1000),
      power_allocation_kw: Number(cabinet.power_allocation_kw || 0),
    }
  } else {
    cabinetModal.form = createCabinetForm()
  }
  if (!cabinet) cabinetModal.form.location_id = selectedRegionLocationOptions.value[0]?.value || null
  cabinetModal.show = true
}

async function submitCabinet() {
  const name = String(cabinetModal.form.name || '').trim()
  const rentalStart = Number(cabinetModal.form.rental_start_u || 1)
  const rentalEnd = Number(cabinetModal.form.rental_end_u || rentalStart)
  const capacity = rentalEnd - rentalStart + 1
  if (!selectedRegionId.value) {
    window.$message?.warning('请先选择地区')
    return
  }
  if (!cabinetModal.form.location_id || !name) {
    window.$message?.warning('请选择机房并填写机柜名称')
    return
  }
  if (rentalStart < 1 || rentalEnd < rentalStart) {
    window.$message?.warning('请填写有效的租用 U 位范围，例如 20-25U')
    return
  }
  cabinetModal.submitting = true
  try {
    const payload = {
      ...cabinetModal.form,
      name,
      code: String(cabinetModal.form.code || name).trim(),
      row: '',
      column: '',
      capacity_u: capacity,
      rental_start_u: rentalStart,
      rental_end_u: rentalEnd,
      width_mm: Math.max(Number(cabinetModal.form.width_mm || 0), 0),
      depth_mm: Math.max(Number(cabinetModal.form.depth_mm || 0), 0),
      power_allocation_kw: Math.max(Number(cabinetModal.form.power_allocation_kw || 0), 0),
      power_overage_rate: String(cabinetModal.form.power_overage_rate || '').trim(),
      pdu_spec: String(cabinetModal.form.pdu_spec || '').trim(),
      power_socket_spec: String(cabinetModal.form.power_socket_spec || '').trim(),
      rack_tray: String(cabinetModal.form.rack_tray || '').trim(),
      pdu_socket_types: String(cabinetModal.form.pdu_socket_types || '').trim(),
    }
    const submit = payload.id ? api.assetApi.updateCabinet : api.assetApi.createCabinet
    const res = await submit(payload)
    cabinetModal.show = false
    await loadData()
    routeToCabinet(selectedRegionId.value, res.data?.id || selectedCabinetId.value)
    window.$message?.success(payload.id ? '机柜已更新' : '机柜已新增')
  } finally {
    cabinetModal.submitting = false
  }
}

async function deleteCabinet(cabinet) {
  if (!cabinet?.id) return
  const count = cabinetDeviceCount(cabinet.id)
  if (count > 0) {
    window.$message?.warning('机柜下存在设备，不能删除')
    return
  }
  if (!window.confirm(`确认删除机柜 ${cabinet.name || ''}？`)) return
  await api.assetApi.deleteCabinet({ cabinet_id: cabinet.id })
  if (selectedCabinetId.value === cabinet.id) {
    const nextCabinetId = selectedCabinets.value.find((item) => item.id !== cabinet.id)?.id || null
    if (nextCabinetId) routeToCabinet(selectedRegionId.value, nextCabinetId)
    else routeToCabinet(selectedRegionId.value)
  }
  await loadData()
  window.$message?.success('机柜已删除')
}

function openDeviceModal(device = null, uPosition = null) {
  if (!selectedCabinetId.value) {
    window.$message?.warning('请先选择机柜')
    return
  }
  const isFourNodeDevice = isFourNodeAttributes(device?.attributes)
  const ipmiInfo = extractIpmiInfo(device?.attributes || {})
  deviceModal.form = device
    ? {
        ...createDeviceForm(),
        ...device,
        ...ipmiInfo,
        form_factor: isFourNodeDevice ? 'four_node' : 'standard',
        attributeList: createAttributeList(device.attributes),
        nodeList: isFourNodeDevice ? normalizeFourNodeList(device.attributes?.nodes || []) : createFourNodeList(),
      }
    : createDeviceForm()
  deviceModal.form.cabinet_id = selectedCabinetId.value
  if (!device) {
    deviceModal.form.u_position = uPosition || firstAvailableU()
  }
  deviceModal.show = true
}

function handleDeviceFormFactorChange(value) {
  if (value === 'four_node') {
    deviceModal.form.type = 0
    deviceModal.form.u_height = Math.min(2, rackVisibleUnitCount.value)
    deviceModal.form.nodeList = normalizeFourNodeList(deviceModal.form.nodeList)
  } else if (!deviceModal.form.u_height || deviceModal.form.u_height < 1) {
    deviceModal.form.u_height = 1
  }
}

function firstAvailableU() {
  return firstAvailableUForHeight(1)
}

function firstAvailableUForHeight(height = 1) {
  const normalizedHeight = Math.max(Number(height || 1), 1)
  for (let no = rackStartU.value; no <= rackEndU.value; no += 1) {
    if (no + normalizedHeight - 1 > rackEndU.value) return null
    if (!hasRackOverlap(no, normalizedHeight)) return no
  }
  return null
}

function hasRackOverlap(start, height, ignoredDeviceId = null) {
  const end = start + height - 1
  return rackPlacedDevices.value.some(
    (device) => device.id !== ignoredDeviceId && device.start <= end && device.end >= start
  )
}

async function submitDevice() {
  const name = String(deviceModal.form.name || '').trim()
  const start = Number(deviceModal.form.u_position || 0)
  const isFourNode = deviceModal.form.form_factor === 'four_node'
  const height = isFourNode ? 2 : Number(deviceModal.form.u_height || 1)
  if (!deviceModal.form.cabinet_id || !name) {
    window.$message?.warning('请选择机柜并填写设备名称')
    return
  }
  if (!start || start < rackStartU.value || height < 1 || start + height - 1 > rackEndU.value) {
    window.$message?.warning(`请填写有效的 U 位和占用 U 数，当前机柜可用范围为 ${rackStartU.value}-${rackEndU.value}U`)
    return
  }
  if (hasRackOverlap(start, height, deviceModal.form.id || null)) {
    window.$message?.warning('该 U 位已被占用，请调整起始 U 位或占用 U 数')
    return
  }

  deviceModal.submitting = true
  try {
    await ensureDeviceBrandAndModel()
    const attributes = {
      ...(isFourNode ? {} : buildAttributesFromList(deviceModal.form.attributeList)),
      form_factor: isFourNode ? 'four_node' : 'standard',
      设备形态: isFourNode ? '四节点服务器' : '标准设备',
    }
    if (!isFourNode) Object.assign(attributes, applyIpmiInfoToAttributes(attributes))
    if (isFourNode) {
      attributes.node_count = '4'
      attributes.节点数量 = '4'
      attributes.nodes = serializeFourNodeList(deviceModal.form.nodeList)
      deviceModal.form.status = aggregateFourNodeStatus(attributes.nodes)
    } else {
      delete attributes.node_count
      delete attributes.节点数量
      delete attributes.nodes
    }
    const payload = {
      ...deviceModal.form,
      asset_no: String(deviceModal.form.asset_no || name).trim(),
      name,
      brand: String(deviceModal.form.brand || '').trim(),
      model: String(deviceModal.form.model || '').trim(),
      u_position: start,
      u_height: height,
      attributes,
    }
    delete payload.owner
    delete payload.mgmt_ip
    delete payload.business_ip
    delete payload.ipmi_host
    delete payload.ipmi_user
    delete payload.ipmi_password
    delete payload.form_factor
    delete payload.nodeList
    delete payload.attributeList
    const submit = payload.id ? api.assetApi.updateDevice : api.assetApi.createDevice
    await submit(payload)
    deviceModal.show = false
    await loadData()
    routeToCabinet(selectedRegionId.value || regionIdByCabinetId(payload.cabinet_id), payload.cabinet_id)
    window.$message?.success('设备已新增')
  } finally {
    deviceModal.submitting = false
  }
}

function openRackContextMenu(event, u, device = null) {
  const menuWidth = 132
  const menuHeight = device ? 184 : 48
  const maxX = Math.max(8, window.innerWidth - menuWidth - 8)
  const maxY = Math.max(8, window.innerHeight - menuHeight - 8)
  rackContextMenu.show = true
  rackContextMenu.x = Math.min(Math.max(event.clientX, 8), maxX)
  rackContextMenu.y = Math.min(Math.max(event.clientY, 8), maxY)
  rackContextMenu.u = u
  rackContextMenu.device = device
}

function closeRackContextMenu() {
  rackContextMenu.show = false
}

function handleRackMenuAdd() {
  const u = rackContextMenu.u
  closeRackContextMenu()
  openDeviceModal(null, u)
}

function handleRackMenuEdit() {
  const device = rackContextMenu.device
  closeRackContextMenu()
  if (device) openDeviceModal(device)
}

function handleRackMenuClone() {
  const device = rackContextMenu.device
  closeRackContextMenu()
  if (device) openDeviceCloneModal(device)
}

function handleRackMenuConsole() {
  const device = rackContextMenu.device
  closeRackContextMenu()
  if (device) openDeviceConsole(device)
}

function openDeviceCloneModal(device) {
  if (!selectedCabinetId.value || !device) return
  const isFourNodeDevice = isFourNodeAttributes(device.attributes)
  const ipmiInfo = extractIpmiInfo(device.attributes || {})
  const height = isFourNodeDevice ? 2 : Math.max(Number(device.u_height || 1), 1)
  const nextU = firstAvailableUForHeight(height)
  if (!nextU) {
    window.$message?.warning(`当前机柜没有可放置 ${height}U 设备的连续空位`)
    return
  }
  deviceModal.form = {
    ...createDeviceForm(),
    ...device,
    ...ipmiInfo,
    id: null,
    cabinet_id: selectedCabinetId.value,
    asset_no: '',
    name: buildCloneDeviceName(device.name),
    serial_no: '',
    u_position: nextU,
    u_height: height,
    ipmi_host: '',
    ipmi_user: '',
    ipmi_password: '',
    form_factor: isFourNodeDevice ? 'four_node' : 'standard',
    attributeList: createCloneAttributeList(device.attributes),
    nodeList: isFourNodeDevice ? normalizeCloneFourNodeList(device.attributes?.nodes || []) : createFourNodeList(),
  }
  deviceModal.show = true
}

function buildCloneDeviceName(name) {
  const baseName = String(name || '设备').trim()
  return `${baseName}-副本`
}

function createCloneAttributeList(attributes) {
  return createAttributeList(attributes).filter((item) => !isCloneUniqueAttributeKey(item.key))
}

function isCloneUniqueAttributeKey(key) {
  const normalizedKey = String(key || '').toLowerCase()
  return ['serial', 'sn', '序列', '资产', 'asset', 'ipmi', 'password', '密码'].some((item) =>
    normalizedKey.includes(item.toLowerCase())
  )
}

function normalizeCloneFourNodeList(nodes) {
  return normalizeFourNodeList(nodes).map((node) => ({
    ...node,
    device_name: node.device_name ? buildCloneDeviceName(node.device_name) : '',
    serial_no: '',
    ipmi_host: '',
    ipmi_user: '',
    ipmi_password: '',
  }))
}

async function handleRackMenuDelete() {
  const device = rackContextMenu.device
  closeRackContextMenu()
  if (!device?.id) return
  await api.assetApi.deleteDevice({ device_id: device.id })
  window.$message?.success('设备已删除')
  await loadData()
  await loadCabinetDevices()
}

function cabinetLocationName(cabinet) {
  return locations.value.find((location) => location.id === cabinet.location_id)?.name || '-'
}

function cabinetDeviceCount(cabinetId) {
  const cabinet = cabinets.value.find((item) => item.id === cabinetId)
  return Number(cabinet?.device_count || 0)
}

function updateCabinetDeviceCount(cabinetId, count) {
  const cabinet = cabinets.value.find((item) => item.id === cabinetId)
  if (cabinet) cabinet.device_count = Math.max(Number(count || 0), 0)
}

function formatCabinetURange(cabinet) {
  const start = Math.max(Number(cabinet?.rental_start_u || 1), 1)
  const fallbackEnd = start + Math.max(Number(cabinet?.capacity_u || 42), 1) - 1
  const end = Math.max(Number(cabinet?.rental_end_u || fallbackEnd), start)
  const capacity = end - start + 1
  return start === 1 ? `${capacity}U` : `${start}-${end}U (${capacity}U)`
}

function formatCabinetSize(cabinet) {
  const width = Number(cabinet?.width_mm || 0)
  const depth = Number(cabinet?.depth_mm || 0)
  if (!width && !depth) return '尺寸未录入'
  if (!width) return `深 ${depth}mm`
  if (!depth) return `宽 ${width}mm`
  return `${width}W x ${depth}D mm`
}

function formatCabinetPower(cabinet) {
  const power = Number(cabinet?.power_allocation_kw || 0)
  const sockets = String(cabinet?.pdu_socket_types || '').trim()
  if (power && sockets) return `${power}kW / ${sockets}`
  if (power) return `${power}kW`
  if (sockets) return sockets
  return '电力未录入'
}

function formatDeviceUPosition(row) {
  if (!row?.u_position) return '-'
  return row.u_height > 1 ? `${row.u_position}-${row.u_position + row.u_height - 1}U` : `${row.u_position}U`
}

function rackBlockStyle(block) {
  return {
    gridRow: `${rackEndU.value - block.end + 1} / span ${Math.max(block.end - block.start + 1, 1)}`,
  }
}

function rackUnitGridRow(unit) {
  return String(rackEndU.value - unit.no + 1)
}

function getDeviceType(value) {
  return deviceTypeOptions.find((item) => item.value === Number(value))?.label || '其他'
}

function getDeviceStatus(value) {
  const status = Number(value)
  return deviceStatusOptions.find((item) => item.value === status)?.label || legacyDeviceStatusLabels[status] || '未知'
}

function attributesToList(attributes) {
  if (!attributes || typeof attributes !== 'object') return []
  return Object.entries(attributes).map(([key, value]) => ({ key, value }))
}

function firstAttributeValue(attributes = {}, keys = []) {
  for (const key of keys) {
    const value = attributes?.[key]
    if (value !== null && value !== undefined && String(value).trim()) return String(value).trim()
  }
  return ''
}

function hasDeviceVncConfig(device) {
  return Boolean(firstAttributeValue(device?.attributes || {}, vncAttributeKeys))
}

function hasNodeVncConfig(node) {
  return Boolean(firstAttributeValue(node || {}, ['vnc_host', 'vnc_address', 'VNC地址', 'VNC主机', 'ipmi_host', 'ipmiHost', 'IPMI地址']))
}

function hasDevicePowerConfig(device) {
  return Boolean(firstAttributeValue(device?.attributes || {}, ['ipmi_host', 'IPMI地址']))
}

function hasNodePowerConfig(node) {
  return Boolean(firstAttributeValue(node || {}, ['ipmi_host', 'ipmiHost', 'IPMI地址']))
}

function devicePowerKey(device, action, node = null) {
  return [device?.id || '', node?.name || '', action].join(':')
}

function deviceIpmiLogKey(device, node = null) {
  return [device?.id || '', node?.name || 'device', 'ipmi-log'].join(':')
}

function devicePowerLabel(action) {
  return devicePowerActions.find((item) => item.value === action)?.label || action
}

function severityClass(value) {
  const text = String(value || '').toLowerCase()
  if (['critical', 'fatal', 'error'].some((item) => text.includes(item))) return 'danger'
  if (['warning', 'warn'].some((item) => text.includes(item))) return 'warning'
  if (['ok', 'normal', 'info'].some((item) => text.includes(item))) return 'success'
  return ''
}

function apiErrorMessage(error, fallback) {
  return error?.error?.detail || error?.error?.msg || error?.message || fallback
}

function deviceSignature(device) {
  return [device?.brand, device?.model, device?.name, JSON.stringify(device?.attributes || {})].join(' ').toLowerCase()
}

function isIloDevice(device) {
  const text = deviceSignature(device)
  return ['ilo', 'hpe', 'hewlett', 'hewlett-packard', '惠普'].some((keyword) => text.includes(keyword))
}

function isInspurDevice(device) {
  const text = deviceSignature(device)
  return ['inspur', '浪潮'].some((keyword) => text.includes(keyword))
}

function isWebConsoleDevice(device) {
  return isIloDevice(device) || isInspurDevice(device)
}

function deviceConsoleLabel(device) {
  if (isInspurDevice(device)) return 'BMC控制台'
  return isIloDevice(device) ? 'iLO控制台' : 'VNC控制台'
}

function deviceConsoleButtonLabel(device) {
  if (isInspurDevice(device)) return '打开 BMC 控制台'
  return isIloDevice(device) ? '打开 iLO 控制台' : '打开 VNC 控制台'
}

function normalizeConsoleUrl(value) {
  const text = String(value || '').trim()
  if (!text) return ''
  if (/^https?:\/\//i.test(text)) return text
  return `https://${text}`
}

function deviceWebConsoleUrl(device) {
  const attributes = device?.attributes || {}
  const configuredUrl = firstAttributeValue(attributes, webConsoleUrlKeys)
  if (configuredUrl) return normalizeConsoleUrl(configuredUrl)
  return normalizeConsoleUrl(firstAttributeValue(attributes, ['ipmi_host', 'IPMI地址']))
}

function openWebConsole(device) {
  const url = deviceWebConsoleUrl(device)
  if (!url) {
    window.$message?.warning('该设备未配置 BMC/IPMI 地址')
    return false
  }
  window.open(url, '_blank', 'noopener,noreferrer')
  return true
}

function openDeviceConsole(device) {
  if (isWebConsoleDevice(device)) {
    openWebConsole(device)
    return
  }
  openDeviceVnc(device)
}

function deviceVncProfile(device) {
  const text = deviceSignature(device)
  if (['ibmc', 'huawei', '华为'].some((keyword) => text.includes(keyword))) return 'huawei'
  return 'default'
}

function resetDeviceVnc() {
  vncModal.loading = false
  vncModal.title = '设备 VNC 控制台'
  vncModal.deviceName = ''
  vncModal.wsUrl = ''
  vncModal.password = ''
  vncModal.target = ''
  vncModal.profile = 'default'
}

function closeDeviceVnc() {
  vncModal.show = false
}

function normalizeDeviceVncResponse(res) {
  return res?.data?.wsUrl
    ? res.data
    : res?.wsUrl
      ? res
      : res?.data?.data?.wsUrl
        ? res.data.data
        : null
}

async function openDeviceVnc(device, node = null) {
  if (!device?.id) return
  if (node && !hasNodeVncConfig(node)) {
    window.$message?.warning('该节点未配置 VNC 地址或 IPMI 地址')
    return
  }
  if (!node && !hasDeviceVncConfig(device)) {
    window.$message?.warning('该设备未配置 VNC 地址或 IPMI 地址')
    return
  }
  vncModal.loading = true
  const displayName = node ? `${device.name || '设备'} / ${node.device_name || node.name}` : device.name || '设备'
  vncModal.title = `${displayName} VNC 控制台`
  vncModal.deviceName = displayName
  vncModal.wsUrl = ''
  vncModal.password = ''
  vncModal.target = ''
  vncModal.profile = deviceVncProfile(device)
  try {
    const payload = node ? { device_id: device.id, node_name: node.name } : { device_id: device.id }
    const res = await api.assetApi.deviceVnc(payload)
    const data = normalizeDeviceVncResponse(res)
    if (!data?.wsUrl) {
      throw new Error('后端未返回 VNC websocket 地址')
    }
    vncModal.deviceName = node
      ? `${device.name || '设备'} / ${data.device_name || node.device_name || node.name}`
      : data.device_name || device.name || ''
    vncModal.wsUrl = data.wsUrl
    vncModal.password = data.password || ''
    vncModal.target = [data.host, data.port].filter(Boolean).join(':')
    vncModal.show = true
  } catch (error) {
    vncModal.show = false
    window.$message?.error(error.message || '打开 VNC 控制台失败')
  } finally {
    vncModal.loading = false
  }
}

async function controlDevicePower(device, action, node = null) {
  if (!device?.id) return
  const key = devicePowerKey(device, action, node)
  powerLoadingKey.value = key
  try {
    const payload = node ? { device_id: device.id, action, node_name: node.name } : { device_id: device.id, action }
    const res = await api.assetApi.devicePower(payload)
    const data = res?.data?.data || res?.data || {}
    const name = data.device_name || (node ? node.device_name || node.name : device.name) || '设备'
    const resetType = data.reset_type ? `（${data.reset_type}）` : ''
    window.$message?.success(`${name} ${devicePowerLabel(action)}指令已提交${resetType}`)
  } catch (error) {
    window.$message?.error(error.message || `${devicePowerLabel(action)}操作失败`)
  } finally {
    powerLoadingKey.value = ''
  }
}

async function loadDeviceIpmiLogs(device, node = null) {
  if (!device?.id) return
  const key = deviceIpmiLogKey(device, node)
  ipmiLogLoadingKey.value = key
  ipmiLogTarget.value = key
  ipmiLogs.value = []
  try {
    const payload = node ? { device_id: device.id, node_name: node.name, limit: 50 } : { device_id: device.id, limit: 50 }
    const res = await api.assetApi.deviceIpmiLogs(payload)
    const data = res?.data?.data || res?.data || {}
    ipmiLogs.value = Array.isArray(data.logs) ? data.logs : []
    window.$message?.success(`已加载 ${ipmiLogs.value.length} 条 IPMI 日志`)
  } catch (error) {
    ipmiLogs.value = []
    window.$message?.error(apiErrorMessage(error, '读取 IPMI 日志失败'))
  } finally {
    ipmiLogLoadingKey.value = ''
  }
}

function openDeviceDetail(device) {
  deviceDrawer.row = device
  deviceDrawer.show = true
}

watch(mapRegionNodes, () => renderMapMarkers(true))
watch(viewMode, (mode) => {
  if (mode === 'map') ensureMap()
})
watch(
  () => [route.query.region_id, route.query.cabinet_id],
  () => {
    applyRouteSelection()
  }
)

onMounted(async () => {
  await loadData()
  ensureMap()
})

onBeforeUnmount(() => {
  destroyMap()
})
</script>

<style scoped>
.cabinet-world-page {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
  background:
    linear-gradient(180deg, #f7f9fc 0%, #eef3f9 100%);
  padding: 10px;
}

:deep(.device-vnc-modal) {
  overflow: visible;
  background: transparent;
  padding: 0;
  box-shadow: none;
}

.device-vnc-shell {
  overflow: hidden;
  border-radius: 8px;
  background: #000;
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.62);
}

.cabinet-world-page.is-map-home {
  height: 100%;
  min-height: 0;
  overflow: hidden;
  padding: 0;
}

.map-panel,
.region-list,
.cabinet-stage {
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.07);
}

.map-panel {
  padding: 16px;
}

.map-panel.map-only {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.map-spin {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.map-panel.map-only :deep(.n-spin-container),
.map-panel.map-only :deep(.n-spin-content) {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.map-head,
.stage-head,
.section-head,
.rack-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 12px;
}

.stage-head {
  min-height: 86px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(240, 245, 252, 0.98));
  padding: 14px 16px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.map-head h2,
.stage-head h2,
.section-head h3,
.rack-title h3 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 21px;
  line-height: 1.25;
}

.stage-actions {
  flex-shrink: 0;
}

.eyebrow {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.world-map {
  position: relative;
  overflow: hidden;
  min-height: 0;
  flex: 1;
  margin-top: 14px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 8px;
  background: #bcd7f2;
}

.world-map :deep(.leaflet-container) {
  width: 100%;
  height: 100%;
  min-height: inherit;
  background: #bcd7f2;
  font-family: inherit;
}

.world-map :deep(.leaflet-control-zoom a) {
  color: #111827;
  font-weight: 700;
}

.world-map :deep(.leaflet-control-attribution) {
  color: #475569;
  font-size: 11px;
}

.world-map :deep(.cabinet-map-marker) {
  border: 0;
  background: transparent;
}

.world-map :deep(.cabinet-marker-wrap) {
  position: relative;
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  cursor: pointer;
}

.world-map :deep(.cabinet-marker-count) {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 3px solid #e30613;
  border-radius: 999px;
  background: #fff;
  color: #111827;
  font-size: 14px;
  font-weight: 800;
  line-height: 1;
  box-shadow:
    0 0 0 3px rgba(255, 255, 255, 0.95),
    0 0 0 6px rgba(126, 58, 242, 0.55),
    0 8px 16px rgba(15, 23, 42, 0.26);
}

.world-map :deep(.cabinet-marker-label) {
  position: absolute;
  left: 38px;
  top: 50%;
  max-width: 140px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.32);
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.96);
  color: #111827;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  padding: 5px 9px;
  text-overflow: ellipsis;
  white-space: nowrap;
  box-shadow: 0 4px 10px rgba(15, 23, 42, 0.12);
  transform: translateY(-50%);
}

.world-map :deep(.leaflet-marker-icon:hover .cabinet-marker-count) {
  border-color: #b91c1c;
  box-shadow:
    0 0 0 3px rgba(255, 255, 255, 0.95),
    0 0 0 7px rgba(126, 58, 242, 0.7),
    0 10px 18px rgba(15, 23, 42, 0.3);
}

.region-layout {
  display: grid;
  min-height: 0;
  flex: 1;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}

.region-list,
.cabinet-stage {
  padding: 10px;
}

.cabinet-stage {
  display: flex;
  min-height: 0;
  flex-direction: column;
  padding: 10px;
}

.region-list {
  display: flex;
  min-height: 560px;
  flex-direction: column;
  gap: 10px;
}

.region-item,
.cabinet-card {
  position: relative;
  display: flex;
  width: 100%;
  flex-direction: column;
  gap: 7px;
  overflow: hidden;
  border: 1px solid rgba(203, 213, 225, 0.9);
  border-radius: 8px;
  background: #fff;
  color: #0f172a;
  cursor: pointer;
  padding: 12px;
  text-align: left;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease,
    transform 0.16s ease;
}

.region-item:hover,
.region-item.active,
.cabinet-card:hover,
.cabinet-card.active {
  border-color: #fb5b2f;
  background: #fffaf4;
}

.cabinet-card:hover {
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}

.cabinet-card.active {
  box-shadow:
    0 0 0 1px rgba(251, 91, 47, 0.14),
    0 12px 26px rgba(251, 91, 47, 0.1);
}

.region-item span,
.cabinet-card span,
.cabinet-card em {
  color: #64748b;
  font-size: 12px;
  font-style: normal;
}

.cabinet-active-mark {
  position: absolute;
  left: 0;
  top: 0;
  width: 4px;
  height: 100%;
  background: #fb4b22;
}

.cabinet-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.cabinet-card-head strong {
  min-width: 0;
  overflow: hidden;
  color: #0b1220;
  font-size: 17px;
  letter-spacing: 0;
  line-height: 1.15;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cabinet-card-actions {
  display: inline-flex;
  flex-shrink: 0;
  gap: 4px;
}

.cabinet-card-actions button {
  border: 0;
  border-radius: 4px;
  background: #f1f5f9;
  color: #475569;
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
  padding: 4px 6px;
}

.cabinet-card-actions button:hover {
  background: #fee2e2;
  color: #dc2626;
}

.cabinet-location {
  overflow: hidden;
  color: #466083 !important;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cabinet-card-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.cabinet-card-metrics em {
  border-radius: 999px;
  background: #edf4ff;
  color: #31537a;
  font-weight: 600;
  line-height: 1;
  padding: 5px 8px;
}

.cabinet-card-foot {
  display: grid;
  gap: 4px;
  padding-top: 2px;
}

.region-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.region-meta span {
  border: 1px solid rgba(148, 163, 184, 0.26);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.84);
  color: #475569;
  font-size: 12px;
  line-height: 1;
  padding: 6px 10px;
}

.cabinet-content {
  display: grid;
  min-height: 0;
  flex: 1;
  grid-template-columns: minmax(680px, 1fr) clamp(300px, 22vw, 380px);
  gap: 10px;
  margin-top: 10px;
}

.cabinet-side {
  display: grid;
  min-height: 0;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 10px;
}

.cabinet-list {
  display: flex;
  max-height: none;
  min-height: 0;
  flex-direction: column;
  gap: 9px;
  overflow-y: auto;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 8px;
  background:
    linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
  padding: 10px;
}

.side-section-title {
  position: sticky;
  top: -10px;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: -10px -10px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(248, 250, 252, 0.96);
  color: #52637a;
  font-size: 12px;
  font-weight: 700;
  padding: 11px 12px;
  text-transform: uppercase;
  backdrop-filter: blur(8px);
}

.side-section-title strong {
  color: #0f172a;
  font-size: 14px;
}

.rack-spin {
  display: flex;
  min-height: 0;
  flex-direction: column;
}

.rack-spin :deep(.n-spin-container),
.rack-spin :deep(.n-spin-content) {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.rack-board {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background: #ffffff;
}

.rack-title {
  min-height: 52px;
  border: 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 0;
  background:
    linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  padding: 10px 12px;
}

.rack-title h3 {
  font-size: 16px;
}

.rack-title :deep(.n-button) {
  height: 30px;
  padding-inline: 12px;
}

.rack-title :deep(.n-tag) {
  height: 26px;
}

.rack-table-shell {
  position: relative;
  width: 100%;
  max-height: none;
  min-height: 0;
  flex: 1;
  margin: 0;
  overflow: auto;
  border: 0;
  border-radius: 0;
  background:
    linear-gradient(90deg, #e8eef5 0, #f8fafc 52px, #ffffff 52px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.rack-table {
  width: 100%;
  min-width: 620px;
  border-collapse: collapse;
  table-layout: fixed;
}

.rack-table th {
  position: sticky;
  top: 0;
  z-index: 3;
  height: 32px;
  border: 1px solid #344052;
  background: #3f4b5d;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}

.rack-table th:not(.rack-u-head) {
  color: #f59e0b;
}

.rack-u-head,
.rack-u-cell {
  width: 56px;
}

.rack-u-cell,
.rack-empty-cell,
.rack-device-cell {
  height: clamp(14px, calc((100vh - 222px) / var(--rack-units, 42)), 25px);
  border: 1px solid #ccd6e2;
}

.rack-u-cell {
  background: #eef3f8;
  color: #475569;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  text-align: center;
}

.rack-empty-cell {
  background:
    linear-gradient(90deg, rgba(148, 163, 184, 0.08), transparent 22%, transparent 78%, rgba(148, 163, 184, 0.08)),
    linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(248, 250, 252, 0.7)),
    #fff;
  cursor: context-menu;
}

.rack-empty-cell:hover {
  background: #fef3c7;
}

.rack-device-cell {
  position: relative;
  overflow: hidden;
  background:
    linear-gradient(180deg, #3477f6 0%, #2563eb 100%);
  color: #fff;
  cursor: pointer;
  padding: 3px 34px 3px 12px;
  text-align: center;
  vertical-align: middle;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.22),
    inset 0 -1px 0 rgba(15, 23, 42, 0.16);
}

.rack-device-cell:hover {
  filter: brightness(1.05);
}

.rack-device-cell.conflict {
  outline: 2px solid #dc2626;
  outline-offset: -2px;
}

.rack-device-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.rack-device-main strong,
.rack-device-main span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rack-device-main strong {
  font-size: 12px;
  line-height: 1.1;
}

.rack-device-main span {
  opacity: 0.9;
  font-size: 10px;
  line-height: 1.1;
}

.rack-status-dot {
  position: absolute;
  right: 12px;
  top: 50%;
  width: 10px;
  height: 10px;
  border: 2px solid rgba(255, 255, 255, 0.86);
  border-radius: 999px;
  background: #9ca3af;
  transform: translateY(-50%);
}

.rack-device-cell.device-type-1,
.rack-device-cell.device-type-2 {
  background: linear-gradient(180deg, #10b981 0%, #059669 100%);
}

.rack-device-cell.device-type-3 {
  background: linear-gradient(180deg, #f59e0b 0%, #d97706 100%);
}

.rack-device-cell.device-type-4,
.rack-device-cell.device-type-5 {
  background: linear-gradient(180deg, #ec4899 0%, #db2777 100%);
}

.rack-device-cell.device-status-0 .rack-status-dot {
  background: #38bdf8;
}

.rack-device-cell.device-status-1 .rack-status-dot {
  background: #22c55e;
}

.rack-device-cell.device-status-2 .rack-status-dot,
.rack-device-cell.device-status-3 .rack-status-dot,
.rack-device-cell.device-status-5 .rack-status-dot {
  background: #ef4444;
}

.rack-device-cell.device-status-4 .rack-status-dot {
  background: #64748b;
}

.rack-context-menu {
  position: fixed;
  z-index: 3000;
  min-width: 118px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.32);
  border-radius: 6px;
  background: #fff;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.18);
}

.rack-context-menu button {
  display: block;
  width: 100%;
  border: 0;
  background: transparent;
  color: #0f172a;
  cursor: pointer;
  padding: 9px 12px;
  text-align: left;
}

.rack-context-menu button:hover {
  background: #f1f5f9;
}

.rack-shell {
  max-width: 520px;
  margin: 16px auto 0;
  border: 1px solid #1f2937;
  border-radius: 8px;
  background:
    linear-gradient(90deg, rgba(15, 23, 42, 0.18), transparent 12%, transparent 88%, rgba(15, 23, 42, 0.2)),
    linear-gradient(180deg, #475569, #111827);
  box-shadow: 16px 18px 30px rgba(15, 23, 42, 0.18);
  padding: 18px;
}

.rack-cap {
  height: 18px;
  border-radius: 6px;
  background: linear-gradient(180deg, #64748b, #1f2937);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22);
}

.rack-cap.base {
  margin-top: 10px;
}

.rack-body {
  position: relative;
  min-height: 680px;
  margin-top: 10px;
  border: 1px solid rgba(15, 23, 42, 0.72);
  background: #020617;
  padding: 0 28px;
}

.rack-rail {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 18px;
  background:
    radial-gradient(circle at 50% 10px, rgba(255, 255, 255, 0.34) 0 2px, transparent 3px) 0 0 / 18px 30px,
    linear-gradient(180deg, #334155, #0f172a);
}

.rack-rail.left {
  left: 0;
}

.rack-rail.right {
  right: 0;
}

.rack-slots {
  position: relative;
  display: grid;
  height: 680px;
  grid-template-rows: repeat(var(--rack-units, 42), minmax(10px, 1fr));
  grid-template-columns: 64px minmax(0, 1fr);
  overflow: hidden;
  border-inline: 1px solid rgba(148, 163, 184, 0.28);
  background:
    linear-gradient(90deg, rgba(15, 23, 42, 0.42), transparent 16%, transparent 84%, rgba(15, 23, 42, 0.42)),
    #0f172a;
}

.rack-row {
  position: relative;
  grid-column: 1 / -1;
  min-height: 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
}

.rack-row span {
  position: absolute;
  left: 8px;
  top: 50%;
  z-index: 1;
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  transform: translateY(-50%);
}

.rack-row.occupied {
  background: rgba(59, 130, 246, 0.06);
}

.rack-row.conflict {
  background: rgba(239, 68, 68, 0.18);
}

.device-block {
  grid-column: 2;
  z-index: 2;
  display: flex;
  min-height: 0;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
  border: 1px solid rgba(96, 165, 250, 0.58);
  border-radius: 4px;
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.12), transparent 18%),
    linear-gradient(180deg, #2563eb, #1d4ed8);
  color: #eff6ff;
  cursor: pointer;
  align-self: stretch;
  box-sizing: border-box;
  margin: 2px 24px 2px 8px;
  padding: 1px 12px;
  text-align: left;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18), 0 8px 18px rgba(15, 23, 42, 0.32);
}

.device-block:hover {
  border-color: rgba(191, 219, 254, 0.86);
  filter: brightness(1.08);
}

.device-block strong,
.device-block span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-block strong {
  font-size: 12px;
  line-height: 1;
}

.device-block span {
  margin-top: 3px;
  opacity: 0.82;
  font-size: 10px;
  line-height: 1;
}

.device-block.compact {
  padding-block: 0;
}

.device-block.device-type-1,
.device-block.device-type-2 {
  border-color: rgba(52, 211, 153, 0.72);
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.14), transparent 18%),
    linear-gradient(180deg, #059669, #047857);
}

.device-block.device-type-3 {
  border-color: rgba(251, 191, 36, 0.78);
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.14), transparent 18%),
    linear-gradient(180deg, #d97706, #92400e);
}

.device-block.device-type-4,
.device-block.device-type-5 {
  border-color: rgba(244, 114, 182, 0.74);
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.14), transparent 18%),
    linear-gradient(180deg, #db2777, #be185d);
}

.device-block.conflict,
.device-block.device-status-2,
.device-block.device-status-3,
.device-block.device-status-5 {
  border-color: rgba(252, 165, 165, 0.82);
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.14), transparent 18%),
    linear-gradient(180deg, #dc2626, #991b1b);
}

.rack-empty {
  margin-top: 14px;
}

.detail-section {
  margin-top: 16px;
}

.detail-section h3 {
  margin: 0 0 10px;
  color: #0f172a;
  font-size: 15px;
}

.node-detail-grid,
.four-node-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 10px;
}

.node-detail-card,
.four-node-card {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 7px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 10px;
}

.node-detail-card strong,
.four-node-card strong {
  color: #0f172a;
  font-size: 13px;
}

.node-detail-head {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.node-detail-head strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.four-node-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
}

.four-node-fields :deep(.n-input-number) {
  width: 100%;
}

.node-detail-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px 10px;
}

.node-detail-fields span {
  display: grid;
  min-width: 0;
  grid-template-columns: 58px minmax(0, 1fr);
  align-items: start;
  gap: 6px;
  color: #475569;
  font-size: 12px;
  line-height: 1.45;
}

.node-detail-fields span.wide {
  grid-column: 1 / -1;
}

.node-detail-fields b {
  color: #64748b;
  font-weight: 500;
  white-space: nowrap;
}

.node-detail-fields em {
  min-width: 0;
  color: #0f172a;
  font-style: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.detail-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.ipmi-log-panel {
  margin-top: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 8px;
}

.node-log-panel {
  grid-column: 1 / -1;
}

.ipmi-log-list {
  display: flex;
  max-height: 360px;
  flex-direction: column;
  gap: 6px;
  overflow: auto;
}

.ipmi-log-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: 8px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
  padding: 8px 10px;
}

.ipmi-log-row div {
  min-width: 0;
}

.ipmi-log-row strong,
.ipmi-log-row span {
  display: block;
}

.ipmi-log-row strong {
  color: #0f172a;
  font-size: 13px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.ipmi-log-row span,
.ipmi-log-row time {
  color: #64748b;
  font-size: 12px;
  line-height: 1.4;
}

.ipmi-log-row em {
  border-radius: 999px;
  background: #e2e8f0;
  color: #334155;
  padding: 2px 8px;
  font-size: 12px;
  font-style: normal;
  text-align: center;
  white-space: nowrap;
}

.ipmi-log-row time {
  grid-column: 1 / -1;
  white-space: nowrap;
}

.ipmi-log-row em.danger {
  background: #fee2e2;
  color: #b91c1c;
}

.ipmi-log-row em.warning {
  background: #fef3c7;
  color: #92400e;
}

.ipmi-log-row em.success {
  background: #dcfce7;
  color: #166534;
}

.device-ipmi-editor,
.device-attribute-editor,
.four-node-editor {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background: #f8fafc;
  padding: 12px;
}

.device-ipmi-editor,
.device-attribute-editor {
  margin-bottom: 12px;
}

.four-node-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.four-node-head h3 {
  margin: 2px 0 0;
  color: #0f172a;
  font-size: 15px;
}

.attribute-editor-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.attribute-editor-row {
  display: grid;
  grid-template-columns: minmax(140px, 0.8fr) minmax(180px, 1.2fr) auto;
  gap: 8px;
}

.attribute-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.attribute-item {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 10px;
  border: 1px solid #eef2f7;
  border-radius: 6px;
  padding: 8px 10px;
}

.attribute-item span {
  color: #64748b;
}

.attribute-item strong {
  min-width: 0;
  overflow: hidden;
  color: #0f172a;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.platform-manager {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.platform-add-row,
.model-add-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
}

.platform-list {
  display: grid;
  max-height: 56vh;
  gap: 10px;
  overflow: auto;
  padding-right: 2px;
}

.platform-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  padding: 10px;
}

.platform-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.platform-card-head strong {
  color: #0f172a;
  font-size: 15px;
}

.model-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.muted-text {
  color: #94a3b8;
  font-size: 12px;
}

@media (max-width: 1180px) {
  .region-layout,
  .cabinet-content {
    grid-template-columns: 1fr;
  }

  .region-list {
    min-height: auto;
  }

  .cabinet-list {
    display: flex;
    max-height: 88px;
    flex-direction: row;
    overflow-x: auto;
    overflow-y: hidden;
    padding-bottom: 2px;
  }

  .cabinet-card {
    min-width: 190px;
  }
}

@media (max-width: 720px) {
  .map-head,
  .stage-head,
  .rack-title {
    align-items: flex-start;
    flex-direction: column;
  }

  .cabinet-list {
    grid-template-columns: 1fr;
  }

  .world-map {
    min-height: 0;
  }
}
</style>

