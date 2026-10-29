import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';

describe('EmptyState and ErrorState components', () => {
  it('renders honest empty state with title and description', () => {
    render(
      <EmptyState
        title="No Machines Found"
        description="No registered turbofan assets match the selected criteria."
      />
    );

    expect(screen.getByText('No Machines Found')).toBeInTheDocument();
    expect(
      screen.getByText('No registered turbofan assets match the selected criteria.')
    ).toBeInTheDocument();
  });

  it('renders error state with request ID and triggers onRetry', () => {
    const handleRetry = vi.fn();
    render(
      <ErrorState
        title="Backend Unavailable"
        message="Could not reach the Sentinel REST gateway."
        requestId="req-trace-9988"
        onRetry={handleRetry}
      />
    );

    expect(screen.getByText('Backend Unavailable')).toBeInTheDocument();
    expect(screen.getByText('Could not reach the Sentinel REST gateway.')).toBeInTheDocument();
    expect(screen.getByText(/req-trace-9988/)).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /Retry/i });
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalledTimes(1);
  });
});
