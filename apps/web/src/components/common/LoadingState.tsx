import React from 'react';
import { Loader2 } from 'lucide-react';

interface LoadingStateProps {
  message?: string;
  className?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Loading telemetry and fleet data...',
  className = '',
}) => {
  return (
    <div
      className={`card flex flex-col items-center justify-center p-8 text-center ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '3rem 1.5rem',
        textAlign: 'center',
        gap: '0.75rem',
      }}
      role="status"
      aria-live="polite"
    >
      <Loader2
        size={32}
        className="animate-spin text-primary"
        style={{
          color: 'var(--primary)',
          animation: 'spin 1s linear infinite',
        }}
        aria-hidden="true"
      />
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem' }}>{message}</p>
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};
