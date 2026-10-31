// Deterministic attempt "script": one timeline of LLM calls, tool calls and
// terminal output, used both for the live simulation and for replay/inspection.
import type { CostStatus, LlmCall, ModelProfile, TaskInfo, Thinking, ToolCall } from '@/lib/types'
import { mulberry32, hashStr } from '@/lib/stats'
import { RATES, effectiveCost } from './catalog'
import { MODEL_SHORT, HARNESS_LABEL } from '@/lib/labels'

export interface ScriptCtx {
  attemptId: string
  harnessKey: string // e.g. "dsh/ptc"
  harnessVersion: string
  profile: ModelProfile
  task: TaskInfo
  idx: number
  passProb: number
}

export interface PtyChunk {
  t: number // seconds from t0
  data: string
}

export interface Script {
  wall_s: number
  llm_s: number
  tool_s: number
  overhead_s: number
  verify_s: number
  ttft_ms: number
  passed: boolean
  f2p: [number, number]
  p2p: [number, number]
  diff_files: number
  diff_lines: number
  calls: (Omit<LlmCall, 'attempt_id' | 't_start' | 't_first_byte' | 't_end'> & { rs: number; rfb: number; re: number })[]
  tools: (Omit<ToolCall, 'attempt_id' | 't_start' | 't_end'> & { rs: number; re: number; label: string })[]
  pty: PtyChunk[]
  cost_status: CostStatus
  failing: string[]
  log_tail: string
  subagents: number
  thinking_verified: string
  dialogs: number
}

const THINK_MULT: Record<Thinking, number> = { off: 0, low: 0.35, medium: 0.8, high: 1.6, xhigh: 2.4, max: 3.4 }

export function callCost(model: string, t: { input: number; cache_read: number; cw5: number; cw1: number; output: number; thinking: number; tool_prompt: number }): number {
  const r = RATES[model]
  if (!r) return 0
  return (
    (t.input * (r.input ?? 0) +
      t.cache_read * (r.cache_read ?? 0) +
      t.cw5 * (r.cache_write_5m ?? 0) +
      t.cw1 * (r.cache_write_1h ?? 0) +
      t.output * (r.output ?? 0) +
      t.thinking * (r.thinking ?? r.output ?? 0) +
      t.tool_prompt * (r.tool_use_prompt ?? 0)) /
    1e6
  )
}

const TOOLSETS: Record<string, string[]> = {
  claude_code: ['Read', 'Read', 'Grep', 'Edit', 'Edit', 'Bash', 'Bash', 'Glob', 'TodoWrite', 'Write'],
  pi: ['read', 'read', 'bash', 'edit', 'edit', 'bash', 'write', 'grep'],
  omp: ['read', 'read', 'grep', 'edit', 'edit', 'bash', 'bash', 'find', 'lsp'],
  agy: ['view_file', 'view_file', 'grep_search', 'replace_file_content', 'run_command', 'run_command', 'list_dir'],
  'dsh/web-native': ['read_file', 'read_file', 'search', 'edit_file', 'edit_file', 'shell', 'shell'],
  'dsh/web-ptc': ['run_code'],
  'dsh/acp-ptc': ['run_code'],
}
const PTC_NESTED = ['read', 'read', 'grep', 'edit', 'bash', 'edit', 'list']

function files(task: TaskInfo): string[] {
  const slug = task.id.split('/')[1]
  const mod = slug.split('-').slice(0, 2).join('_')
  const lang = task.languages[0]
  const ext: Record<string, string> = { python: 'py', node: 'js', go: 'go', rust: 'rs', java: 'java', c: 'c', make: 'mk' }
  const e = ext[lang] ?? 'txt'
  const base = lang === 'java' ? `src/main/java/com/acme/${mod}` : lang === 'go' ? `internal/${mod}` : `src/${mod}`
  return [`${base}.${e}`, `${base}_util.${e}`, `${base}/models.${e}`, `tests/test_${mod}.${e}`, `README.md`, `config/${mod}.toml`]
}

function testCmd(task: TaskInfo): string {
  switch (task.languages[0]) {
    case 'python':
      return 'python3 -m unittest -q'
    case 'node':
      return 'node --test'
    case 'go':
      return 'go test ./...'
    case 'rust':
      return 'cargo test --offline'
    case 'java':
      return 'javac -d out $(find src -name "*.java") && java -cp out TestMain'
    case 'c':
      return 'make test'
    default:
      return 'make check'
  }
}

// ---------- ANSI helpers ----------
const E = '\x1b['
const c = (code: string, s: string) => `${E}${code}m${s}${E}0m`
const dim = (s: string) => c('2', s)
const bold = (s: string) => c('1', s)
const fg = (n: number, s: string) => c(`38;5;${n}`, s)
const NL = '\r\n'

const ASSIST_LINES = [
  "I'll start by reading the module and the existing tests to understand the current behavior.",
  'The bug is in the normalization step: input is compared before stripping spaces and upper-casing.',
  "Let me check where this helper is called so the fix doesn't change other call sites.",
  "I'll write the fix and add a regression test for the edge case from the ticket.",
  'Running the test suite to confirm nothing else regressed.',
  'Two tests fail; the boundary case needs an inclusive comparison. Adjusting.',
  'All tests pass. Summarizing the change against the acceptance criteria.',
  'Refactoring the parser into a pure function so it can be tested in isolation.',
  'The acceptance criteria also require an audit entry; adding that to the service layer.',
]

function banner(ctx: ScriptCtx, model: string, think: Thinking): string {
  const h = ctx.harnessKey
  const m = `${model} · thinking ${think}`
  if (h === 'claude_code') {
    const w = 62
    const line = (s: string) => fg(209, '│') + ' ' + s + ' '.repeat(Math.max(0, w - 2 - stripAnsi(s).length)) + fg(209, '│')
    return (
      fg(209, '╭' + '─'.repeat(w - 1) + '╮') + NL +
      line(fg(209, '✻') + ' ' + bold('Welcome to Claude Code') + dim(` v${ctx.harnessVersion}`)) + NL +
      line('') + NL +
      line(dim('cwd: /work/') + ctx.task.id.split('/')[1]) + NL +
      line(dim('model: ') + m) + NL +
      line(dim('vertex: your-gcp-project · global · ADC')) + NL +
      fg(209, '╰' + '─'.repeat(w - 1) + '╯') + NL + NL
    )
  }
  if (h === 'pi' || h === 'omp') {
    const tag = h === 'omp' ? fg(141, bold(' ◆ oh-my-pi ')) : fg(81, bold(' π pi '))
    return tag + dim(` v${ctx.harnessVersion}  `) + fg(250, m) + NL + dim('─'.repeat(72)) + NL
  }
  if (h === 'agy') {
    return fg(75, bold('▲ Antigravity')) + dim(` ${ctx.harnessVersion} · agent platform · your-gcp-project`) + NL + dim(`  model: ${MODEL_SHORT[model] ?? model} (${think[0].toUpperCase() + think.slice(1)})`) + NL + NL
  }
  // dsh transcript (web UI rendered as text for replay)
  return fg(44, bold(h.includes('acp') ? '◉ dsh acp (stdio)' : '◉ dsh web')) + dim(` ${ctx.harnessVersion} · ${h.endsWith('ptc') ? 'tools: ptc (run_code)' : 'tools: native'} · ${m}`) + NL + NL
}

export function stripAnsi(s: string) {
  // eslint-disable-next-line no-control-regex
  return s.replace(/\x1b\[[0-9;]*m/g, '')
}

function promptLine(ctx: ScriptCtx): string {
  const p = ctx.task.title
  if (ctx.harnessKey === 'claude_code') return fg(245, '> ') + p + NL + NL
  if (ctx.harnessKey === 'agy') return fg(75, '› ') + p + NL + NL
  if (ctx.harnessKey.startsWith('dsh')) return fg(44, 'you  ') + p + NL + NL
  return fg(81, '❯ ') + p + NL + NL
}

function thinkingLine(ctx: ScriptCtx, secs: number, tok: number): string {
  if (ctx.harnessKey === 'claude_code') return fg(209, '✻ ') + fg(209, 'Thinking…') + dim(` (${secs.toFixed(0)}s · ↓ ${(tok / 1000).toFixed(1)}k tokens)`) + NL
  if (ctx.harnessKey === 'agy') return dim('  ⋯ planning ') + dim(`${secs.toFixed(0)}s`) + NL
  return dim(`  ∴ thinking ${secs.toFixed(1)}s · ${tok} tok`) + NL
}

function assistantLine(ctx: ScriptCtx, text: string): string {
  if (ctx.harnessKey === 'claude_code') return fg(255, '● ') + text + NL
  if (ctx.harnessKey === 'agy') return fg(75, '◆ ') + text + NL
  if (ctx.harnessKey.startsWith('dsh')) return fg(44, 'dsh  ') + text + NL
  return fg(250, text) + NL
}

function toolLines(ctx: ScriptCtx, name: string, arg: string, status: 'ok' | 'error' | 'denied', result: string, retry: boolean): string {
  const ok = status === 'ok'
  const mark = retry ? fg(214, '↻') : ok ? fg(78, '✓') : fg(203, '✗')
  if (ctx.harnessKey === 'claude_code') {
    return (ok ? fg(78, '● ') : fg(203, '● ')) + bold(name) + `(${arg})` + NL + dim('  ⎿  ') + (ok ? dim(result) : fg(203, result)) + NL
  }
  if (ctx.harnessKey === 'agy') return `  ${mark} ${fg(117, name)} ${dim(arg)}` + NL + `    ${ok ? dim(result) : fg(203, result)}` + NL
  if (ctx.harnessKey.endsWith('-ptc')) return `  ${mark} ${fg(44, 'run_code')} ${dim(arg)}` + NL + `    ${ok ? dim(result) : fg(203, result)}` + NL
  return `${mark} ${fg(ctx.harnessKey === 'omp' ? 141 : 81, name)} ${arg}` + NL + `  ${ok ? dim(result) : fg(203, result)}` + NL
}

/** Raw thinking request as the Meter records it (provider-shaped JSON). */
function thinkReq(model: string, level: Thinking, harnessKey: string): string {
  if (model.startsWith('claude')) return level === 'off' ? JSON.stringify({ thinking: { type: 'disabled' } }) : JSON.stringify({ thinking: { type: 'adaptive' }, output_config: { effort: level } })
  if (harnessKey === 'agy' && model.includes('flash')) return JSON.stringify({ generationConfig: { thinkingConfig: { thinkingBudget: level === 'low' ? 1024 : level === 'medium' ? 8192 : 24576, includeThoughts: true } } })
  return JSON.stringify({ generationConfig: { thinkingConfig: { thinkingLevel: level.toUpperCase(), includeThoughts: true } } })
}

export function genScript(ctx: ScriptCtx): Script {
  const r = mulberry32(hashStr(ctx.attemptId))
  const rr = (a: number, b: number) => a + (b - a) * r()
  const ri = (a: number, b: number) => Math.floor(rr(a, b + 1))
  const tier = ctx.task.tier
  const ptc = ctx.harnessKey.endsWith('-ptc')
  const roles = ctx.profile.roles ?? { default: { model: ctx.profile.stages?.[0]?.model ?? 'gemini-3.8-flash', thinking: 'medium' as Thinking } }
  const def = roles.default ?? Object.values(roles)[0]
  const plan = roles.plan
  const sub = roles.subagent

  const passed = r() < ctx.passProb
  const baseCalls = tier === 'simple' ? ri(7, 15) : tier === 'medium' ? ri(14, 28) : ri(28, 56)
  const nCalls = Math.max(3, Math.round(baseCalls * (ptc ? 0.55 : 1) * (passed ? 1 : rr(0.9, 1.4))))
  const files_ = files(ctx.task)
  const tools = TOOLSETS[ctx.harnessKey] ?? TOOLSETS.pi
  const calls: Script['calls'] = []
  const toolsOut: Script['tools'] = []
  const pty: PtyChunk[] = []

  let t = rr(0.4, 1.2)
  let prompt = rr(9000, 16000)
  let llm_s = 0
  let tool_s = 0
  let ttft = 0
  let subagents = 0
  const status: CostStatus = r() < 0.04 ? 'check' : r() < 0.012 ? 'unpriced' : 'verified'

  if (ctx.harnessKey.startsWith('dsh')) {
    // harness-internal call (session title generation): counted in spend, excluded from timing views
    const tk = { input: 420, cache_read: 0, cw5: 0, cw1: 0, output: 14, thinking: 0, tool_prompt: 0 }
    calls.push({
      id: `${ctx.attemptId}-aux`, seq: 0, rs: 0.05, rfb: 0.4, re: 0.7, http_status: 200, error_kind: null, provider: 'google', model: 'gemini-3.8-flash', model_version: 'gemini-3.8-flash-002', location: 'global', role: 'aux', traffic_type: 'ON_DEMAND', stream: false,
      tok_input: tk.input, tok_cache_read: 0, tok_cache_write_5m: 0, tok_cache_write_1h: 0, tok_output: tk.output, tok_thinking: 0, tok_tool_prompt: 0, tok_total: tk.input + tk.output, prompt_size: tk.input, tools_defined: 0, tool_calls_emitted: 0, stop_reason: 'STOP', thinking_requested: null, request_hash: 'a0a0' + (hashStr(ctx.attemptId) % 9999), is_retry: false, cost_usd: callCost('gemini-3.8-flash', tk), cost_effective_usd: effectiveCost('gemini-3.8-flash', tk, callCost('gemini-3.8-flash', tk)).usd, promotions: 'flash38-intro-50', cost_status: 'verified',
    })
  }
  pty.push({ t: 0, data: banner(ctx, def.model, def.thinking) })
  pty.push({ t: 0.2, data: promptLine(ctx) })

  for (let i = 0; i < nCalls; i++) {
    let role = 'default'
    let spec = def
    if (plan && i < 2) {
      role = 'plan'
      spec = plan
    } else if (sub && i > 3 && r() < 0.18) {
      role = 'subagent'
      spec = sub
      if (r() < 0.4) subagents++
    }
    const isClaude = spec.model.startsWith('claude')
    const thinkTok = Math.round(rr(250, 1400) * THINK_MULT[spec.thinking] * (i === 0 ? 1.8 : 1))
    const outTok = Math.round(rr(120, 900) * (i === nCalls - 1 ? 1.6 : 1))
    const growth = rr(1200, 3800)
    const cacheRead = i === 0 ? 0 : Math.round(prompt * rr(0.78, 0.94))
    const cw5 = isClaude ? Math.round(i === 0 ? prompt * 0.92 : growth * 0.9) : 0
    const uncached = Math.max(200, Math.round(prompt - cacheRead - cw5))
    const toolPrompt = isClaude ? 0 : Math.round(rr(40, 260))
    const latency = 0.6 + (outTok + thinkTok) / rr(110, 220)
    const fb = rr(0.35, 1.4) + thinkTok / 900
    if (i === 0) ttft = fb * 1000
    const is429 = r() < 0.025
    if (thinkTok > 0 && (i === 0 || r() < 0.35)) pty.push({ t: t + Math.min(fb, latency) * 0.6, data: thinkingLine(ctx, fb, thinkTok) })
    const tokens = { input: uncached, cache_read: cacheRead, cw5, cw1: 0, output: outTok, thinking: thinkTok, tool_prompt: toolPrompt }
    const cost = callCost(spec.model, tokens)
    const nTools = i === nCalls - 1 ? 0 : ptc ? 1 : r() < 0.25 ? 2 : 1
    if (is429) {
      calls.push({
        id: `${ctx.attemptId}-c${calls.length}`,
        seq: calls.length,
        rs: t,
        rfb: t + 0.2,
        re: t + 0.25,
        http_status: 429,
        error_kind: 'RESOURCE_EXHAUSTED',
        provider: isClaude ? 'anthropic' : 'google',
        model: spec.model,
        model_version: null,
        location: 'global',
        role,
        traffic_type: null,
        stream: true,
        tok_input: 0,
        tok_cache_read: 0,
        tok_cache_write_5m: 0,
        tok_cache_write_1h: 0,
        tok_output: 0,
        tok_thinking: 0,
        tok_tool_prompt: 0,
        tok_total: 0,
        prompt_size: Math.round(prompt),
        tools_defined: tools.length,
        tool_calls_emitted: 0,
        stop_reason: null,
        thinking_requested: thinkReq(spec.model, spec.thinking, ctx.harnessKey),
        request_hash: (hashStr(ctx.attemptId + i + 'r') >>> 0).toString(16),
        is_retry: false,
        cost_usd: 0,
        cost_effective_usd: 0,
        cost_status: 'verified',
      })
      t += rr(2, 6)
    }
    calls.push({
      id: `${ctx.attemptId}-c${calls.length}`,
      seq: calls.length,
      rs: t,
      rfb: t + fb,
      re: t + latency,
      http_status: 200,
      error_kind: null,
      provider: isClaude ? 'anthropic' : 'google',
      model: spec.model,
      model_version: isClaude ? 'claude-opus-5-5@20260915' : spec.model.includes('argon') ? 'gemini-4-argon-001' : 'gemini-3.8-flash-002',
      location: 'global',
      role,
      traffic_type: isClaude ? 'standard' : 'ON_DEMAND',
      stream: true,
      tok_input: uncached,
      tok_cache_read: cacheRead,
      tok_cache_write_5m: cw5,
      tok_cache_write_1h: 0,
      tok_output: outTok,
      tok_thinking: thinkTok,
      tok_tool_prompt: toolPrompt,
      tok_total: uncached + cacheRead + cw5 + outTok + thinkTok + toolPrompt,
      prompt_size: Math.round(prompt),
      tools_defined: ptc ? 1 : tools.length,
      tool_calls_emitted: nTools,
      stop_reason: nTools ? (isClaude ? 'tool_use' : 'STOP') : isClaude ? 'end_turn' : 'STOP',
      thinking_requested: thinkReq(spec.model, spec.thinking, ctx.harnessKey),
      request_hash: (hashStr(ctx.attemptId + i) >>> 0).toString(16).padStart(8, '0'),
      is_retry: is429,
      cost_usd: status === 'unpriced' ? null : cost,
      cost_effective_usd: status === 'unpriced' ? null : effectiveCost(spec.model, tokens, cost).usd,
      promotions: effectiveCost(spec.model, tokens, cost).promos.join(',') || null,
      cost_status: status,
    })
    llm_s += latency
    t += latency
    const text = ASSIST_LINES[(i + ri(0, 3)) % ASSIST_LINES.length]
    if (i === 0 || r() < 0.45 || i === nCalls - 1) pty.push({ t: t - 0.05, data: assistantLine(ctx, i === nCalls - 1 ? (passed ? 'Done. The change satisfies every acceptance criterion and the suite is green.' : 'I believe this addresses the ticket; one edge case may still be uncovered.') : text) })

    for (let k = 0; k < nTools; k++) {
      const name = tools[ri(0, tools.length - 1)]
      const f = files_[ri(0, files_.length - 1)]
      const isTest = /bash|Bash|run_command|shell|run_code/.test(name) && r() < 0.6
      const failP = isTest && !passed && i > nCalls * 0.6 ? 0.55 : 0.08
      const st: 'ok' | 'error' | 'denied' = r() < failP ? 'error' : r() < 0.01 ? 'denied' : 'ok'
      const prev = toolsOut[toolsOut.length - 1]
      const retry = !!prev && prev.status === 'error' && r() < 0.5
      const dur = ptc ? rr(2, 9) : isTest ? rr(1.5, 8) : rr(0.05, 0.8)
      const arg = ptc
        ? `${ri(3, 9)} calls: ${PTC_NESTED.slice(0, ri(2, 5)).join(', ')}`
        : isTest
          ? testCmd(ctx.task)
          : f
      const result =
        st === 'error'
          ? isTest
            ? `FAILED (failures=${ri(1, 3)}) — test_${ctx.task.id.split('/')[1].replace(/-/g, '_')}_edge`
            : 'Error: old_string not found in file'
          : st === 'denied'
            ? 'Permission denied by preset'
            : isTest
              ? `Ran ${ri(8, 40)} tests in ${rr(0.2, 3).toFixed(2)}s — OK`
              : /edit|Edit|replace|write|Write/.test(name)
                ? `Updated ${f} with ${ri(1, 12)} additions and ${ri(0, 6)} removals`
                : `Read ${ri(20, 400)} lines`
      const callId = `${ctx.attemptId}-t${toolsOut.length}`
      toolsOut.push({
        id: callId,
        call_id: callId,
        parent_id: null,
        name,
        args_hash: (hashStr(callId) >>> 0).toString(16).slice(0, 8),
        status: st,
        error_code: st === 'error' ? (isTest ? 'EXIT_1' : 'NOT_FOUND') : st === 'denied' ? 'DENIED' : null,
        rs: t,
        re: t + dur,
        is_retry: retry,
        source: 'native',
        label: arg,
      })
      if (ptc) {
        const n = ri(2, 6)
        for (let j = 0; j < n; j++) {
          const nid = `${callId}:ptc:${j}`
          toolsOut.push({
            id: nid,
            call_id: nid,
            parent_id: callId,
            name: PTC_NESTED[ri(0, PTC_NESTED.length - 1)],
            args_hash: null,
            status: st === 'error' && j === n - 1 ? 'error' : 'ok',
            error_code: st === 'error' && j === n - 1 ? 'exception' : null,
            rs: t + (dur * j) / n,
            re: t + (dur * (j + 1)) / n,
            is_retry: false,
            source: 'native',
            label: f,
          })
        }
      }
      pty.push({ t: t + 0.05, data: toolLines(ctx, name, arg, st, result, retry) })
      tool_s += dur
      t += dur + rr(0.05, 0.4)
    }
    prompt += growth + outTok
  }
  const overhead = (llm_s + tool_s) * rr(0.08, 0.2)
  t += overhead * 0.3
  const f2pTotal = ri(2, 6)
  const p2pTotal = ri(4, 24)
  const f2pPassed = passed ? f2pTotal : ri(0, f2pTotal - 1)
  const p2pPassed = passed ? p2pTotal : r() < 0.3 ? p2pTotal - ri(1, 2) : p2pTotal
  const failing = passed ? [] : Array.from({ length: f2pTotal - f2pPassed }, (_, i) => `test_${ctx.task.id.split('/')[1].replace(/-/g, '_')}_case_${i + 1}`)
  pty.push({
    t: t,
    data:
      NL +
      (ctx.harnessKey === 'claude_code' ? dim('  ⏵⏵ idle · ') : dim('  · idle · ')) +
      dim(`${calls.length} calls · ${toolsOut.filter((x) => !x.parent_id).length} tools`) +
      NL,
  })
  const verify = rr(6, tier === 'complex' ? 45 : 20)
  const log_tail = [
    `$ bash tests/run.sh /tmp/verify-${ctx.attemptId.slice(-6)} results.json`,
    `overlaying ${f2pTotal + 2} hidden test files`,
    `${testCmd(ctx.task)}`,
    ...failing.map((f) => `FAIL: ${f} (AssertionError: expected True, got False)`),
    `Ran ${f2pTotal + p2pTotal} tests in ${rr(0.4, 6).toFixed(2)}s`,
    passed ? 'OK' : `FAILED (failures=${failing.length + (p2pTotal - p2pPassed)})`,
  ].join('\n')
  return {
    wall_s: t,
    llm_s,
    tool_s,
    overhead_s: Math.max(0, t - llm_s - tool_s),
    verify_s: verify,
    ttft_ms: ttft,
    passed,
    f2p: [f2pPassed, f2pTotal],
    p2p: [p2pPassed, p2pTotal],
    diff_files: ri(1, tier === 'simple' ? 2 : tier === 'medium' ? 5 : 11),
    diff_lines: ri(4, tier === 'simple' ? 40 : tier === 'medium' ? 180 : 620),
    calls,
    tools: toolsOut,
    pty,
    cost_status: status,
    failing,
    log_tail,
    subagents,
    thinking_verified: def.thinking === 'off' ? 'absent' : r() < 0.86 ? 'match' : r() < 0.5 ? 'partial' : ctx.harnessKey === 'pi' ? 'mismatch' : 'unknown',
    dialogs: r() < 0.2 ? ri(1, 2) : 0,
  }
}

export function scriptToCast(s: Script, t0: number, title: string): string {
  const head = JSON.stringify({ version: 2, width: 110, height: 34, timestamp: Math.floor(t0), title, env: { TERM: 'xterm-256color', SHELL: '/bin/bash' } })
  const lines = s.pty.map((p) => JSON.stringify([Number(p.t.toFixed(3)), 'o', p.data]))
  return [head, ...lines].join('\n') + '\n'
}

export { HARNESS_LABEL }
