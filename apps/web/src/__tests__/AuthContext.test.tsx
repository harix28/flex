import { render, screen, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { authApi } from '../services/api';
import { User, Role } from '../services/types';

vi.mock('../services/api', () => ({
  authApi: {
    me: vi.fn(),
    refreshCsrf: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  },
  setCsrfToken: vi.fn(),
  getCsrfToken: vi.fn(),
}));

const mockUser: User = {
  id: 'usr-123',
  email: 'operator@meridian.local',
  display_name: 'Test Operator',
};

const mockOrganizations = [
  {
    id: 'tenant-alpha',
    name: 'Alpha Maintenance Org',
    slug: 'alpha-org',
    roles: ['plant_manager' as Role],
  },
  {
    id: 'tenant-beta',
    name: 'Beta Fleet Org',
    slug: 'beta-org',
    roles: ['technician' as Role],
  },
];

const TestConsumer = () => {
  const {
    user,
    activeTenant,
    isAuthenticated,
    isLoading,
    login,
    logout,
    switchTenant,
    canApproveWorkOrders,
    canExecuteWorkOrders,
  } = useAuth();

  if (isLoading) return <div>Loading auth...</div>;

  return (
    <div>
      <div data-testid="auth-status">{isAuthenticated ? 'authenticated' : 'unauthenticated'}</div>
      {user && <div data-testid="user-email">{user.email}</div>}
      {activeTenant && <div data-testid="active-tenant">{activeTenant.name}</div>}
      {activeTenant && <div data-testid="active-roles">{activeTenant.roles.join(', ')}</div>}
      <div data-testid="can-approve">{canApproveWorkOrders() ? 'yes' : 'no'}</div>
      <div data-testid="can-execute">{canExecuteWorkOrders() ? 'yes' : 'no'}</div>
      <button onClick={() => login('admin@meridian.local', 'password123')}>Login</button>
      <button onClick={() => logout()}>Logout</button>
      <button onClick={() => switchTenant('tenant-beta')}>Switch to Beta</button>
    </div>
  );
};

describe('AuthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initializes as unauthenticated when me fails with 401', async () => {
    vi.mocked(authApi.me).mockRejectedValueOnce({ status: 401, message: 'unauthenticated' });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('unauthenticated');
    });
  });

  it('loads user and defaults to first tenant on mount', async () => {
    vi.mocked(authApi.me).mockResolvedValueOnce({
      user: mockUser,
      organizations: mockOrganizations,
      request_id: 'req-1',
    });
    vi.mocked(authApi.refreshCsrf).mockResolvedValueOnce({
      csrf_token: 'csrf-xyz',
      request_id: 'req-2',
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('authenticated');
    });

    expect(screen.getByTestId('user-email')).toHaveTextContent('operator@meridian.local');
    expect(screen.getByTestId('active-tenant')).toHaveTextContent('Alpha Maintenance Org');
    expect(screen.getByTestId('active-roles')).toHaveTextContent('plant_manager');
    expect(screen.getByTestId('can-approve')).toHaveTextContent('yes');
    expect(screen.getByTestId('can-execute')).toHaveTextContent('yes');
  });

  it('switches active tenant and updates permissions', async () => {
    vi.mocked(authApi.me).mockResolvedValueOnce({
      user: mockUser,
      organizations: mockOrganizations,
      request_id: 'req-1',
    });
    vi.mocked(authApi.refreshCsrf).mockResolvedValueOnce({
      csrf_token: 'csrf-xyz',
      request_id: 'req-2',
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('active-tenant')).toHaveTextContent('Alpha Maintenance Org');
    });

    act(() => {
      screen.getByText('Switch to Beta').click();
    });

    expect(screen.getByTestId('active-tenant')).toHaveTextContent('Beta Fleet Org');
    expect(screen.getByTestId('active-roles')).toHaveTextContent('technician');
    expect(screen.getByTestId('can-approve')).toHaveTextContent('no');
    expect(screen.getByTestId('can-execute')).toHaveTextContent('yes');
  });

  it('clears state on logout', async () => {
    vi.mocked(authApi.me).mockResolvedValueOnce({
      user: mockUser,
      organizations: mockOrganizations,
      request_id: 'req-1',
    });
    vi.mocked(authApi.refreshCsrf).mockResolvedValueOnce({
      csrf_token: 'csrf-xyz',
      request_id: 'req-2',
    });
    vi.mocked(authApi.logout).mockResolvedValueOnce({ logged_out: true, request_id: 'req-3' } as any);

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('authenticated');
    });

    await act(async () => {
      screen.getByText('Logout').click();
    });

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('unauthenticated');
    });
  });
});
