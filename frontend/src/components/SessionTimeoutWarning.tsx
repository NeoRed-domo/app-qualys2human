import { Modal, Button, Space, Typography } from 'antd';
import { ClockCircleOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

const { Text } = Typography;

export default function SessionTimeoutWarning() {
  const { t } = useTranslation();
  const { showTimeoutWarning, timeoutRemaining, dismissWarning, logout } = useAuth();
  const navigate = useNavigate();

  const minutes = Math.floor(timeoutRemaining / 60);
  const seconds = timeoutRemaining % 60;
  const display = `${minutes}:${String(seconds).padStart(2, '0')}`;

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <Modal
      open={showTimeoutWarning}
      title={
        <Space>
          <ClockCircleOutlined style={{ color: '#faad14' }} />
          {t('modals.sessionExpiring')}
        </Space>
      }
      closable={false}
      maskClosable={false}
      footer={
        <Space>
          <Button onClick={handleLogout}>{t('modals.sessionLogout')}</Button>
          <Button type="primary" onClick={dismissWarning}>{t('modals.sessionStay')}</Button>
        </Space>
      }
    >
      <Text>
        {t('modals.sessionExpiresIn')} <Text strong style={{ fontSize: 18 }}>{display}</Text>
      </Text>
      <br />
      <Text type="secondary" style={{ marginTop: 8, display: 'block' }}>
        {t('modals.sessionStayHint')}
      </Text>
    </Modal>
  );
}
