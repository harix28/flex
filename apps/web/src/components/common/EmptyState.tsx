import { Database } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon,
  action,
  className = '',
}) => {
  return (
    <div
      className={`card ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '3rem 1.5rem',
        textAlign: 'center',
        gap: '0.75rem',
        borderStyle: 'dashed',
      }}
    >
      <div
        style={{
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          backgroundColor: 'var(--bg-surface-elevated)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-muted)',
          marginBottom: '0.25rem',
        }}
        aria-hidden="true"
      >
        {icon || <Database size={24} />}
      </div>
      <h3 style={{ fontSize: '1.125rem', fontWeight: 600 }}>{title}</h3>
      <p
        style={{
          color: 'var(--text-secondary)',
          fontSize: '0.875rem',
          maxWidth: '460px',
          lineHeight: 1.5,
        }}
      >
        {description}
      </p>
      {action && <div style={{ marginTop: '0.75rem' }}>{action}</div>}
    </div>
  );
};
