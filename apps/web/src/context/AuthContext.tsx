import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User, OrganizationMembership, Role } from '../services/types';
import { authApi, setCsrfToken, getCsrfToken, ApiError } from '../services/api';

interface AuthContextType {
  user: User | null;
  activeTenant: OrganizationMembership | null;
  organizations: OrganizationMembership[];
  isAuthenticated: boolean;
  isLoading: boolean;
  authError: string | null;
  login: (email: string, pass: string) => Promise<void>;
  logout: () => Promise<void>;
  switchTenant: (tenantId: string) => void;
  hasRole: (role: Role) => boolean;
  canManageRegistry: () => boolean;
  canManageInstallations: () => boolean;
  canCreatePredictions: () => boolean;
  canApproveWorkOrders: () => boolean;
  canAssignWorkOrders: () => boolean;
  canExecuteWorkOrders: () => boolean;
  canManageMembers: () => boolean;
  canIngestReplay: () => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [organizations, setOrganizations] = useState<OrganizationMembership[]>([]);
  const [activeTenant, setActiveTenant] = useState<OrganizationMembership | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [authError, setAuthError] = useState<string | null>(null);

  // Initialize session on mount
  const checkSession = useCallback(async () => {
    setIsLoading(true);
    setAuthError(null);
    try {
      // 1. Check user and memberships
      const res = await authApi.me();
      setUser(res.user);
      setOrganizations(res.organizations || []);

      if (res.organizations && res.organizations.length > 0) {
        // Keep prior active tenant if valid, otherwise select first
        setActiveTenant((prev) => {
          if (prev && res.organizations.some((o) => o.id === prev.id)) {
            const updated = res.organizations.find((o) => o.id === prev.id)!;
            return updated;
          }
          return res.organizations[0];
        });
      } else {
        setActiveTenant(null);
      }

      // 2. Hydrate session CSRF token into memory if not set
      if (!getCsrfToken()) {
        try {
          await authApi.refreshCsrf();
        } catch {
          // If CSRF refresh fails, the next mutating action will report error
        }
      }
    } catch {
      // Not logged in or expired session
      setUser(null);
      setOrganizations([]);
      setActiveTenant(null);
      setCsrfToken(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkSession();
  }, [checkSession]);

  const login = async (email: string, pass: string) => {
    setIsLoading(true);
    setAuthError(null);
    try {
      const res = await authApi.login(email, pass);
      setOrganizations(res.organizations || []);
      if (res.organizations && res.organizations.length > 0) {
        setActiveTenant(res.organizations[0]);
      } else {
        setActiveTenant(null);
      }
      // Re-fetch user details
      const meRes = await authApi.me();
      setUser(meRes.user);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setAuthError(err.message);
      } else {
        setAuthError(err.message || 'Login failed. Please verify credentials.');
      }
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await authApi.logout();
    } catch {
      // Proceed with clearing client state even if network fails
    } finally {
      setUser(null);
      setOrganizations([]);
      setActiveTenant(null);
      setCsrfToken(null);
      setIsLoading(false);
    }
  };

  const switchTenant = (tenantId: string) => {
    const org = organizations.find((o) => o.id === tenantId);
    if (org) {
      setActiveTenant(org);
    }
  };

  // Role evaluations
  const currentRoles = activeTenant?.roles || [];

  const hasRole = useCallback((role: Role) => currentRoles.includes(role), [currentRoles]);

  const canManageRegistry = useCallback(
    () => currentRoles.some((r) => r === 'admin' || r === 'plant_manager'),
    [currentRoles]
  );

  const canManageInstallations = useCallback(
    () => currentRoles.some((r) => r === 'admin' || r === 'plant_manager' || r === 'technician'),
    [currentRoles]
  );

  const canCreatePredictions = useCallback(
    () => currentRoles.some((r) => r === 'admin' || r === 'plant_manager' || r === 'technician'),
    [currentRoles]
  );

  const canApproveWorkOrders = useCallback(
    () => currentRoles.some((r) => r === 'admin' || r === 'plant_manager'),
    [currentRoles]
  );

  const canAssignWorkOrders = useCallback(
    () => currentRoles.some((r) => r === 'admin' || r === 'plant_manager'),
    [currentRoles]
  );

  const canExecuteWorkOrders = useCallback(
    () => currentRoles.some((r) => r === 'admin' || r === 'plant_manager' || r === 'technician'),
    [currentRoles]
  );

  const canManageMembers = useCallback(
    () => currentRoles.includes('admin'),
    [currentRoles]
  );

  const canIngestReplay = useCallback(
    () => currentRoles.some((r) => r === 'admin' || r === 'plant_manager'),
    [currentRoles]
  );

  const value: AuthContextType = {
    user,
    activeTenant,
    organizations,
    isAuthenticated: !!user && !!activeTenant,
    isLoading,
    authError,
    login,
    logout,
    switchTenant,
    hasRole,
    canManageRegistry,
    canManageInstallations,
    canCreatePredictions,
    canApproveWorkOrders,
    canAssignWorkOrders,
    canExecuteWorkOrders,
    canManageMembers,
    canIngestReplay,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
