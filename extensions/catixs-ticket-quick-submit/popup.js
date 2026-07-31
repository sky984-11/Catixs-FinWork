const WEB_ORIGIN = 'https://finwork.catixs.net'
const API_BASE_URL = `${WEB_ORIGIN}/api/v1`

const DEFAULT_SETTINGS = {
  username: '',
  password: '',
}

const descriptionTemplates = {
  0: '故障现象：\n\n影响范围：\n\n当前状态：\n\n已尝试操作：\n\n期望处理：',
  1: '',
  2: '维护说明：\n\n涉及线路/设备：\n\n实施内容：\n\n影响范围：\n\n备注信息：',
}

const elements = {
  form: document.getElementById('ticketForm'),
  settingsPanel: document.getElementById('settingsPanel'),
  openSettings: document.getElementById('openSettings'),
  username: document.getElementById('username'),
  password: document.getElementById('password'),
  type: document.getElementById('type'),
  title: document.getElementById('title'),
  locationField: document.getElementById('locationField'),
  location: document.getElementById('location'),
  singleTimeField: document.getElementById('singleTimeField'),
  planTime: document.getElementById('planTime'),
  rangeTimeField: document.getElementById('rangeTimeField'),
  startTime: document.getElementById('startTime'),
  endTime: document.getElementById('endTime'),
  desc: document.getElementById('desc'),
  submitBtn: document.getElementById('submitBtn'),
  message: document.getElementById('message'),
}

let quickDraft = null

init()

async function init() {
  const settings = await loadSettings()
  elements.username.value = settings.username
  elements.password.value = settings.password
  elements.settingsPanel.classList.toggle('hidden', Boolean(settings.username && settings.password))

  quickDraft = await consumeQuickDraft()
  fillDefaultContent()
  syncTypeFields()

  elements.openSettings.addEventListener('click', toggleSettings)
  elements.username.addEventListener('change', saveSettings)
  elements.password.addEventListener('change', saveSettings)
  elements.type.addEventListener('change', () => {
    syncTypeFields(true)
  })
  elements.form.addEventListener('submit', submitTicket)
}

function toggleSettings() {
  elements.settingsPanel.classList.toggle('hidden')
}

async function loadSettings() {
  const stored = await chrome.storage.local.get(DEFAULT_SETTINGS)
  return { ...DEFAULT_SETTINGS, ...stored }
}

async function saveSettings() {
  await chrome.storage.local.set({
    username: elements.username.value.trim(),
    password: elements.password.value,
  })
}

async function consumeQuickDraft() {
  const { quickDraft: draft } = await chrome.storage.session.get('quickDraft')
  await chrome.storage.session.remove('quickDraft')
  if (!draft || Date.now() - Number(draft.createdAt || 0) > 10 * 60 * 1000) return null
  return draft
}

function fillDefaultContent() {
  const selectedText = quickDraft?.selectionText?.trim()
  if (selectedText && !elements.desc.value) {
    elements.desc.value = selectedText
  }
}

function syncTypeFields(shouldResetDescription = false) {
  const type = Number(elements.type.value)
  elements.locationField.classList.toggle('hidden', !(type === 0 || type === 2))
  elements.singleTimeField.classList.toggle('hidden', type !== 0)
  elements.rangeTimeField.classList.toggle('hidden', type !== 2)

  if (type === 0 && !elements.planTime.value) {
    elements.planTime.value = toDatetimeLocalValue(new Date())
  }
  if (type === 2 && (!elements.startTime.value || !elements.endTime.value)) {
    const now = new Date()
    elements.startTime.value = toDatetimeLocalValue(now)
    elements.endTime.value = toDatetimeLocalValue(now)
  }

  const current = elements.desc.value.trim()
  const knownTemplates = Object.values(descriptionTemplates).filter(Boolean)
  if (shouldResetDescription && (!current || knownTemplates.includes(current))) {
    elements.desc.value = descriptionTemplates[type] || ''
  } else if (!current && descriptionTemplates[type]) {
    elements.desc.value = descriptionTemplates[type]
  }
}

async function submitTicket(event) {
  event.preventDefault()
  await saveSettings()

  const username = elements.username.value.trim()
  const password = elements.password.value
  if (!username || !password) {
    setMessage('请先填写用户名和密码。', 'error')
    elements.settingsPanel.classList.remove('hidden')
    ;(!username ? elements.username : elements.password).focus()
    return
  }

  const payload = buildPayload()
  if (!payload.title || !payload.desc) {
    setMessage('请填写工单标题和描述。', 'error')
    return
  }

  elements.submitBtn.disabled = true
  elements.submitBtn.textContent = '提交中...'
  setMessage('正在登录并提交工单...')

  try {
    const token = await loginAndGetToken(username, password)
    const data = await createTicket(payload, token)
    setMessage(`提交成功：${data.data?.ticket_no || data.data?.ticketNo || '工单已创建'}`, 'success')
    openTicketDetail(data.data?.id)
    resetFormAfterSubmit(username, password)
  } catch (error) {
    setMessage(error?.message || '提交失败，请检查用户名、密码或网络。', 'error')
  } finally {
    elements.submitBtn.disabled = false
    elements.submitBtn.textContent = '提交工单'
  }
}

async function loginAndGetToken(username, password) {
  const res = await fetch(`${API_BASE_URL}/base/access_token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok || data.code !== 200 || !data.data?.access_token) {
    throw new Error(data.msg || data.detail || `登录失败：HTTP ${res.status}`)
  }
  await chrome.storage.local.set({ generatedToken: data.data.access_token })
  return data.data.access_token
}

async function createTicket(payload, token) {
  const res = await fetch(`${API_BASE_URL}/ticket/create`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      token,
    },
    body: JSON.stringify(payload),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok || data.code !== 200) {
    throw new Error(data.msg || data.detail || `提交失败：HTTP ${res.status}`)
  }
  return data
}

function buildPayload() {
  const type = Number(elements.type.value)
  return {
    title: elements.title.value.trim(),
    type,
    desc: cleanupDescription(elements.desc.value),
    location: type === 0 || type === 2 ? elements.location.value.trim() : undefined,
    start_time: getSubmitStartTime(type),
    end_time: getSubmitEndTime(type),
  }
}

function getSubmitStartTime(type) {
  if (type === 0 && elements.planTime.value) return formatDatetimeLocal(elements.planTime.value)
  if (type === 2 && elements.startTime.value) return formatDatetimeLocal(elements.startTime.value)
  return undefined
}

function getSubmitEndTime(type) {
  if (type === 2 && elements.endTime.value) return formatDatetimeLocal(elements.endTime.value)
  return undefined
}

function cleanupDescription(value) {
  return String(value || '').trimEnd()
}

function toDatetimeLocalValue(date) {
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function formatDatetimeLocal(value) {
  return String(value || '').replace('T', ' ')
}

function openTicketDetail(ticketId) {
  if (!ticketId) return
  chrome.tabs.create({ url: `${WEB_ORIGIN}/ticket/detail?ticket_id=${ticketId}` })
}

function resetFormAfterSubmit(username, password) {
  elements.form.reset()
  elements.username.value = username
  elements.password.value = password
  elements.desc.value = descriptionTemplates[Number(elements.type.value)] || ''
  syncTypeFields()
}

function setMessage(text, type = '') {
  elements.message.textContent = text
  elements.message.classList.toggle('is-error', type === 'error')
  elements.message.classList.toggle('is-success', type === 'success')
}
