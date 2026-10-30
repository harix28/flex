import React, { useState, useEffect } from 'react';
import { useAuth } from './context/AuthContext';
import { Shell, NavigationPage } from './components/layout/Shell';
import { LoginPage } from './pages/LoginPage';
import { OverviewPage } from './pages/OverviewPage';
import { MachinesPage } from './pages/MachinesPage';
import { MachineDetailPage } from './pages/MachineDetailPage';
import { WorkOrdersPage } from './pages/WorkOrdersPage';
import { WorkOrderDetailPage } from './pages/WorkOrderDetailPage';
import { RegistryPage } from './pages/RegistryPage';
import { MembersPage } from './pages/MembersPage';
import { ModelMonitoringPage } from './pages/ModelMonitoringPage';
import { PlanningPage } from './pages/PlanningPage';
import { JobsPage } from './pages/JobsPage';
import { IntegrationsPage } from './pages/IntegrationsPage';
import { LoadingState } from './components/common/LoadingState';
import { ShieldAlert, ArrowLeft } from 'lucide-react';

interface RoleBoundaryGuardProps {
  requiredRole: string;
  featureName: string;
  onReturnHome: () => void;
}

const RoleBoundaryGuard: React.FC<RoleBoundaryGuardProps> = ({
  requiredRole,
  featureName,
  onReturnHome,
}) => {
  return (
    <div
      className="card card-elevated"
      style={{
        maxWidth: '560px',
        margin: '3rem auto',
        padding: '2.5rem',
        textAlign: 'center',
        border: '1px solid rgba(239, 68, 68, 0.25)',
      }}
    >
      <div
        style={{
          width: '56px',
          height: '56px',
          borderRadius: '50%',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 1.25rem',
          color: '#ef4444',
        }}
      >
        <ShieldAlert size={28} />
      </div>
      <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
        Role Boundary Access Blocked
      </h2>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', lineHeight: '1.5', marginBottom: '1.5rem' }}>
        Access to <strong>{featureName}</strong> is strictly segregated to prevent cross-role operational interference.
        This feature requires <strong>{requiredRole}</strong> clearance.
      </p>
      <button
        type="button"
        className="btn btn-primary"
        onClick={onReturnHome}
        style={{ margin: '0 auto', display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
      >
        <ArrowLeft size={16} />
        <span>Return to Permitted Workspace</span>
      </button>
    </div>
  );
};

export const App: React.FC = () => {
  const { isAuthenticated, isLoading, activeTenant, isGeneralManager, isMaintenanceEngineer, isTechnician } = useAuth();
  const defaultHome: NavigationPage = isTechnician ? 'work-orders' : 'overview';

  const [currentPage, setCurrentPage] = useState<NavigationPage>('overview');
  const [selectedMachineId, setSelectedMachineId] = useState<string | null>(null);
  const [selectedWorkOrderId, setSelectedWorkOrderId] = useState<string | null>(null);

  // Sync state with URL hash
  useEffect(() => {
    const parseHash = () => {
      const hash = window.location.hash.replace(/^#\/?/, '');
      const [route, id] = hash.split('/');

      if (route === 'machines' && id) {
        setCurrentPage('machine-detail');
        setSelectedMachineId(id);
      } else if (route === 'work-orders' && id) {
        setCurrentPage('work-order-detail');
        setSelectedWorkOrderId(id);
      } else if (route === 'machines') {
        setCurrentPage('machines');
      } else if (route === 'work-orders') {
        setCurrentPage('work-orders');
      } else if (route === 'planning') {
        setCurrentPage('planning');
      } else if (route === 'jobs') {
        setCurrentPage('jobs');
      } else if (route === 'integrations') {
        setCurrentPage('integrations');
      } else if (route === 'model-monitoring') {
        setCurrentPage('model-monitoring');
      } else if (route === 'registry') {
        setCurrentPage('registry');
      } else if (route === 'members') {
        setCurrentPage('members');
      } else {
        setCurrentPage(isTechnician ? 'work-orders' : 'overview');
      }
    };

    parseHash();
    window.addEventListener('hashchange', parseHash);
    return () => window.removeEventListener('hashchange', parseHash);
  }, []);

  const navigateTo = (page: NavigationPage, params?: Record<string, string>) => {
    setCurrentPage(page);
    if (page === 'machine-detail' && params?.machineId) {
      setSelectedMachineId(params.machineId);
      window.location.hash = `/machines/${params.machineId}`;
    } else if (page === 'work-order-detail' && params?.workOrderId) {
      setSelectedWorkOrderId(params.workOrderId);
      window.location.hash = `/work-orders/${params.workOrderId}`;
    } else {
      window.location.hash = `/${page}`;
    }
  };

  if (isLoading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: 'var(--bg-canvas)',
        }}
      >
        <LoadingState message="Verifying session and security boundaries..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage onLoginSuccess={() => navigateTo('overview')} />;
  }

  return (
    <Shell key={activeTenant?.id} currentPage={currentPage} onNavigate={navigateTo}>
      {currentPage === 'overview' && (
        isTechnician ? (
          <WorkOrdersPage
            onSelectWorkOrder={(woId) => navigateTo('work-order-detail', { workOrderId: woId })}
          />
        ) : (
          <OverviewPage
            onSelectMachine={(mId) => navigateTo('machine-detail', { machineId: mId })}
            onNavigateToRegistry={() => navigateTo('registry')}
          />
        )
      )}

      {currentPage === 'machines' && (
        <MachinesPage
          onSelectMachine={(mId) => navigateTo('machine-detail', { machineId: mId })}
          onNavigateToRegistry={() => navigateTo('registry')}
        />
      )}

      {currentPage === 'machine-detail' && selectedMachineId && (
        <MachineDetailPage key={selectedMachineId}
          machineId={selectedMachineId}
          onNavigateBack={() => navigateTo('machines')}
          onSelectWorkOrder={(woId) => navigateTo('work-order-detail', { workOrderId: woId })}
        />
      )}

      {currentPage === 'work-orders' && (
        <WorkOrdersPage
          onSelectWorkOrder={(woId) => navigateTo('work-order-detail', { workOrderId: woId })}
        />
      )}

      {currentPage === 'work-order-detail' && selectedWorkOrderId && (
        <WorkOrderDetailPage key={selectedWorkOrderId}
          workOrderId={selectedWorkOrderId}
          onNavigateBack={() => navigateTo('work-orders')}
          onSelectMachine={(mId) => navigateTo('machine-detail', { machineId: mId })}
        />
      )}

      {currentPage === 'planning' && <PlanningPage />}

      {currentPage === 'jobs' && (
        (isMaintenanceEngineer || isGeneralManager) ? (
          <JobsPage />
        ) : (
          <RoleBoundaryGuard
            requiredRole="Maintenance Engineer (Lead)"
            featureName="Fleet Scoring & Background Jobs"
            onReturnHome={() => navigateTo(defaultHome)}
          />
        )
      )}

      {currentPage === 'integrations' && (
        isGeneralManager ? (
          <IntegrationsPage />
        ) : (
          <RoleBoundaryGuard
            requiredRole="General Manager (Admin)"
            featureName="Live Integrations & Security Keys"
            onReturnHome={() => navigateTo(defaultHome)}
          />
        )
      )}

      {currentPage === 'model-monitoring' && (
        (isMaintenanceEngineer || isGeneralManager) ? (
          <ModelMonitoringPage />
        ) : (
          <RoleBoundaryGuard
            requiredRole="Maintenance Engineer (Lead)"
            featureName="Model Observability & MLOps Divergence"
            onReturnHome={() => navigateTo(defaultHome)}
          />
        )
      )}

      {currentPage === 'registry' && (
        isGeneralManager ? (
          <RegistryPage />
        ) : (
          <RoleBoundaryGuard
            requiredRole="General Manager (Admin)"
            featureName="Fleet Registry Schema Configuration"
            onReturnHome={() => navigateTo(defaultHome)}
          />
        )
      )}

      {currentPage === 'members' && (
        isGeneralManager ? (
          <MembersPage />
        ) : (
          <RoleBoundaryGuard
            requiredRole="General Manager (Admin)"
            featureName="Organization Members Governance"
            onReturnHome={() => navigateTo(defaultHome)}
          />
        )
      )}
    </Shell>
  );
};
