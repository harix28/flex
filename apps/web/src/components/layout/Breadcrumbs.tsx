import React from 'react';
import { ChevronRight, Home } from 'lucide-react';

export interface BreadcrumbItem {
  label: string;
  href?: string;
  onClick?: () => void;
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
}

export const Breadcrumbs: React.FC<BreadcrumbsProps> = ({ items }) => {
  return (
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      <span style={{ display: 'inline-flex', alignItems: 'center' }}>
        <Home size={14} aria-hidden="true" style={{ color: 'var(--text-muted)' }} />
      </span>
      {items.map((item, idx) => {
        const isLast = idx === items.length - 1;
        return (
          <React.Fragment key={`crumb-${idx}-${item.label}`}>
            <ChevronRight size={12} aria-hidden="true" style={{ color: 'var(--text-muted)' }} />
            {isLast || (!item.href && !item.onClick) ? (
              <span className="current" aria-current={isLast ? 'page' : undefined}>
                {item.label}
              </span>
            ) : (
              <a
                href={item.href || '#'}
                onClick={(e) => {
                  if (item.onClick) {
                    e.preventDefault();
                    item.onClick();
                  }
                }}
              >
                {item.label}
              </a>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
};
