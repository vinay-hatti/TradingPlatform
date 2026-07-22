import React, { type ErrorInfo, type PropsWithChildren } from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

interface BoundaryState { error?: Error }

class Boundary extends React.Component<PropsWithChildren, BoundaryState> {
  state: BoundaryState = {};

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Workstation render failure', error, info);
  }

  render() {
    if (this.state.error) {
      return <div style={{ padding: 40, fontFamily: 'system-ui' }}><h1>Workstation error</h1><p>{this.state.error.message}</p><button onClick={() => location.reload()}>Reload</button></div>;
    }
    return this.props.children;
  }
}

const root = document.getElementById('root');
if (!root) throw new Error('Missing #root mount element');
ReactDOM.createRoot(root).render(<React.StrictMode><Boundary><App /></Boundary></React.StrictMode>);
