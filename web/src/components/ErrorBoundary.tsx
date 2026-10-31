import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'

/** Contains a render failure to the subtree; shows the message inline instead of blanking the page. */
export class ErrorBoundary extends Component<{ children: ReactNode; label?: string; compact?: boolean; resetKey?: unknown }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) {
    return { error }
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.warn(`[dashboard] ${this.props.label ?? 'view'} failed to render:`, error, info.componentStack)
  }
  componentDidUpdate(prev: { resetKey?: unknown }) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null })
  }
  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className={`panel flex items-start gap-3 border-[color-mix(in_oklab,var(--fail)_40%,transparent)] ${this.props.compact ? 'p-3' : 'p-4'}`} role="alert">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-fail" />
        <div className="min-w-0">
          <div className="text-[12.5px] font-medium">{this.props.label ?? 'This view'} could not render</div>
          <div className="mt-0.5 break-words font-mono text-[11px] text-muted">{this.state.error.message}</div>
          <button className="mt-2 text-[11.5px] text-accent hover:underline" onClick={() => this.setState({ error: null })}>
            Try again
          </button>
        </div>
      </div>
    )
  }
}
