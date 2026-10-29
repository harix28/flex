import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message: string;
  requestId?: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Failed to load data',
  message,
  requestId,
  onRetry,
  className = '',
}) => {
  return (
    <div
      className={`alert alert-danger ${className}`}
      role="alert"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <AlertCircle size={20} aria-hidden="true" />
        <strong style={{ fontSize: '0.9375rem' }}>{title}</strong>
      </div>
      <p style={{ fontSize: '0.875rem', lineHeight: 1.4 }}>{message}</p>
      {requestId && (
        <span
          className="mono"
          style={{
            fontSize: '0.75rem',
            color: 'var(--text-muted)',
          }}
        >
          Request ID: {requestId}
        </span>
      )}
      {onRetry && (
        <div style={{ marginTop: '0.5rem' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onRetry}
            style={{ fontSize: '0.8125rem', padding: '0.375rem 0.75rem' }}
          >
            <RefreshCw size={14} aria-hidden="true" />
            <span>Retry Operation</span>
          </button>
        </div>
      )}
    </div>
  );
};
