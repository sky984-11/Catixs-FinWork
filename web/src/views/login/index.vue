<template>
  <AppPage :show-footer="true" bg-cover :style="{ backgroundImage: `url(${bgImg})` }">
    <!-- Using explicit flex and absolute positioning for centering if flex-1 fails -->
    <div class="login-screen flex flex-col flex-1 items-center justify-center w-full min-h-0 relative">
      <main class="login-container flex flex-col items-center justify-center">
        <div class="login-card-wrapper relative">
          <!-- Subtle decorative background elements -->
          <div
            class="login-decor login-decor--primary absolute -top-60px -left-60px w-200px h-200px bg-primary/10 rounded-full blur-3xl opacity-50 pointer-events-none">
          </div>
          <div
            class="login-decor login-decor--accent absolute -bottom-40px -right-40px w-160px h-160px bg-green-500/5 rounded-full blur-3xl opacity-30 pointer-events-none">
          </div>

          <!-- Perfectly Centered Professional Login Card -->
          <div
            class="login-card bg-white/75 dark:bg-dark/80 backdrop-blur-3xl border border-white/20 rounded-24px shadow-premium transition-all duration-300">
            <header class="card-header flex flex-col items-center justify-center mb-40px">
              <!-- Branded Icon -->
              <div class="icon-wrap flex items-center justify-center mb-20px animate-float-slow">
                <img class="login-logo" :src="logoUrl" alt="Catixs FinWork" />
              </div>

              <!-- Branding Text -->
              <div class="branding-text text-center">
                <h1
                  class="text-32px font-bold tracking-tight text-gray-800 dark:text-gray-100 flex items-center justify-center">
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
              <div v-if="oauthMessage" class="oauth-message">
                {{ oauthMessage }}
              </div>
              <div class="action-group mt-40px">
                <n-button
                  class="feishu-login-button h-52px w-full rounded-12px text-17px font-bold shadow-md hover:shadow-lg transition-all duration-300"
                  type="primary" :loading="oauthLoading" @click="handleFeishuLogin">
                  <template #icon>
                    <img class="feishu-mark" :src="feishuLogoUrl" alt="" aria-hidden="true" />
                  </template>
                  飞书登录
                </n-button>
                <button class="password-toggle" type="button" @click="passwordLoginVisible = !passwordLoginVisible">
                  {{ passwordLoginVisible ? '收起账号密码登录' : '账号密码登录' }}
                </button>
              </div>

              <n-collapse-transition :show="passwordLoginVisible">
                <div class="password-login-panel">
                  <div class="input-group">
                    <n-input v-model:value="loginInfo.username" size="large" autofocus class="login-input text-16px"
                      placeholder="请输入用户名" :maxlength="20">
                      <template #prefix>
                        <i class="i-carbon-user text-gray-400 mr-2" />
                      </template>
                    </n-input>
                  </div>
                  <div class="input-group mt-20px">
                    <n-input v-model:value="loginInfo.password" size="large" class="login-input  text-16px" type="password"
                      show-password-on="mousedown" placeholder="请输入密码" :maxlength="20" @keypress.enter="handleLogin">
                      <template #prefix>
                        <i class="i-carbon-locked text-gray-400 mr-2" />
                      </template>
                    </n-input>
                  </div>
                  <n-button
                    class="h-44px w-full rounded-12px text-15px font-bold mt-18px"
                    secondary
                    type="primary"
                    :loading="loading"
                    @click="handleLogin"
                  >
                    {{ $t('views.login.text_login') }}
                  </n-button>
                </div>
              </n-collapse-transition>
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
import logoUrl from '@/assets/svg/logo.svg?url'
import feishuLogoUrl from '@/assets/svg/feishu-logo.svg?url'

const router = useRouter()
const route = useRoute()
const { t } = useI18n({ useScope: 'global' })
const FEISHU_OAUTH_STATE_KEY = 'feishuOAuthState'
const FEISHU_OAUTH_REDIRECT_URI_KEY = 'feishuOAuthRedirectUri'
const HOME_PATH = '/workbench'

const loginInfo = ref({
  username: '',
  password: '',
})
const oauthMessage = ref('')
const passwordLoginVisible = ref(false)

initLoginInfo()

function initLoginInfo() {
  const localLoginInfo = lStorage.get('loginInfo')
  if (localLoginInfo) {
    loginInfo.value.username = localLoginInfo.username || ''
    loginInfo.value.password = localLoginInfo.password || ''
  }
}

const loading = ref(false)
const oauthLoading = ref(false)

function currentRedirectUri() {
  return `${window.location.origin}${window.location.pathname}`
}

function randomState() {
  if (window.crypto?.getRandomValues) {
    const values = window.crypto.getRandomValues(new Uint32Array(4))
    return Array.from(values, (value) => value.toString(16).padStart(8, '0')).join('')
  }
  return `${Date.now()}${Math.random()}`.replace(/\D/g, '')
}

function errorText(error, fallback = '操作失败') {
  const data = error?.error || error?.response?.data || error
  return data?.detail || data?.msg || data?.message || error?.message || fallback
}

async function goAfterLogin() {
  await addDynamicRoutes()
  const query = { ...route.query }
  delete query.redirect
  delete query.code
  delete query.state
  delete query.error

  router.push({ path: HOME_PATH, query })
}

async function handleFeishuLogin() {
  try {
    oauthLoading.value = true
    oauthMessage.value = '正在跳转飞书授权...'
    const state = randomState()
    const redirectUri = currentRedirectUri()
    const res = await api.getFeishuOAuthConfig({ redirect_uri: redirectUri, state })
    if (!res.data?.enabled || !res.data?.auth_url) {
      oauthMessage.value = '飞书登录未配置，请联系管理员配置 FEISHU_APP_ID / FEISHU_APP_SECRET'
      return
    }
    lStorage.set(FEISHU_OAUTH_STATE_KEY, res.data.state || state, 600)
    lStorage.set(FEISHU_OAUTH_REDIRECT_URI_KEY, res.data.redirect_uri || redirectUri, 600)
    window.location.href = res.data.auth_url
  } catch (error) {
    console.error('feishu oauth start error', error)
    oauthMessage.value = errorText(error, '飞书登录初始化失败')
  } finally {
    oauthLoading.value = false
  }
}

async function handleFeishuCallback() {
  const { code, state, error } = route.query
  if (error) {
    oauthMessage.value = `飞书授权失败：${error}`
    return
  }
  if (!code) return

  const savedState = lStorage.get(FEISHU_OAUTH_STATE_KEY)
  const callbackState = String(Array.isArray(state) ? state[0] : state || '')
  if (savedState && callbackState && savedState !== callbackState) {
    oauthMessage.value = '飞书登录状态校验失败，请重新登录'
    return
  }
  lStorage.remove(FEISHU_OAUTH_STATE_KEY)

  try {
    oauthLoading.value = true
    oauthMessage.value = '正在验证飞书身份...'
    const res = await api.loginByFeishuOAuth({
      code: String(Array.isArray(code) ? code[0] : code),
      state: callbackState,
      redirect_uri: lStorage.get(FEISHU_OAUTH_REDIRECT_URI_KEY) || currentRedirectUri(),
    })
    lStorage.remove(FEISHU_OAUTH_REDIRECT_URI_KEY)
    setToken(res.data.access_token)
    $message.success('飞书登录成功')
    await goAfterLogin()
  } catch (error) {
    console.error('feishu oauth login error', error)
    oauthMessage.value = errorText(error, '飞书登录失败')
  } finally {
    oauthLoading.value = false
  }
}

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
    await goAfterLogin()
  } catch (e) {
    console.error('login error', e.error)
  }
  loading.value = false
}

onMounted(handleFeishuCallback)
</script>

<style scoped>
.animate-float-slow {
  animation: float-slow 8s ease-in-out infinite;
}

@keyframes float-slow {

  0%,
  100% {
    transform: translateY(0);
  }

  50% {
    transform: translateY(-8px);
  }
}

.shadow-premium {
  box-shadow:
    0 25px 50px -12px rgba(0, 0, 0, 0.1),
    0 10px 20px -5px rgba(0, 0, 0, 0.05),
    0 0 1px rgba(0, 0, 0, 0.1);
}

.login-logo {
  width: 88px;
  height: 88px;
  object-fit: contain;
}

.text-blue-standard {
  color: #092a6b;
}

.text-green-standard {
  color: #17a889;
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

.login-screen {
  min-height: calc(100vh - 72px);
  padding: 24px 16px;
}

.login-container {
  width: 100%;
}

.login-card-wrapper {
  width: min(480px, 100%);
}

.login-card {
  width: 100%;
  padding: 48px;
  transition: all 0.3s ease;
}

.login-input :deep(.n-input-wrapper) {
  padding-left: 12px;
}

.oauth-message {
  padding: 11px 14px;
  color: #0f4c81;
  font-size: 13px;
  line-height: 1.5;
  border: 1px solid rgba(23, 168, 137, 0.24);
  border-radius: 10px;
  background: rgba(23, 168, 137, 0.08);
}

.feishu-login-button {
  background: linear-gradient(135deg, #0d6efd 0%, #17a889 100%);
  border: 0;
}

.feishu-mark {
  width: 24px;
  height: 24px;
  object-fit: contain;
}

.password-toggle {
  display: block;
  width: 100%;
  margin-top: 14px;
  color: #64748b;
  font-size: 13px;
  text-align: center;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.password-toggle:hover {
  color: #0d6efd;
}

.password-login-panel {
  margin-top: 18px;
  padding-top: 20px;
  border-top: 1px solid rgba(148, 163, 184, 0.22);
}

.dark .text-blue-standard {
  color: #3B82F6;
}

.dark .text-green-standard {
  color: #34D399;
}

.login-card:hover {
  transform: translateY(-4px);
  box-shadow:
    0 30px 60px -10px rgba(0, 0, 0, 0.15),
    0 10px 25px -5px rgba(0, 0, 0, 0.1);
}

@media (max-width: 640px) {
  .login-screen {
    justify-content: flex-start;
    min-height: calc(100vh - 56px);
    padding: 18px 0;
  }

  .login-container {
    justify-content: flex-start;
  }

  .login-card-wrapper {
    width: 100%;
  }

  .login-card {
    padding: 28px 22px;
    border-radius: 16px;
  }

  .card-header {
    margin-bottom: 28px;
  }

  .icon-wrap {
    margin-bottom: 14px;
  }

  .login-logo {
    width: 68px;
    height: 68px;
  }

  .branding-text h1 {
    font-size: 26px;
    line-height: 1.2;
  }

  .branding-text p {
    margin-top: 6px;
    font-size: 12px;
    letter-spacing: 0.22em;
    margin-right: -0.22em;
  }

  .form-content {
    gap: 18px;
  }

  .input-group.mt-20px {
    margin-top: 16px;
  }

  .action-group.mt-40px {
    margin-top: 28px;
  }

  .action-group :deep(.n-button) {
    height: 48px;
    font-size: 16px;
  }

  .login-card:hover {
    transform: none;
  }

  .login-decor {
    display: none;
  }
}

@media (max-width: 380px) {
  .login-card {
    padding: 24px 16px;
  }

  .branding-text h1 {
    font-size: 24px;
  }

  .login-logo {
    width: 60px;
    height: 60px;
  }
}

@media (max-height: 620px) and (orientation: landscape) {
  .login-screen {
    justify-content: flex-start;
    padding-block: 10px;
  }

  .login-card {
    padding: 20px 28px;
  }

  .card-header {
    margin-bottom: 18px;
  }

  .login-logo {
    width: 54px;
    height: 54px;
  }

  .branding-text h1 {
    font-size: 24px;
  }

  .branding-text p {
    display: none;
  }

  .action-group.mt-40px {
    margin-top: 20px;
  }
}
</style>
