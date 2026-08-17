<template>
  <main class="cabinet-upload-page">
    <section class="upload-shell">
      <header>
        <span>Cabinet Photo Upload</span>
        <h1>{{ cabinet.name || '机柜图上传' }}</h1>
        <p>{{ [cabinet.region_name, cabinet.location_name, cabinet.code].filter(Boolean).join(' / ') || '请上传机柜正反面图片' }}</p>
      </header>

      <n-spin :show="loading">
        <div v-if="errorMessage" class="upload-error">{{ errorMessage }}</div>
        <div v-else class="upload-grid">
          <article v-for="item in sides" :key="item.value" class="upload-card">
            <div class="upload-card-head">
              <strong>{{ item.label }}</strong>
              <n-tag size="small" round :type="cabinet[item.field] ? 'success' : 'warning'">
                {{ cabinet[item.field] ? '已上传' : '待上传' }}
              </n-tag>
            </div>
            <a
              v-if="cabinet[item.field]"
              class="upload-preview"
              :href="cabinet[item.field]"
              target="_blank"
              rel="noopener noreferrer"
            >
              <img :src="cabinet[item.field]" :alt="`机柜${item.label}图`" />
            </a>
            <div v-else class="upload-empty">暂无{{ item.label }}图片</div>
            <label class="upload-button">
              <input type="file" accept="image/*" @change="(event) => uploadPhoto(item.value, event)" />
              <span>{{ uploadingSide === item.value ? '上传中...' : `上传${item.label}` }}</span>
            </label>
          </article>
        </div>
      </n-spin>
    </section>
  </main>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api'

defineOptions({ name: 'CabinetPhotoUpload' })

const route = useRoute()
const loading = ref(false)
const uploadingSide = ref('')
const errorMessage = ref('')
const cabinet = reactive({
  id: null,
  name: '',
  code: '',
  region_name: '',
  location_name: '',
  front_image_url: '',
  back_image_url: '',
})
const sides = [
  { label: '正面', value: 'front', field: 'front_image_url' },
  { label: '反面', value: 'back', field: 'back_image_url' },
]

function token() {
  return String(route.params.token || route.query.token || '').trim()
}

async function loadCabinet() {
  if (!token()) {
    errorMessage.value = '上传链接无效'
    return
  }
  loading.value = true
  try {
    const res = await api.assetPublicApi.cabinetPhotoInfo({ token: token() })
    Object.assign(cabinet, res.data || {})
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value = error?.message || '读取机柜信息失败'
  } finally {
    loading.value = false
  }
}

async function uploadPhoto(side, event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file || uploadingSide.value) return
  if (!String(file.type || '').startsWith('image/')) {
    window.$message?.warning('请选择图片文件')
    return
  }
  const formData = new FormData()
  formData.append('file', file)
  formData.append('token', token())
  formData.append('side', side)
  uploadingSide.value = side
  try {
    const res = await api.assetPublicApi.uploadCabinetPhoto(formData, { token: token(), side })
    const data = res.data || {}
    if (side === 'back') cabinet.back_image_url = data.back_image_url || data.image_url || ''
    else cabinet.front_image_url = data.front_image_url || data.image_url || ''
    window.$message?.success('上传成功')
  } catch (error) {
    window.$message?.error(error?.message || '上传失败，请重新生成上传链接后再试')
  } finally {
    uploadingSide.value = ''
  }
}

onMounted(loadCabinet)
</script>

<style scoped>
.cabinet-upload-page {
  box-sizing: border-box;
  width: 100%;
  height: 100vh;
  height: 100dvh;
  min-height: 100vh;
  min-height: 100dvh;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 32px 16px;
  background: #eef3f8;
  -webkit-overflow-scrolling: touch;
}

.upload-shell {
  box-sizing: border-box;
  width: 100%;
  max-width: 1040px;
  margin: 0 auto;
  padding: 22px;
  border: 1px solid #dbe4ef;
  border-radius: 8px;
  background: #fff;
}

.upload-shell header {
  margin-bottom: 18px;
}

.upload-shell header span {
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.upload-shell h1 {
  margin: 4px 0;
  color: #0f172a;
  font-size: 24px;
}

.upload-shell p {
  margin: 0;
  color: #64748b;
  line-height: 1.6;
  word-break: break-word;
}

.upload-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.upload-card {
  display: grid;
  min-width: 0;
  gap: 12px;
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.upload-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.upload-preview,
.upload-empty {
  width: 100%;
  height: 460px;
  overflow: hidden;
  border-radius: 6px;
  background: #fff;
}

.upload-preview img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.upload-empty {
  display: grid;
  place-items: center;
  color: #94a3b8;
  border: 1px dashed #cbd5e1;
}

.upload-button {
  display: grid;
  height: 38px;
  place-items: center;
  color: #fff;
  font-weight: 700;
  border-radius: 6px;
  background: #fb4b22;
  cursor: pointer;
  transition:
    background 0.18s ease,
    transform 0.18s ease,
    box-shadow 0.18s ease;
  user-select: none;
}

.upload-button:hover {
  background: #ef3f18;
  box-shadow: 0 8px 18px rgba(251, 75, 34, 0.2);
}

.upload-button:active {
  transform: translateY(1px);
}

.upload-button input {
  display: none;
}

.upload-error {
  padding: 24px;
  color: #b91c1c;
  text-align: center;
  border: 1px solid #fecaca;
  border-radius: 8px;
  background: #fff1f2;
}

@media (max-width: 760px) {
  .cabinet-upload-page {
    height: 100vh;
    height: 100dvh;
    min-height: 0;
    overflow-y: auto;
    padding: 0;
    background: #fff;
  }

  .upload-shell {
    min-height: 100%;
    padding: 16px 14px 20px;
    border: 0;
    border-radius: 0;
  }

  .upload-shell header {
    margin-bottom: 14px;
  }

  .upload-shell header span {
    font-size: 11px;
  }

  .upload-shell h1 {
    margin: 6px 0 2px;
    font-size: 26px;
    line-height: 1.15;
  }

  .upload-shell p {
    font-size: 13px;
  }

  .upload-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .upload-card {
    gap: 10px;
    padding: 12px;
    border-radius: 10px;
  }

  .upload-card-head strong {
    font-size: 15px;
  }

  .upload-preview,
  .upload-empty {
    height: min(52vh, 360px);
    min-height: 220px;
    border-radius: 8px;
  }

  .upload-button {
    height: 44px;
    border-radius: 8px;
    font-size: 15px;
  }
}

@media (max-width: 420px) {
  .upload-shell {
    padding: 14px 10px 16px;
  }

  .upload-preview,
  .upload-empty {
    height: min(46vh, 300px);
    min-height: 190px;
  }
}
</style>
