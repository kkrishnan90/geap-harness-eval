import type { ModelProfile } from './types'

export const PRESET_PROFILES: ModelProfile[] = [
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

export const ROLE_SETS: Record<string, string[]> = {
  single: ['default'],
  native_roles: ['plan', 'default', 'subagent'],
  pipeline: ['plan', 'execute'],
}
