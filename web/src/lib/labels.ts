export const HARNESS_LABEL: Record<string, string> = {
  claude_code: 'Claude Code',
  pi: 'Pi',
  omp: 'Oh My Pi',
  dsh: 'dsh',
  agy: 'Antigravity',
}

export const MODEL_SHORT: Record<string, string> = {
  'gemini-4-argon': 'Argon',
  'gemini-3.8-flash': 'Flash 3.8',
  'claude-opus-5-5': 'Opus 5.5',
  'claude-sonnet-5-5': 'Sonnet 5.5',
  'gemini-3.1-flash-lite': 'Flash-Lite 3.1',
}

/** Short display name for any model id (known ids get curated names). */
export function modelShort(id: string): string {
  if (MODEL_SHORT[id]) return MODEL_SHORT[id]
  const m = id.match(/^gemini-([\d.]+)-(.+)$/)
  if (m) return `${m[2].split('-').map((w) => w[0].toUpperCase() + w.slice(1)).join('-')} ${m[1]}`
  const c = id.match(/^claude-([a-z]+)-(\d+)-(\d+)/)
  if (c) return `${c[1][0].toUpperCase() + c[1].slice(1)} ${c[2]}.${c[3]}`
  return id
}

/** Canonical harness key: dsh variants are web-ptc (default), web-native, acp-ptc. Legacy ptc/native map onto web-*. */
export function canonKey(k: string): string {
  if (k === 'dsh' || k === 'dsh/ptc' || k === 'dsh/default') return 'dsh/web-ptc'
  if (k === 'dsh/native') return 'dsh/web-native'
  return k
}

export function harnessLabel(name: string, variant?: string | null): string {
  if (name === 'dsh') {
    const v = canonKey(variant ? `dsh/${variant}` : 'dsh').split('/')[1]
    return v === 'web-native' ? 'dsh native' : v === 'acp-ptc' ? 'dsh ACP' : 'dsh PTC'
  }
  const base = HARNESS_LABEL[name] ?? name
  return variant && variant !== 'default' ? `${base} /${variant}` : base
}

export function harnessLabelKey(key: string): string {
  const [n, v] = canonKey(key).split('/')
  return harnessLabel(n, v)
}

/** True for dsh variants driven through the web UI (their live stream is JPEG screencast frames). */
export const isDshWeb = (name?: string, variant?: string | null) => name === 'dsh' && canonKey(variant ? `dsh/${variant}` : 'dsh').startsWith('dsh/web')

/** Stable categorical hue per harness, used for series. */
export const HARNESS_COLOR: Record<string, string> = {
  claude_code: '#d9825b',
  pi: '#5aa9e6',
  omp: '#a78bfa',
  'dsh/web-ptc': '#2cc1b0',
  'dsh/web-native': '#7fa39c',
  'dsh/acp-ptc': '#5fd4e8',
  agy: '#e3b341',
}
export const harnessColor = (k: string) => HARNESS_COLOR[canonKey(k)] ?? '#8a919c'

export const INDUSTRY_LABEL: Record<string, string> = {
  banking: 'Banking',
  telecom: 'Telecom',
  retail: 'Retail',
  'oem-devices': 'OEM devices',
  healthcare: 'Healthcare',
  insurance: 'Insurance',
  logistics: 'Logistics',
  energy: 'Energy',
}

/** Installed / latest versions: GET /api/harnesses first, then preflight (whose `installed` may be a boolean). */
export function harnessVersions(
  name: string,
  harnesses?: { name: string; version: string; installed?: string | null; latest?: string | null }[],
  pre?: { name: string; version: string; installed: string | boolean | null; latest: string | null }[],
): { installed: string | null; latest: string | null; upgrade: boolean } {
  const h = harnesses?.find((x) => x.name === name)
  const v = pre?.find((x) => x.name === name)
  const fromPre = v ? (typeof v.installed === 'string' ? v.installed : v.installed === true ? v.version : null) : null
  const installed = h?.installed ?? fromPre ?? h?.version ?? null
  const latest = h?.latest ?? v?.latest ?? null
  return { installed, latest, upgrade: !!latest && installed !== latest }
}
