import { Routes, Route, Navigate } from 'react-router-dom';
import { Spin } from 'antd';
import { useAuth } from './contexts/AuthContext';
import { FilterProvider } from './contexts/FilterContext';
import Login from './pages/Login';
import MainLayout from './layouts/MainLayout';
import AdminLayout from './layouts/AdminLayout';
import Overview from './pages/Overview';
import VulnList from './pages/VulnList';
import VulnDetail from './pages/VulnDetail';
import HostList from './pages/HostList';
import HostDetail from './pages/HostDetail';
import FullDetail from './pages/FullDetail';

import ImportManager from './pages/admin/ImportManager';
import UserManagement from './pages/admin/UserManagement';
import EnterpriseRules from './pages/admin/EnterpriseRules';
import Branding from './pages/admin/Branding';
import LayerRules from './pages/admin/LayerRules';
import OrphanVulns from './pages/admin/OrphanVulns';
import LdapSettings from './pages/admin/LdapSettings';
import UpgradeManager from './pages/admin/UpgradeManager';
import Monitoring from './pages/Monitoring';
import BasicSearch from './pages/investigation/BasicSearch';
import Trends from './pages/Trends';
import Profile from './pages/Profile';
import MyProposals from './pages/MyProposals';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  // While verifying identity against server, show spinner (not login redirect)
  if (loading) return <Spin size="large" style={{ display: 'block', margin: '40vh auto' }} />;
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

function MonitoringGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (user?.profile === 'monitoring') return <Navigate to="/monitoring" replace />;
  return <>{children}</>;
}

function Placeholder({ title }: { title: string }) {
  return <div style={{ padding: 24 }}><h2>{title}</h2><p>Coming soon...</p></div>;
}

export default function AppRouter() {
  const { isAuthenticated, loading } = useAuth();

  return (
    <FilterProvider>
      <Routes>
        <Route
          path="/login"
          element={!loading && isAuthenticated ? <Navigate to="/" replace /> : <Login />}
        />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <MainLayout />
            </PrivateRoute>
          }
        >
          <Route index element={<MonitoringGuard><Overview /></MonitoringGuard>} />
          <Route path="trends" element={<MonitoringGuard><Trends /></MonitoringGuard>} />
          <Route path="proposals" element={<MonitoringGuard><MyProposals /></MonitoringGuard>} />
          <Route path="categorization/orphans" element={<MonitoringGuard><OrphanVulns /></MonitoringGuard>} />
          <Route path="admin" element={<MonitoringGuard><AdminLayout /></MonitoringGuard>}>
            <Route index element={<Navigate to="/admin/imports" replace />} />
            <Route path="imports" element={<ImportManager />} />
            <Route path="users" element={<UserManagement />} />
            <Route path="rules" element={<EnterpriseRules />} />
            <Route path="branding" element={<Branding />} />
            <Route path="layers" element={<LayerRules />} />
            <Route path="layers/orphans" element={<OrphanVulns />} />
            <Route path="ldap" element={<LdapSettings />} />
            <Route path="upgrade" element={<UpgradeManager />} />
          </Route>
          <Route path="investigation/search" element={<MonitoringGuard><BasicSearch /></MonitoringGuard>} />
          <Route path="monitoring" element={<Monitoring />} />
          <Route path="profile" element={<MonitoringGuard><Profile /></MonitoringGuard>} />
          <Route path="vulnerabilities" element={<MonitoringGuard><VulnList /></MonitoringGuard>} />
          <Route path="vulnerabilities/:qid" element={<MonitoringGuard><VulnDetail /></MonitoringGuard>} />
          <Route path="hosts" element={<MonitoringGuard><HostList /></MonitoringGuard>} />
          <Route path="hosts/:ip" element={<MonitoringGuard><HostDetail /></MonitoringGuard>} />
          <Route path="hosts/:ip/vulnerabilities/:qid" element={<MonitoringGuard><FullDetail /></MonitoringGuard>} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </FilterProvider>
  );
}
