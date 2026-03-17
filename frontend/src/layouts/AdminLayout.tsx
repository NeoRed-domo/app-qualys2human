import { Tabs } from 'antd';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import HelpTooltip from '../components/help/HelpTooltip';
import type { HelpTopic } from '../components/help/HelpPanel';

const TAB_HELP: Record<string, HelpTopic> = {
  '/admin/imports': 'admin-imports',
  '/admin/users': 'admin-users',
  '/admin/rules': 'admin-rules',
  '/admin/layers': 'admin-layers',
  '/admin/branding': 'admin-branding',
  '/admin/ldap': 'admin-ldap',
  '/admin/upgrade': 'admin-upgrade',
};

export default function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();

  const ADMIN_TABS = [
    { key: '/admin/imports', label: t('admin.imports') },
    { key: '/admin/users', label: t('admin.users') },
    { key: '/admin/rules', label: t('admin.enterpriseRules') },
    { key: '/admin/layers', label: t('admin.categorization') },
    { key: '/admin/branding', label: t('admin.brandingTab') },
    { key: '/admin/ldap', label: t('admin.ldapTab') },
    { key: '/admin/upgrade', label: t('admin.upgradeTab') },
  ];

  const activeKey = ADMIN_TABS.find((tab) => location.pathname.startsWith(tab.key))?.key || '/admin/imports';
  const helpTopic = TAB_HELP[activeKey] || 'admin-imports';

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Tabs
          activeKey={activeKey}
          onChange={(key) => navigate(key)}
          items={ADMIN_TABS}
          style={{ marginBottom: 16, flex: 1 }}
        />
        <HelpTooltip topic={helpTopic} style={{ marginBottom: 16 }} />
      </div>
      <Outlet />
    </div>
  );
}
