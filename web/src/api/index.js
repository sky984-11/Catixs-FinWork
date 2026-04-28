import { request } from '@/utils'

export default {
  login: (data) => request.post('/base/access_token', data, { noNeedToken: true }),
  getUserInfo: () => request.get('/base/userinfo'),
  getUserMenu: () => request.get('/base/usermenu'),
  getUserApi: () => request.get('/base/userapi'),
  // profile
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
}
