import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { App } from '../App';
const state = vi.hoisted(() => ({ tenant: 'a' }));
vi.mock('../context/AuthContext', () => ({ useAuth: () => ({
  isAuthenticated: true, isLoading: false, activeTenant: { id: state.tenant }
}) }));
vi.mock('../components/layout/Shell', () => ({ Shell: ({ children }: any) => <>{children}</> }));
vi.mock('../pages/WorkOrderDetailPage', () => ({ WorkOrderDetailPage: () => {
  const [loadedFor] = useState(state.tenant);
  return <div>Order belongs to {loadedFor}</div>;
} }));
it('discards mounted detail state when the active tenant changes', () => {
  window.location.hash = '/work-orders/order-a';
  const { rerender } = render(<App />);
  expect(screen.getByText('Order belongs to a')).toBeInTheDocument();
  state.tenant = 'b';
  rerender(<App />);
  expect(screen.queryByText('Order belongs to a')).not.toBeInTheDocument();
  expect(screen.getByText('Order belongs to b')).toBeInTheDocument();
});

