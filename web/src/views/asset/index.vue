<template>
  <AppPage :show-footer="false">
    <div class="asset-page">
      <section class="asset-layout">
        <aside class="asset-sidebar">
          <div class="panel-head">
            <div>
              <span class="eyebrow">Location</span>
              <h2>区域结构</h2>
            </div>
            <n-dropdown
              v-if="permittedCreateOptions.length"
              trigger="click"
              :options="permittedCreateOptions"
              @select="handleCreateSelect"
            >
              <n-button secondary circle>
                <template #icon>
                  <TheIcon icon="mdi:plus" :size="18" />
                </template>
              </n-button>
            </n-dropdown>
          </div>

          <n-empty v-if="!treeData.length && !loading.tree" description="暂无区域数据" />
          <n-tree
            v-else
            block-line
            block-node
            :data="treeData"
            :loading="loading.tree"
            :expanded-keys="expandedKeys"
            :selected-keys="selectedKeys"
            key-field="id"
            label-field="label"
            children-field="children"
            @update:expanded-keys="expandedKeys = $event"
            @update:selected-keys="handleTreeSelect"
          />
        </aside>

        <main class="asset-main">
          <section class="summary-band">
            <article>
              <span>区域</span>
              <strong>{{ regionOptions.length }}</strong>
            </article>
            <article>
              <span>位置</span>
              <strong>{{ locationOptions.length }}</strong>
            </article>
            <article>
              <span>机柜</span>
              <strong>{{ cabinetOptions.length }}</strong>
            </article>
            <article>
              <span>{{ isInventoryView ? '当前库存项' : '当前设备' }}</span>
              <strong>{{ pagination.itemCount }}</strong>
            </article>
          </section>

          <section class="filter-panel">
            <n-input
              v-model:value="filters.keyword"
              clearable
              :placeholder="
                isInventoryView
                  ? '全局搜索：分类 / 子类 / 数量 / 扩展属性'
                  : '全局搜索：设备名称 / SN / IP'
              "
              @keyup.enter="searchCurrentList"
            >
              <template #prefix>
                <TheIcon icon="mdi:magnify" :size="18" />
              </template>
            </n-input>
            <n-select
              v-if="isInventoryView"
              v-model:value="filters.inventoryType"
              clearable
              placeholder="库存分类"
              :options="inventoryTypeOptions"
              @update:value="handleInventoryFilterTypeChange"
            />
            <n-select
              v-if="isInventoryView"
              v-model:value="filters.inventorySubtype"
              clearable
              placeholder="库存子类"
              :options="filterInventorySubtypeOptions"
            />
            <n-select
              v-else
              v-model:value="filters.deviceType"
              clearable
              placeholder="设备类型"
              :options="deviceTypeOptions"
            />
            <n-select
              v-if="!isInventoryView"
              v-model:value="filters.deviceStatus"
              clearable
              placeholder="设备状态"
              :options="deviceStatusOptions"
            />
            <n-button secondary round @click="resetFilters">重置</n-button>
            <n-button type="primary" round @click="searchCurrentList">搜索</n-button>
          </section>

          <section class="content-panel">
            <div class="panel-head">
              <div>
                <span class="eyebrow">{{ selectedLabel }}</span>
                <h2>{{ isInventoryView ? '库存列表' : '设备列表' }}</h2>
              </div>
              <div class="toolbar-actions">
                <input
                  ref="inventoryImportInputRef"
                  class="hidden-file-input"
                  type="file"
                  accept=".csv,text/csv"
                  @change="handleInventoryImport"
                />
                <n-button
                  v-if="isInventoryView && canExportInventory"
                  secondary
                  round
                  :loading="loading.inventoryExport"
                  @click="exportInventory"
                >
                  <template #icon>
                    <TheIcon icon="mdi:download" :size="18" />
                  </template>
                  导出
                </n-button>
                <n-button
                  v-if="isInventoryView && canImportInventory"
                  secondary
                  round
                  :loading="loading.inventoryImport"
                  @click="triggerInventoryImport"
                >
                  <template #icon>
                    <TheIcon icon="mdi:upload" :size="18" />
                  </template>
                  导入
                </n-button>
                <n-button
                  v-if="isInventoryView && canMaintainCategories"
                  secondary
                  round
                  @click="categoryModal.show = true"
                >
                  <template #icon>
                    <TheIcon icon="mdi:shape-plus-outline" :size="18" />
                  </template>
                  分类维护
                </n-button>
                <n-button
                  v-if="!isInventoryView && canMaintainDeviceBrands"
                  secondary
                  round
                  @click="brandModal.show = true"
                >
                  <template #icon>
                    <TheIcon icon="mdi:tag-multiple-outline" :size="18" />
                  </template>
                  品牌型号维护
                </n-button>
                <div v-if="canShowRackView" class="view-switch">
                  <n-button
                    :type="viewMode === 'table' ? 'primary' : 'default'"
                    :secondary="viewMode !== 'table'"
                    round
                    @click="switchAssetView('table')"
                  >
                    <template #icon>
                      <TheIcon icon="mdi:table" :size="18" />
                    </template>
                    表格
                  </n-button>
                  <n-button
                    :type="viewMode === 'rack' ? 'primary' : 'default'"
                    :secondary="viewMode !== 'rack'"
                    round
                    @click="switchAssetView('rack')"
                  >
                    <template #icon>
                      <TheIcon icon="mdi:server-network" :size="18" />
                    </template>
                    机柜图
                  </n-button>
                </div>
                <n-button v-if="canUseContextAction" secondary round @click="openContextModal">
                  <template #icon>
                    <TheIcon :icon="contextIcon" :size="18" />
                  </template>
                  {{ contextActionText }}
                </n-button>
                <n-button
                  v-if="canUsePrimaryAction"
                  type="primary"
                  round
                  @click="openPrimaryModal()"
                >
                  <template #icon>
                    <TheIcon
                      :icon="isInventoryView ? 'mdi:package-variant-plus' : 'mdi:server-plus'"
                      :size="18"
                    />
                  </template>
                  {{ isInventoryView ? '新增库存' : '新增设备' }}
                </n-button>
              </div>
            </div>

            <n-data-table
              v-if="viewMode === 'table' || !canShowRackView"
              remote
              :loading="loading.list"
              :columns="isInventoryView ? inventoryColumns : deviceColumns"
              :data="isInventoryView ? inventoryItems : devices"
              :pagination="pagination"
              :row-key="(row) => row.id"
              :row-class-name="() => 'asset-table-row'"
              @update:page="handlePageChange"
              @update:page-size="handlePageSizeChange"
              @update:sorter="handleSorterChange"
            />
            <n-spin v-else :show="loading.rack">
              <div class="rack-visual">
                <div class="rack-summary">
                  <div>
                    <span class="eyebrow">Rack View</span>
                    <h3>{{ currentCabinet?.name || selectedLabel }}</h3>
                  </div>
                  <div class="rack-stats">
                    <span>{{ rackCapacity }}U</span>
                    <span>{{ rackPlacedDevices.length }} 台设备</span>
                    <span>{{ rackUsedUnits }}U 已占用</span>
                    <span v-if="rackConflictCount" class="rack-conflict-text"
                      >{{ rackConflictCount }} 个冲突U位</span
                    >
                  </div>
                </div>
                <div class="rack-scene">
                  <div class="rack-cabinet">
                    <div class="rack-top"></div>
                    <div class="rack-body">
                      <div class="rack-rail left"></div>
                      <div class="rack-rail right"></div>
                      <div class="rack-slots" :style="{ '--rack-units': rackCapacity }">
                        <div
                          v-for="unit in rackUnits"
                          :key="unit.no"
                          class="rack-u-row"
                          :class="{ occupied: unit.occupied, conflict: unit.conflict }"
                          :style="{ gridRow: rackUnitGridRow(unit) }"
                        >
                          <span>{{ unit.no }}U</span>
                        </div>
                        <button
                          v-for="block in rackBlocks"
                          :key="block.device.id"
                          class="rack-device-block"
                          :class="[
                            `device-type-${Number(block.device.type)}`,
                            `device-status-${Number(block.device.status)}`,
                            { compact: block.height <= 1 },
                            { selected: selectedRackDevice?.id === block.device.id },
                            { conflict: block.conflict },
                          ]"
                          :style="rackBlockStyle(block)"
                          :title="`${block.device.name || '-'} · ${formatDeviceUPosition(block.device)}`"
                          @click="selectRackDevice(block.device)"
                        >
                          <div class="rack-device-info">
                            <strong>{{ block.device.name || '-' }}</strong>
                            <span>{{ getDeviceType(block.device.type) }} · {{ formatDeviceUPosition(block.device) }}</span>
                          </div>
                          <i
                            class="rack-status-dot"
                            :class="`device-status-${Number(block.device.status)}`"
                            :title="getDeviceStatus(block.device.status)"
                          ></i>
                        </button>
                      </div>
                    </div>
                    <div class="rack-base"></div>
                  </div>
                  <div class="rack-side-panel">
                  <div class="rack-legend">
                    <span><i class="server"></i>服务器</span>
                    <span><i class="switch"></i>交换机</span>
                    <span><i class="router"></i>路由器</span>
                    <span><i class="firewall"></i>防火墙</span>
                    <span><i class="pdu"></i>PDU</span>
                    <span><i class="part"></i>配件</span>
                    <span><i class="danger"></i>故障/冲突</span>
                  </div>
                  <div class="rack-device-detail">
                    <template v-if="selectedRackDevice">
                      <div class="rack-detail-head">
                        <div>
                          <span class="eyebrow">Device</span>
                          <h3>{{ selectedRackDevice.name || '-' }}</h3>
                        </div>
                        <span
                          class="rack-detail-status"
                          :class="`device-status-${Number(selectedRackDevice.status)}`"
                        >
                          {{ getDeviceStatus(selectedRackDevice.status) }}
                        </span>
                      </div>
                      <n-descriptions bordered :column="2" label-placement="left" size="small">
                        <n-descriptions-item label="类型">
                          {{ getDeviceType(selectedRackDevice.type) }}
                        </n-descriptions-item>
                        <n-descriptions-item label="U位">
                          {{ formatDeviceUPosition(selectedRackDevice) }}
                        </n-descriptions-item>
                        <n-descriptions-item label="品牌">
                          {{ selectedRackDevice.brand || '-' }}
                        </n-descriptions-item>
                        <n-descriptions-item label="型号">
                          {{ selectedRackDevice.model || '-' }}
                        </n-descriptions-item>
                        <n-descriptions-item label="序列号">
                          {{ selectedRackDevice.serial_no || '-' }}
                        </n-descriptions-item>
                        <n-descriptions-item label="管理IP">
                          {{ selectedRackDevice.mgmt_ip || '-' }}
                        </n-descriptions-item>
                        <n-descriptions-item label="业务IP">
                          {{ selectedRackDevice.business_ip || '-' }}
                        </n-descriptions-item>
                        <n-descriptions-item label="备注">
                          {{ selectedRackDevice.remark || '-' }}
                        </n-descriptions-item>
                      </n-descriptions>
                      <div class="detail-section">
                        <h3>设备配置</h3>
                        <n-empty
                          v-if="!attributesToList(selectedRackDevice.attributes).length"
                          description="暂无配置"
                        />
                        <div v-else class="device-config-table">
                          <div
                            v-for="row in getDeviceAttributeRows(
                              selectedRackDevice.attributes,
                              selectedRackDevice.type
                            )"
                            :key="row.label"
                            class="device-config-row"
                          >
                            <div class="device-config-label">{{ row.label }}</div>
                            <div class="device-config-values">
                              <span
                                v-for="item in row.items"
                                :key="item.label"
                                :class="{ 'is-sensitive': item.sensitive }"
                              >
                                <strong>{{ item.label }}</strong>
                                {{ item.sensitive ? '仅 NOC / Admin 可见' : item.value || '-' }}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                      <div class="rack-detail-actions">
                        <n-button
                          v-if="hasAssetPermission('device', 'update')"
                          type="primary"
                          round
                          @click="openDeviceModal(selectedRackDevice)"
                        >
                          编辑设备
                        </n-button>
                      </div>
                    </template>
                    <div v-else class="rack-detail-empty">点击设备显示设备信息</div>
                  </div>
                  </div>
                </div>
                <n-empty
                  v-if="!rackPlacedDevices.length"
                  class="rack-empty"
                  description="当前机柜暂无配置U位的设备"
                />
              </div>
            </n-spin>
          </section>
        </main>
      </section>

      <n-modal
        v-model:show="inventoryModal.show"
        preset="card"
        :title="inventoryModal.form.id ? '编辑库存' : '新增库存'"
        class="asset-modal"
      >
        <n-form
          ref="inventoryFormRef"
          :model="inventoryModal.form"
          :rules="inventoryRules"
          label-placement="left"
          label-width="90"
        >
          <n-grid :cols="2" :x-gap="16">
            <n-form-item-gi label="库存位置" path="location_id">
              <n-select
                v-model:value="inventoryModal.form.location_id"
                filterable
                :options="inventoryLocationOptions"
              />
            </n-form-item-gi>
            <n-form-item-gi label="分类" path="type">
              <n-select
                v-model:value="inventoryModal.form.type"
                filterable
                tag
                :options="inventoryTypeOptions"
                @update:value="handleInventoryTypeChange"
              />
            </n-form-item-gi>
            <n-form-item-gi label="子类">
              <n-select
                v-model:value="inventoryModal.form.subtype"
                clearable
                filterable
                tag
                :options="modalInventorySubtypeOptions"
              />
            </n-form-item-gi>
            <n-form-item-gi label="数量" path="quantity">
              <n-input-number v-model:value="inventoryModal.form.quantity" :min="0" />
            </n-form-item-gi>
            <n-form-item-gi label="告警阈值" path="threshold">
              <n-input-number v-model:value="inventoryModal.form.threshold" :min="0" />
            </n-form-item-gi>
            <n-form-item-gi label="成本价">
              <n-input-number v-model:value="inventoryModal.form.cost_price" :min="0" />
            </n-form-item-gi>
            <n-form-item-gi label="默认售价">
              <n-input-number v-model:value="inventoryModal.form.sale_price" :min="0" />
            </n-form-item-gi>
            <n-form-item-gi :span="2" label="扩展属性">
              <div class="attribute-editor">
                <div
                  v-for="(attr, index) in inventoryModal.form.attributeList"
                  :key="index"
                  class="attribute-row"
                >
                  <n-input v-model:value="attr.key" placeholder="属性名，如规格型号" />
                  <n-input v-model:value="attr.value" placeholder="属性值" />
                  <n-button secondary circle @click="removeInventoryAttribute(index)">
                    <template #icon>
                      <TheIcon icon="mdi:minus" :size="16" />
                    </template>
                  </n-button>
                </div>
                <n-button secondary round @click="addInventoryAttribute">
                  <template #icon>
                    <TheIcon icon="mdi:plus" :size="16" />
                  </template>
                  添加属性
                </n-button>
              </div>
            </n-form-item-gi>
            <n-form-item-gi :span="2" label="备注">
              <n-input v-model:value="inventoryModal.form.remark" type="textarea" />
            </n-form-item-gi>
          </n-grid>
        </n-form>
        <template #footer>
          <div class="modal-footer">
            <CButton
              show-cancel
              :show-save="canSaveInventory"
              :save-loading="inventoryModal.submitting"
              @cancel="inventoryModal.show = false"
              @save="submitInventory"
            />
          </div>
        </template>
      </n-modal>

      <n-modal v-model:show="saleModal.show" preset="card" title="库存售卖" class="simple-modal">
        <n-form label-placement="left" label-width="90">
          <n-form-item label="库存项">
            <n-input :value="saleModal.inventoryLabel" readonly />
          </n-form-item>
          <n-grid :cols="2" :x-gap="16">
            <n-form-item-gi label="客户名称">
              <n-input v-model:value="saleModal.form.customer_name" />
            </n-form-item-gi>
            <n-form-item-gi label="联系人">
              <n-input v-model:value="saleModal.form.customer_contact" />
            </n-form-item-gi>
            <n-form-item-gi label="销售日期">
              <n-date-picker
                v-model:formatted-value="saleModal.form.sale_date"
                type="date"
                value-format="yyyy-MM-dd"
                clearable
              />
            </n-form-item-gi>
            <n-form-item-gi label="销售数量">
              <n-input-number v-model:value="saleModal.form.quantity" :min="1" :max="saleModal.maxQuantity" />
            </n-form-item-gi>
            <n-form-item-gi label="销售单价">
              <n-input-number v-model:value="saleModal.form.unit_price" :min="0" />
            </n-form-item-gi>
            <n-form-item-gi label="小计">
              <n-input :value="String(saleAmount)" readonly />
            </n-form-item-gi>
            <n-form-item-gi :span="2" label="备注">
              <n-input v-model:value="saleModal.form.remark" type="textarea" />
            </n-form-item-gi>
          </n-grid>
        </n-form>
        <template #footer>
          <div class="modal-footer">
            <n-button round @click="saleModal.show = false">取消</n-button>
            <n-button type="primary" round :loading="saleModal.submitting" @click="submitInventorySale">
              确认售卖
            </n-button>
          </div>
        </template>
      </n-modal>

      <n-modal v-model:show="saleRecordsModal.show" preset="card" title="销售记录" class="asset-modal">
        <n-data-table
          remote
          :loading="saleRecordsModal.loading"
          :columns="saleRecordColumns"
          :data="saleRecords"
          :pagination="saleRecordsPagination"
          @update:page="handleSaleRecordsPageChange"
          @update:page-size="handleSaleRecordsPageSizeChange"
        />
      </n-modal>

      <n-modal v-model:show="stockFlowsModal.show" preset="card" title="库存流水" class="asset-modal">
        <n-data-table
          remote
          :loading="stockFlowsModal.loading"
          :columns="stockFlowColumns"
          :data="stockFlows"
          :pagination="stockFlowsPagination"
          @update:page="handleStockFlowsPageChange"
          @update:page-size="handleStockFlowsPageSizeChange"
        />
      </n-modal>

      <n-modal
        v-model:show="deviceModal.show"
        preset="card"
        :title="deviceModal.form.id ? '编辑设备' : '新增设备'"
        class="asset-modal"
      >
        <n-form
          ref="deviceFormRef"
          :model="deviceModal.form"
          :rules="deviceRules"
          label-placement="left"
          label-width="90"
        >
          <n-grid :cols="2" :x-gap="16">
            <n-form-item-gi label="所属机柜" path="cabinet_id">
              <n-select
                v-model:value="deviceModal.form.cabinet_id"
                filterable
                :options="cabinetOptions"
              />
            </n-form-item-gi>
            <n-form-item-gi label="设备名称" path="name">
              <n-input v-model:value="deviceModal.form.name" />
            </n-form-item-gi>
            <n-form-item-gi label="设备类型">
              <n-select
                v-model:value="deviceModal.form.type"
                :options="deviceTypeOptions"
                @update:value="handleDeviceTypeChange"
              />
            </n-form-item-gi>
            <n-form-item-gi label="品牌">
              <n-select
                v-model:value="deviceModal.form.brand"
                clearable
                filterable
                :options="deviceBrandOptions"
                @update:value="handleDeviceBrandChange"
              />
            </n-form-item-gi>
            <n-form-item-gi label="型号">
              <n-select
                v-model:value="deviceModal.form.model"
                clearable
                filterable
                :disabled="!deviceModal.form.brand"
                :options="deviceModelOptions"
              />
            </n-form-item-gi>
            <n-form-item-gi label="序列号">
              <n-input v-model:value="deviceModal.form.serial_no" />
            </n-form-item-gi>
            <n-form-item-gi label="状态">
              <n-select v-model:value="deviceModal.form.status" :options="deviceStatusOptions" />
            </n-form-item-gi>
            <n-form-item-gi label="起始U位">
              <n-input-number v-model:value="deviceModal.form.u_position" clearable :min="1" />
            </n-form-item-gi>
            <n-form-item-gi label="占用U数">
              <n-input-number v-model:value="deviceModal.form.u_height" :min="1" />
            </n-form-item-gi>
            <n-form-item-gi label="管理IP">
              <n-input v-model:value="deviceModal.form.mgmt_ip" />
            </n-form-item-gi>
            <n-form-item-gi label="业务IP">
              <n-input v-model:value="deviceModal.form.business_ip" />
            </n-form-item-gi>
            <n-form-item-gi :span="2" label="设备配置">
              <div class="attribute-editor">
                <div
                  v-for="(attr, index) in deviceModal.form.attributeList"
                  :key="index"
                  class="attribute-row"
                >
                  <n-input v-model:value="attr.key" placeholder="配置项，如 CPU数量" />
                  <n-input v-model:value="attr.value" placeholder="配置值" />
                  <n-button secondary circle @click="removeDeviceAttribute(index)">
                    <template #icon>
                      <TheIcon icon="mdi:minus" :size="16" />
                    </template>
                  </n-button>
                </div>
                <div class="attribute-actions">
                  <n-button secondary round @click="addDeviceAttribute">
                    <template #icon>
                      <TheIcon icon="mdi:plus" :size="16" />
                    </template>
                    添加配置
                  </n-button>
                  <n-button
                    secondary
                    round
                    @click="
                      deviceModal.form.id
                        ? applyDeviceAttributeTemplate()
                        : syncDeviceAttributeTemplate()
                    "
                    >应用类型模板</n-button
                  >
                </div>
              </div>
            </n-form-item-gi>
            <n-form-item-gi :span="2" label="备注">
              <n-input v-model:value="deviceModal.form.remark" type="textarea" />
            </n-form-item-gi>
          </n-grid>
        </n-form>
        <template #footer>
          <div class="modal-footer">
            <CButton
              show-cancel
              :show-save="canSaveDevice"
              :save-loading="deviceModal.submitting"
              @cancel="deviceModal.show = false"
              @save="submitDevice"
            />
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="deviceDetailModal.show"
        preset="card"
        :title="deviceDetailModal.row?.name || '设备详情'"
        class="asset-modal"
      >
        <n-descriptions bordered :column="2" label-placement="left" size="small">
          <n-descriptions-item label="设备名称">
            {{ deviceDetailModal.row?.name || '-' }}
          </n-descriptions-item>
          <n-descriptions-item label="类型">
            {{ getDeviceType(deviceDetailModal.row?.type) }}
          </n-descriptions-item>
          <n-descriptions-item label="状态">
            {{ getDeviceStatus(deviceDetailModal.row?.status) }}
          </n-descriptions-item>
          <n-descriptions-item label="区域">
            {{ deviceDetailModal.row?.region_name || '-' }}
          </n-descriptions-item>
          <n-descriptions-item label="位置">
            {{ deviceDetailModal.row?.location_name || '-' }}
          </n-descriptions-item>
          <n-descriptions-item label="机柜">
            {{ deviceDetailModal.row?.cabinet_name || '-' }}
          </n-descriptions-item>
          <n-descriptions-item label="U位">
            {{ formatDeviceUPosition(deviceDetailModal.row) }}
          </n-descriptions-item>
          <n-descriptions-item label="品牌">
            {{ deviceDetailModal.row?.brand || '-' }}
          </n-descriptions-item>
          <n-descriptions-item label="型号">
            {{ deviceDetailModal.row?.model || '-' }}
          </n-descriptions-item>
          <n-descriptions-item label="序列号">
            {{ deviceDetailModal.row?.serial_no || '-' }}
          </n-descriptions-item>
          <n-descriptions-item label="管理IP">
            {{ deviceDetailModal.row?.mgmt_ip || '-' }}
          </n-descriptions-item>
          <n-descriptions-item label="业务IP">
            {{ deviceDetailModal.row?.business_ip || '-' }}
          </n-descriptions-item>
          <n-descriptions-item label="备注">
            {{ deviceDetailModal.row?.remark || '-' }}
          </n-descriptions-item>
        </n-descriptions>
        <div class="detail-section">
          <h3>设备配置</h3>
          <n-empty
            v-if="!attributesToList(deviceDetailModal.row?.attributes).length"
            description="暂无配置"
          />
          <div v-else class="device-config-table">
            <div
              v-for="row in getDeviceAttributeRows(
                deviceDetailModal.row?.attributes,
                deviceDetailModal.row?.type
              )"
              :key="row.label"
              class="device-config-row"
            >
              <div class="device-config-label">{{ row.label }}</div>
              <div class="device-config-values">
                <span
                  v-for="item in row.items"
                  :key="item.label"
                  :class="{ 'is-sensitive': item.sensitive }"
                >
                  <strong>{{ item.label }}</strong>
                  {{ item.sensitive ? '仅 NOC / Admin 可见' : item.value || '-' }}
                </span>
              </div>
            </div>
          </div>
        </div>
        <template #footer>
          <div class="modal-footer">
            <n-button round @click="deviceDetailModal.show = false">关闭</n-button>
            <n-button
              v-if="hasAssetPermission('device', 'update')"
              type="primary"
              round
              @click="openDeviceModal(deviceDetailModal.row)"
              >编辑</n-button
            >
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="simpleModal.show"
        preset="card"
        :title="simpleModal.title"
        class="simple-modal"
      >
        <n-form
          ref="simpleFormRef"
          :model="simpleModal.form"
          :rules="simpleRules"
          label-placement="left"
          label-width="80"
        >
          <template v-if="simpleModal.kind === 'region'">
            <n-form-item label="区域名称" path="name">
              <n-input v-model:value="simpleModal.form.name" />
            </n-form-item>
            <n-form-item label="区域编码" path="code">
              <n-input v-model:value="simpleModal.form.code" />
            </n-form-item>
          </template>
          <template v-if="simpleModal.kind === 'location'">
            <n-form-item label="所属区域" path="region_id">
              <n-select v-model:value="simpleModal.form.region_id" :options="regionOptions" />
            </n-form-item>
            <n-form-item label="位置名称" path="name">
              <n-input v-model:value="simpleModal.form.name" />
            </n-form-item>
            <n-form-item label="位置类型">
              <n-radio-group v-model:value="simpleModal.form.type">
                <n-radio-button :value="0">库存</n-radio-button>
                <n-radio-button :value="1">机房</n-radio-button>
              </n-radio-group>
            </n-form-item>
            <n-form-item label="地址">
              <n-input v-model:value="simpleModal.form.address" />
            </n-form-item>
          </template>
          <template v-if="simpleModal.kind === 'cabinet'">
            <n-form-item label="所属位置" path="location_id">
              <n-select
                v-model:value="simpleModal.form.location_id"
                filterable
                :options="locationOptions"
              />
            </n-form-item>
            <n-form-item label="机柜名称" path="name">
              <n-input v-model:value="simpleModal.form.name" />
            </n-form-item>
            <n-form-item label="机柜编码">
              <n-input v-model:value="simpleModal.form.code" />
            </n-form-item>
            <n-form-item label="容量U数">
              <n-input-number v-model:value="simpleModal.form.capacity_u" :min="1" />
            </n-form-item>
          </template>
          <n-form-item label="备注">
            <n-input v-model:value="simpleModal.form.remark" type="textarea" />
          </n-form-item>
          <n-form-item label="启用">
            <n-switch v-model:value="simpleModal.form.status" />
          </n-form-item>
        </n-form>
        <template #footer>
          <div class="modal-footer">
            <n-button
              v-if="simpleModal.form.id && canDeleteSimple"
              type="error"
              ghost
              round
              @click="deleteSimple"
              >删除</n-button
            >
            <span></span>
            <CButton
              show-cancel
              :show-save="canSaveSimple"
              :save-loading="simpleModal.submitting"
              @cancel="simpleModal.show = false"
              @save="submitSimple"
            />
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="brandModal.show"
        preset="card"
        title="品牌型号维护"
        class="simple-modal"
      >
        <div class="category-editor">
          <div class="category-add">
            <n-input v-model:value="brandModal.brandName" placeholder="新增品牌" />
            <n-button type="primary" round @click="addDeviceBrand">添加</n-button>
          </div>
          <div
            v-for="brand in deviceBrandTree"
            :key="brand.id || brand.value"
            class="category-block"
          >
            <div class="category-title">
              <strong>{{ brand.label }}</strong>
              <n-button text type="error" round @click="deleteDeviceBrand(brand)">删除</n-button>
            </div>
            <div class="subcategory-list">
              <n-tag
                v-for="model in brand.models"
                :key="model.id || model.value"
                closable
                @close="deleteDeviceModel(model)"
              >
                {{ model.label }}
              </n-tag>
            </div>
            <div class="category-add">
              <n-input v-model:value="brandModal.modelDrafts[brand.value]" placeholder="新增型号" />
              <n-button secondary round @click="addDeviceModel(brand)">添加型号</n-button>
            </div>
          </div>
        </div>
      </n-modal>

      <n-modal
        v-model:show="categoryModal.show"
        preset="card"
        title="分类维护"
        class="simple-modal"
      >
        <div class="category-editor">
          <div class="category-add">
            <n-input v-model:value="categoryModal.categoryName" placeholder="新增分类" />
            <n-button type="primary" round @click="addInventoryCategory">添加</n-button>
          </div>
          <div
            v-for="category in inventoryCategoryTree"
            :key="category.id || category.value"
            class="category-block"
          >
            <div class="category-title">
              <strong>{{ category.label }}</strong>
              <n-button text type="error" round @click="deleteInventoryCategory(category)"
                >删除</n-button
              >
            </div>
            <div class="subcategory-list">
              <n-tag
                v-for="child in category.children"
                :key="child.id || child.value"
                closable
                @close="deleteInventorySubtype(category, child)"
              >
                {{ child.label }}
              </n-tag>
            </div>
            <div class="category-add">
              <n-input
                v-model:value="categoryModal.subtypeDrafts[category.value]"
                placeholder="新增子类"
              />
              <n-button secondary round @click="addInventorySubtype(category)">添加子类</n-button>
            </div>
          </div>
        </div>
      </n-modal>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton } from 'naive-ui'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'
import CButton from '@/components/public/CButton.vue'
import { usePermissionStore, useUserStore } from '@/store'

defineOptions({ name: 'AssetManagement' })

const treeData = ref([])
const selectedNode = ref(null)
const selectedKeys = ref([])
const expandedKeys = ref([])
const devices = ref([])
const rackDevices = ref([])
const selectedRackDevice = ref(null)
const inventoryItems = ref([])
const regions = ref([])
const locations = ref([])
const cabinets = ref([])
const deviceBrandTree = ref([])
const deviceFormRef = ref(null)
const inventoryFormRef = ref(null)
const simpleFormRef = ref(null)
const inventoryImportInputRef = ref(null)
const permissionStore = usePermissionStore()
const userStore = useUserStore()
const viewMode = ref('table')

const loading = reactive({
  tree: false,
  list: false,
  rack: false,
  inventoryExport: false,
  inventoryImport: false,
  saleRecords: false,
  stockFlows: false,
})
const filters = reactive({
  keyword: '',
  deviceType: null,
  deviceStatus: null,
  inventoryType: '',
  inventorySubtype: '',
})
const inventorySorter = reactive({
  columnKey: '',
  order: '',
})
const pagination = reactive({
  page: 1,
  pageSize: 10,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
})

const deviceModal = reactive({ show: false, submitting: false, form: createEmptyDevice() })
const deviceDetailModal = reactive({ show: false, row: null })
const inventoryModal = reactive({ show: false, submitting: false, form: createEmptyInventory() })
const saleModal = reactive({
  show: false,
  submitting: false,
  inventory: null,
  inventoryLabel: '',
  maxQuantity: 1,
  form: createEmptySaleForm(),
})
const saleRecords = ref([])
const stockFlows = ref([])
const saleRecordsModal = reactive({ show: false, loading: false })
const stockFlowsModal = reactive({ show: false, loading: false })
const saleRecordsPagination = reactive({
  page: 1,
  pageSize: 10,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
})
const stockFlowsPagination = reactive({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [20, 50, 100],
})
const simpleModal = reactive({
  show: false,
  submitting: false,
  kind: 'region',
  title: '',
  form: {},
})
const categoryModal = reactive({
  show: false,
  categoryName: '',
  subtypeDrafts: {},
})
const brandModal = reactive({
  show: false,
  brandName: '',
  modelDrafts: {},
})

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
  { label: '使用', value: 1 },
  { label: '维护', value: 2 },
  { label: '故障', value: 3 },
  { label: '下架', value: 4 },
  { label: '报废', value: 5 },
]

const createOptions = [
  { label: '新增区域', key: 'region' },
  { label: '新增位置', key: 'location' },
  { label: '新增机柜', key: 'cabinet' },
]

const assetResourcePathMap = {
  region: 'region',
  location: 'location',
  cabinet: 'cabinet',
  device: 'device',
  deviceBrand: 'device-brand',
  deviceModel: 'device-model',
  inventory: 'inventory',
  inventoryCategory: 'inventory-category',
  inventorySale: 'inventory-sale',
  inventoryFlow: 'inventory-flow',
}

const assetActionMethodMap = {
  list: 'get',
  get: 'get',
  create: 'post',
  update: 'post',
  delete: 'delete',
  export: 'get',
  import: 'post',
  cancel: 'post',
}

const inventoryAttributeTemplateMap = {
  光模块: ['发送波长', '接收波长', '模式', '兼容性', '传输距离'],
  光纤: ['芯类型', '封装类型', '长度'],
  网线: ['接口类型', '长度'],
  电源线: ['长度'],
}

const deviceAttributeTemplateMap = {
  0: [
    'CPU数量',
    'CPU型号',
    '内存数量',
    '内存大小',
    '磁盘数量',
    '磁盘大小',
    'IPMI用户名',
    'IPMI密码',
  ],
  1: ['版本', '补丁', 'snmp版本', 'snmp团体名'],
}
const deviceAttributeTemplateKeys = new Set(Object.values(deviceAttributeTemplateMap).flat())

const inventoryCategoryTree = ref([])
const inventoryTypeOptions = computed(() =>
  inventoryCategoryTree.value.map(({ label, value }) => ({ label, value }))
)
const deviceBrandOptions = computed(() =>
  deviceBrandTree.value.map(({ label, value }) => ({ label, value }))
)
const deviceModelOptions = computed(() => {
  const brand = deviceBrandTree.value.find((item) => item.value === deviceModal.form.brand)
  return (brand?.models || []).map(({ label, value }) => ({ label, value }))
})

const deviceRules = {
  cabinet_id: {
    required: true,
    type: 'number',
    message: '请选择机柜',
    trigger: ['change', 'blur'],
  },
  name: { required: true, message: '请输入设备名称', trigger: ['input', 'blur'] },
}

const inventoryRules = {
  location_id: {
    required: true,
    type: 'number',
    message: '请选择库存位置',
    trigger: ['change', 'blur'],
  },
  type: { required: true, message: '请输入类型', trigger: ['input', 'blur'] },
  quantity: { required: true, type: 'number', message: '请输入数量', trigger: ['change', 'blur'] },
}

const simpleRules = {
  name: { required: true, message: '请输入名称', trigger: ['input', 'blur'] },
  code: { required: true, message: '请输入编码', trigger: ['input', 'blur'] },
  region_id: { required: true, type: 'number', message: '请选择区域', trigger: ['change', 'blur'] },
  location_id: {
    required: true,
    type: 'number',
    message: '请选择位置',
    trigger: ['change', 'blur'],
  },
}

const selectedLabel = computed(() => selectedNode.value?.label || '全部资产')
const selectedLocation = computed(() => {
  if (selectedNode.value?.type === 'location')
    return locations.value.find((item) => item.id === selectedNode.value.raw_id)
  if (selectedNode.value?.type === 'cabinet') {
    const cabinet = cabinets.value.find((item) => item.id === selectedNode.value.raw_id)
    return locations.value.find((item) => item.id === cabinet?.location_id)
  }
  return null
})
const isInventoryView = computed(() => selectedLocation.value?.type === 0)
const currentCabinet = computed(() => {
  if (selectedNode.value?.type !== 'cabinet') return null
  return cabinets.value.find((item) => item.id === selectedNode.value.raw_id) || null
})
const canShowRackView = computed(() => !isInventoryView.value && selectedNode.value?.type === 'cabinet')
const rackCapacity = computed(() => Math.max(Number(currentCabinet.value?.capacity_u) || 42, 1))
const permittedCreateOptions = computed(() =>
  createOptions.filter((item) => hasAssetPermission(item.key, 'create'))
)

const regionOptions = computed(() =>
  regions.value.map((item) => ({ label: `${item.name} (${item.code})`, value: item.id }))
)
const locationOptions = computed(() =>
  locations.value.map((item) => {
    const region = regions.value.find((region) => region.id === item.region_id)
    return {
      label: `${region?.name || '-'} / ${item.type === 0 ? '库存' : '机房'} / ${item.name}`,
      value: item.id,
    }
  })
)
const inventoryLocationOptions = computed(() =>
  locations.value
    .filter((item) => item.type === 0)
    .map((item) => {
      const region = regions.value.find((region) => region.id === item.region_id)
      return { label: `${region?.name || '-'} / ${item.name}`, value: item.id }
    })
)

const filterInventorySubtypeOptions = computed(() =>
  getInventorySubtypeOptions(filters.inventoryType)
)

const modalInventorySubtypeOptions = computed(() =>
  getInventorySubtypeOptions(inventoryModal.form.type)
)

const cabinetOptions = computed(() =>
  cabinets.value.map((item) => {
    const location = locations.value.find((location) => location.id === item.location_id)
    return { label: `${location?.name || '-'} / ${item.name}`, value: item.id }
  })
)
const contextActionText = computed(() => {
  if (!selectedNode.value) return '新增区域'
  if (selectedNode.value.type === 'region') return '编辑区域'
  if (selectedNode.value.type === 'location') return '编辑位置'
  return '编辑机柜'
})
const contextIcon = computed(() => {
  if (!selectedNode.value) return 'mdi:map-marker-plus-outline'
  if (selectedNode.value.type === 'region') return 'mdi:map-marker-radius-outline'
  if (selectedNode.value.type === 'location') return 'mdi:warehouse'
  return 'mdi:server-network'
})
const canUseContextAction = computed(() => {
  const resource = selectedNode.value?.type || 'region'
  const action = selectedNode.value ? 'update' : 'create'
  return hasAssetPermission(resource, action)
})
const canUsePrimaryAction = computed(() =>
  hasAssetPermission(isInventoryView.value ? 'inventory' : 'device', 'create')
)
const canMaintainCategories = computed(
  () =>
    hasAssetPermission('inventoryCategory', 'create') ||
    hasAssetPermission('inventoryCategory', 'update') ||
    hasAssetPermission('inventoryCategory', 'delete')
)
const canMaintainDeviceBrands = computed(
  () =>
    hasAssetPermission('deviceBrand', 'create') ||
    hasAssetPermission('deviceBrand', 'delete') ||
    hasAssetPermission('deviceModel', 'create') ||
    hasAssetPermission('deviceModel', 'delete')
)
const canSaveSimple = computed(() =>
  hasAssetPermission(simpleModal.kind, simpleModal.form.id ? 'update' : 'create')
)
const canDeleteSimple = computed(() => hasAssetPermission(simpleModal.kind, 'delete'))
const canSaveInventory = computed(() =>
  hasAssetPermission('inventory', inventoryModal.form.id ? 'update' : 'create')
)
const canExportInventory = computed(() => hasAssetPermission('inventory', 'export'))
const canImportInventory = computed(() => hasAssetPermission('inventory', 'import'))
const canCreateInventorySale = computed(() => hasAssetPermission('inventorySale', 'create'))
const canViewInventorySales = computed(() => hasAssetPermission('inventorySale', 'list'))
const canCancelInventorySale = computed(() => hasAssetPermission('inventorySale', 'cancel'))
const canViewInventoryFlows = computed(() => hasAssetPermission('inventoryFlow', 'list'))
const canSaveDevice = computed(() =>
  hasAssetPermission('device', deviceModal.form.id ? 'update' : 'create')
)
const hasGlobalKeyword = computed(() => Boolean(String(filters.keyword || '').trim()))
const saleAmount = computed(() =>
  ((Number(saleModal.form.quantity) || 0) * (Number(saleModal.form.unit_price) || 0)).toFixed(2)
)
const rackPlacedDevices = computed(() =>
  rackDevices.value
    .map((device) => {
      const start = Number(device.u_position)
      const height = Math.max(Number(device.u_height) || 1, 1)
      if (!start || start < 1 || start > rackCapacity.value) return null
      return {
        device,
        start,
        height,
        end: Math.min(start + height - 1, rackCapacity.value),
      }
    })
    .filter(Boolean)
)
const rackUnits = computed(() => {
  const units = []
  for (let no = rackCapacity.value; no >= 1; no -= 1) {
    const occupants = rackPlacedDevices.value.filter((item) => item.start <= no && item.end >= no)
    units.push({
      no,
      occupied: occupants.length > 0,
      conflict: occupants.length > 1,
    })
  }
  return units
})
const rackConflictCount = computed(() => rackUnits.value.filter((unit) => unit.conflict).length)
const rackUsedUnits = computed(() => rackUnits.value.filter((unit) => unit.occupied).length)
const rackBlocks = computed(() =>
  rackPlacedDevices.value.map((item) => ({
    ...item,
    conflict: rackPlacedDevices.value.some(
      (other) =>
        other.device.id !== item.device.id && other.start <= item.end && other.end >= item.start
    ),
  }))
)

const inventoryColumns = computed(() => [
  {
    title: '分类',
    key: 'type',
    width: 120,
    sorter: true,
    sortOrder: inventorySorter.columnKey === 'type' ? inventorySorter.order : false,
  },
  {
    title: '子类',
    key: 'subtype',
    width: 120,
    sorter: true,
    sortOrder: inventorySorter.columnKey === 'subtype' ? inventorySorter.order : false,
  },
  ...(hasGlobalKeyword.value
    ? [
        {
          title: '区域 / 库房',
          key: 'location',
          width: 190,
          render: renderInventoryLocation,
        },
      ]
    : []),
  {
    title: '数量',
    key: 'quantity',
    width: 110,
    sorter: true,
    sortOrder: inventorySorter.columnKey === 'quantity' ? inventorySorter.order : false,
    render: renderInventoryQuantity,
  },
  {
    title: '告警阈值',
    key: 'threshold',
    width: 110,
    render(row) {
      return Number(row.threshold || 0) > 0 ? row.threshold : '-'
    },
  },
  {
    title: '成本价',
    key: 'cost_price',
    width: 110,
    align: 'right',
    sorter: true,
    sortOrder: inventorySorter.columnKey === 'cost_price' ? inventorySorter.order : false,
    render(row) {
      return formatPrice(row.cost_price)
    },
  },
  {
    title: '默认售价',
    key: 'sale_price',
    width: 110,
    align: 'right',
    sorter: true,
    sortOrder: inventorySorter.columnKey === 'sale_price' ? inventorySorter.order : false,
    render(row) {
      return formatPrice(row.sale_price)
    },
  },
  {
    title: '扩展属性',
    key: 'attributes',
    minWidth: 360,
    render(row) {
      return renderInventoryAttributes(row)
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 290,
    render(row) {
      return renderInventoryActions(row)
    },
  },
])

const saleRecordColumns = computed(() => [
  { title: '销售单号', key: 'sale_no', width: 170 },
  { title: '客户', key: 'customer_name', width: 140, ellipsis: { tooltip: true } },
  { title: '销售日期', key: 'sale_date', width: 120 },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render(row) {
      return row.status === 2 ? '已取消' : '已确认'
    },
  },
  { title: '金额', key: 'total_amount', width: 110 },
  {
    title: '明细',
    key: 'items',
    minWidth: 260,
    render(row) {
      const text = (row.items || [])
        .map((item) => `${item.type}/${item.subtype || '-'} x ${item.quantity}`)
        .join('；')
      return h('span', { class: 'device-remark', title: text }, text || '-')
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render(row) {
      if (row.status === 2 || !canCancelInventorySale.value) return '-'
      return h(
        NButton,
        {
          size: 'tiny',
          type: 'warning',
          secondary: true,
          round: true,
          onClick: () => cancelSaleOrder(row),
        },
        { default: () => '取消' }
      )
    },
  },
])

const stockFlowColumns = [
  { title: '时间', key: 'created_at', width: 170 },
  { title: '库存项', key: 'inventory_type', width: 150 },
  { title: '子类', key: 'inventory_subtype', width: 120 },
  { title: '类型', key: 'flow_type', width: 120 },
  { title: '变更前', key: 'quantity_before', width: 90 },
  { title: '变更', key: 'quantity_change', width: 90 },
  { title: '变更后', key: 'quantity_after', width: 90 },
  { title: '备注', key: 'remark', ellipsis: { tooltip: true } },
]

function renderInventoryLocation(row) {
  return h('div', { class: 'inventory-location-cell' }, [
    h('span', { class: 'device-meta-line' }, row.region_name || '-'),
    h(
      'button',
      {
        class: 'detail-link location-link',
        title: row.location_name || '-',
        onClick: () => selectInventoryLocation(row),
      },
      row.location_name || '-'
    ),
  ])
}

function renderInventoryQuantity(row) {
  const quantity = Number(row.quantity || 0)
  const threshold = Number(row.threshold || 0)
  const isEmpty = quantity <= 0
  const isLow = isEmpty || (threshold > 0 && quantity < threshold)
  return h(
    'span',
    {
      class: ['inventory-quantity-badge', isLow ? 'is-low' : ''],
      title: isEmpty ? '库存已为 0' : isLow ? `低于告警阈值 ${threshold}` : '',
    },
    String(quantity)
  )
}

function formatPrice(value) {
  const number = Number(value || 0)
  if (!number) return '-'
  return number.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function renderInventoryActions(row) {
  const actions = []
  if (hasAssetPermission('inventory', 'create')) {
    actions.push(
      h(
        NButton,
        {
          size: 'tiny',
          type: 'success',
          secondary: true,
          round: true,
          onClick: () => cloneInventory(row),
        },
        {
          icon: () => h(TheIcon, { icon: 'mdi:content-copy', size: 14 }),
          default: () => '克隆',
        }
      )
    )
  }
  if (hasAssetPermission('inventory', 'update')) {
    actions.push(
      h(
        NButton,
        {
          size: 'tiny',
          type: 'info',
          secondary: true,
          round: true,
          onClick: () => openInventoryModal(row),
        },
        {
          icon: () => h(TheIcon, { icon: 'material-symbols:edit-outline-rounded', size: 14 }),
          default: () => '编辑',
        }
      )
    )
  }
  if (hasAssetPermission('inventory', 'delete')) {
    actions.push(
      h(
        NButton,
        {
          size: 'tiny',
          type: 'error',
          secondary: true,
          round: true,
          onClick: () => deleteInventory(row),
        },
        {
          icon: () => h(TheIcon, { icon: 'material-symbols:delete-outline-rounded', size: 14 }),
          default: () => '删除',
        }
      )
    )
  }
  if (!actions.length) return '-'
  return h('div', { class: 'asset-row-actions' }, actions)
}

const deviceColumns = computed(() => [
  {
    title: '设备名称',
    key: 'name',
    minWidth: 230,
    render: renderDeviceName,
  },
  { title: '类型', key: 'type', width: 120, render: renderDeviceType },
  { title: '状态', key: 'status', width: 110, render: renderDeviceStatus },
  {
    title: 'U位',
    key: 'u_position',
    width: 100,
    render: renderDeviceUPosition,
  },
  { title: 'IP 信息', key: 'ip', minWidth: 210, render: renderDeviceIpGroup },
  { title: '备注', key: 'remark', minWidth: 170, render: renderDeviceRemark },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    render(row) {
      if (!hasAssetPermission('device', 'update') && !hasAssetPermission('device', 'delete')) {
        return '-'
      }
      return h(CButton, {
        showEdit: hasAssetPermission('device', 'update'),
        showDelete: hasAssetPermission('device', 'delete'),
        class: 'asset-row-actions',
        size: 'tiny',
        spaceSize: 4,
        wrap: false,
        editLoading: false,
        deleteLoading: false,
        onEdit: () => openDeviceModal(row),
        onDelete: () => deleteDevice(row),
      })
    },
  },
])

function createEmptyDevice() {
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
    status: 1,
    mgmt_ip: '',
    business_ip: '',
    owner: '',
    purchase_date: null,
    warranty_expire: null,
    attributes: {},
    attributeList: [],
    remark: '',
  }
}

function createEmptyInventory() {
  return {
    location_id: null,
    type: '',
    subtype: '',
    quantity: 1,
    threshold: 0,
    cost_price: 0,
    sale_price: 0,
    attributes: {},
    attributeList: [],
    remark: '',
    status: true,
  }
}

function createEmptySaleForm() {
  return {
    customer_name: '',
    customer_contact: '',
    sale_date: new Date().toISOString().slice(0, 10),
    quantity: 1,
    unit_price: 0,
    remark: '',
  }
}

function assetPermissionKey(resource, action) {
  const path = assetResourcePathMap[resource]
  const method = assetActionMethodMap[action]
  if (!path || !method) return ''
  return `${method}/api/v1/asset/${path}/${action}`
}

function hasAssetPermission(resource, action) {
  if (userStore.isSuperUser) return true
  const permission = assetPermissionKey(resource, action)
  return Boolean(permission && permissionStore.apis.includes(permission))
}

function warnNoPermission() {
  window.$message?.warning('暂无资产管理操作权限')
}

async function refreshAll() {
  await Promise.all([loadMeta(), loadTree()])
  await loadCurrentList()
}

async function loadMeta() {
  const [regionRes, locationRes, cabinetRes] = await Promise.all([
    api.assetApi.regions({ page_size: 1000 }),
    api.assetApi.locations({ page_size: 1000 }),
    api.assetApi.cabinets({ page_size: 1000 }),
    loadInventoryCategories(),
    loadDeviceBrands(),
  ])
  regions.value = regionRes.data || []
  locations.value = locationRes.data || []
  cabinets.value = cabinetRes.data || []
}

async function loadInventoryCategories() {
  try {
    const res = await api.assetApi.inventoryCategories()
    inventoryCategoryTree.value = normalizeInventoryCategoryTree(res.data || [])
  } catch {
    inventoryCategoryTree.value = []
  }
}

async function loadDeviceBrands() {
  try {
    const res = await api.assetApi.deviceBrands()
    deviceBrandTree.value = normalizeDeviceBrandTree(res.data || [])
  } catch {
    deviceBrandTree.value = []
  }
}

async function loadTree() {
  loading.tree = true
  try {
    const res = await api.assetApi.tree()
    treeData.value = res.data || []
    expandedKeys.value = collectTreeKeys(treeData.value)
  } finally {
    loading.tree = false
  }
}

function collectTreeKeys(nodes = []) {
  return nodes.flatMap((node) => [
    node.id,
    ...collectTreeKeys(node.children || []),
  ])
}

async function loadCurrentList() {
  if (isInventoryView.value) {
    await loadInventory()
  } else {
    await loadDevices()
  }
}

async function loadDevices() {
  loading.list = true
  try {
    const res = await api.assetApi.devices({
      page: pagination.page,
      page_size: pagination.pageSize,
      keyword: filters.keyword || undefined,
      type: filters.deviceType ?? undefined,
      status: filters.deviceStatus ?? undefined,
      ...getSelectedParams({ ignoreSelection: hasGlobalKeyword.value }),
    })
    devices.value = res.data || []
    pagination.itemCount = res.total || 0
    if (canShowRackView.value) {
      await loadRackDevices()
    } else {
      rackDevices.value = []
      selectedRackDevice.value = null
      viewMode.value = 'table'
    }
  } finally {
    loading.list = false
  }
}

async function loadRackDevices() {
  if (!canShowRackView.value) {
    rackDevices.value = []
    selectedRackDevice.value = null
    return
  }
  loading.rack = true
  try {
    const res = await api.assetApi.devices({
      page: 1,
      page_size: 1000,
      cabinet_id: selectedNode.value.raw_id,
      keyword: filters.keyword || undefined,
      type: filters.deviceType ?? undefined,
      status: filters.deviceStatus ?? undefined,
    })
    rackDevices.value = res.data || []
    if (selectedRackDevice.value) {
      selectedRackDevice.value =
        rackDevices.value.find((item) => item.id === selectedRackDevice.value.id) || null
    }
  } finally {
    loading.rack = false
  }
}

async function loadInventory() {
  loading.list = true
  try {
    const res = await api.assetApi.inventory({
      page: pagination.page,
      page_size: pagination.pageSize,
      keyword: filters.keyword || undefined,
      type: filters.inventoryType || undefined,
      subtype: filters.inventorySubtype || undefined,
      sort_by: inventorySorter.columnKey || undefined,
      sort_order: inventorySorter.order || undefined,
      ...getSelectedParams({ ignoreSelection: hasGlobalKeyword.value }),
    })
    inventoryItems.value = res.data || []
    pagination.itemCount = res.total || 0
  } finally {
    loading.list = false
  }
}

function getSelectedParams({ ignoreSelection = false } = {}) {
  if (ignoreSelection || !selectedNode.value) return {}
  if (isInventoryView.value && selectedNode.value.type === 'cabinet') {
    return { location_id: selectedLocation.value?.id }
  }
  const keyMap = { region: 'region_id', location: 'location_id', cabinet: 'cabinet_id' }
  return { [keyMap[selectedNode.value.type]]: selectedNode.value.raw_id }
}

function handleTreeSelect(keys, options) {
  selectedKeys.value = keys
  selectedNode.value = options?.[0] || null
  if (!canShowRackView.value) {
    viewMode.value = 'table'
    selectedRackDevice.value = null
  }
  if (hasGlobalKeyword.value) {
    filters.keyword = ''
  }
  pagination.page = 1
  loadCurrentList()
}

function selectInventoryLocation(row) {
  if (!row.location_id) return
  filters.keyword = ''
  selectedKeys.value = [`location-${row.location_id}`]
  selectedNode.value = {
    id: `location-${row.location_id}`,
    raw_id: row.location_id,
    label: row.location_name || '库房',
    type: 'location',
  }
  pagination.page = 1
  loadInventory()
}

function handlePageChange(page) {
  pagination.page = page
  loadCurrentList()
}

function handlePageSizeChange(pageSize) {
  pagination.pageSize = pageSize
  pagination.page = 1
  loadCurrentList()
}

function searchCurrentList() {
  pagination.page = 1
  loadCurrentList()
}

function handleSorterChange(sorter) {
  if (!isInventoryView.value) return
  const currentSorter = Array.isArray(sorter) ? sorter[0] : sorter
  inventorySorter.columnKey = currentSorter?.order ? currentSorter.columnKey || '' : ''
  inventorySorter.order = currentSorter?.order || ''
  pagination.page = 1
  loadInventory()
}

function resetFilters() {
  filters.keyword = ''
  filters.deviceType = null
  filters.deviceStatus = null
  filters.inventoryType = ''
  filters.inventorySubtype = ''
  inventorySorter.columnKey = ''
  inventorySorter.order = ''
  pagination.page = 1
  loadCurrentList()
}

function switchAssetView(mode) {
  viewMode.value = mode
  if (mode === 'rack' && canShowRackView.value && !rackDevices.value.length) {
    loadRackDevices()
  }
}

function selectRackDevice(device) {
  selectedRackDevice.value = device
}

function openPrimaryModal(row = null) {
  if (!row && !canUsePrimaryAction.value) {
    warnNoPermission()
    return
  }
  if (isInventoryView.value) openInventoryModal(row)
  else openDeviceModal(row)
}

function handleCreateSelect(kind) {
  if (!hasAssetPermission(kind, 'create')) {
    warnNoPermission()
    return
  }
  openSimpleModal(kind)
}

function openContextModal() {
  if (!canUseContextAction.value) {
    warnNoPermission()
    return
  }
  if (!selectedNode.value) openSimpleModal('region')
  else openSimpleModal(selectedNode.value.type, selectedNode.value)
}

function openSimpleModal(kind, node = null) {
  simpleModal.kind = kind
  simpleModal.title = `${node ? '编辑' : '新增'}${kindName(kind)}`
  simpleModal.form = createSimpleForm(kind, node)
  simpleModal.show = true
}

function createSimpleForm(kind, node) {
  if (kind === 'region') {
    const row = node ? regions.value.find((item) => item.id === node.raw_id) : null
    return {
      id: row?.id,
      name: row?.name || '',
      code: row?.code || '',
      remark: row?.remark || '',
      status: row?.status ?? true,
    }
  }
  if (kind === 'location') {
    const row = node ? locations.value.find((item) => item.id === node.raw_id) : null
    return {
      id: row?.id,
      region_id: row?.region_id || selectedRegionId(),
      name: row?.name || '',
      type: row?.type ?? 1,
      address: row?.address || '',
      remark: row?.remark || '',
      status: row?.status ?? true,
    }
  }
  const row = node ? cabinets.value.find((item) => item.id === node.raw_id) : null
  return {
    id: row?.id,
    location_id: row?.location_id || selectedLocationId(),
    name: row?.name || '',
    code: row?.code || '',
    capacity_u: row?.capacity_u || 42,
    row: row?.row || '',
    column: row?.column || '',
    remark: row?.remark || '',
    status: row?.status ?? true,
  }
}

function selectedRegionId() {
  if (selectedNode.value?.type === 'region') return selectedNode.value.raw_id
  return selectedLocation.value?.region_id || regionOptions.value[0]?.value || null
}

function selectedLocationId() {
  if (selectedNode.value?.type === 'location') return selectedNode.value.raw_id
  if (selectedNode.value?.type === 'cabinet')
    return cabinets.value.find((item) => item.id === selectedNode.value.raw_id)?.location_id
  return locationOptions.value[0]?.value || null
}

async function submitSimple() {
  if (!canSaveSimple.value) {
    warnNoPermission()
    return
  }
  await simpleFormRef.value?.validate()
  simpleModal.submitting = true
  try {
    const map = {
      region: [api.assetApi.createRegion, api.assetApi.updateRegion],
      location: [api.assetApi.createLocation, api.assetApi.updateLocation],
      cabinet: [api.assetApi.createCabinet, api.assetApi.updateCabinet],
    }
    const [createFn, updateFn] = map[simpleModal.kind]
    await (simpleModal.form.id ? updateFn(simpleModal.form) : createFn(simpleModal.form))
    window.$message?.success('保存成功')
    simpleModal.show = false
    await refreshAll()
  } finally {
    simpleModal.submitting = false
  }
}

async function deleteSimple() {
  if (!canDeleteSimple.value) {
    warnNoPermission()
    return
  }
  const id = simpleModal.form.id
  if (!id) return
  const map = {
    region: [api.assetApi.deleteRegion, 'region_id'],
    location: [api.assetApi.deleteLocation, 'location_id'],
    cabinet: [api.assetApi.deleteCabinet, 'cabinet_id'],
  }
  const [deleteFn, key] = map[simpleModal.kind]
  await deleteFn({ [key]: id })
  window.$message?.success('删除成功')
  simpleModal.show = false
  selectedKeys.value = []
  selectedNode.value = null
  await refreshAll()
}

function openInventoryModal(row = null) {
  if (row && !hasAssetPermission('inventory', 'update')) {
    warnNoPermission()
    return
  }
  if (!row && !hasAssetPermission('inventory', 'create')) {
    warnNoPermission()
    return
  }
  inventoryModal.form = row
    ? {
        ...createEmptyInventory(),
        ...row,
        attributeList: attributesToList(row.attributes),
      }
    : {
        ...createEmptyInventory(),
        location_id:
          selectedLocation.value?.type === 0
            ? selectedLocation.value.id
            : inventoryLocationOptions.value[0]?.value || null,
      }
  if (!row) applyInventoryAttributeTemplate()
  inventoryModal.show = true
}

function cloneInventory(row) {
  if (!hasAssetPermission('inventory', 'create')) {
    warnNoPermission()
    return
  }
  const cloned = {
    ...createEmptyInventory(),
    ...row,
    attributes: { ...(row.attributes || {}) },
    attributeList: attributesToList(row.attributes),
  }
  delete cloned.id
  inventoryModal.form = cloned
  inventoryModal.show = true
}

async function submitInventory() {
  if (!canSaveInventory.value) {
    warnNoPermission()
    return
  }
  await inventoryFormRef.value?.validate()
  inventoryModal.submitting = true
  try {
    const submit = inventoryModal.form.id
      ? api.assetApi.updateInventory
      : api.assetApi.createInventory
    const payload = {
      ...inventoryModal.form,
      attributes: attributeListToObject(inventoryModal.form.attributeList),
    }
    delete payload.attributeList
    await submit(payload)
    window.$message?.success('保存成功')
    inventoryModal.show = false
    await loadInventory()
  } finally {
    inventoryModal.submitting = false
  }
}

function openSaleModal(row) {
  if (!canCreateInventorySale.value) {
    warnNoPermission()
    return
  }
  saleModal.inventory = row
  saleModal.inventoryLabel = `${row.type || '-'} / ${row.subtype || '-'}，当前库存 ${row.quantity}`
  saleModal.maxQuantity = Math.max(Number(row.quantity || 0), 1)
  saleModal.form = createEmptySaleForm()
  saleModal.show = true
}

async function submitInventorySale() {
  if (!saleModal.inventory) return
  if (!String(saleModal.form.customer_name || '').trim()) {
    window.$message?.warning('请输入客户名称')
    return
  }
  if (Number(saleModal.form.quantity || 0) <= 0) {
    window.$message?.warning('请输入销售数量')
    return
  }
  saleModal.submitting = true
  try {
    await api.assetApi.createInventorySale({
      customer_name: saleModal.form.customer_name,
      customer_contact: saleModal.form.customer_contact,
      sale_date: saleModal.form.sale_date,
      remark: saleModal.form.remark,
      items: [
        {
          inventory_id: saleModal.inventory.id,
          quantity: saleModal.form.quantity,
          unit_price: saleModal.form.unit_price,
          remark: saleModal.form.remark,
        },
      ],
    })
    window.$message?.success('销售单创建成功')
    saleModal.show = false
    await loadInventory()
  } finally {
    saleModal.submitting = false
  }
}

async function openSaleRecords() {
  if (!canViewInventorySales.value) {
    warnNoPermission()
    return
  }
  saleRecordsPagination.page = 1
  saleRecordsModal.show = true
  await loadSaleRecords()
}

async function loadSaleRecords() {
  saleRecordsModal.loading = true
  try {
    const res = await api.assetApi.inventorySales({
      page: saleRecordsPagination.page,
      page_size: saleRecordsPagination.pageSize,
    })
    saleRecords.value = res.data || []
    saleRecordsPagination.itemCount = res.total || 0
  } finally {
    saleRecordsModal.loading = false
  }
}

function handleSaleRecordsPageChange(page) {
  saleRecordsPagination.page = page
  loadSaleRecords()
}

function handleSaleRecordsPageSizeChange(pageSize) {
  saleRecordsPagination.pageSize = pageSize
  saleRecordsPagination.page = 1
  loadSaleRecords()
}

async function cancelSaleOrder(row) {
  if (!canCancelInventorySale.value) {
    warnNoPermission()
    return
  }
  await api.assetApi.cancelInventorySale({ id: row.id, reason: '页面取消销售单' })
  window.$message?.success('销售单已取消')
  await loadSaleRecords()
  await loadInventory()
}

async function openStockFlows() {
  if (!canViewInventoryFlows.value) {
    warnNoPermission()
    return
  }
  stockFlowsPagination.page = 1
  stockFlowsModal.show = true
  await loadStockFlows()
}

async function loadStockFlows() {
  stockFlowsModal.loading = true
  try {
    const res = await api.assetApi.inventoryFlows({
      page: stockFlowsPagination.page,
      page_size: stockFlowsPagination.pageSize,
    })
    stockFlows.value = res.data || []
    stockFlowsPagination.itemCount = res.total || 0
  } finally {
    stockFlowsModal.loading = false
  }
}

function handleStockFlowsPageChange(page) {
  stockFlowsPagination.page = page
  loadStockFlows()
}

function handleStockFlowsPageSizeChange(pageSize) {
  stockFlowsPagination.pageSize = pageSize
  stockFlowsPagination.page = 1
  loadStockFlows()
}

async function deleteInventory(row) {
  if (!hasAssetPermission('inventory', 'delete')) {
    warnNoPermission()
    return
  }
  await api.assetApi.deleteInventory({ inventory_id: row.id })
  window.$message?.success('删除成功')
  loadInventory()
}

function triggerInventoryImport() {
  inventoryImportInputRef.value?.click()
}

async function exportInventory() {
  if (!canExportInventory.value) {
    warnNoPermission()
    return
  }
  loading.inventoryExport = true
  try {
    const response = await api.assetApi.exportInventory()
    const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `库存_${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } finally {
    loading.inventoryExport = false
  }
}

async function handleInventoryImport(event) {
  const file = event.target.files?.[0]
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.csv')) {
    window.$message?.error('请选择 CSV 文件')
    event.target.value = ''
    return
  }
  if (!canSaveInventory.value) {
    warnNoPermission()
    event.target.value = ''
    return
  }

  loading.inventoryImport = true
  try {
    const res = await api.assetApi.importInventory(file)
    window.$message?.success(res?.msg || '导入成功')
    await loadInventory()
  } finally {
    loading.inventoryImport = false
    event.target.value = ''
  }
}

function addInventoryAttribute() {
  inventoryModal.form.attributeList.push({ key: '', value: '' })
}

function addMissingAttributes(attributeList, template = []) {
  const existedKeys = new Set(attributeList.map((item) => String(item.key || '').trim()))
  template.forEach((key) => {
    if (!existedKeys.has(key)) {
      attributeList.push({ key, value: '' })
      existedKeys.add(key)
    }
  })
}

function applyInventoryAttributeTemplate(type = inventoryModal.form.type) {
  const template = inventoryAttributeTemplateMap[type]
  if (!template) return
  addMissingAttributes(inventoryModal.form.attributeList, template)
}

function normalizeInventoryCategoryTree(value) {
  if (!Array.isArray(value)) return []
  const result = []
  value.forEach((item) => {
    const label = String(item?.label || item?.name || item?.value || '').trim()
    const itemValue = String(item?.value || item?.name || label).trim()
    if (!label || !itemValue) return
    const children = Array.isArray(item.children)
      ? item.children
          .map((child) => {
            const childLabel = String(child?.label || child?.name || child?.value || '').trim()
            const childValue = String(child?.value || child?.name || childLabel).trim()
            if (!childLabel || !childValue) return null
            return { ...child, label: childLabel, value: childValue }
          })
          .filter(Boolean)
      : []
    result.push({ ...item, label, value: itemValue, children })
  })
  return result
}

function normalizeDeviceBrandTree(value) {
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

async function addDeviceBrand() {
  if (!hasAssetPermission('deviceBrand', 'create')) {
    warnNoPermission()
    return
  }
  const name = brandModal.brandName.trim()
  if (!name) return
  if (deviceBrandTree.value.some((item) => item.value === name)) {
    window.$message?.warning('品牌已存在')
    return
  }
  const res = await api.assetApi.createDeviceBrand({ name })
  deviceBrandTree.value = normalizeDeviceBrandTree(res.data || [])
  brandModal.brandName = ''
  window.$message?.success('品牌已添加')
}

async function deleteDeviceBrand(brand) {
  if (!hasAssetPermission('deviceBrand', 'delete')) {
    warnNoPermission()
    return
  }
  const res = await api.assetApi.deleteDeviceBrand({ brand_id: brand.id })
  deviceBrandTree.value = normalizeDeviceBrandTree(res.data || [])
  if (deviceModal.form.brand === brand.value) {
    deviceModal.form.brand = ''
    deviceModal.form.model = ''
  }
  delete brandModal.modelDrafts[brand.value]
  window.$message?.success('品牌已删除')
}

async function addDeviceModel(brand) {
  if (!hasAssetPermission('deviceModel', 'create')) {
    warnNoPermission()
    return
  }
  const name = String(brandModal.modelDrafts[brand.value] || '').trim()
  if (!name) return
  if (brand.models.some((item) => item.value === name)) {
    window.$message?.warning('型号已存在')
    return
  }
  const res = await api.assetApi.createDeviceModel({ brand_id: brand.id, name })
  deviceBrandTree.value = normalizeDeviceBrandTree(res.data || [])
  brandModal.modelDrafts[brand.value] = ''
  window.$message?.success('型号已添加')
}

async function deleteDeviceModel(model) {
  if (!hasAssetPermission('deviceModel', 'delete')) {
    warnNoPermission()
    return
  }
  const res = await api.assetApi.deleteDeviceModel({ model_id: model.id })
  deviceBrandTree.value = normalizeDeviceBrandTree(res.data || [])
  if (deviceModal.form.model === model.value) {
    deviceModal.form.model = ''
  }
  window.$message?.success('型号已删除')
}

async function addInventoryCategory() {
  if (!hasAssetPermission('inventoryCategory', 'create')) {
    warnNoPermission()
    return
  }
  const name = categoryModal.categoryName.trim()
  if (!name) return
  if (inventoryCategoryTree.value.some((item) => item.value === name)) {
    window.$message?.warning('分类已存在')
    return
  }
  const res = await api.assetApi.createInventoryCategory({ name, parent_id: null })
  inventoryCategoryTree.value = normalizeInventoryCategoryTree(res.data || [])
  categoryModal.categoryName = ''
  window.$message?.success('分类已添加')
}

async function deleteInventoryCategory(category) {
  if (!hasAssetPermission('inventoryCategory', 'delete')) {
    warnNoPermission()
    return
  }
  const value = category.value
  const res = await api.assetApi.deleteInventoryCategory({ category_id: category.id })
  inventoryCategoryTree.value = normalizeInventoryCategoryTree(res.data || [])
  if (filters.inventoryType === value) {
    filters.inventoryType = ''
    filters.inventorySubtype = ''
  }
  if (inventoryModal.form.type === value) {
    inventoryModal.form.type = ''
    inventoryModal.form.subtype = ''
  }
  delete categoryModal.subtypeDrafts[value]
  window.$message?.success('分类已删除')
}

async function addInventorySubtype(category) {
  if (!hasAssetPermission('inventoryCategory', 'create')) {
    warnNoPermission()
    return
  }
  const parentValue = category.value
  const subtype = String(categoryModal.subtypeDrafts[parentValue] || '').trim()
  if (!subtype) return
  if (category.children.some((item) => item.value === subtype)) {
    window.$message?.warning('子类已存在')
    return
  }
  const res = await api.assetApi.createInventoryCategory({
    name: subtype,
    parent_id: category.id,
  })
  inventoryCategoryTree.value = normalizeInventoryCategoryTree(res.data || [])
  categoryModal.subtypeDrafts[parentValue] = ''
  window.$message?.success('子类已添加')
}

async function deleteInventorySubtype(category, subtype) {
  if (!hasAssetPermission('inventoryCategory', 'delete')) {
    warnNoPermission()
    return
  }
  const parentValue = category.value
  const subtypeValue = subtype.value
  const res = await api.assetApi.deleteInventoryCategory({ category_id: subtype.id })
  inventoryCategoryTree.value = normalizeInventoryCategoryTree(res.data || [])
  if (filters.inventoryType === parentValue && filters.inventorySubtype === subtypeValue) {
    filters.inventorySubtype = ''
  }
  if (inventoryModal.form.type === parentValue && inventoryModal.form.subtype === subtypeValue) {
    inventoryModal.form.subtype = ''
  }
  window.$message?.success('子类已删除')
}

function getInventorySubtypeOptions(type) {
  const category = inventoryCategoryTree.value.find((item) => item.value === type)
  return (category?.children || []).map((item) => ({ label: item.label, value: item.value }))
}

function handleInventoryTypeChange() {
  const validValues = getInventorySubtypeOptions(inventoryModal.form.type).map((item) => item.value)
  if (inventoryModal.form.subtype && !validValues.includes(inventoryModal.form.subtype)) {
    inventoryModal.form.subtype = ''
  }
  applyInventoryAttributeTemplate()
}

function handleInventoryFilterTypeChange() {
  const validValues = getInventorySubtypeOptions(filters.inventoryType).map((item) => item.value)
  if (filters.inventorySubtype && !validValues.includes(filters.inventorySubtype)) {
    filters.inventorySubtype = ''
  }
}

function handleDeviceBrandChange() {
  const validValues = deviceModelOptions.value.map((item) => item.value)
  if (deviceModal.form.model && !validValues.includes(deviceModal.form.model)) {
    deviceModal.form.model = ''
  }
}

function handleDeviceTypeChange() {
  if (deviceModal.form.id) {
    applyDeviceAttributeTemplate()
  } else {
    syncDeviceAttributeTemplate()
  }
}

function removeInventoryAttribute(index) {
  inventoryModal.form.attributeList.splice(index, 1)
}

function addDeviceAttribute() {
  deviceModal.form.attributeList.push({ key: '', value: '' })
}

function removeDeviceAttribute(index) {
  deviceModal.form.attributeList.splice(index, 1)
}

function applyDeviceAttributeTemplate(type = deviceModal.form.type) {
  const template = deviceAttributeTemplateMap[Number(type)] || []
  if (!template.length) return
  addMissingAttributes(deviceModal.form.attributeList, template)
}

function syncDeviceAttributeTemplate(type = deviceModal.form.type) {
  const template = deviceAttributeTemplateMap[Number(type)] || []
  const valueMap = deviceModal.form.attributeList.reduce((result, item) => {
    const key = String(item.key || '').trim()
    if (key && !(key in result)) result[key] = item.value
    return result
  }, {})
  const customAttributes = deviceModal.form.attributeList.filter(
    (item) => item.key && !deviceAttributeTemplateKeys.has(item.key)
  )
  deviceModal.form.attributeList = [
    ...template.map((key) => ({ key, value: valueMap[key] ?? '' })),
    ...customAttributes,
  ]
}

function attributesToList(attributes) {
  if (!attributes || typeof attributes !== 'object') return []
  return Object.entries(attributes).map(([key, value]) => ({ key, value: String(value ?? '') }))
}

function getAttributeValue(attributes, key) {
  return String(attributes?.[key] ?? '')
}

function getDeviceAttributeRows(attributes, type) {
  const isSwitch = Number(type) === 1
  const groupedKeys = new Set(
    isSwitch ? deviceAttributeTemplateMap[1] : deviceAttributeTemplateMap[0]
  )
  const rows = isSwitch
    ? [
        {
          label: '交换机',
          items: [
            { label: '版本', value: getAttributeValue(attributes, '版本') },
            { label: '补丁', value: getAttributeValue(attributes, '补丁') },
            { label: 'SNMP版本', value: getAttributeValue(attributes, 'snmp版本') },
            {
              label: 'SNMP团体名',
              value: getAttributeValue(attributes, 'snmp团体名'),
              sensitive: getAttributeValue(attributes, 'snmp团体名') === '******',
            },
          ],
        },
      ]
    : [
        {
          label: 'CPU',
          items: [
            { label: '数量', value: getAttributeValue(attributes, 'CPU数量') },
            { label: '型号', value: getAttributeValue(attributes, 'CPU型号') },
          ],
        },
        {
          label: '内存',
          items: [
            { label: '数量', value: getAttributeValue(attributes, '内存数量') },
            { label: '大小', value: getAttributeValue(attributes, '内存大小') },
          ],
        },
        {
          label: '磁盘',
          items: [
            { label: '数量', value: getAttributeValue(attributes, '磁盘数量') },
            { label: '大小', value: getAttributeValue(attributes, '磁盘大小') },
          ],
        },
        {
          label: 'IPMI',
          items: [
            { label: '用户名', value: getAttributeValue(attributes, 'IPMI用户名') },
            {
              label: '密码',
              value: getAttributeValue(attributes, 'IPMI密码'),
              sensitive: getAttributeValue(attributes, 'IPMI密码') === '******',
            },
          ],
        },
      ]
  const extraItems = attributesToList(attributes)
    .filter((item) => !groupedKeys.has(item.key))
    .map((item) => ({ label: item.key, value: item.value }))
  if (extraItems.length) rows.push({ label: '其他配置', items: extraItems })
  return rows
}

function attributeListToObject(list) {
  return (list || []).reduce((result, item) => {
    const key = String(item.key || '').trim()
    if (key) result[key] = item.value
    return result
  }, {})
}

function getInventoryAttributeGroups(type, attributes) {
  const list = attributesToList(attributes)
  if (!list.length) return []

  const template = inventoryAttributeTemplateMap[type] || []
  if (!template.length) {
    return [{ label: '扩展属性', items: list }]
  }

  const groupedKeys = new Set(template)
  const templateItems = template.map((key) => list.find((item) => item.key === key)).filter(Boolean)
  const otherItems = list.filter((item) => !groupedKeys.has(item.key))
  const groups = []

  if (templateItems.length) groups.push({ label: type, items: templateItems })
  if (otherItems.length) groups.push({ label: '其他', items: otherItems })
  return groups
}

function renderInventoryAttributes(row) {
  const groups = getInventoryAttributeGroups(row.type, row.attributes)
  if (!groups.length) return '-'

  return h(
    'div',
    { class: 'attribute-tag-groups' },
    groups.map((group) =>
      h('div', { class: 'attribute-tag-group', key: group.label }, [
        h('span', { class: 'attribute-tag-group-title' }, group.label),
        ...group.items.map((item) => {
          const value = item.value || '-'
          return h(
            'span',
            {
              class: 'attribute-tag',
              key: item.key,
              title: `${item.key}: ${value}`,
            },
            [h('b', item.key), h('em', value)]
          )
        }),
      ])
    )
  )
}

function renderDeviceName(row) {
  const metaItems = [
    row.brand || row.model ? [row.brand, row.model].filter(Boolean).join(' / ') : '',
    row.serial_no ? `SN ${row.serial_no}` : '',
  ].filter(Boolean)
  return h('div', { class: 'device-name-cell' }, [
    h(
      'button',
      {
        class: 'detail-link',
        title: row.name || '-',
        onClick: () => openDeviceDetail(row),
      },
      row.name || '-'
    ),
    h(
      'div',
      { class: 'device-meta-line' },
      metaItems.length ? metaItems.map((item) => h('span', item)) : [h('span', '未填写设备信息')]
    ),
  ])
}

function renderDeviceType(row) {
  return h('span', { class: `device-type-badge device-type-${Number(row.type)}` }, [
    h('span', { class: 'device-type-dot' }),
    getDeviceType(row.type),
  ])
}

function renderDeviceStatus(row) {
  return h(
    'span',
    { class: `device-status-badge device-status-${Number(row.status)}` },
    getDeviceStatus(row.status)
  )
}

function renderDeviceUPosition(row) {
  const value = formatDeviceUPosition(row)
  return h('span', { class: ['device-u-badge', value === '-' ? 'is-empty' : ''] }, value)
}

function renderDeviceIpGroup(row) {
  const items = [
    { label: '管理', value: row.mgmt_ip },
    { label: '业务', value: row.business_ip },
  ].filter((item) => item.value)

  if (!items.length) return h('span', { class: 'muted-cell' }, '-')

  return h(
    'div',
    { class: 'device-ip-group' },
    items.map((item) =>
      h('span', { class: 'device-ip-item', key: item.label, title: item.value }, [
        h('b', item.label),
        h('em', item.value),
      ])
    )
  )
}

function renderDeviceRemark(row) {
  if (!row.remark) return h('span', { class: 'muted-cell' }, '暂无备注')
  return h('span', { class: 'device-remark', title: row.remark }, row.remark)
}

function formatDeviceUPosition(row) {
  if (!row?.u_position) return '-'
  return row.u_height > 1
    ? `${row.u_position}-${row.u_position + row.u_height - 1}U`
    : `${row.u_position}U`
}

function rackBlockStyle(block) {
  const capacity = rackCapacity.value
  return {
    gridRow: `${capacity - block.end + 1} / span ${Math.max(block.end - block.start + 1, 1)}`,
  }
}

function rackUnitGridRow(unit) {
  return String(rackCapacity.value - unit.no + 1)
}

function openDeviceDetail(row) {
  deviceDetailModal.row = row
  deviceDetailModal.show = true
}

function openDeviceModal(row = null) {
  if (row && !hasAssetPermission('device', 'update')) {
    warnNoPermission()
    return
  }
  if (!row && !hasAssetPermission('device', 'create')) {
    warnNoPermission()
    return
  }
  deviceModal.form = row
    ? {
        ...createEmptyDevice(),
        ...row,
        status: Number(row.status) || 1,
        attributeList: attributesToList(row.attributes),
      }
    : {
        ...createEmptyDevice(),
        cabinet_id:
          selectedNode.value?.type === 'cabinet' && !isInventoryView.value
            ? selectedNode.value.raw_id
            : cabinetOptions.value[0]?.value || null,
      }
  if (!row) syncDeviceAttributeTemplate()
  deviceModal.show = true
}

async function submitDevice() {
  if (!canSaveDevice.value) {
    warnNoPermission()
    return
  }
  await deviceFormRef.value?.validate()
  deviceModal.form.asset_no = deviceModal.form.name
  deviceModal.submitting = true
  try {
    const submit = deviceModal.form.id ? api.assetApi.updateDevice : api.assetApi.createDevice
    const payload = {
      ...deviceModal.form,
      attributes: attributeListToObject(deviceModal.form.attributeList),
    }
    delete payload.attributeList
    await submit(payload)
    window.$message?.success('保存成功')
    deviceModal.show = false
    await loadDevices()
  } finally {
    deviceModal.submitting = false
  }
}

async function deleteDevice(row) {
  if (!hasAssetPermission('device', 'delete')) {
    warnNoPermission()
    return
  }
  await api.assetApi.deleteDevice({ device_id: row.id })
  window.$message?.success('删除成功')
  loadDevices()
}

function kindName(kind) {
  return { region: '区域', location: '位置', cabinet: '机柜' }[kind]
}

function getDeviceType(value) {
  return deviceTypeOptions.find((item) => item.value === Number(value))?.label || '其他'
}

function getDeviceStatus(value) {
  return deviceStatusOptions.find((item) => item.value === Number(value))?.label || '未知'
}

onMounted(refreshAll)
</script>

<style scoped>
.asset-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

.asset-sidebar,
.content-panel {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
}

.panel-head h2 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 22px;
  line-height: 1.2;
}

.panel-head h2 {
  font-size: 18px;
}

.eyebrow {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.toolbar-actions,
.modal-footer {
  display: flex;
  align-items: center;
  gap: 10px;
}

.view-switch {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.hidden-file-input {
  display: none;
}

.asset-layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 16px;
  min-height: 620px;
}

.asset-sidebar,
.content-panel {
  padding: 16px;
}

.content-panel :deep(.n-data-table-th__title),
.content-panel :deep(.n-data-table-td) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content-panel :deep(.n-data-table) {
  border-radius: 8px;
}

.content-panel :deep(.n-data-table-th) {
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
}

.content-panel :deep(.n-data-table-td) {
  color: #1f2937;
  vertical-align: middle;
}

.content-panel :deep(.asset-table-row .n-data-table-td) {
  height: 62px;
  border-bottom-color: #eef2f7;
}

.content-panel :deep(.asset-table-row:hover .n-data-table-td) {
  background: #f8fbff;
}

.content-panel :deep(.asset-row-actions) {
  display: flex;
  align-items: center;
  flex-flow: row nowrap !important;
  flex-wrap: nowrap;
  gap: 6px !important;
}

.rack-visual {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 520px;
}

.rack-summary {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.rack-summary h3 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 18px;
  line-height: 1.2;
}

.rack-stats {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}

.rack-stats span {
  border: 1px solid #dbeafe;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 600;
  line-height: 24px;
  padding: 0 10px;
}

.rack-stats .rack-conflict-text {
  border-color: #fecaca;
  background: #fef2f2;
  color: #b91c1c;
}

.rack-scene {
  display: grid;
  grid-template-columns: minmax(360px, 620px) minmax(160px, 1fr);
  align-items: start;
  gap: 24px;
}

.rack-side-panel {
  grid-column: 2;
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 14px;
}

.rack-legend,
.rack-device-detail {
  min-width: 0;
}

.rack-cabinet {
  position: relative;
  border: 1px solid #1f2937;
  border-radius: 8px 8px 6px 6px;
  background:
    linear-gradient(90deg, rgba(15, 23, 42, 0.18), transparent 12%, transparent 88%, rgba(15, 23, 42, 0.2)),
    linear-gradient(180deg, #475569, #111827);
  box-shadow: 16px 18px 30px rgba(15, 23, 42, 0.18);
  padding: 18px 18px 14px;
}

.rack-top,
.rack-base {
  height: 18px;
  border-radius: 6px;
  background: linear-gradient(180deg, #64748b, #1f2937);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22);
}

.rack-top {
  margin-bottom: 10px;
}

.rack-base {
  margin-top: 10px;
}

.rack-body {
  position: relative;
  min-height: 760px;
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
  height: 760px;
  grid-template-rows: repeat(var(--rack-units, 42), minmax(10px, 1fr));
  grid-template-columns: 64px minmax(0, 1fr);
  overflow: hidden;
  border-inline: 1px solid rgba(148, 163, 184, 0.28);
  background:
    linear-gradient(90deg, rgba(15, 23, 42, 0.42), transparent 16%, transparent 84%, rgba(15, 23, 42, 0.42)),
    #0f172a;
}

.rack-u-row {
  position: relative;
  grid-column: 1 / -1;
  min-height: 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
}

.rack-u-row span {
  position: absolute;
  left: 8px;
  top: 50%;
  z-index: 1;
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  transform: translateY(-50%);
}

.rack-u-row.occupied {
  background: rgba(59, 130, 246, 0.06);
}

.rack-u-row.conflict {
  background: rgba(239, 68, 68, 0.18);
}

.rack-device-block {
  grid-column: 2;
  z-index: 2;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 10px;
  align-items: center;
  gap: 8px;
  min-height: 0;
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

.rack-device-block:hover {
  border-color: rgba(191, 219, 254, 0.86);
  filter: brightness(1.08);
}

.rack-device-block.selected {
  outline: 2px solid rgba(14, 165, 233, 0.95);
  outline-offset: 2px;
}

.rack-device-block strong,
.rack-device-block span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rack-device-info {
  display: flex;
  min-width: 0;
  flex-direction: column;
  justify-content: center;
}

.rack-device-block strong {
  font-size: 12px;
  line-height: 1;
}

.rack-device-block.compact {
  padding-block: 0;
}

.rack-device-block.compact .rack-device-info {
  flex-direction: row;
  align-items: center;
  gap: 8px;
}

.rack-device-block.compact span {
  margin-top: 0;
  font-size: 10px;
}

.rack-device-block span {
  margin-top: 1px;
  opacity: 0.82;
  font-size: 10px;
  line-height: 1;
}

.rack-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #22c55e;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.24);
}

.rack-device-block.device-type-1 {
  border-color: rgba(52, 211, 153, 0.72);
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.14), transparent 18%),
    linear-gradient(180deg, #059669, #047857);
}

.rack-device-block.device-type-2 {
  border-color: rgba(45, 212, 191, 0.72);
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.14), transparent 18%),
    linear-gradient(180deg, #0d9488, #0f766e);
}

.rack-device-block.device-type-3 {
  border-color: rgba(251, 191, 36, 0.78);
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.14), transparent 18%),
    linear-gradient(180deg, #d97706, #92400e);
}

.rack-device-block.device-type-4 {
  border-color: rgba(244, 114, 182, 0.74);
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.14), transparent 18%),
    linear-gradient(180deg, #db2777, #be185d);
}

.rack-device-block.device-type-5 {
  border-color: rgba(167, 139, 250, 0.74);
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.14), transparent 18%),
    linear-gradient(180deg, #7c3aed, #6d28d9);
}

.rack-device-block.device-type-99 {
  border-color: rgba(148, 163, 184, 0.74);
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.14), transparent 18%),
    linear-gradient(180deg, #64748b, #475569);
}

.rack-status-dot.device-status-2 {
  background: #f59e0b;
}

.rack-status-dot.device-status-3,
.rack-status-dot.device-status-5 {
  background: #ef4444;
}

.rack-status-dot.device-status-4 {
  background: #94a3b8;
}

.rack-device-block.conflict {
  border-color: rgba(252, 165, 165, 0.82);
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.14), transparent 18%),
    linear-gradient(180deg, #dc2626, #991b1b);
}

.rack-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background: #f8fafc;
  padding: 14px;
}

.rack-device-detail {
  min-height: 520px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background: #fff;
  padding: 16px;
}

.rack-detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.rack-detail-head h3 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 18px;
  line-height: 1.25;
}

.rack-detail-status {
  flex: 0 0 auto;
  border-radius: 999px;
  background: #dcfce7;
  color: #15803d;
  font-size: 12px;
  font-weight: 700;
  line-height: 24px;
  padding: 0 10px;
}

.rack-detail-status.device-status-2 {
  background: #fef3c7;
  color: #b45309;
}

.rack-detail-status.device-status-3,
.rack-detail-status.device-status-5 {
  background: #fee2e2;
  color: #b91c1c;
}

.rack-detail-status.device-status-4 {
  background: #e5e7eb;
  color: #4b5563;
}

.rack-detail-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.rack-detail-empty {
  display: flex;
  min-height: 480px;
  align-items: center;
  justify-content: center;
  color: #ef4444;
  font-size: 15px;
}

.rack-legend span {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #475569;
  font-size: 13px;
}

.rack-legend i {
  width: 18px;
  height: 12px;
  border-radius: 3px;
}

.rack-legend .server {
  background: #2563eb;
}

.rack-legend .switch {
  background: #059669;
}

.rack-legend .router {
  background: #0d9488;
}

.rack-legend .firewall {
  background: #d97706;
}

.rack-legend .pdu {
  background: #db2777;
}

.rack-legend .part {
  background: #7c3aed;
}

.rack-legend .danger {
  background: #dc2626;
}

.rack-empty {
  margin-top: -8px;
}

.content-panel :deep(.attribute-tag-groups) {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  white-space: normal;
}

.content-panel :deep(.attribute-tag-group) {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}

.content-panel :deep(.attribute-tag-group-title) {
  border-radius: 999px;
  background: #eef2ff;
  color: #3730a3;
  font-size: 12px;
  font-weight: 600;
  line-height: 22px;
  padding: 0 9px;
}

.content-panel :deep(.attribute-tag) {
  display: inline-flex;
  overflow: hidden;
  max-width: 220px;
  align-items: center;
  border: 1px solid #dbeafe;
  border-radius: 999px;
  background: #f8fafc;
  color: #0f172a;
  line-height: 22px;
}

.content-panel :deep(.attribute-tag b),
.content-panel :deep(.attribute-tag em) {
  overflow: hidden;
  min-width: 0;
  padding: 0 8px;
  font-size: 12px;
  font-style: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content-panel :deep(.attribute-tag b) {
  flex: 0 1 auto;
  background: #eff6ff;
  color: #2563eb;
  font-weight: 600;
}

.content-panel :deep(.attribute-tag em) {
  flex: 1 1 auto;
  color: #334155;
}

.content-panel :deep(.device-name-cell) {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
}

.detail-link {
  max-width: 100%;
  overflow: hidden;
  border: 0;
  background: transparent;
  color: #2563eb;
  cursor: pointer;
  font: inherit;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-link:hover {
  color: #1d4ed8;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.content-panel :deep(.device-meta-line) {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: 6px;
  color: #94a3b8;
  font-size: 12px;
  line-height: 1.2;
}

.content-panel :deep(.device-meta-line span) {
  overflow: hidden;
  max-width: 150px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content-panel :deep(.device-type-badge),
.content-panel :deep(.device-status-badge),
.content-panel :deep(.device-u-badge) {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  line-height: 24px;
}

.content-panel :deep(.inventory-quantity-badge) {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: #f8fafc;
  color: #334155;
  font-weight: 700;
  line-height: 24px;
  padding: 0 10px;
}

.content-panel :deep(.inventory-quantity-badge.is-low) {
  background: #fee2e2;
  color: #b91c1c;
}

.content-panel :deep(.device-type-badge) {
  gap: 6px;
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #1d4ed8;
  padding: 0 10px;
}

.content-panel :deep(.device-type-1),
.content-panel :deep(.device-type-2) {
  border-color: #d1fae5;
  background: #ecfdf5;
  color: #047857;
}

.content-panel :deep(.device-type-3),
.content-panel :deep(.device-type-4) {
  border-color: #fde68a;
  background: #fffbeb;
  color: #b45309;
}

.content-panel :deep(.device-type-5),
.content-panel :deep(.device-type-99) {
  border-color: #e5e7eb;
  background: #f9fafb;
  color: #4b5563;
}

.content-panel :deep(.device-type-dot) {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: currentColor;
}

.content-panel :deep(.device-status-badge) {
  background: #dcfce7;
  color: #15803d;
  padding: 0 11px;
}

.content-panel :deep(.device-status-2) {
  background: #fef3c7;
  color: #b45309;
}

.content-panel :deep(.device-status-3),
.content-panel :deep(.device-status-5) {
  background: #fee2e2;
  color: #b91c1c;
}

.content-panel :deep(.device-status-4) {
  background: #e5e7eb;
  color: #4b5563;
}

.content-panel :deep(.device-u-badge) {
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #334155;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  padding: 0 9px;
}

.content-panel :deep(.device-u-badge.is-empty),
.content-panel :deep(.muted-cell) {
  color: #94a3b8;
}

.content-panel :deep(.device-ip-group) {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
}

.content-panel :deep(.device-ip-item) {
  display: inline-flex;
  overflow: hidden;
  max-width: 190px;
  align-items: center;
  line-height: 21px;
}

.content-panel :deep(.device-ip-item b) {
  flex: 0 0 auto;
  border-radius: 4px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  padding: 0 5px;
}

.content-panel :deep(.device-ip-item em) {
  overflow: hidden;
  min-width: 0;
  margin-left: 6px;
  color: #334155;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-style: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content-panel :deep(.device-remark) {
  display: inline-block;
  overflow: hidden;
  max-width: 100%;
  color: #475569;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-section {
  margin-top: 16px;
}

.detail-section h3 {
  margin: 0 0 10px;
  color: #0f172a;
  font-size: 15px;
  line-height: 1.3;
}

.device-config-table {
  overflow: hidden;
  border: 1px solid #efeff5;
  border-radius: 3px;
}

.device-config-row {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  border-bottom: 1px solid #efeff5;
}

.device-config-row:last-child {
  border-bottom: 0;
}

.device-config-label {
  display: flex;
  align-items: center;
  background: #fafafc;
  color: #1f2937;
  font-weight: 600;
  padding: 9px 12px;
}

.device-config-values {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 18px;
  padding: 9px 12px;
}

.device-config-values span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-config-values strong {
  margin-right: 6px;
  color: #64748b;
  font-weight: 500;
}

.device-config-values span.is-sensitive {
  color: #b45309;
}

.device-config-values span.is-sensitive::after {
  margin-left: 6px;
  border-radius: 999px;
  background: #fef3c7;
  color: #92400e;
  content: '受限';
  font-size: 12px;
  padding: 1px 7px;
}

.asset-main {
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

.summary-band {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-band article {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  background: #fff;
  padding: 14px 16px;
}

.summary-band span {
  display: block;
  color: #64748b;
  font-size: 13px;
}

.summary-band strong {
  display: block;
  margin-top: 6px;
  color: #0f172a;
  font-size: 24px;
}

.filter-panel {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) 180px 160px auto auto;
  gap: 10px;
}

.attribute-editor {
  display: flex;
  width: 100%;
  flex-direction: column;
  gap: 8px;
}

.attribute-row {
  display: grid;
  grid-template-columns: minmax(120px, 1fr) minmax(160px, 1.4fr) 34px;
  gap: 8px;
}

.attribute-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.asset-modal {
  width: min(880px, 92vw);
}

.simple-modal {
  width: min(520px, 92vw);
}

.category-editor {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.category-add {
  display: flex;
  align-items: center;
  gap: 8px;
}

.category-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  padding: 12px;
}

.category-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.subcategory-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 24px;
}

.modal-footer {
  justify-content: flex-end;
}

.modal-footer span {
  flex: 1;
}

html.dark .asset-sidebar,
html.dark .content-panel,
html.dark .summary-band article {
  border-color: rgba(148, 163, 184, 0.2);
  background: rgba(17, 24, 39, 0.86);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.2);
}

html.dark .panel-head h2,
html.dark .rack-summary h3,
html.dark .rack-detail-head h3,
html.dark .summary-band strong,
html.dark .detail-section h3 {
  color: #e5e7eb;
}

html.dark .eyebrow,
html.dark .summary-band span,
html.dark .content-panel :deep(.device-meta-line),
html.dark .content-panel :deep(.muted-cell) {
  color: #94a3b8;
}

html.dark .content-panel :deep(.n-data-table-th) {
  background: #111827;
  color: #cbd5e1;
}

html.dark .content-panel :deep(.n-data-table-td) {
  color: #e5e7eb;
}

html.dark .content-panel :deep(.asset-table-row .n-data-table-td) {
  border-bottom-color: rgba(148, 163, 184, 0.16);
}

html.dark .content-panel :deep(.asset-table-row:hover .n-data-table-td) {
  background: rgba(30, 41, 59, 0.72);
}

html.dark .content-panel :deep(.attribute-tag-group-title),
html.dark .content-panel :deep(.attribute-tag),
html.dark .content-panel :deep(.attribute-tag b),
html.dark .content-panel :deep(.device-ip-item b),
html.dark .content-panel :deep(.device-u-badge) {
  border-color: rgba(96, 165, 250, 0.28);
  background: rgba(30, 41, 59, 0.9);
  color: #bfdbfe;
}

html.dark .content-panel :deep(.attribute-tag em),
html.dark .content-panel :deep(.device-ip-item em),
html.dark .content-panel :deep(.device-remark) {
  color: #cbd5e1;
}

html.dark .content-panel :deep(.device-type-badge) {
  border-color: rgba(96, 165, 250, 0.28);
  background: rgba(30, 64, 175, 0.22);
  color: #93c5fd;
}

html.dark .content-panel :deep(.device-type-1),
html.dark .content-panel :deep(.device-type-2),
html.dark .content-panel :deep(.device-status-badge) {
  border-color: rgba(52, 211, 153, 0.28);
  background: rgba(6, 95, 70, 0.28);
  color: #6ee7b7;
}

html.dark .content-panel :deep(.device-type-3),
html.dark .content-panel :deep(.device-type-4),
html.dark .content-panel :deep(.device-status-2) {
  border-color: rgba(251, 191, 36, 0.3);
  background: rgba(146, 64, 14, 0.3);
  color: #fcd34d;
}

html.dark .content-panel :deep(.device-type-5),
html.dark .content-panel :deep(.device-type-99),
html.dark .content-panel :deep(.device-status-4) {
  border-color: rgba(148, 163, 184, 0.28);
  background: rgba(51, 65, 85, 0.72);
  color: #cbd5e1;
}

html.dark .content-panel :deep(.device-status-3),
html.dark .content-panel :deep(.device-status-5) {
  background: rgba(127, 29, 29, 0.42);
  color: #fca5a5;
}

html.dark .device-config-table,
html.dark .device-config-row {
  border-color: rgba(148, 163, 184, 0.2);
}

html.dark .device-config-label {
  background: rgba(30, 41, 59, 0.9);
  color: #e5e7eb;
}

html.dark .device-config-values,
html.dark .device-config-values strong {
  color: #cbd5e1;
}

html.dark .category-block {
  border-color: rgba(148, 163, 184, 0.22);
  background: rgba(15, 23, 42, 0.38);
}

html.dark .rack-stats span {
  border-color: rgba(96, 165, 250, 0.28);
  background: rgba(30, 64, 175, 0.22);
  color: #93c5fd;
}

html.dark .rack-stats .rack-conflict-text {
  border-color: rgba(252, 165, 165, 0.28);
  background: rgba(127, 29, 29, 0.42);
  color: #fca5a5;
}

html.dark .rack-legend {
  border-color: rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.56);
}

html.dark .rack-device-detail {
  border-color: rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.56);
}

html.dark .rack-legend span {
  color: #cbd5e1;
}

html.dark .rack-detail-empty {
  color: #fca5a5;
}

@media (max-width: 960px) {
  .asset-layout,
  .summary-band,
  .filter-panel,
  .rack-scene {
    grid-template-columns: 1fr;
  }

  .panel-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .toolbar-actions,
  .rack-summary {
    align-items: flex-start;
    flex-direction: column;
  }

  .rack-cabinet {
    transform: none;
  }

  .rack-side-panel {
    grid-column: 1;
  }

  .rack-body,
  .rack-slots {
    height: 560px;
    min-height: 560px;
  }
}
</style>
