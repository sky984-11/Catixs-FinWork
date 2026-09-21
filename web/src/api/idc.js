import { request } from '@/utils'

const root = '/idc'
export const idcApi = {
  catalog: () => request.get(`${root}/catalog`),
  accounts: () => request.get(`${root}/accounts`),
  accountOptions: () => request.get(`${root}/account-options`),
  saveAccount: (data) => request.post(`${root}/accounts`, data),
  orders: (params) => request.get(`${root}/orders`, { params }),
  order: (id) => request.get(`${root}/orders/${id}`),
  create: (data) => request.post(`${root}/orders`, data),
  updateLine: (id, data) => request.post(`${root}/lines/${id}`, data),
  prices: (id) => request.get(`${root}/lines/${id}/prices`),
  quote: (id, data) => request.post(`${root}/lines/${id}/quotes`, data),
  decide: (id, data) => request.post(`${root}/lines/${id}/decision`, data),
  task: (id, data) => request.post(`${root}/tasks/${id}`, data),
  delivery: (id, data) => request.post(`${root}/lines/${id}/delivery`, data),
  accept: (id, data) => request.post(`${root}/lines/${id}/accept`, data),
  supportComplete: (id, data) => request.post(`${root}/lines/${id}/support-complete`, data),
  services: (params) => request.get(`${root}/services`, { params }),
  billing: (params) => request.get(`${root}/billing`, { params }),
  generate: (data) => request.post(`${root}/billing/generate`, data),
  billDecision: (id, data) => request.post(`${root}/billing/${id}/decision`, data),
  usage: (data) => request.post(`${root}/usage`, data),
  event: (data) => request.post(`${root}/billing/events`, data),
  reconcile: () => request.post(`${root}/resources/reconcile`),
  audit: (params) => request.get(`${root}/audit`, { params }),
}
