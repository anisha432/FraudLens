import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error.message, errorInfo.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          padding: 40,
          background: '#0a0e17',
          color: '#e5e7eb',
          fontFamily: "'Inter', sans-serif",
        }}>
          <div style={{
            maxWidth: 500,
            textAlign: 'center',
            background: '#1a2234',
            border: '1px solid #2a3650',
            borderRadius: 12,
            padding: 32,
          }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
            <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>Something went wrong</h2>
            <p style={{ fontSize: 13, color: '#9ca3af', marginBottom: 20 }}>
              An unexpected error occurred. You can try reloading the page.
            </p>
            <p style={{
              fontSize: 11,
              color: '#6b7280',
              fontFamily: "'JetBrains Mono', monospace",
              background: '#0a0e17',
              padding: 12,
              borderRadius: 8,
              marginBottom: 20,
              wordBreak: 'break-word',
              textAlign: 'left',
              maxHeight: 120,
              overflow: 'auto',
            }}>
              {this.state.error?.message || 'Unknown error'}
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.href = '/command';
              }}
              style={{
                padding: '10px 24px',
                background: '#3b82f6',
                color: 'white',
                border: 'none',
                borderRadius: 8,
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
                fontFamily: "'Inter', sans-serif",
              }}
            >
              Reload Command Center
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
