import { Component, type ErrorInfo, type ReactNode } from 'react';

type Props = { children: ReactNode; routeKey: string };
type State = { error: Error | null };

export class WorkstationRouteBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[workstation-route-error]', {
      route: this.props.routeKey,
      message: error.message,
      stack: error.stack,
      componentStack: info.componentStack,
    });
  }

  componentDidUpdate(previous: Props) {
    if (previous.routeKey !== this.props.routeKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <section className="route-recovery-state" role="alert">
        <div>
          <span>WORKSPACE RECOVERY</span>
          <h2>This page could not render.</h2>
          <p>{this.state.error.message || 'An unexpected workstation error occurred.'}</p>
          <div className="route-recovery-actions">
            <button onClick={() => this.setState({ error: null })}>Retry page</button>
            <button onClick={() => location.reload()}>Reload workstation</button>
          </div>
          <details>
            <summary>Technical details</summary>
            <pre>{this.state.error.stack}</pre>
          </details>
        </div>
      </section>
    );
  }
}
