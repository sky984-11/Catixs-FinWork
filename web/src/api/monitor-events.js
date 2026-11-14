import { request } from '@/utils'

export default {
  settings: () => request.get('/monitor-events/settings'),
  saveSettings: (data) => request.put('/monitor-events/settings', data),
  hostGroups: () => request.get('/monitor-events/host-groups'),
  hosts: (groupId, keyword = '') =>
    request.get('/monitor-events/host-options', { params: { group_id: groupId, keyword } }),
  list: (params) => request.get('/monitor-events', { params }),
  detail: (id) => request.get(`/monitor-events/${id}`),
  metricHistory: (id, itemId, params) =>
    request.get(`/monitor-events/${id}/metrics/${itemId}/history`, { params }),
  action: (id, data) => request.post(`/monitor-events/${id}/actions`, data),
}
