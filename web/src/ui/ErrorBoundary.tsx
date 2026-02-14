import React from 'react'

type Props = { children: React.ReactNode }
type State = { error?: string }

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = {}
  }

  static getDerivedStateFromError(error: any) {
    return { error: String(error?.message || error) }
  }

  componentDidCatch(error: any, info: any) {
    // eslint-disable-next-line no-console
    console.error('UI crash:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="container">
          <div className="card" style={{ borderColor: 'rgba(255,92,92,0.35)' }}>
            <div className="cardTitle">UI error</div>
            <div className="small">The UI crashed while rendering. Check the message below (and browser console) to pinpoint the issue.</div>
            <div style={{ height: 10 }} />
            <div className="mono">{this.state.error}</div>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
