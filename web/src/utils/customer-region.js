import { translateCity, translateCountry, translateLocationPath } from '@/utils/location-i18n'
import { buildPinyinSearchText } from '@/utils/pinyin-search'

function regionText(value) {
  return String(value || '').trim()
}

function displayCustomerRegion(value) {
  const text = regionText(value)
  if (!text) return ''
  return translateLocationPath(text) || translateCountry(text) || translateCity(text) || text
}

function customerRegionPathParts(item = {}) {
  const country = translateCountry(regionText(item.country) || regionText(item.country_name))
  const city = translateCity(regionText(item.city) || regionText(item.city_name))
  const nameParts = displayCustomerRegion(regionText(item.name) || regionText(item.region_name))
    .split('/')
    .map((part) => part.trim())
    .filter(Boolean)
  const parts = [country, city].filter(Boolean)
  if (!parts.length) parts.push(...nameParts)
  nameParts.forEach((part) => {
    if (parts.some((current) => normalizeCustomerRegion(current) === normalizeCustomerRegion(part)))
      return
    if (!city || normalizeCustomerRegion(part) !== normalizeCustomerRegion(city)) parts.push(part)
  })
  return parts.filter(Boolean)
}

function normalizeCustomerRegion(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/\s+/g, '')
    .replace(/\/+/g, '/')
    .trim()
}

function addCustomerRegionOption(roots, parts = []) {
  let children = roots
  const path = []
  parts.filter(Boolean).forEach((part) => {
    const label = displayCustomerRegion(part)
    if (!label) return
    path.push(label)
    const value = path.join(' / ')
    const key = normalizeCustomerRegion(value)
    let node = children.find((item) => normalizeCustomerRegion(item.value) === key)
    if (!node) {
      node = {
        label,
        value,
        searchText: buildPinyinSearchText([label, value]),
        children: [],
      }
      children.push(node)
    } else {
      node.searchText = buildPinyinSearchText([node.searchText, label, value])
    }
    children = node.children
  })
}

function sortCustomerRegionTree(nodes) {
  return nodes
    .sort((left, right) =>
      String(left.label || '').localeCompare(String(right.label || ''), 'zh-Hans-CN')
    )
    .map((node) => ({
      ...node,
      children: node.children?.length ? sortCustomerRegionTree(node.children) : undefined,
    }))
}

export function customerRegionFilter(pattern, option, path = []) {
  const keyword = buildPinyinSearchText([pattern])
  if (!keyword) return true
  const text = (Array.isArray(path) && path.length ? path : [option])
    .map((item) => [item?.label, item?.value, item?.searchText].filter(Boolean).join(' '))
    .join(' ')
  return buildPinyinSearchText([text]).includes(keyword)
}

export function buildCustomerRegionOptions(regions = [], currentValue = '') {
  const roots = []
  regions.forEach((item) => addCustomerRegionOption(roots, customerRegionPathParts(item)))
  const current = String(currentValue || '').trim()
  if (current)
    addCustomerRegionOption(
      roots,
      current
        .split('/')
        .map((part) => part.trim())
        .filter(Boolean)
    )
  return sortCustomerRegionTree(roots)
}
