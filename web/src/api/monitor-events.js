import { request } from '@/utils'

export default {
  cabinet: () => request.get('/monitor-events/cabinet'),
  saveAutomaticHost: (data) => request.put('/monitor-events/cabinet/hosts', data),
  removeAutomaticHost: (id, revision) =>
    request.delete(`/monitor-events/cabinet/hosts/${id}`, { params: { revision } }),
  restoreAutomaticHost: (id, revision) =>
    request.post(`/monitor-events/cabinet/hosts/${id}/restore`, null, { params: { revision } }),
  cabinetOptions: () => request.get('/monitor-events/cabinet/options'),
  saveCabinet: (data) => request.put('/monitor-events/cabinet', data),
  syncCabinet: () => request.post('/monitor-events/cabinet/sync'),
  notifications: () => request.get('/monitor-events/notifications'),
  saveNotifications: (data) => request.put('/monitor-events/notifications', data),
  previewNotification: (data) => request.post('/monitor-events/notifications/preview', data),
  notificationDeliveries: (params) =>
    request.get('/monitor-events/notifications/deliveries', { params }),
  retryNotification: (id) => request.post(`/monitor-events/notifications/deliveries/${id}/retry`),
  settings: () => request.get('/monitor-events/settings'),
  saveSettings: (data) => request.put('/monitor-events/settings', data),
  saveHostItems: (data) => request.put('/monitor-events/settings/items', data),
  hostGroups: () => request.get('/monitor-events/host-groups'),
  hostItems: (hostId, keyword = '') =>
    request.get('/monitor-events/host-items', { params: { host_id: hostId, keyword } }),
  hosts: (groupId, keyword = '') =>
    request.get('/monitor-events/host-options', { params: { group_id: groupId, keyword } }),
  list: (params) => request.get('/monitor-events', { params }),
  detail: (id) => request.get(`/monitor-events/${id}`),
  metricHistory: (id, itemId, params) =>
    request.get(`/monitor-events/${id}/metrics/${itemId}/history`, { params }),
  action: (id, data) => request.post(`/monitor-events/${id}/actions`, data),
}
