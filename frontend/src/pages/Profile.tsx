import { useState, useEffect } from 'react';
import { Card, Select, message, Descriptions, Spin } from 'antd';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';

const LANGUAGES = [
  { value: 'fr', label: 'Français' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Español' },
  { value: 'de', label: 'Deutsch' },
];

export default function Profile() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const [language, setLanguage] = useState(i18n.language?.slice(0, 2) || 'en');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/user/preferences').then(res => {
      if (res.data.language) {
        setLanguage(res.data.language);
      }
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const handleLanguageChange = async (lang: string) => {
    setLanguage(lang);
    i18n.changeLanguage(lang);
    localStorage.setItem('q2h_language', lang);
    try {
      await api.put('/user/preferences', { language: lang });
      message.success(t('profile.languageSaved'));
    } catch {
      message.error(t('common.error'));
    }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '20vh auto' }} />;

  return (
    <div>
      <Card title={t('profile.title')} style={{ maxWidth: 600 }}>
        <Descriptions column={1} bordered>
          <Descriptions.Item label={t('login.username')}>{user?.username}</Descriptions.Item>
          {user?.firstName && <Descriptions.Item label={t('admin.user.firstName')}>{user.firstName}</Descriptions.Item>}
          {user?.lastName && <Descriptions.Item label={t('admin.user.lastName')}>{user.lastName}</Descriptions.Item>}
          <Descriptions.Item label={t('profile.language')}>
            <Select
              value={language}
              onChange={handleLanguageChange}
              options={LANGUAGES}
              style={{ width: 200 }}
            />
          </Descriptions.Item>
        </Descriptions>
      </Card>
    </div>
  );
}
