import { request } from '@/utils'

const root = '/resource-costs'
export default {
  options: () => request.get(`${root}/options`),
  list: (params) => request.get(root, { params }),
  create: (data) => request.post(root, data),
  update: (id, data) => request.put(`${root}/${id}`, data),
  versions: (id) => request.get(`${root}/${id}/versions`),
  previewImport: (data) => request.post(`${root}/import/preview`, data),
  import: (data) => request.post(`${root}/import/commit`, data),
  links: (id) => request.get(`${root}/products/${id}/links`),
  link: (id, versionId) => request.post(`${root}/products/${id}/links`, { version_id: versionId }),
  unlink: (id, linkId) => request.delete(`${root}/products/${id}/links/${linkId}`),
}
