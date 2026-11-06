import { request } from '@/utils'

const root = '/crm-billing'
export default {
  list: (params) => request.get(`${root}/bills`, { params }),
  detail: (id) => request.get(`${root}/bills/${id}`),
  preview: (data) => request.post(`${root}/preview`, data),
  generate: (data) => request.post(`${root}/generate`, data),
  update: (id, data) => request.put(`${root}/bills/${id}`, data),
  action: (id, data) => request.post(`${root}/bills/${id}/actions`, data),
  payment: (id, data) => request.post(`${root}/bills/${id}/payments`, data),
  reverse: (id, paymentId, data) =>
    request.post(`${root}/bills/${id}/payments/${paymentId}/reverse`, data),
  plans: () => request.get(`${root}/plans`),
  createPlan: (data) => request.post(`${root}/plans`, data),
  stopPlan: (id) => request.post(`${root}/plans/${id}/stop`),
  runPlan: (id) => request.post(`${root}/plans/${id}/run`),
}
