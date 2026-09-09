import { setupI18n } from '@start9labs/start-sdk'
import { defaultDict, translations, DEFAULT_LANG } from './dictionaries/default.js'

export const i18n = setupI18n(defaultDict, translations, DEFAULT_LANG)
