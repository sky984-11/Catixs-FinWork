<template>
  <AppPage :show-footer="true" bg-cover :style="{ backgroundImage: `url(${bgImg})` }">
    <!-- Using h-full and m-auto for guaranteed centering in flex-col container -->
    <div class="h-full w-full f-c-c m-auto relative">
      <main class="login-container f-c-c">
        <div class="login-card-wrapper relative">
          <!-- Subtle decorative background elements -->
          <div class="absolute -top-60px -left-60px w-200px h-200px bg-primary/10 rounded-full blur-3xl opacity-50"></div>
          <div class="absolute -bottom-40px -right-40px w-160px h-160px bg-green-500/5 rounded-full blur-3xl opacity-30"></div>

          <!-- Perfectly Centered Professional Login Card -->
          <div class="login-card w-480px bg-white/75 dark:bg-dark/80 backdrop-blur-2xl border border-white/40 rounded-24px p-48px shadow-premium">
            <header class="card-header f-c-c flex-col mb-40px">
              <!-- Branded Icon -->
              <div class="icon-wrap f-c-c mb-20px animate-float-slow">
                <icon-custom-logo class="text-80px" />
              </div>
              
              <!-- Branding Text -->
              <div class="branding-text text-center">
                <h1 class="text-32px font-bold tracking-tight text-gray-800 dark:text-gray-100 f-c-c">
                  <span class="text-blue-standard">Catixs</span>
                  <span class="text-green-standard ml-2">FinWork</span>
                </h1>
                <p class="text-14px font-medium text-gray-400 dark:text-gray-500 mt-8px tracking-Widest uppercase">
                  财工一体化管理平台
                </p>
              </div>
            </header>

            <!-- Login Form -->
            <div class="form-content space-y-28px">
              <div class="input-group">
                <n-input
                  v-model:value="loginInfo.username"
                  autofocus
                  class="login-input h-52px text-16px"
                  placeholder="admin"
                  :maxlength="20"
                >
                  <template #prefix>
                    <i class="i-carbon-user text-gray-400 mr-2" />
                  </template>
                </n-input>
              </div>
              <div class="input-group mt-20px">
                <n-input
                  v-model:value="loginInfo.password"
                  class="login-input h-52px text-16px"
                  type="password"
                  show-password-on="mousedown"
                  placeholder="123456"
                  :maxlength="20"
                  @keypress.enter="handleLogin"
                >
                  <template #prefix>
                    <i class="i-carbon-locked text-gray-400 mr-2" />
                  </template>
                </n-input>
              </div>
              
              <div class="action-group mt-40px">
                <n-button
                  class="h-52px w-full rounded-12px text-17px font-bold shadow-md hover:shadow-lg transition-all duration-300"
                  type="primary"
                  :loading="loading"
                  @click="handleLogin"
                >
                  {{ $t('views.login.text_login') }}
                </n-button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </AppPage>
</template>

<script setup>
import { lStorage, setToken } from '@/utils'
import bgImg from '@/assets/images/login_bg.webp'
import api from '@/api'
import { addDynamicRoutes } from '@/router'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const { query } = useRoute()
const { t } = useI18n({ useScope: 'global' })

const loginInfo = ref({
  username: '',
  password: '',
})

initLoginInfo()

function initLoginInfo() {
  const localLoginInfo = lStorage.get('loginInfo')
  if (localLoginInfo) {
    loginInfo.value.username = localLoginInfo.username || ''
    loginInfo.value.password = localLoginInfo.password || ''
  }
}

const loading = ref(false)
async function handleLogin() {
  const { username, password } = loginInfo.value
  if (!username || !password) {
    $message.warning(t('views.login.message_input_username_password'))
    return
  }
  try {
    loading.value = true
    $message.loading(t('views.login.message_verifying'))
    const res = await api.login({ username, password: password.toString() })
    $message.success(t('views.login.message_login_success'))
    setToken(res.data.access_token)
    await addDynamicRoutes()
    if (query.redirect) {
      const path = query.redirect
      Reflect.deleteProperty(query, 'redirect')
      router.push({ path, query })
    } else {
      router.push('/')
    }
  } catch (e) {
    console.error('login error', e.error)
  }
  loading.value = false
}
</script>

<style scoped>
.animate-float-slow {
  animation: float-slow 8s ease-in-out infinite;
}

@keyframes float-slow {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}

.shadow-premium {
  box-shadow: 
    0 25px 50px -12px rgba(0, 0, 0, 0.1),
    0 10px 20px -5px rgba(0, 0, 0, 0.05),
    0 0 1px rgba(0, 0, 0, 0.1);
}

.text-blue-standard {
  color: #0A369D;
}

.text-green-standard {
  color: #10B981;
}

.tracking-Widest {
  letter-spacing: 0.4em;
  margin-right: -0.4em;
}

.rounded-24px {
  border-radius: 24px;
}

.rounded-12px {
  border-radius: 12px;
}

.login-container {
  width: 100%;
}

.login-input :deep(.n-input-wrapper) {
  padding-left: 12px;
}

.dark .text-blue-standard {
  color: #3B82F6;
}

.dark .text-green-standard {
  color: #34D399;
}

.login-card {
  transition: all 0.3s ease;
}

.login-card:hover {
  transform: translateY(-4px);
  box-shadow: 
    0 30px 60px -10px rgba(0, 0, 0, 0.15),
    0 10px 25px -5px rgba(0, 0, 0, 0.1);
}
</style>
