chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'catixs-submit-ticket',
    title: '提交为 Catixs 工单',
    contexts: ['selection', 'page'],
  })
})

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== 'catixs-submit-ticket') return
  await chrome.storage.session.set({
    quickDraft: {
      title: tab?.title || '',
      url: tab?.url || '',
      selectionText: info.selectionText || '',
      createdAt: Date.now(),
    },
  })
  await chrome.action.openPopup()
})
