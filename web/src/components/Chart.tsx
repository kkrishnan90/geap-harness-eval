import * as echarts from 'echarts/core'
import { BarChart, LineChart, ScatterChart, HeatmapChart, SankeyChart, CustomChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, VisualMapComponent, MarkLineComponent, MarkAreaComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useEffect, useMemo, useRef } from 'react'
import { useTheme } from '@/lib/theme'
import { cssVar } from '@/lib/utils'

echarts.use([BarChart, LineChart, ScatterChart, HeatmapChart, SankeyChart, CustomChart, GridComponent, TooltipComponent, LegendComponent, VisualMapComponent, MarkLineComponent, MarkAreaComponent, DataZoomComponent, CanvasRenderer])

/** Mix two hex colors (t=0 → a, t=1 → b). ECharts cannot parse CSS color-mix(). */
export function mix(a: string, b: string, t: number): string {
  const h = (x: string) => {
    const s = x.replace('#', '')
    const f = s.length === 3 ? s.split('').map((c) => c + c).join('') : s
    return [0, 2, 4].map((i) => parseInt(f.slice(i, i + 2), 16))
  }
  try {
    const A = h(a)
    const B = h(b)
    return '#' + A.map((v, i) => Math.round(v + (B[i] - v) * t).toString(16).padStart(2, '0')).join('')
  } catch {
    return a
  }
}

export type ChartTokens = ReturnType<typeof readTokens>

function readTokens() {
  const v = (n: string) => cssVar(n)
  return {
    fg: v('--fg'),
    fg2: v('--fg-2'),
    muted: v('--muted'),
    faint: v('--faint'),
    line: v('--line'),
    lineStrong: v('--line-strong'),
    panel: v('--panel'),
    raised: v('--raised'),
    sunken: v('--sunken'),
    accent: v('--accent'),
    pass: v('--pass'),
    fail: v('--fail'),
    warn: v('--warn'),
    verified: v('--cost-verified'),
    check: v('--cost-check'),
    unpriced: v('--cost-unpriced'),
    tok: {
      input: v('--tok-input'),
      cache_read: v('--tok-cache-read'),
      cache_write: v('--tok-cache-write'),
      output: v('--tok-output'),
      thinking: v('--tok-thinking'),
    } as Record<string, string>,
    mono: "'JetBrains Mono Variable', ui-monospace, monospace",
    sans: "'Geist Variable', ui-sans-serif, system-ui",
  }
}

export function useChartTokens(): ChartTokens {
  const { theme } = useTheme()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  return useMemo(() => readTokens(), [theme])
}

/** Common axis/tooltip styling derived from CSS tokens. */
export function baseOption(k: ChartTokens) {
  return {
    backgroundColor: 'transparent',
    textStyle: { fontFamily: k.sans, color: k.fg2, fontSize: 11 },
    animationDuration: 500,
    animationEasing: 'cubicOut' as const,
    tooltip: {
      backgroundColor: k.raised,
      borderColor: k.lineStrong,
      borderWidth: 1,
      padding: [8, 10],
      textStyle: { color: k.fg, fontSize: 11.5, fontFamily: k.sans },
      extraCssText: 'border-radius:8px;box-shadow:0 8px 24px -8px rgba(0,0,0,.45);',
    },
  }
}

export function axis(k: ChartTokens, extra: Record<string, unknown> = {}) {
  return {
    axisLine: { lineStyle: { color: k.line } },
    axisTick: { show: false },
    axisLabel: { color: k.muted, fontSize: 10.5, fontFamily: k.mono },
    splitLine: { lineStyle: { color: k.line, type: [2, 3] as number[] } },
    nameTextStyle: { color: k.muted, fontSize: 10.5 },
    ...extra,
  }
}

export function Chart({ option, height = 260, className, onEvents }: { option: Record<string, unknown>; height?: number | string; className?: string; onEvents?: Record<string, (p: unknown) => void> }) {
  const { theme } = useTheme()
  const el = useRef<HTMLDivElement>(null)
  const inst = useRef<echarts.ECharts | null>(null)
  useEffect(() => {
    const c = echarts.init(el.current!, undefined, { renderer: 'canvas' })
    inst.current = c
    const ro = new ResizeObserver(() => c.resize())
    ro.observe(el.current!)
    return () => {
      ro.disconnect()
      c.dispose()
      inst.current = null
    }
  }, [theme])
  useEffect(() => {
    inst.current?.setOption(option, { notMerge: true, lazyUpdate: true })
  }, [option, theme])
  useEffect(() => {
    const c = inst.current
    if (!c || !onEvents) return
    for (const [k, f] of Object.entries(onEvents)) c.on(k, f)
    return () => {
      for (const k of Object.keys(onEvents)) c.off(k)
    }
  }, [onEvents, theme])
  return <div ref={el} className={className} style={{ height, width: '100%' }} />
}
