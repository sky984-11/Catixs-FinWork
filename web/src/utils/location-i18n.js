import i18n from '~/i18n'

function messageMap(path) {
  return i18n.global.tm(path) || {}
}

function translateFromMap(path, value) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  return messageMap(path)[raw] || raw
}

export function translateCountry(value) {
  return translateFromMap('locations.countries', value)
}

export function translateCity(value) {
  return translateFromMap('locations.cities', value)
}

export function translateRegion(region) {
  if (!region) return ''
  const country = translateCountry(region.country)
  const city = translateCity(region.city)
  return [country, city].filter(Boolean).join(' / ') || translateLocationPath(region.name) || region.code || ''
}

export function translateLocationPath(value) {
  const parts = String(value || '')
    .split('/')
    .map((item) => item.trim())
    .filter(Boolean)
  if (!parts.length) return ''
  if (parts.length === 1) return translateCountry(parts[0]) || translateCity(parts[0]) || parts[0]
  return parts
    .map((part, index) => (index === 0 ? translateCountry(part) : translateCity(part)))
    .join(' / ')
}
