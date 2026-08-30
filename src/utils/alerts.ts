import type { ParsedAlert } from '../types/api'

export function parseAlert(raw: string): ParsedAlert {
  try {
    const parsed = JSON.parse(raw) as Omit<ParsedAlert, 'raw'>

    return {
      ...parsed,
      raw,
    }
  } catch {
    return {
      detalle: raw,
      raw,
    }
  }
}
