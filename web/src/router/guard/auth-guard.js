import { getToken, isNullOrWhitespace } from '@/utils'

const WHITE_LIST = ['/login', '/404']
const WHITE_PREFIX_LIST = ['/asset/cabinet-photo-upload/']
const HOME_PATH = '/workbench'

export function createAuthGuard(router) {
  router.beforeEach(async (to) => {
    const token = getToken()

    if (isNullOrWhitespace(token)) {
      if (WHITE_LIST.includes(to.path) || WHITE_PREFIX_LIST.some((path) => to.path.startsWith(path))) return true
      return { path: '/login', query: { ...to.query, redirect: to.path } }
    }

    if (to.path === '/login') {
      return { path: HOME_PATH }
    }

    return true
  })
}
