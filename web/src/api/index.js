import { request } from '@/utils'

export default {
  login: (data) => request.post('/base/access_token', data, { noNeedToken: true }),
  getUserInfo: () => request.get('/base/userinfo'),
  getUserMenu: () => request.get('/base/usermenu'),
  getUserApi: () => request.get('/base/userapi'),
  // profile
  updateProfile: (data = {}) => request.post('/base/profile', data),
  uploadAvatar: (data = {}) => request.post('/base/avatar', data),
  updatePassword: (data = {}) => request.post('/base/update_password', data),
  // users
  getUserList: (params = {}) => request.get('/user/list', { params }),
  getUserById: (params = {}) => request.get('/user/get', { params }),
  createUser: (data = {}) => request.post('/user/create', data),
  updateUser: (data = {}) => request.post('/user/update', data),
  deleteUser: (params = {}) => request.delete(`/user/delete`, { params }),
  resetPassword: (data = {}) => request.post(`/user/reset_password`, data),
  // role
  getRoleList: (params = {}) => request.get('/role/list', { params }),
  createRole: (data = {}) => request.post('/role/create', data),
  updateRole: (data = {}) => request.post('/role/update', data),
  deleteRole: (params = {}) => request.delete('/role/delete', { params }),
  updateRoleAuthorized: (data = {}) => request.post('/role/authorized', data),
  getRoleAuthorized: (params = {}) => request.get('/role/authorized', { params }),
  // menus
  getMenus: (params = {}) => request.get('/menu/list', { params }),
  createMenu: (data = {}) => request.post('/menu/create', data),
  updateMenu: (data = {}) => request.post('/menu/update', data),
  deleteMenu: (params = {}) => request.delete('/menu/delete', { params }),
  // apis
  getApis: (params = {}) => request.get('/api/list', { params }),
  createApi: (data = {}) => request.post('/api/create', data),
  updateApi: (data = {}) => request.post('/api/update', data),
  deleteApi: (params = {}) => request.delete('/api/delete', { params }),
  refreshApi: (data = {}) => request.post('/api/refresh', data),
  getApiDocs: (params = {}) => request.get('/api/docs', { params, noNeedToken: true }),
  // depts
  getDepts: (params = {}) => request.get('/dept/list', { params }),
  createDept: (data = {}) => request.post('/dept/create', data),
  updateDept: (data = {}) => request.post('/dept/update', data),
  deleteDept: (params = {}) => request.delete('/dept/delete', { params }),
  // auditlog
  getAuditLogList: (params = {}) => request.get('/auditlog/list', { params }),
  // scheduled tasks
  getTaskList: (params = {}) => request.get('/task/list', { params }),
  createTask: (data = {}) => request.post('/task/create', data),
  updateTask: (data = {}) => request.post('/task/update', data),
  deleteTask: (params = {}) => request.delete('/task/delete', { params }),
  toggleTask: (data = {}) => request.post('/task/toggle', data),
  runTask: (params = {}) => request.post('/task/run', {}, { params }),
  getTaskLogs: (params = {}) => request.get('/task/logs', { params }),
  clearTaskLogs: (params = {}) => request.delete('/task/logs', { params }),

  // vendor
  getVendorList: (params = {}) => request.get('/vendor/list', { params }),
  getVendorById: (params = {}) => request.get('/vendor/get', { params }),
  createVendor: (data = {}) => request.post('/vendor/create', data),
  updateVendor: (data = {}) => request.post('/vendor/update', data),
  deleteVendor: (params = {}) => request.delete(`/vendor/delete`, { params }),
  exportVendor: () => {
    return request.get('/vendor/export', { responseType: 'blob', skipErrorHandle: true })
  },
  importVendor: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/vendor/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // company (签约主体)
  getCompanyList: (params = {}) => request.get('/company/list', { params }),
  getCompanyById: (params = {}) => request.get('/company/get', { params }),
  createCompany: (data = {}) => request.post('/company/create', data),
  updateCompany: (data = {}) => request.post('/company/update', data),
  deleteCompany: (params = {}) => request.delete(`/company/delete`, { params }),

  // customer project board
  projectApi: {
    list: (params = {}) => request.get('/project/list', { params }),
    get: (params = {}) => request.get('/project/get', { params }),
    create: (data = {}) => request.post('/project/create', data),
    update: (data = {}) => request.post('/project/update', data),
    updateStatus: (data = {}) => request.post('/project/status', data),
    delete: (params = {}) => request.delete('/project/delete', { params }),
    createDiscussion: (data = {}) => request.post('/project/discussion/create', data),
    deleteDiscussion: (params = {}) => request.delete('/project/discussion/delete', { params }),
    createTask: (data = {}) => request.post('/project/task/create', data),
    updateTask: (data = {}) => request.post('/project/task/update', data),
    deleteTask: (params = {}) => request.delete('/project/task/delete', { params }),
    uploadAttachment: (data = {}) => request.post('/project/attachment/upload', data),
    deleteAttachment: (params = {}) => request.delete('/project/attachment/delete', { params }),
  },

  // bank
  getBankList: (params = {}) => request.get('/bank/list', { params }),
  createBank: (data = {}) => request.post('/bank/create', data),
  updateBank: (data = {}) => request.post('/bank/update', data),
  deleteBank: (params = {}) => request.delete('/bank/delete', { params }),

  // bank account
  getBankAccountList: (params = {}) => request.get('/bank_account/list', { params }),
  createBankAccount: (data = {}) => request.post('/bank_account/create', data),
  updateBankAccount: (data = {}) => request.post('/bank_account/update', data),
  deleteBankAccount: (params = {}) => request.delete('/bank_account/delete', { params }),

  // bill
  getBillList: (params = {}) => request.get('/bill/list', { params }),
  getBillById: (params = {}) => request.get('/bill/get', { params }),
  createBill: (data = {}) => request.post('/bill/create', data),
  updateBill: (data = {}) => request.post('/bill/update', data),
  deleteBill: (params = {}) => request.delete('/bill/delete', { params }),
  uploadBillVoucher: (params = {}, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/bill/upload_voucher', formData, { params })
  },

  // finance quote
  financeQuoteApi: {
    list: (params = {}) => request.get('/finance/quote/list', { params }),
    get: (params = {}) => request.get('/finance/quote/get', { params }),
    siteOptions: (params = {}) => request.get('/finance/quote/site-options', { params }),
    fieldOptions: (params = {}) => request.get('/finance/quote/field-options', { params }),
    create: (data = {}) => request.post('/finance/quote/create', data),
    update: (data = {}) => request.post('/finance/quote/update', data),
    delete: (params = {}) => request.delete('/finance/quote/delete', { params }),
  },

  // ticket
  ticketApi: {
    dashboard: () => request.get('/ticket/dashboard'),
    list: (params = {}) => request.get('/ticket/list', { params }),
    get: (params = {}) => request.get('/ticket/get', { params }),
    create: (data = {}) => request.post('/ticket/create', data),
    update: (data = {}) => request.post('/ticket/update', data),
    delete: (params = {}) => request.delete('/ticket/delete', { params }),
    getByNo: (params = {}) => request.get('/ticket/get_by_no', { params }),
    users: () => request.get('/ticket/users'),
    sendEmail: (data = {}) => request.post('/ticket/send_email', data),
    replies: (params = {}) => request.get('/ticket/reply/list', { params }),
    reply: (data = {}) => request.post('/ticket/reply_create', data),
    upload: (data = {}, params = {}) => request.post('/ticket/upload', data, { params }),
  },

  // asset
  assetApi: {
    tree: () => request.get('/asset/tree'),
    regions: (params = {}) => request.get('/asset/region/list', { params }),
    createRegion: (data = {}) => request.post('/asset/region/create', data),
    updateRegion: (data = {}) => request.post('/asset/region/update', data),
    deleteRegion: (params = {}) => request.delete('/asset/region/delete', { params }),
    locations: (params = {}) => request.get('/asset/location/list', { params }),
    createLocation: (data = {}) => request.post('/asset/location/create', data),
    updateLocation: (data = {}) => request.post('/asset/location/update', data),
    deleteLocation: (params = {}) => request.delete('/asset/location/delete', { params }),
    cabinets: (params = {}) => request.get('/asset/cabinet/list', { params }),
    getCabinet: (params = {}) => request.get('/asset/cabinet/get', { params }),
    createCabinet: (data = {}) => request.post('/asset/cabinet/create', data),
    updateCabinet: (data = {}) => request.post('/asset/cabinet/update', data),
    deleteCabinet: (params = {}) => request.delete('/asset/cabinet/delete', { params }),
    deviceBrands: () => request.get('/asset/device-brand/list'),
    createDeviceBrand: (data = {}) => request.post('/asset/device-brand/create', data),
    deleteDeviceBrand: (params = {}) => request.delete('/asset/device-brand/delete', { params }),
    createDeviceModel: (data = {}) => request.post('/asset/device-model/create', data),
    deleteDeviceModel: (params = {}) => request.delete('/asset/device-model/delete', { params }),
    devices: (params = {}) => request.get('/asset/device/list', { params }),
    getDevice: (params = {}) => request.get('/asset/device/get', { params }),
    createDevice: (data = {}) => request.post('/asset/device/create', data),
    updateDevice: (data = {}) => request.post('/asset/device/update', data),
    redfishProbeDevice: (data = {}) => request.post('/asset/device/redfish-probe', data),
    deleteDevice: (params = {}) => request.delete('/asset/device/delete', { params }),
    inventory: (params = {}) => request.get('/asset/inventory/list', { params }),
    getInventory: (params = {}) => request.get('/asset/inventory/get', { params }),
    exportInventory: () =>
      request.get('/asset/inventory/export', { responseType: 'blob', skipErrorHandle: true }),
    importInventory: (file) => {
      const formData = new FormData()
      formData.append('file', file)
      return request.post('/asset/inventory/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
    createInventory: (data = {}) => request.post('/asset/inventory/create', data),
    updateInventory: (data = {}) => request.post('/asset/inventory/update', data),
    deleteInventory: (params = {}) => request.delete('/asset/inventory/delete', { params }),
    inventorySales: (params = {}) => request.get('/asset/inventory-sale/list', { params }),
    createInventorySale: (data = {}) => request.post('/asset/inventory-sale/create', data),
    cancelInventorySale: (data = {}) => request.post('/asset/inventory-sale/cancel', data),
    inventoryFlows: (params = {}) => request.get('/asset/inventory-flow/list', { params }),
    inventoryCategories: () => request.get('/asset/inventory-category/list'),
    createInventoryCategory: (data = {}) => request.post('/asset/inventory-category/create', data),
    updateInventoryCategory: (data = {}) => request.post('/asset/inventory-category/update', data),
    deleteInventoryCategory: (params = {}) =>
      request.delete('/asset/inventory-category/delete', { params }),
  },

  // syslog
  syslogApi: {
    devices: () => request.get('/syslog/devices'),
    files: (params = {}) => request.get('/syslog/files', { params }),
    logs: (params = {}) => request.get('/syslog/logs', { params }),
    raw: (params = {}) => request.get('/syslog/raw', { params }),
  },

  // NetBox IPAM
  netboxApi: {
    ipamOverview: (params = {}) => request.get('/netbox/ipam/overview', { params }),
    ipamFilterOptions: (params = {}) => request.get('/netbox/ipam/filter-options', { params }),
    prefixIps: (params = {}) => request.get('/netbox/ipam/prefix-ips', { params }),
    prefixOptions: () => request.get('/netbox/ipam/prefix-options'),
    createIpAddress: (data = {}) => request.post('/netbox/ipam/ip-addresses', data),
    updateIpAddress: (id, data = {}) => request.patch(`/netbox/ipam/ip-addresses/${id}`, data),
    deleteIpAddress: (id) => request.delete(`/netbox/ipam/ip-addresses/${id}`),
    createPrefix: (data = {}) => request.post('/netbox/ipam/prefixes', data),
    updatePrefix: (id, data = {}) => request.patch(`/netbox/ipam/prefixes/${id}`, data),
    deletePrefix: (id) => request.delete(`/netbox/ipam/prefixes/${id}`),
    syncPveIps: (params = {}) => request.post('/netbox/ipam/sync-pve-ips', {}, { params }),
  },

  // virtual machine
  virtualMachineApi: {
    pveNodes: () => request.get('/pve/nodes'),
    pveVms: (params = {}) => request.get('/pve/vms', { params }),
    pveVmIps: (params = {}) => request.get('/pve/vms/ips', { params }),
    addNode: (data = {}) => request.post('/pve/nodes/add', data),
    updateNode: (remote, data = {}) => request.put(`/pve/nodes/remote/${encodeURIComponent(remote)}`, data),
    deleteNode: (remote) => request.delete(`/pve/nodes/remote/${encodeURIComponent(remote)}`),
    nodeRemark: (remote, params = {}) =>
      request.get(`/pve/nodes/remote/${encodeURIComponent(remote)}/remark`, { params }),
    updateNodeRemark: (remote, data = {}) =>
      request.put(`/pve/nodes/remote/${encodeURIComponent(remote)}/remark`, data),
    probeNode: (data = {}) => request.post('/pve/nodes/probe', data),
    nodeRealms: (params = {}) => request.get('/pve/nodes/realms', { params }),
    createOptions: (params = {}) => request.get('/pve/vms/create-options', { params }),
    createVm: (data = {}) => request.post('/pve/vms/create', data),
    migrationOptions: (params = {}) => request.get('/pve/vms/migration-options', { params }),
    migrateVm: (data = {}) => request.post('/pve/vms/migrate', data),
    deleteVm: (data = {}) => request.post('/pve/vms/delete', data),
    powerVm: (data = {}) => request.post('/pve/vms/power', data),
    vmConfig: (params = {}) => request.get('/pve/vms/config', { params }),
    updateVmConfig: (data = {}) => request.post('/pve/vms/config', data),
    rebootVm: (data = {}) => request.post('/pve/vms/reboot', data),
    novnc: (data = {}) => request.post('/pve/vms/novnc', data),
    taskStatus: (params = {}) => request.get('/pve/tasks/status', { params }),
  },

  // remote assistance and engineers
  remoteAssistanceApi: {
    overview: () => request.get('/remote-assistance/overview'),
    createRemoteHands: (data = {}) => request.post('/remote-assistance/remote-hands', data),
    updateRemoteHands: (id, data = {}) => request.put(`/remote-assistance/remote-hands/${id}`, data),
    deleteRemoteHands: (id) => request.delete(`/remote-assistance/remote-hands/${id}`),
    createEngineer: (data = {}) => request.post('/remote-assistance/engineers', data),
    updateEngineer: (id, data = {}) => request.put(`/remote-assistance/engineers/${id}`, data),
    deleteEngineer: (id) => request.delete(`/remote-assistance/engineers/${id}`),
  },
}
