const descriptionSections = {
  0: [
    {
      key: 'fault',
      title: '故障现象',
      placeholder: '请输入当前出现的问题，例如网络中断、访问失败、设备告警等。',
    },
    {
      key: 'scope',
      title: '影响范围',
      placeholder: '请输入受影响的业务、用户、线路、设备或区域。',
    },
    {
      key: 'status',
      title: '当前状态',
      placeholder: '请输入报错信息、告警内容、持续时间或当前现象。',
    },
    {
      key: 'actions',
      title: '已尝试操作',
      placeholder: '请输入已做过的排查、重启、切换或临时处理操作。',
    },
    {
      key: 'expectation',
      title: '期望处理',
      placeholder: '请输入希望运维协助排查、恢复、升级或现场处理的事项。',
    },
  ],
  1: [],
  2: [
    { key: 'description', title: '维护说明', placeholder: '请输入本次维护/割接的背景及原因。' },
    {
      key: 'resource',
      title: '涉及线路/设备',
      placeholder: '请输入线路编号、设备名称或相关业务信息。',
    },
    { key: 'implementation', title: '实施内容', placeholder: '请输入本次维护的具体操作内容。' },
    { key: 'scope', title: '影响范围', placeholder: '请输入可能受影响的业务或网络情况。' },
    { key: 'remark', title: '备注信息', placeholder: '请输入其他补充内容。' },
  ],
}

descriptionSections[3] = descriptionSections[2]

const deprecatedDescriptionSections = {
  1: [
    { title: '业务背景', placeholder: '请输入申请原因、业务用途或关联项目。' },
    { title: '实施要求', placeholder: '请输入期望完成时间、窗口期或特殊要求。' },
    { title: '备注信息', placeholder: '请输入其他补充内容。' },
  ],
}

export const TICKET_DESCRIPTION_CURSOR_PLACEHOLDER = '\u200B'

export function getTicketDescriptionSections(type) {
  return descriptionSections[type] || []
}

export function getTicketDescriptionTitleTemplate(type) {
  return getTicketDescriptionSections(type)
    .map((section) => `${section.title}：\n${TICKET_DESCRIPTION_CURSOR_PLACEHOLDER}`)
    .join('\n')
}

export function getTicketDescriptionPlaceholder(type) {
  const sections = getTicketDescriptionSections(type)
  if (!sections.length) return '请选择工单类型后填写描述'
  return sections.map((section) => `${section.title}：\n${section.placeholder}`).join('\n\n')
}

export function cleanupDeprecatedTicketDescription(type, value) {
  let nextValue = value || ''
  const deprecatedSections = deprecatedDescriptionSections[type] || []
  deprecatedSections.forEach((section) => {
    nextValue = removeDeprecatedSection(nextValue, section)
  })
  return nextValue.replace(/\n{3,}/g, '\n\n').trimEnd()
}

export function cleanupTicketDescriptionForSubmit(value) {
  return String(value || '').replaceAll(TICKET_DESCRIPTION_CURSOR_PLACEHOLDER, '').trimEnd()
}

function removeDeprecatedSection(value, section) {
  const title = `${section.title}：`
  const startIndex = value.indexOf(title)
  if (startIndex < 0) return value

  const contentStart = startIndex + title.length
  const nextTitleIndex = findNextTitleIndex(value, contentStart)
  const endIndex = nextTitleIndex >= 0 ? nextTitleIndex : value.length
  const content = value.slice(contentStart, endIndex).trim()
  if (content && content !== section.placeholder) return value

  const before = value.slice(0, startIndex).replace(/\n+$/, '')
  const after = value.slice(endIndex).replace(/^\n+/, '')
  return [before, after].filter(Boolean).join('\n\n')
}

function findNextTitleIndex(value, fromIndex) {
  const match = value.slice(fromIndex).match(/\n\S[^：\n]*：/u)
  return match ? fromIndex + match.index + 1 : -1
}
