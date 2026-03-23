import { useEffect, useState, useCallback } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Dropdown, Button, Typography, Badge } from 'antd';
import {
  DashboardOutlined,
  LineChartOutlined,
  SearchOutlined,
  SettingOutlined,
  MonitorOutlined,
  UserOutlined,
  LogoutOutlined,
  SunOutlined,
  MoonOutlined,
  BulbOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import AppFooter from '../components/AppFooter';
import AnnouncementBanner from '../components/AnnouncementBanner';
import MaintenanceBanner from '../components/MaintenanceBanner';
import BusyBanner from '../components/BusyBanner';
import SessionTimeoutWarning from '../components/SessionTimeoutWarning';
import WhatsNewModal from '../components/WhatsNewModal';
import api from '../api/client';

const { Header, Content } = Layout;

interface NavItem {
  key: string; label: string; icon: React.ReactNode;
  adminOnly?: boolean; monitoringOnly?: boolean;
  children?: { key: string; label: string; disabled?: boolean }[];
}

export default function MainLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { isDark, toggleTheme, tokens } = useTheme();
  const { t, i18n } = useTranslation();

  const [unseenNotes, setUnseenNotes] = useState<any[]>([]);
  const [currentVersion, setCurrentVersion] = useState<string>('');
  const [showWhatsNew, setShowWhatsNew] = useState(false);
  const [pendingProposalsCount, setPendingProposalsCount] = useState(0);

  const NAV_ITEMS: NavItem[] = [
    { key: '/', label: t('nav.overview'), icon: <DashboardOutlined /> },
    { key: '/trends', label: t('nav.trends'), icon: <LineChartOutlined /> },
    {
      key: '/investigation', label: t('nav.investigation'), icon: <SearchOutlined />,
      children: [
        { key: '/investigation/search', label: t('nav.search') },
        { key: '/investigation/reports', label: t('nav.reports'), disabled: true },
      ],
    },
    { key: '/categorization/orphans', label: t('nav.uncategorized'), icon: <QuestionCircleOutlined /> },
    { key: '/admin', label: t('nav.admin'), icon: <SettingOutlined />, adminOnly: true },
    { key: '/monitoring', label: t('nav.monitoring'), icon: <MonitorOutlined />, adminOnly: true, monitoringOnly: true },
    { key: '/profile', label: t('nav.profile'), icon: <UserOutlined /> },
  ];

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [versionRes, prefsRes] = await Promise.all([
          api.get('/version'),
          api.get('/user/preferences'),
        ]);
        if (cancelled) return;
        const { current, notes } = versionRes.data as { current: string; notes: any[] };
        const lastSeen = prefsRes.data.last_seen_version;
        const savedLang = prefsRes.data.language;
        if (savedLang) {
          i18n.changeLanguage(savedLang);
          localStorage.setItem('q2h_language', savedLang);
        }
        if (!lastSeen) {
          // First login — silently set version, no popup
          if (current) {
            await api.put('/user/preferences', { last_seen_version: current });
          }
          return;
        }
        if (!current || current === lastSeen) return;
        // Filter notes newer than lastSeen
        let unseen = notes;
        if (lastSeen) {
          const idx = notes.findIndex((n: any) => n.version === lastSeen);
          if (idx >= 0) unseen = notes.slice(0, idx);
          // If lastSeen not found (very old version), show all
        }
        if (unseen.length > 0) {
          // Resolve multi-lang fields (new entries are {fr,en,es,de}, old are plain strings)
          const lang = (savedLang || i18n.language?.slice(0, 2) || 'en') as string;
          const resolve = (v: any): string =>
            typeof v === 'string' ? v : (v?.[lang] || v?.en || v?.fr || '');
          const resolved = unseen.map((n: any) => ({
            ...n,
            title: resolve(n.title),
            features: (n.features || []).map(resolve),
            fixes: (n.fixes || []).map(resolve),
            improvements: (n.improvements || []).map(resolve),
          }));
          setCurrentVersion(current);
          setUnseenNotes(resolved);
          setShowWhatsNew(true);
        }
      } catch {
        // silently ignore — non-critical
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Fetch pending proposals count for admin badge
  useEffect(() => {
    if (user?.profile !== 'admin') return;
    let cancelled = false;
    api.get('/rules/proposals/pending/count')
      .then((r) => { if (!cancelled) setPendingProposalsCount(r.data.count); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [user?.profile]);

  const handleCloseWhatsNew = useCallback(async () => {
    setShowWhatsNew(false);
    if (currentVersion) {
      try {
        await api.put('/user/preferences', { last_seen_version: currentVersion });
      } catch {
        // silently ignore
      }
    }
  }, [currentVersion]);

  const isAdmin = user?.profile === 'admin';
  const isMonitoring = user?.profile === 'monitoring';

  const menuItems = NAV_ITEMS
    .filter((item) => {
      if (isMonitoring) return !!item.monitoringOnly;
      return !item.adminOnly || isAdmin;
    })
    .map(({ key, label, icon, children }) => {
      if (children) {
        return { key, label, icon, children: children.map((c) => ({ key: c.key, label: c.label, disabled: c.disabled })) };
      }
      // Add pending proposals badge on Uncategorized QIDs menu (admin only)
      if (key === '/categorization/orphans' && isAdmin && pendingProposalsCount > 0) {
        return {
          key, icon,
          label: (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              {label}
              <Badge count={pendingProposalsCount} size="small" />
            </span>
          ),
        };
      }
      return { key, label, icon };
    });

  const selectedKey = menuItems
    .map((i) => i.key)
    .filter((k) => location.pathname.startsWith(k))
    .sort((a, b) => b.length - a.length)[0] || '/';

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: t('nav.profile'),
      onClick: () => navigate('/profile'),
    },
    {
      key: 'proposals',
      icon: <BulbOutlined />,
      label: t('nav.myProposals'),
      onClick: () => navigate('/proposals'),
    },
    { type: 'divider' as const },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: t('nav.logout'),
      onClick: () => { logout(); navigate('/login'); },
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{
        display: 'flex',
        alignItems: 'center',
        padding: '0 24px',
        background: tokens.headerBg,
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}>
        <Typography.Title
          level={4}
          style={{ color: tokens.textOnHeader, margin: '0 32px 0 0', whiteSpace: 'nowrap' }}
        >
          Qualys2Human
        </Typography.Title>

        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ flex: 1, minWidth: 0 }}
        />

        {/* Theme toggle hidden for now — dark mode not finalized
        <Button
          type="text"
          icon={isDark ? <SunOutlined /> : <MoonOutlined />}
          onClick={toggleTheme}
          style={{ color: tokens.textOnHeader, fontSize: 18 }}
        />
        */}

        <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
          <Button type="text" style={{ color: tokens.textOnHeader }}>
            <UserOutlined /> {[user?.firstName, user?.lastName].filter(Boolean).join(' ') || user?.username}
          </Button>
        </Dropdown>
      </Header>

      <MaintenanceBanner />
      <AnnouncementBanner userProfile={user?.profile} username={user?.username} />
      <BusyBanner />

      <Content style={{ padding: 24, background: tokens.contentBg, flex: 1 }}>
        <Outlet />
      </Content>
      <AppFooter />
      <SessionTimeoutWarning />
      {unseenNotes.length > 0 && (
        <WhatsNewModal
          open={showWhatsNew}
          notes={unseenNotes}
          onClose={handleCloseWhatsNew}
        />
      )}
    </Layout>
  );
}
