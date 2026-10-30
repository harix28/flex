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

export const App: React.FC = () => {
  const { isAuthenticated, isLoading, activeTenant } = useAuth();

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
        setCurrentPage('overview');
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
        <OverviewPage
          onSelectMachine={(mId) => navigateTo('machine-detail', { machineId: mId })}
          onNavigateToRegistry={() => navigateTo('registry')}
        />
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

      {currentPage === 'jobs' && <JobsPage />}

      {currentPage === 'integrations' && <IntegrationsPage />}

      {currentPage === 'model-monitoring' && <ModelMonitoringPage />}

      {currentPage === 'registry' && <RegistryPage />}

      {currentPage === 'members' && <MembersPage />}
    </Shell>
  );
};
