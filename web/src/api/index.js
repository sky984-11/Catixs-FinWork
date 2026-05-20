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
  // depts
  getDepts: (params = {}) => request.get('/dept/list', { params }),
  createDept: (data = {}) => request.post('/dept/create', data),
  updateDept: (data = {}) => request.post('/dept/update', data),
  deleteDept: (params = {}) => request.delete('/dept/delete', { params }),
  // auditlog
  getAuditLogList: (params = {}) => request.get('/auditlog/list', { params }),

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
  uploadBillPdf: (params = {}, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/bill/upload', formData, { params })
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
    devices: (params = {}) => request.get('/asset/device/list', { params }),
    getDevice: (params = {}) => request.get('/asset/device/get', { params }),
    createDevice: (data = {}) => request.post('/asset/device/create', data),
    updateDevice: (data = {}) => request.post('/asset/device/update', data),
    deleteDevice: (params = {}) => request.delete('/asset/device/delete', { params }),
    inventory: (params = {}) => request.get('/asset/inventory/list', { params }),
    getInventory: (params = {}) => request.get('/asset/inventory/get', { params }),
    createInventory: (data = {}) => request.post('/asset/inventory/create', data),
    updateInventory: (data = {}) => request.post('/asset/inventory/update', data),
    deleteInventory: (params = {}) => request.delete('/asset/inventory/delete', { params }),
  },
}
