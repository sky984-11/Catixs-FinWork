import * as en from './en.json'
import * as cn from './cn.json'
import * as locationsEn from './locations.en.json'
import * as locationsCn from './locations.cn.json'

export default {
  en: {
    ...en,
    ...locationsEn,
  },
  cn: {
    ...cn,
    ...locationsCn,
  },
}
