import type {
  ResolvedTheme,
  ThemeMode,
} from '../types/theme'

const STORAGE_KEY = 'nexus-theme-mode'

const validModes: ThemeMode[] = [
  'AUTO',
  'LIGHT',
  'DARK',
  'DAY',
  'AFTERNOON',
  'NIGHT',
]

export function readThemeMode(): ThemeMode {
  const stored =
    window.localStorage.getItem(
      STORAGE_KEY,
    ) as ThemeMode | null

  if (
    stored &&
    validModes.includes(stored)
  ) {
    return stored
  }

  return 'AUTO'
}

export function saveThemeMode(
  mode: ThemeMode,
) {
  window.localStorage.setItem(
    STORAGE_KEY,
    mode,
  )
}

export function resolveTheme(
  mode: ThemeMode,
  date = new Date(),
): ResolvedTheme {
  switch (mode) {
    case 'LIGHT':
      return 'light'

    case 'DARK':
      return 'dark'

    case 'DAY':
      return 'day'

    case 'AFTERNOON':
      return 'afternoon'

    case 'NIGHT':
      return 'night'

    case 'AUTO':
    default: {
      const hour = date.getHours()

      if (hour < 11) {
        return 'day'
      }

      if (hour < 17) {
        return 'afternoon'
      }

      return 'night'
    }
  }
}

export function applyTheme(
  mode: ThemeMode,
) {
  const resolved =
    resolveTheme(mode)

  document.documentElement.dataset.theme =
    resolved

  document.documentElement.dataset.themeMode =
    mode.toLowerCase()

  return resolved
}
