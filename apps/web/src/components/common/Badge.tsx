import React from 'react';
import { PriorityBand, WorkOrderStatus } from '../../services/types';
import { AlertCircle, AlertTriangle, CheckCircle, Clock, XCircle, HelpCircle, ShieldAlert, PauseCircle } from 'lucide-react';

interface PriorityBadgeProps {
  priority: PriorityBand | string;
  className?: string;
}

export const PriorityBadge: React.FC<PriorityBadgeProps> = ({ priority, className = '' }) => {
  const p = (priority || 'unknown').toLowerCase();
  switch (p) {
    case 'urgent':
      return (
        <span className={`badge badge-urgent ${className}`} role="status">
          <ShieldAlert size={13} aria-hidden="true" />
          <span>Urgent</span>
        </span>
      );
    case 'high':
      return (
        <span className={`badge badge-high ${className}`} role="status">
          <AlertTriangle size={13} aria-hidden="true" />
          <span>High</span>
        </span>
      );
    case 'medium':
      return (
        <span className={`badge badge-medium ${className}`} role="status">
          <Clock size={13} aria-hidden="true" />
          <span>Medium</span>
        </span>
      );
    case 'low':
      return (
        <span className={`badge badge-low ${className}`} role="status">
          <CheckCircle size={13} aria-hidden="true" />
          <span>Low</span>
        </span>
      );
    case 'outdated':
      return (
        <span className={`badge badge-outdated ${className}`} role="status">
          <AlertCircle size={13} aria-hidden="true" />
          <span>Outdated</span>
        </span>
      );
    default:
      return (
        <span className={`badge badge-unknown ${className}`} role="status">
          <HelpCircle size={13} aria-hidden="true" />
          <span>Unknown</span>
        </span>
      );
  }
};

interface StatusBadgeProps {
  status: WorkOrderStatus | string;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '' }) => {
  const s = status.toLowerCase();
  switch (s) {
    case 'draft':
      return (
        <span className={`badge badge-unknown ${className}`} role="status">
          <Clock size={13} aria-hidden="true" />
          <span>Draft</span>
        </span>
      );
    case 'approved':
      return (
        <span className={`badge badge-medium ${className}`} role="status">
          <CheckCircle size={13} aria-hidden="true" />
          <span>Approved</span>
        </span>
      );
    case 'in_progress':
      return (
        <span className={`badge badge-high ${className}`} role="status">
          <Clock size={13} aria-hidden="true" />
          <span>In Progress</span>
        </span>
      );
    case 'blocked':
      return (
        <span className={`badge badge-urgent ${className}`} role="status">
          <PauseCircle size={13} aria-hidden="true" />
          <span>Blocked</span>
        </span>
      );
    case 'completed':
      return (
        <span className={`badge badge-low ${className}`} role="status">
          <CheckCircle size={13} aria-hidden="true" />
          <span>Completed</span>
        </span>
      );
    case 'cancelled':
      return (
        <span className={`badge badge-unknown ${className}`} role="status">
          <XCircle size={13} aria-hidden="true" />
          <span>Cancelled</span>
        </span>
      );
    default:
      return (
        <span className={`badge badge-unknown ${className}`} role="status">
          <HelpCircle size={13} aria-hidden="true" />
          <span>{status}</span>
        </span>
      );
  }
};
