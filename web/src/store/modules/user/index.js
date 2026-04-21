import { defineStore } from 'pinia'
import { resetRouter } from '@/router'
import { useTagsStore, usePermissionStore, useAppStore } from '@/store'
import { removeToken, toLogin } from '@/utils'
import api from '@/api'

export const useUserStore = defineStore('user', {
  state() {
    return {
      userInfo: {},
    }
  },
  getters: {
    userId() {
      return this.userInfo?.id
    },
    name() {
      return this.userInfo?.username
    },
    email() {
      return this.userInfo?.email
    },
    avatar() {
      return this.userInfo?.avatar
    },
    role() {
      return this.userInfo?.roles || []
    },
    isSuperUser() {
      return this.userInfo?.is_superuser
    },
    isActive() {
      return this.userInfo?.is_active
    },
  },
  actions: {
    async getUserInfo() {
      try {
        const res = await api.getUserInfo()
        if (res.code === 401) {
          this.logout()
          return
        }
        const { id, username, email, avatar, roles, is_superuser, is_active } = res.data
        this.userInfo = { id, username, email, avatar, roles, is_superuser, is_active }
        return res.data
      } catch (error) {
        return error
      }
    },
    async logout() {
      const { resetTags } = useTagsStore()
      const { resetPermission } = usePermissionStore()
      const { $reset: resetApp } = useAppStore()
      // remove auth token
      removeToken()
      // reset stores
      resetTags()
      resetPermission()
      // clear storages (local/session) to remove cached data
      try {
        const { lStorage, sStorage } = await import('@/utils')
        lStorage.clear()
        sStorage.clear()
      } catch (e) {
        // ignore
      }
      // remove any direct localStorage keys used by app
      try {
        window.localStorage.removeItem('__THEME_COLOR__')
      } catch (e) {}

      // reset router and app state
      resetRouter()
      try {
        resetApp()
      } catch (e) {}

      this.$reset()
      toLogin()
    },
    setUserInfo(userInfo = {}) {
      this.userInfo = { ...this.userInfo, ...userInfo }
    },
  },
})
