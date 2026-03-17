import { useEffect, useState } from 'react';
import { Card, Input, Switch, Button, Space, Typography, message, Alert, Form, Modal, Select } from 'antd';
import { SaveOutlined, ApiOutlined, UserOutlined, LockOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import api from '../../api/client';

const { Text, Paragraph } = Typography;

interface GroupMapping {
  profile_name: string;
  ad_group_dn: string;
}

interface LdapSettings {
  enabled: boolean;
  server_url: string;
  use_starttls: boolean;
  upn_template: string;
  search_base: string;
  group_attribute: string;
  tls_verify: boolean;
  tls_ca_cert: string;
  default_auth_mode: string;
  group_mappings: GroupMapping[];
}

const DEFAULT_SETTINGS: LdapSettings = {
  enabled: false,
  server_url: '',
  use_starttls: false,
  upn_template: '{username}@domain.com',
  search_base: '',
  group_attribute: 'memberOf',
  tls_verify: false,
  tls_ca_cert: '',
  default_auth_mode: 'local',
  group_mappings: [],
};

export default function LdapSettingsPage() {
  const { t } = useTranslation();

  const PROFILE_LABELS: Record<string, string> = {
    admin: t('admin.user.profileAdmin'),
    user: t('admin.user.profileUser'),
    monitoring: t('admin.user.profileMonitoring'),
  };

  const [settings, setSettings] = useState<LdapSettings>(DEFAULT_SETTINGS);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  // Group mapping state (3 fixed profiles)
  const [adminDn, setAdminDn] = useState('');
  const [userDn, setUserDn] = useState('');
  const [monitoringDn, setMonitoringDn] = useState('');

  // Test connection modal
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [testUsername, setTestUsername] = useState('');
  const [testPassword, setTestPassword] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  useEffect(() => {
    api.get('/ldap/settings')
      .then((r) => {
        const data = r.data as LdapSettings;
        setSettings(data);
        // Extract group mappings into individual fields
        const mappings = data.group_mappings || [];
        setAdminDn(mappings.find((m) => m.profile_name === 'admin')?.ad_group_dn || '');
        setUserDn(mappings.find((m) => m.profile_name === 'user')?.ad_group_dn || '');
        setMonitoringDn(mappings.find((m) => m.profile_name === 'monitoring')?.ad_group_dn || '');
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const group_mappings: GroupMapping[] = [
        { profile_name: 'admin', ad_group_dn: adminDn },
        { profile_name: 'user', ad_group_dn: userDn },
        { profile_name: 'monitoring', ad_group_dn: monitoringDn },
      ];
      const payload = { ...settings, group_mappings };
      const r = await api.put('/ldap/settings', payload);
      setSettings(r.data);
      message.success(t('admin.ldap.saved'));
    } catch (err: any) {
      message.error(err.response?.data?.detail || t('admin.ldap.saveError'));
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const r = await api.post('/ldap/test', {
        username: testUsername,
        password: testPassword,
      });
      setTestResult(r.data);
    } catch (err: any) {
      setTestResult({
        success: false,
        message: err.response?.data?.detail || t('common.error'),
      });
    } finally {
      setTesting(false);
    }
  };

  if (loading) return null;

  return (
    <div>
      <Card title={t('admin.ldap.title')}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Text strong>{t('admin.ldap.enableAd')}</Text>
            <Switch
              checked={settings.enabled}
              onChange={(checked) => setSettings({ ...settings, enabled: checked })}
            />
          </div>

          {settings.enabled && (
            <div>
              <Text strong>{t('admin.ldap.defaultAuthMode')}</Text>
              <Select
                value={settings.default_auth_mode}
                onChange={(v) => setSettings({ ...settings, default_auth_mode: v })}
                style={{ width: 260, marginLeft: 12 }}
              >
                <Select.Option value="local">{t('login.localMode')}</Select.Option>
                <Select.Option value="ad">{t('login.adMode')}</Select.Option>
              </Select>
              <div><Text type="secondary" style={{ fontSize: 12 }}>{t('admin.ldap.defaultAuthHelp')}</Text></div>
            </div>
          )}

          <div>
            <Text strong>{t('admin.ldap.serverUrl')}</Text>
            <Input
              value={settings.server_url}
              onChange={(e) => setSettings({ ...settings, server_url: e.target.value })}
              placeholder={t('admin.ldap.serverUrlPlaceholder')}
              style={{ marginTop: 4 }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Text strong>{t('admin.ldap.starttls')}</Text>
            <Switch
              checked={settings.use_starttls}
              onChange={(checked) => setSettings({ ...settings, use_starttls: checked })}
            />
            <Text type="secondary">{t('admin.ldap.starttlsHint')}</Text>
          </div>

          <div>
            <Text strong>{t('admin.ldap.upnTemplate')}</Text>
            <Input
              value={settings.upn_template}
              onChange={(e) => setSettings({ ...settings, upn_template: e.target.value })}
              placeholder="{username}@domain.com"
              style={{ marginTop: 4 }}
            />
            <Paragraph type="secondary" style={{ marginTop: 4, marginBottom: 0 }}>
              {t('admin.ldap.upnHint', {
                interpolation: { escapeValue: false },
              })}
            </Paragraph>
          </div>

          <div>
            <Text strong>{t('admin.ldap.searchBase')}</Text>
            <Input
              value={settings.search_base}
              onChange={(e) => setSettings({ ...settings, search_base: e.target.value })}
              placeholder={t('admin.ldap.searchBasePlaceholder')}
              style={{ marginTop: 4 }}
            />
          </div>

          <div>
            <Text strong>{t('admin.ldap.groupAttribute')}</Text>
            <Input
              value={settings.group_attribute}
              onChange={(e) => setSettings({ ...settings, group_attribute: e.target.value })}
              placeholder={t('admin.ldap.groupAttributePlaceholder')}
              style={{ marginTop: 4 }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Text strong>{t('admin.ldap.tlsVerify')}</Text>
            <Switch
              checked={settings.tls_verify}
              onChange={(checked) => setSettings({ ...settings, tls_verify: checked })}
            />
            <Text type="secondary">{t('admin.ldap.tlsVerifyHint')}</Text>
          </div>

          <div>
            <Text strong>{t('admin.ldap.caCert')}</Text>
            <Input
              value={settings.tls_ca_cert}
              onChange={(e) => setSettings({ ...settings, tls_ca_cert: e.target.value })}
              placeholder={t('admin.ldap.caCertPlaceholder')}
              style={{ marginTop: 4 }}
            />
          </div>

          <Space>
            <Button
              type="default"
              icon={<ApiOutlined />}
              onClick={() => {
                setTestResult(null);
                setTestModalOpen(true);
              }}
            >
              {t('admin.ldap.testConnection')}
            </Button>
          </Space>
        </Space>
      </Card>

      <Card title={t('admin.ldap.groupMapping')} style={{ marginTop: 16 }}>
        <Paragraph type="secondary" style={{ marginBottom: 16 }}>
          {t('admin.ldap.groupMappingDesc')}
        </Paragraph>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {(['admin', 'user', 'monitoring'] as const).map((profile) => {
            const value = profile === 'admin' ? adminDn : profile === 'user' ? userDn : monitoringDn;
            const setter = profile === 'admin' ? setAdminDn : profile === 'user' ? setUserDn : setMonitoringDn;
            return (
              <div key={profile}>
                <Text strong>{PROFILE_LABELS[profile]}</Text>
                <Input
                  value={value}
                  onChange={(e) => setter(e.target.value)}
                  placeholder={`CN=${PROFILE_LABELS[profile]},OU=Groups,DC=domain,DC=com`}
                  style={{ marginTop: 4 }}
                />
              </div>
            );
          })}
        </Space>
      </Card>

      <div style={{ marginTop: 16 }}>
        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={handleSave}
          loading={saving}
          size="large"
        >
          {t('common.save')}
        </Button>
      </div>

      <Modal
        title={t('admin.ldap.testTitle')}
        open={testModalOpen}
        onCancel={() => setTestModalOpen(false)}
        footer={null}
      >
        <Form layout="vertical">
          <Form.Item label={t('admin.ldap.testUsername')}>
            <Input
              prefix={<UserOutlined />}
              value={testUsername}
              onChange={(e) => setTestUsername(e.target.value)}
              placeholder={t('admin.ldap.testUsernamePlaceholder')}
            />
          </Form.Item>
          <Form.Item label={t('admin.ldap.testPassword')}>
            <Input.Password
              prefix={<LockOutlined />}
              value={testPassword}
              onChange={(e) => setTestPassword(e.target.value)}
              placeholder={t('admin.ldap.testPasswordPlaceholder')}
            />
          </Form.Item>
          <Button
            type="primary"
            icon={<ApiOutlined />}
            onClick={handleTest}
            loading={testing}
            block
          >
            {t('admin.ldap.testBtn')}
          </Button>
          {testResult && (
            <Alert
              type={testResult.success ? 'success' : 'error'}
              message={testResult.message}
              showIcon
              style={{ marginTop: 16 }}
            />
          )}
        </Form>
      </Modal>
    </div>
  );
}
