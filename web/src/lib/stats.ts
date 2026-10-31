// Small, dependency-free statistics used by the mock aggregator and client-side slices.

export function mulberry32(seed: number) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function hashStr(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

export const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0)

export function quantile(xs: number[], q: number): number {
  if (!xs.length) return 0
  const s = [...xs].sort((a, b) => a - b)
  const pos = (s.length - 1) * q
  const lo = Math.floor(pos)
  const hi = Math.ceil(pos)
  return s[lo] + (s[hi] - s[lo]) * (pos - lo)
}

/** 95% percentile bootstrap CI of the mean. */
export function bootstrapCI(xs: number[], iters = 400, seed = 7): [number, number] {
  if (xs.length < 2) return [xs[0] ?? 0, xs[0] ?? 0]
  const r = mulberry32(seed)
  const ms: number[] = []
  for (let i = 0; i < iters; i++) {
    let s = 0
    for (let j = 0; j < xs.length; j++) s += xs[Math.floor(r() * xs.length)]
    ms.push(s / xs.length)
  }
  return [quantile(ms, 0.025), quantile(ms, 0.975)]
}

/** Wilson score interval for a proportion. */
export function wilson(k: number, n: number, z = 1.96): [number, number] {
  if (n === 0) return [0, 0]
  const p = k / n
  const d = 1 + (z * z) / n
  const c = p + (z * z) / (2 * n)
  const w = z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))
  return [Math.max(0, (c - w) / d), Math.min(1, (c + w) / d)]
}

/** Unbiased pass@k estimator (Chen et al.). n samples, c correct. */
export function passAtK(n: number, c: number, k: number): number {
  if (n - c < k) return 1
  let prod = 1
  for (let i = n - c + 1; i <= n; i++) prod *= 1 - k / i
  return 1 - prod
}
