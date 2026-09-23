<script setup>
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  currency: { type: String, default: 'USD' },
  disabled: Boolean,
})
const emit = defineEmits(['update:modelValue'])
function update(index, key, value) {
  emit(
    'update:modelValue',
    props.modelValue.map((fee, i) => (i === index ? { ...fee, [key]: value } : fee))
  )
}
function add() {
  emit('update:modelValue', [
    ...props.modelValue,
    {
      id:
        globalThis.crypto?.randomUUID?.() ||
        `fee-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`,
      name: '',
      mode: 'fixed',
      amount: null,
      minutes_source: 'actual',
      minutes: 60,
      increment_minutes: 30,
      excluded_regions: [],
    },
  ])
}
</script>

<template>
  <section class="fee-section">
    <div class="fee-heading">
      <div>
        <strong>附加费用</strong>
        <p>打车、通勤等费用，可按次或按时长计算</p>
      </div>
      <CButton
        show-save
        save-text="添加费用"
        size="small"
        :disabled="disabled || modelValue.length >= 30"
        @save="add"
      >
        <template #save-icon><TheIcon icon="mdi:plus" :size="18" /></template>
      </CButton>
    </div>
    <div v-if="!modelValue.length" class="fee-empty">暂无附加费用，按需添加即可</div>
    <article v-for="(fee, index) in modelValue" :key="fee.id" class="fee-card">
      <div class="fee-heading">
        <strong>费用 {{ index + 1 }}</strong
        ><CButton
          show-delete
          size="small"
          :disabled="disabled"
          @delete="
            emit(
              'update:modelValue',
              modelValue.filter((_, i) => i !== index)
            )
          "
        />
      </div>
      <div class="fee-grid">
        <n-form-item label="费用名称"
          ><n-input
            :value="fee.name"
            :disabled="disabled"
            maxlength="100"
            placeholder="例如打车费、通勤费"
            @update:value="update(index, 'name', $event)"
        /></n-form-item>
        <n-form-item label="计费方式"
          ><n-select
            :value="fee.mode"
            :disabled="disabled"
            :options="[
              { label: '每次固定金额', value: 'fixed' },
              { label: '按时长计费', value: 'hourly' },
            ]"
            @update:value="update(index, 'mode', $event)"
        /></n-form-item>
        <n-form-item
          :label="fee.mode === 'fixed' ? `每次金额（${currency}）` : `小时单价（${currency}）`"
          ><n-input-number
            :value="fee.amount"
            :min="0"
            :max="9999999999.99"
            :precision="2"
            :disabled="disabled"
            placeholder="未确认留空"
            @update:value="update(index, 'amount', $event)"
        /></n-form-item>
        <template v-if="fee.mode === 'hourly'">
          <n-form-item label="时长来源"
            ><n-select
              :value="fee.minutes_source"
              :disabled="disabled"
              :options="[
                { label: '在运维记录中填写', value: 'actual' },
                { label: '每次固定时长', value: 'fixed' },
                { label: '本次实际作业工时', value: 'work' },
              ]"
              @update:value="update(index, 'minutes_source', $event)"
          /></n-form-item>
          <n-form-item v-if="fee.minutes_source === 'fixed'" label="固定时长（分钟）"
            ><n-input-number
              :value="fee.minutes"
              :min="0"
              :max="10080"
              :precision="0"
              :disabled="disabled"
              @update:value="update(index, 'minutes', $event)"
          /></n-form-item>
          <n-form-item label="向上取整步长（分钟）"
            ><n-input-number
              :value="fee.increment_minutes"
              :min="1"
              :max="1440"
              :precision="0"
              :disabled="disabled"
              @update:value="update(index, 'increment_minutes', $event)"
          /></n-form-item>
        </template>
      </div>
      <p v-if="fee.excluded_regions?.length" class="legacy-note">
        原规则免收地区：{{ fee.excluded_regions.join('、') }}
      </p>
    </article>
  </section>
</template>

<style scoped>
.fee-section {
  margin-top: 20px;
  border-top: 1px solid #e8edf3;
  padding-top: 18px;
}
.fee-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.fee-heading strong {
  font-size: 14px;
  color: #334155;
}
.fee-heading p,
.legacy-note {
  color: #94a3b8;
  font-size: 12px;
  margin: 4px 0 0;
}
.fee-card {
  background: #f8fbff;
  border: 1px solid #e5edf6;
  border-radius: 10px;
  padding: 14px 16px 0;
  margin-top: 12px;
}
.fee-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}
.fee-empty {
  border: 1px dashed #d9e3ee;
  border-radius: 8px;
  padding: 18px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}
.fee-section :deep(.n-input-number) {
  width: 100%;
}
@media (max-width: 600px) {
  .fee-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .fee-heading {
    flex-wrap: wrap;
  }
}
</style>
