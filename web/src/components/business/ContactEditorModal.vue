<template>
  <NModal
    :show="show"
    preset="card"
    :title="form.id ? '编辑联系人' : '新增联系人'"
    class="contact-editor"
    style="width: min(720px, calc(100vw - 32px))"
    :mask-closable="false"
    :closable="!loading"
    :close-on-esc="!loading"
    @update:show="close"
  >
    <div class="contact-intro">
      <span class="contact-icon"><TheIcon icon="mdi:card-account-phone-outline" :size="24" /></span>
      <div>
        <strong>{{ form.contact_type === 'group' ? '维护组邮箱' : '维护联系人' }}</strong>
        <p>用于记录商务、技术、财务、运维或紧急沟通入口。</p>
      </div>
    </div>
    <NForm :model="form" label-placement="top" class="contact-form" :disabled="loading">
      <section class="form-section">
        <div class="section-head">
          <span>归属与身份</span><small>确认联系人归属、类型和沟通角色</small>
        </div>
        <div class="form-grid">
          <NFormItem :label="ownerLabel" required class="full">
            <NSelect
              v-model:value="form[ownerField]"
              filterable
              multiple
              :options="owners"
              :render-label="renderOwnerLabel"
              :placeholder="`请选择${ownerLabel.replace('所属', '')}`"
            />
          </NFormItem>
          <NFormItem label="联系人类型"
            ><NSelect v-model:value="form.contact_type" :options="types"
          /></NFormItem>
          <NFormItem label="联系人角色"
            ><NSelect v-model:value="form[roleField]" multiple :options="roles"
          /></NFormItem>
          <NFormItem
            :label="form.contact_type === 'group' ? '组名 / 部门名' : '联系人姓名'"
            class="full"
          >
            <NInput
              v-model:value="form.name"
              :maxlength="100"
              :placeholder="
                form.contact_type === 'group'
                  ? '如：NOC / Accounting / Billing'
                  : '请输入联系人姓名'
              "
            />
          </NFormItem>
        </div>
      </section>
      <section class="form-section">
        <div class="section-head">
          <span>联系方式</span><small>组邮箱可只维护邮箱，个人联系人可补充电话和地址</small>
        </div>
        <div class="form-grid">
          <NFormItem label="邮箱"
            ><NInput v-model:value="form.email" :maxlength="200" placeholder="name@example.com"
          /></NFormItem>
          <NFormItem label="电话"
            ><NInput v-model:value="form.phone" :maxlength="100" placeholder="国家码 + 电话号码"
          /></NFormItem>
          <NFormItem label="联系地址" class="full"
            ><NInput
              v-model:value="form.address"
              :maxlength="500"
              placeholder="可填写办公地址、邮寄地址或所在地"
          /></NFormItem>
          <NFormItem label="备注" class="full"
            ><NInput
              v-model:value="form.remark"
              type="textarea"
              :maxlength="10000"
              :autosize="{ minRows: 2, maxRows: 6 }"
              placeholder="内部备注、沟通偏好、账单抄送说明等"
          /></NFormItem>
        </div>
      </section>
    </NForm>
    <template #footer
      ><div class="footer">
        <CButton
          show-cancel
          show-save
          :disabled="loading"
          :save-loading="loading"
          @cancel="close(false)"
          @save="save"
        /></div
    ></template>
  </NModal>
</template>

<script setup>
import { computed } from 'vue'
import CButton from '@/components/public/CButton.vue'
import TheIcon from '@/components/icon/TheIcon.vue'

const props = defineProps({
  show: Boolean,
  loading: Boolean,
  form: { type: Object, required: true },
  owners: { type: Array, default: () => [] },
  roles: { type: Array, default: () => [] },
  types: { type: Array, default: () => [] },
  ownerLabel: { type: String, default: '所属客户' },
  ownerField: { type: String, default: 'customer_ids' },
  roleField: { type: String, default: 'role' },
  renderOwnerLabel: { type: Function, default: undefined },
})
const emit = defineEmits(['update:show', 'save'])
const form = computed(() => props.form)
function close(show) {
  if (!props.loading) emit('update:show', show)
}
function save() {
  if (props.loading) return
  if (
    !form.value[props.ownerField]?.length ||
    (!form.value.name?.trim() && !form.value.email?.trim())
  ) {
    window.$message?.warning(
      `请选择${props.ownerLabel.replace('所属', '')}，并填写联系人姓名/组名或邮箱`
    )
    return
  }
  if (!form.value[props.roleField]?.length) {
    window.$message?.warning('请选择联系人角色')
    return
  }
  if (form.value.email?.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.value.email.trim())) {
    window.$message?.warning('邮箱格式错误')
    return
  }
  emit('save')
}
</script>

<style scoped>
.contact-editor :deep(.n-card-header) {
  padding: 20px 24px 12px;
}
.contact-editor :deep(.n-card__content) {
  padding: 0 24px 8px;
  max-height: min(72vh, 680px);
  overflow: auto;
}
.contact-editor :deep(.n-card__footer) {
  padding: 14px 24px 20px;
  border-top: 1px solid #e8edf3;
  background: #fbfdff;
}
.contact-intro {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 14px 16px;
  border: 1px solid #dceafe;
  border-radius: 8px;
  background: #f8fbff;
}
.contact-icon {
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
.contact-intro strong {
  display: block;
  color: #0f172a;
  font-size: 16px;
}
.contact-intro p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
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
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #edf2f7;
}
.section-head span {
  color: #0f172a;
  font-size: 15px;
  font-weight: 700;
}
.section-head small {
  color: #94a3b8;
  font-size: 12px;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 16px;
}
.full {
  grid-column: 1 / -1;
}
.footer {
  display: flex;
  justify-content: flex-end;
}
@media (max-width: 720px) {
  .form-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .section-head {
    align-items: flex-start;
    flex-direction: column;
    gap: 2px;
  }
  .contact-intro {
    align-items: flex-start;
  }
}
</style>
