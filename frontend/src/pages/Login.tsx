import { useState, useEffect } from 'react';
import { Card, Form, Input, Button, Select, Alert, Typography } from 'antd';
import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import AppFooter from '../components/AppFooter';

const { Title } = Typography;

export default function Login() {
  const { login } = useAuth();
  const { tokens } = useTheme();
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [logoError, setLogoError] = useState(false);
  const [adEnabled, setAdEnabled] = useState(false);
  const [defaultMode, setDefaultMode] = useState<string>('local');
  const [form] = Form.useForm();

  useEffect(() => {
    fetch('/api/branding/logo')
      .then((resp) => {
        if (!resp.ok) throw new Error('No logo');
        return resp.blob();
      })
      .then((blob) => setLogoUrl(URL.createObjectURL(blob)))
      .catch(() => setLogoError(true));

    fetch('/api/ldap/enabled')
      .then((resp) => resp.json())
      .then((data) => {
        setAdEnabled(data.enabled === true);
        const mode = data.default_mode === 'ad' ? 'ad' : 'local';
        setDefaultMode(mode);
        form.setFieldsValue({ domain: mode });
      })
      .catch(() => setAdEnabled(false));
  }, [form]);

  const onFinish = async (values: { username: string; password: string; domain: string }) => {
    setLoading(true);
    setError(null);
    try {
      await login(values.username, values.password, values.domain);
    } catch (err: any) {
      const code = err.response?.data?.detail || '';
      const localized = t(`errors.${code}`, { defaultValue: '' });
      setError(localized || code || t('login.error'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      background: tokens.contentBg,
      minHeight: '100vh',
      paddingTop: '12vh',
    }}>
      <Card style={{ width: 440, maxWidth: '90vw', boxShadow: '0 2px 8px rgba(0,0,0,0.15)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          {logoUrl && !logoError ? (
            <img
              src={logoUrl}
              alt="Logo"
              style={{ maxHeight: 120, maxWidth: 380, marginBottom: 8 }}
              onError={() => setLogoError(true)}
            />
          ) : (
            <Title level={3} style={{ margin: 0 }}>Qualys2Human</Title>
          )}
          <div><Typography.Text type="secondary">{t('login.title')}</Typography.Text></div>
        </div>

        {error && (
          <Alert
            message={error}
            type="error"
            showIcon
            closable
            style={{ marginBottom: 16 }}
            onClose={() => setError(null)}
          />
        )}

        <Form
          form={form}
          name="login"
          onFinish={onFinish}
          initialValues={{ domain: defaultMode }}
          layout="vertical"
          size="large"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: t('login.usernameRequired') }]}
          >
            <Input
              id="q2h-login-username"
              prefix={<UserOutlined />}
              placeholder={t('login.username')}
              autoComplete="username"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: t('login.passwordRequired') }]}
          >
            <Input.Password
              id="q2h-login-password"
              prefix={<LockOutlined />}
              placeholder={t('login.password')}
              autoComplete="current-password"
            />
          </Form.Item>

          {adEnabled && (
            <Form.Item name="domain">
              <Select id="q2h-login-domain">
                <Select.Option value="local">{t('login.localMode')}</Select.Option>
                <Select.Option value="ad">{t('login.adMode')}</Select.Option>
              </Select>
            </Form.Item>
          )}

          <Form.Item>
            <Button
              id="q2h-login-submit"
              type="primary"
              htmlType="submit"
              loading={loading}
              block
            >
              {t('login.submit')}
            </Button>
          </Form.Item>
        </Form>
      </Card>
      <AppFooter showVersion={false} />
    </div>
  );
}
