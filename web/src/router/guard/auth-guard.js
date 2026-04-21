import { getToken, isNullOrWhitespace } from '@/utils'
import { usePermissionStore } from '@/store'

const WHITE_LIST = ['/login', '/404']
export function createAuthGuard(router) {
  router.beforeEach(async (to) => {
    const token = getToken()

    /** 没有token的情况 */
    if (isNullOrWhitespace(token)) {
      if (WHITE_LIST.includes(to.path)) return true
      return { path: 'login', query: { ...to.query, redirect: to.path } }
    }

    /** 有token的情况 */
    if (to.path === '/login') {
      // 尝试获取用户第一个可访问路由，优先使用后端返回的 accessRoutes
      try {
        const permissionStore = usePermissionStore()
        const registered = new Set(router.getRoutes().map((r) => r.path))

        const buildFull = (parent, child) => {
          if (!child || child === '' || child === '/') return parent
          if (child.startsWith('/')) return child
          return `${parent.replace(/\/$/, '')}/${child}`
        }

        const dfs = (nodes, parent = '') => {
          if (!nodes || !nodes.length) return null
          for (const node of nodes) {
            if (node.isHidden) continue
            const nodePath = node.path || ''
            const full = nodePath.startsWith('/') ? nodePath : (parent ? `${parent.replace(/\/$/, '')}/${nodePath}` : nodePath)
            if (node.children && node.children.length) {
              const res = dfs(node.children, full || node.path)
              if (res) return res
            }
            const candidate = (!nodePath || nodePath === '' || nodePath === '/') ? (parent || node.path) : full
            if (candidate && registered.has(candidate)) return candidate
          }
          return null
        }

        const p = dfs(permissionStore.accessRoutes || []) || dfs(permissionStore.menus || [])
        // 如果没有找到有效菜单，回退到个人中心而不是根路径，避免跳转到已删除的 /workbench
        return { path: p || '/profile' }
      } catch (e) {
        return { path: '/' }
      }
    }
    return true
  })
}
