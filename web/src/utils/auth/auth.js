import { router } from '@/router'

export function toLogin(needRedirect = false) {
  const currentRoute = unref(router.currentRoute)
  const shouldRedirect = needRedirect && !['/404', '/login'].includes(router.currentRoute.value.path)
  router.replace({
    path: '/login',
    query: shouldRedirect ? { ...currentRoute.query, redirect: currentRoute.path } : {},
  })
}

export function toFourZeroFour() {
  router.replace({
    path: '/404',
  })
}
