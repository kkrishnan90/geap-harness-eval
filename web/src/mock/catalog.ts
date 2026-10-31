import { HARNESS_LABEL } from '@/lib/labels'
import type { HarnessInfo, ModelInfo, ModelProfile, PricingBook, Preflight, Promotion, TaskInfo, Thinking } from '@/lib/types'

export const LOCATIONS = [
  'global',
  'us-central1',
  'us-east5',
  'us-east1',
  'us-south1',
  'europe-west1',
  'europe-west4',
  'asia-southeast1',
  'asia-south1',
  'asia-northeast1',
]

// From PLAN.md §0 availability probe (2026-10-30).
const AVAIL: Record<string, string[]> = {
  'gemini-4-argon': ['ok', '404', '404', '404', '404', '404', '404', 'ok', '404', '404'],
  'gemini-3.8-flash': ['ok', '404', '404', '404', '404', '404', '404', '404', '404', '404'],
  'claude-opus-5-5': ['ok', '429', '429', '429', '429', '429', '429', '429', '404', '400'],
  'claude-sonnet-5-5': ['404', '404', '404', '404', '404', '404', '404', '404', '404', '404'],
}

export const MODELS: ModelInfo[] = [
  { id: 'gemini-4-argon', family: 'Gemini 4', provider: 'google', locations: ['global', 'asia-southeast1'], thinking_levels: ['low', 'medium', 'high'], priced: true, enabled: true },
  { id: 'gemini-3.8-flash', family: 'Gemini 3.8', provider: 'google', locations: ['global'], thinking_levels: ['low', 'medium', 'high'], priced: true, enabled: true },
  { id: 'claude-opus-5-5', family: 'Claude Opus 5.5', provider: 'anthropic', locations: ['global'], thinking_levels: ['off', 'low', 'medium', 'high', 'xhigh', 'max'], priced: true, enabled: true },
  { id: 'claude-sonnet-5-5', family: 'Claude Sonnet 5.5', provider: 'anthropic', locations: [], thinking_levels: [], priced: true, enabled: false },
]

export { MODEL_SHORT, HARNESS_LABEL } from '@/lib/labels'

export const HARNESSES: HarnessInfo[] = [
  { name: 'claude_code', variant: 'default', version: '2.1.314', capabilities: { roles: ['default', 'plan', 'subagent'], native_multi_model: true, pipeline: true, thinking_control: true, meter_mode: 'reverse_proxy', driver: 'pty' } },
  { name: 'pi', variant: 'default', version: '1.4.0', capabilities: { roles: ['default'], native_multi_model: false, pipeline: true, thinking_control: true, meter_mode: 'reverse_proxy', driver: 'pty' } },
  { name: 'omp', variant: 'default', version: '18.14.0', capabilities: { roles: ['default', 'plan', 'subagent'], native_multi_model: true, pipeline: true, thinking_control: true, meter_mode: 'reverse_proxy', driver: 'pty' } },
  { name: 'dsh', variant: 'web-ptc', version: '0.2.1-rc.5', capabilities: { roles: ['default'], native_multi_model: false, pipeline: false, thinking_control: true, meter_mode: 'reverse_proxy', driver: 'browser' } },
  { name: 'dsh', variant: 'web-native', version: '0.2.1-rc.5', capabilities: { roles: ['default'], native_multi_model: false, pipeline: false, thinking_control: true, meter_mode: 'reverse_proxy', driver: 'browser' } },
  { name: 'dsh', variant: 'acp-ptc', version: '0.2.1-rc.5', capabilities: { roles: ['default'], native_multi_model: false, pipeline: false, thinking_control: true, meter_mode: 'reverse_proxy', driver: 'acp' } },
  { name: 'agy', variant: 'default', version: '1.9.2', capabilities: { roles: ['default'], native_multi_model: false, pipeline: true, thinking_control: true, meter_mode: 'reverse_proxy', driver: 'pty' } },
]


const T = (id: string, title: string, tier: TaskInfo['tier'], sdlc: string, languages: string[]): TaskInfo => ({
  id,
  version: '1',
  title,
  industry: id.split('/')[0],
  tier,
  sdlc_type: sdlc,
  languages,
  timeout_s: tier === 'simple' ? 600 : tier === 'medium' ? 1500 : 3600,
})

export const TASKS: TaskInfo[] = [
  T('banking/iban-checksum-bug', 'Fix IBAN mod-97 validation for lowercase and spaced input', 'simple', 'bug-fix', ['python']),
  T('banking/ledger-rounding-drift', 'Stop half-cent drift in daily ledger close', 'medium', 'bug-fix', ['python']),
  T('banking/sepa-batch-export', 'Add SEPA pain.001 batch export with schema checks', 'complex', 'feature', ['java']),
  T('banking/kyc-pii-logging', 'Remove PII from KYC audit log lines', 'simple', 'security', ['python']),
  T('banking/fx-rate-cache', 'Cache FX rates with TTL and stale-while-revalidate', 'medium', 'performance', ['go']),
  T('telecom/cdr-parser-overflow', 'Fix 32-bit overflow in CDR duration parser', 'simple', 'bug-fix', ['c']),
  T('telecom/number-porting-flow', 'Implement number-porting state machine', 'complex', 'feature', ['go']),
  T('telecom/plan-pricing-tests', 'Write tests for tiered data-plan pricing', 'medium', 'test-authoring', ['node']),
  T('telecom/sip-header-refactor', 'Extract SIP header parsing into a module', 'medium', 'refactor', ['rust']),
  T('retail/cart-tax-rounding', 'Correct per-line tax rounding in cart totals', 'simple', 'bug-fix', ['node']),
  T('retail/inventory-reservation', 'Add expiring inventory reservations', 'medium', 'feature', ['python']),
  T('retail/promo-engine-refactor', 'Split promo engine rules from evaluation', 'complex', 'refactor', ['node']),
  T('retail/search-n-plus-one', 'Remove N+1 queries from catalog search', 'medium', 'performance', ['python']),
  T('oem-devices/firmware-crc', 'Fix CRC-16 check on firmware chunk boundaries', 'simple', 'bug-fix', ['c']),
  T('oem-devices/ota-rollout-gate', 'Gate OTA rollout by device cohort and battery', 'complex', 'feature', ['rust']),
  T('oem-devices/telemetry-ring-buffer', 'Make telemetry ring buffer lock-free safe', 'medium', 'bug-fix', ['c']),
  T('oem-devices/ci-cross-compile', 'Repair ARM cross-compile CI job', 'medium', 'ci-repair', ['make']),
  T('healthcare/hl7-segment-parse', 'Parse repeating HL7 OBX segments correctly', 'simple', 'bug-fix', ['python']),
  T('healthcare/fhir-patient-merge', 'Implement FHIR patient merge with link audit', 'complex', 'feature', ['java']),
  T('healthcare/phi-redaction', 'Redact PHI in exported CSV reports', 'medium', 'security', ['python']),
  T('healthcare/dose-calc-tests', 'Add tests for pediatric dose calculator', 'simple', 'test-authoring', ['node']),
  T('insurance/claim-dedupe', 'Deduplicate claims by policy, date and amount', 'medium', 'bug-fix', ['python']),
  T('insurance/premium-calc-upgrade', 'Upgrade premium calculator to decimal money', 'medium', 'upgrade', ['java']),
  T('insurance/fraud-rules-dsl', 'Add a small DSL for fraud screening rules', 'complex', 'feature', ['python']),
  T('insurance/sql-injection-quote', 'Fix SQL injection in quote search', 'simple', 'security', ['python']),
  T('logistics/route-eta-timezone', 'Fix ETA timezone handling across DST', 'simple', 'bug-fix', ['go']),
  T('logistics/manifest-validator', 'Validate shipment manifests against carrier rules', 'medium', 'feature', ['node']),
  T('logistics/warehouse-pick-optimizer', 'Speed up warehouse pick-path optimizer', 'complex', 'performance', ['rust']),
  T('logistics/label-printer-ci', 'Fix flaky label-printer integration CI', 'medium', 'ci-repair', ['python']),
  T('energy/meter-reading-gaps', 'Interpolate gaps in smart-meter readings', 'simple', 'bug-fix', ['python']),
  T('energy/tariff-engine-refactor', 'Refactor time-of-use tariff engine', 'complex', 'refactor', ['go']),
  T('energy/outage-api-tests', 'Write contract tests for outage API', 'medium', 'test-authoring', ['node']),
  T('energy/scada-cert-pinning', 'Pin certificates for SCADA gateway client', 'medium', 'security', ['go']),
  T('banking/openapi-upgrade', 'Upgrade payments client to OpenAPI 3.1 types', 'medium', 'upgrade', ['node']),
  T('retail/checkout-ci-cache', 'Repair checkout CI cache key collisions', 'simple', 'ci-repair', ['make']),
  T('telecom/billing-batch-perf', 'Cut nightly billing batch time by 3x', 'complex', 'performance', ['java']),
]

export const MVP_TASKS = [
  'banking/iban-checksum-bug',
  'banking/ledger-rounding-drift',
  'telecom/cdr-parser-overflow',
  'telecom/number-porting-flow',
  'retail/cart-tax-rounding',
  'retail/promo-engine-refactor',
  'oem-devices/firmware-crc',
  'healthcare/hl7-segment-parse',
  'healthcare/fhir-patient-merge',
  'insurance/claim-dedupe',
  'logistics/route-eta-timezone',
  'energy/tariff-engine-refactor',
]

// USD per 1M tokens (catalog snapshot, global, standard on-demand, ≤200k tier).
export const RATES: Record<string, Record<string, number>> = {
  'gemini-4-argon': { input: 4.0, cache_read: 0.2, output: 20.0, thinking: 20.0, tool_use_prompt: 4.0 },
  'gemini-3.8-flash': { input: 1.5, cache_read: 0.15, output: 7.5, thinking: 7.5, tool_use_prompt: 1.5 },
  'claude-opus-5-5': { input: 5.0, cache_write_5m: 6.25, cache_write_1h: 10.0, cache_read: 0.5, output: 25.0, thinking: 25.0 },
  'claude-sonnet-5-5': { input: 2.0, cache_write_5m: 2.5, cache_write_1h: 4.0, cache_read: 0.1, output: 10.0, thinking: 10.0 },
}

const PAGE = 'https://cloud.google.com/vertex-ai/generative-ai/pricing'

export const PROMOTIONS: Promotion[] = [
  {
    id: 'argon-launch-credit-50',
    models: ['gemini-4-argon'],
    locality: 'global',
    until: '2026-11-30',
    factor: { input: 0.5, cache_read: 0.5, output: 0.5 },
    mechanism: 'Credit: billed at list price, 50% of net spend credited back to the billing account',
    quote: 'Gemini 4 Argon launch offer: receive 50% credits back on net spend through November 30, 2026.',
    source: PAGE,
  },
  {
    id: 'flash38-intro-50',
    models: ['gemini-3.8-flash'],
    locality: 'global',
    until: '2026-12-31',
    factor: { input: 0.5, output: 0.5 },
    mechanism: 'Credit: billed at list price, introductory 50% on input and output credited back',
    quote: 'Introductory pricing for Gemini 3.8 Flash: 50% off input and output tokens through December 31, 2026.',
    source: PAGE,
  },
]

const L4: [string, string, number, number, string][] = [
  ['gemini-4-argon', 'input', 4.0, 4.0, 'Gemini 4 Argon · Input (text, image, video) · $4.00 / 1M tokens'],
  ['gemini-4-argon', 'output', 20.0, 20.0, 'Gemini 4 Argon · Text output (incl. thinking) · $20.00 / 1M tokens'],
  ['gemini-4-argon', 'cache_read', 0.2, 0.2, 'Context caching · $0.20 / 1M tokens'],
  ['gemini-3.8-flash', 'input', 1.5, 1.5, 'Gemini 3.8 Flash · Input · $1.50 / 1M tokens'],
  ['gemini-3.8-flash', 'output', 7.5, 7.5, 'Gemini 3.8 Flash · Output (incl. thinking) · $7.50 / 1M tokens'],
  ['claude-opus-5-5', 'input', 5.0, 5.0, 'Claude Opus 5.5 · Input · $5.00 / MTok'],
  ['claude-opus-5-5', 'output', 25.0, 25.0, 'Claude Opus 5.5 · Output · $25.00 / MTok'],
  ['claude-opus-5-5', 'cache_write_5m', 6.25, 6.25, 'Claude Opus 5.5 · 5m cache write · $6.25 / MTok'],
  ['claude-opus-5-5', 'cache_read', 0.5, 0.5, 'Claude Opus 5.5 · Cache hits · $0.50 / MTok'],
  ['claude-sonnet-5-5', 'input', 2.0, 2.0, 'Claude Sonnet 5.5 · Input · $2.00 / MTok'],
]

export const PRICING: PricingBook = {
  snapshot_id: 'pb-2026-10-30-7f3a91c2',
  fetched_at: Date.now() / 1000 - 3600 * 2.4,
  models: Object.entries(RATES).map(([model, rates]) => ({ model, location: 'global', rates })),
  issues: ['gemini-3.8-flash: introductory pricing ends 2026-12-31; snapshot will change on sync after that date.'],
  reviewed: true,
  layer4: {
    ok: true,
    fetched_at: Date.now() / 1000 - 3600 * 9,
    url: PAGE,
    checks: L4.map(([model, category, c, p, quote]) => ({ model, category, catalog_per_1m: c, page_per_1m: p, ok: Math.abs(c - p) < 1e-9, quote })),
    failed: [],
  },
  promotions: PROMOTIONS,
  promotions_reviewed: true,
}

/** Effective (after reviewed promotions) cost of one call. Thinking is billed as output. */
export function effectiveCost(model: string, t: { input: number; cache_read: number; cw5: number; cw1: number; output: number; thinking: number; tool_prompt: number }, list: number): { usd: number; promos: string[] } {
  const r = RATES[model]
  const ps = PROMOTIONS.filter((p) => p.models.includes(model))
  if (!r || !ps.length) return { usd: list, promos: [] }
  let usd = list
  for (const p of ps) {
    const f = p.factor
    const save = (k: keyof typeof f, tok: number, rate: number) => (f[k] != null ? (tok * rate * (1 - f[k]!)) / 1e6 : 0)
    usd -= save('input', t.input + t.tool_prompt, r.input ?? 0) + save('cache_read', t.cache_read, r.cache_read ?? 0) + save('output', t.output + t.thinking, r.output ?? 0)
  }
  return { usd: Math.max(0, usd), promos: ps.map((p) => p.id) }
}

export const PREFLIGHT: Preflight = {
  credentials: {
    ok: true,
    identity: 'you@example.com',
    project: 'your-gcp-project',
    adc_type: 'authorized_user',
    expires_in: 3412,
    issues: [],
  },
  models: {
    ok: true,
    availability: Object.entries(AVAIL).flatMap(([model, row]) =>
      row.map((status, i) => ({
        model,
        location: LOCATIONS[i],
        status,
        thinking_levels: status === 'ok' ? (MODELS.find((m) => m.id === model)?.thinking_levels ?? []) : ([] as Thinking[]),
      })),
    ),
  },
  pricing: { ok: true, snapshot_id: PRICING.snapshot_id, fetched_at: PRICING.fetched_at, issues: PRICING.issues },
  harnesses: [
    { name: 'claude_code', version: '2.1.314', installed: '2.1.311', latest: '2.1.314' },
    { name: 'pi', version: '1.4.0', installed: '1.4.0', latest: '1.4.0' },
    { name: 'omp', version: '18.14.0', installed: '18.12.3', latest: '18.14.0' },
    { name: 'dsh', version: '0.2.1-rc.5', installed: '0.2.1-rc.5', latest: '0.2.1-rc.5' },
    { name: 'agy', version: '1.9.2', installed: null, latest: '1.9.2' },
  ],
}

export const DEFAULT_PROFILES: ModelProfile[] = [
  { id: 'opus-high', mode: 'single', roles: { default: { model: 'claude-opus-5-5', thinking: 'high' } } },
  { id: 'flash-med', mode: 'single', roles: { default: { model: 'gemini-3.8-flash', thinking: 'medium' } } },
  { id: 'argon-high', mode: 'single', roles: { default: { model: 'gemini-4-argon', thinking: 'high' } } },
  {
    id: 'argon-plans-flash-codes',
    mode: 'native_roles',
    roles: {
      plan: { model: 'gemini-4-argon', thinking: 'high' },
      default: { model: 'gemini-3.8-flash', thinking: 'medium' },
      subagent: { model: 'gemini-3.8-flash', thinking: 'low' },
    },
  },
]

export function profileModels(p: ModelProfile): string[] {
  const s = new Set<string>()
  Object.values(p.roles ?? {}).forEach((r) => s.add(r.model))
  ;(p.stages ?? []).forEach((r) => s.add(r.model))
  return [...s]
}

/** N/A rules used by the mock dry-run (mirrors PLAN.md §0 / §5 / §12). */
export function naReason(harnessKey: string, profile: ModelProfile): string | null {
  const [name] = harnessKey.split('/')
  const models = profileModels(profile)
  const disabled = models.find((m) => MODELS.find((x) => x.id === m && !x.enabled))
  if (disabled) return `${disabled} is not enabled for this project (Model Garden terms not accepted)`
  if (name === 'claude_code' && models.some((m) => m.startsWith('gemini')))
    return 'Claude Code speaks only the Anthropic Messages API; Gemini models are not routable'
  if ((name === 'pi' || name === 'dsh') && models.some((m) => m.startsWith('claude')))
    return `${name === 'pi' ? 'Pi' : 'dsh'} has no vanilla route to Claude on Vertex (no Anthropic-on-Vertex provider)`
  if (name === 'omp') {
    const roles = [...Object.values(profile.roles ?? {}), ...(profile.stages ?? []).map((s) => ({ model: s.model, thinking: s.thinking ?? 'high' }))]
    const bad = roles.find((r) => r.model.startsWith('claude') && r.thinking !== 'high')
    if (bad) return `omp drives Claude only with adaptive thinking ("high"); ${bad.thinking} is not expressible`
  }
  if (name === 'pi' && models.includes('gemini-4-argon'))
    return 'pi-ai sends thinkingBudget for Argon; Argon requires thinkingLevel (harness-incompatible)'
  if (profile.mode === 'native_roles' && !['claude_code', 'omp'].includes(name))
    return `${HARNESS_LABEL[name] ?? name} has no native per-role model routing`
  if (profile.mode === 'pipeline' && name === 'dsh') return 'dsh web has no in-session model switch'
  return null
}
