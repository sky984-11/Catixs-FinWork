<script setup>
import { ref } from 'vue'
import { NAvatar, NButton, NForm, NFormItem, NInput, NTabPane, NTabs, NUpload } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import CommonPage from '@/components/page/CommonPage.vue'
import { useUserStore } from '@/store'
import api from '@/api'
import { fileToBase64Payload } from '../ticket/utils/fileBase64'

const { t } = useI18n()
const userStore = useUserStore()
const isLoading = ref(false)
const avatarUploading = ref(false)
const avatarFileList = ref([])

// 用户信息的表单
const infoFormRef = ref(null)
const infoForm = ref({
  avatar: userStore.avatar,
  username: userStore.name,
  email: userStore.email,
})
async function updateProfile() {
  isLoading.value = true
  infoFormRef.value?.validate(async (err) => {
    if (err) {
      isLoading.value = false
      return
    }
    await api
      .updateProfile(infoForm.value)
      .then((res) => {
        userStore.setUserInfo(res.data || infoForm.value)
        isLoading.value = false
        $message.success(t('common.text.update_success'))
      })
      .catch(() => {
        isLoading.value = false
      })
  })
}
const infoFormRules = {
  username: [
    {
      required: true,
      message: t('views.profile.message_username_required'),
      trigger: ['input', 'blur', 'change'],
    },
  ],
}

function beforeAvatarUpload({ file }) {
  const rawFile = file.file
  if (!rawFile) return false
  const isImage = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'].includes(
    rawFile.type
  )
  if (!isImage) {
    $message.error('仅支持 JPG、PNG、GIF、WebP、SVG 图片')
    return false
  }
  if (rawFile.size > 2 * 1024 * 1024) {
    $message.error('头像图片不能超过 2MB')
    return false
  }
  return true
}

async function uploadAvatar({ file, onFinish, onError }) {
  if (!file.file) return
  avatarUploading.value = true
  try {
    const res = await api.uploadAvatar(await fileToBase64Payload(file.file))
    const avatar = res.data?.avatar
    if (avatar) {
      infoForm.value.avatar = avatar
      userStore.setUserInfo({ avatar })
    }
    avatarFileList.value = []
    onFinish()
    $message.success('头像上传成功')
  } catch (error) {
    onError()
  } finally {
    avatarUploading.value = false
  }
}

// 修改密码的表单
const passwordFormRef = ref(null)
const passwordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

async function updatePassword() {
  isLoading.value = true
  passwordFormRef.value?.validate(async (err) => {
    if (!err) {
      const data = { ...passwordForm.value, id: userStore.userId }
      await api
        .updatePassword(data)
        .then((res) => {
          $message.success(res.msg)
          passwordForm.value = {
            old_password: '',
            new_password: '',
            confirm_password: '',
          }
          isLoading.value = false
        })
        .catch(() => {
          isLoading.value = false
        })
    }
  })
}
const passwordFormRules = {
  old_password: [
    {
      required: true,
      message: t('views.profile.message_old_password_required'),
      trigger: ['input', 'blur', 'change'],
    },
  ],
  new_password: [
    {
      required: true,
      message: t('views.profile.message_new_password_required'),
      trigger: ['input', 'blur', 'change'],
    },
  ],
  confirm_password: [
    {
      required: true,
      message: t('views.profile.message_password_confirmation_required'),
      trigger: ['input', 'blur'],
    },
    {
      validator: validatePasswordStartWith,
      message: t('views.profile.message_password_confirmation_diff'),
      trigger: 'input',
    },
    {
      validator: validatePasswordSame,
      message: t('views.profile.message_password_confirmation_diff'),
      trigger: ['blur', 'password-input'],
    },
  ],
}
function validatePasswordStartWith(rule, value) {
  return (
    !!passwordForm.value.new_password &&
    passwordForm.value.new_password.startsWith(value) &&
    passwordForm.value.new_password.length >= value.length
  )
}
function validatePasswordSame(rule, value) {
  return value === passwordForm.value.new_password
}
</script>

<template>
  <CommonPage :show-header="false">
    <NTabs type="line" animated>
      <NTabPane name="website" :tab="$t('views.profile.label_modify_information')">
        <div class="m-30 flex items-center">
          <NForm
            ref="infoFormRef"
            label-placement="left"
            label-align="left"
            label-width="100"
            :model="infoForm"
            :rules="infoFormRules"
            class="w-400"
          >
            <NFormItem :label="$t('views.profile.label_avatar')" path="avatar">
              <div class="avatar-uploader">
                <NAvatar round :size="96" :src="infoForm.avatar" class="profile-avatar" />
                <NUpload
                  v-model:file-list="avatarFileList"
                  :show-file-list="false"
                  :custom-request="uploadAvatar"
                  :max="1"
                  accept="image/jpeg,image/png,image/gif,image/webp,image/svg+xml"
                  :on-before-upload="beforeAvatarUpload"
                >
                  <NButton secondary round :loading="avatarUploading">上传头像</NButton>
                </NUpload>
              </div>
            </NFormItem>
            <NFormItem :label="$t('views.profile.label_username')" path="username">
              <NInput
                v-model:value="infoForm.username"
                type="text"
                :placeholder="$t('views.profile.placeholder_username')"
              />
            </NFormItem>
            <NFormItem :label="$t('views.profile.label_email')" path="email">
              <NInput
                v-model:value="infoForm.email"
                type="text"
                :placeholder="$t('views.profile.placeholder_email')"
              />
            </NFormItem>
            <NButton type="primary" :loading="isLoading" @click="updateProfile">
              {{ $t('common.buttons.update') }}
            </NButton>
          </NForm>
        </div>
      </NTabPane>
      <NTabPane name="contact" :tab="$t('views.profile.label_change_password')">
        <NForm
          ref="passwordFormRef"
          label-placement="left"
          label-align="left"
          :model="passwordForm"
          label-width="200"
          :rules="passwordFormRules"
          class="m-30 w-500"
        >
          <NFormItem :label="$t('views.profile.label_old_password')" path="old_password">
            <NInput
              v-model:value="passwordForm.old_password"
              type="password"
              show-password-on="mousedown"
              :placeholder="$t('views.profile.placeholder_old_password')"
            />
          </NFormItem>
          <NFormItem :label="$t('views.profile.label_new_password')" path="new_password">
            <NInput
              v-model:value="passwordForm.new_password"
              :disabled="!passwordForm.old_password"
              type="password"
              show-password-on="mousedown"
              :placeholder="$t('views.profile.placeholder_new_password')"
            />
          </NFormItem>
          <NFormItem :label="$t('views.profile.label_confirm_password')" path="confirm_password">
            <NInput
              v-model:value="passwordForm.confirm_password"
              :disabled="!passwordForm.new_password"
              type="password"
              show-password-on="mousedown"
              :placeholder="$t('views.profile.placeholder_confirm_password')"
            />
          </NFormItem>
          <NButton type="primary" :loading="isLoading" @click="updatePassword">
            {{ $t('common.buttons.update') }}
          </NButton>
        </NForm>
      </NTabPane>
    </NTabs>
  </CommonPage>
</template>

<style scoped>
.avatar-uploader {
  display: flex;
  align-items: center;
  gap: 16px;
}

.profile-avatar {
  width: 96px;
  height: 96px;
  flex: 0 0 96px;
}

.profile-avatar :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
