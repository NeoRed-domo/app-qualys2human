import { useEffect, useState } from 'react';
import { Card, Upload, Button, message, Space, Typography, Image, Input, Select, Radio, Alert } from 'antd';
import { UploadOutlined, DeleteOutlined, DownloadOutlined, SaveOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { UploadProps } from 'antd';
import api from '../../api/client';
import { useTheme } from '../../contexts/ThemeContext';

const { Text, Paragraph } = Typography;

export default function Branding() {
  const { t } = useTranslation();
  const { tokens } = useTheme();
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [footerText, setFooterText] = useState('');
  const [savingFooter, setSavingFooter] = useState(false);

  const [bannerMessage, setBannerMessage] = useState('');
  const [bannerColor, setBannerColor] = useState('info');
  const [bannerVisibility, setBannerVisibility] = useState('none');
  const [savingBanner, setSavingBanner] = useState(false);

  const COLOR_OPTIONS = [
    { value: 'info', label: t('admin.branding.colorInfo'), color: '#1677ff' },
    { value: 'warning', label: t('admin.branding.colorWarning'), color: '#faad14' },
    { value: 'alert', label: t('admin.branding.colorAlert'), color: '#ff4d4f' },
    { value: 'other', label: t('admin.branding.colorOther'), color: '#8c8c8c' },
  ];

  useEffect(() => {
    // Fetch logo
    const token = localStorage.getItem('access_token');
    fetch('/api/branding/logo', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((resp) => {
        if (!resp.ok) throw new Error('No logo');
        return resp.blob();
      })
      .then((blob) => setLogoUrl(URL.createObjectURL(blob)))
      .catch(() => setLogoUrl(null));

    // Fetch branding settings
    fetch('/api/branding/settings')
      .then((resp) => resp.json())
      .then((data) => setFooterText(data.footer_text || ''))
      .catch(() => setFooterText(''));

    // Fetch banner settings
    api.get('/settings/banner')
      .then((r) => {
        setBannerMessage(r.data.message || '');
        setBannerColor(r.data.color || 'info');
        setBannerVisibility(r.data.visibility || 'none');
      })
      .catch(() => {});
  }, [refresh]);

  const uploadProps: UploadProps = {
    name: 'file',
    accept: '.svg,.png,.jpg,.jpeg',
    showUploadList: false,
    customRequest: async (options) => {
      const { file, onSuccess, onError } = options;
      setUploading(true);
      const formData = new FormData();
      formData.append('file', file as Blob);
      try {
        const token = localStorage.getItem('access_token');
        const resp = await fetch('/api/branding/logo', {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        });
        if (!resp.ok) {
          const err = await resp.json();
          throw new Error(err.detail || 'Upload failed');
        }
        message.success(t('admin.branding.logoUpdated'));
        onSuccess?.(await resp.json());
        setRefresh((r) => r + 1);
      } catch (err: any) {
        message.error(err.message || t('admin.branding.uploadError'));
        onError?.(err);
      } finally {
        setUploading(false);
      }
    },
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await api.delete('/branding/logo');
      message.success(t('admin.branding.logoReset'));
      setRefresh((r) => r + 1);
    } catch (err: any) {
      message.error(err.response?.data?.detail || t('common.error'));
    } finally {
      setDeleting(false);
    }
  };

  const handleDownloadTemplate = () => {
    const token = localStorage.getItem('access_token');
    fetch('/api/branding/template', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((resp) => resp.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'logo-template.svg';
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch(() => message.error(t('admin.branding.downloadError')));
  };

  const handleSaveFooter = async () => {
    setSavingFooter(true);
    try {
      await api.put('/branding/settings', { footer_text: footerText });
      message.success(t('admin.branding.footerSaved'));
    } catch (err: any) {
      message.error(err.response?.data?.detail || t('common.error'));
    } finally {
      setSavingFooter(false);
    }
  };

  const handleSaveBanner = async () => {
    setSavingBanner(true);
    try {
      await api.put('/settings/banner', {
        message: bannerMessage,
        color: bannerColor,
        visibility: bannerVisibility,
      });
      message.success(t('admin.branding.bannerSaved'));
    } catch (err: any) {
      message.error(err.response?.data?.detail || t('common.error'));
    } finally {
      setSavingBanner(false);
    }
  };

  const bannerTypeMap: Record<string, 'info' | 'warning' | 'error'> = {
    info: 'info', warning: 'warning', alert: 'error', other: 'info',
  };
  const bannerIsOther = bannerColor === 'other';

  const footerPreview = `${footerText || 'Qualys2Human'} - NeoRed - 2026/${new Date().getFullYear()}`;

  return (
    <div>
      <Card title={t('admin.branding.appLogo')}>
        <div style={{ textAlign: 'center', marginBottom: 24, padding: 24, background: tokens.surfaceSecondary, borderRadius: 8 }}>
          {logoUrl ? (
            <Image
              src={logoUrl}
              alt="Logo"
              style={{ maxHeight: 100, maxWidth: 400 }}
              preview={false}
            />
          ) : (
            <Text type="secondary">{t('admin.branding.noLogo')}</Text>
          )}
        </div>

        <Space direction="vertical" style={{ width: '100%' }}>
          <Space wrap>
            <Upload {...uploadProps}>
              <Button icon={<UploadOutlined />} type="primary" loading={uploading}>
                {t('admin.branding.importLogo')}
              </Button>
            </Upload>
            <Button icon={<DeleteOutlined />} danger onClick={handleDelete} loading={deleting}>
              {t('admin.branding.restoreDefaultLogo')}
            </Button>
            <Button icon={<DownloadOutlined />} onClick={handleDownloadTemplate}>
              {t('admin.branding.downloadTemplate')}
            </Button>
          </Space>

          <Paragraph type="secondary" style={{ marginTop: 16 }}>
            {t('admin.branding.logoFormats')}
          </Paragraph>
        </Space>
      </Card>

      <Card title={t('admin.branding.footer')} style={{ marginTop: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text strong>{t('admin.branding.customText')}</Text>
            <Input
              value={footerText}
              onChange={(e) => setFooterText(e.target.value)}
              placeholder="Qualys2Human"
              style={{ marginTop: 8 }}
            />
            <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
              {t('admin.branding.footerHint')}
            </Paragraph>
          </div>

          <div style={{ padding: '12px 16px', background: tokens.surfaceSecondary, borderRadius: 8, textAlign: 'center' }}>
            <Text type="secondary" style={{ fontSize: 12 }}>{t('admin.branding.preview')}</Text>
            <div style={{ marginTop: 4 }}>
              <Text type="secondary" style={{ fontSize: 13 }}>{footerPreview}</Text>
            </div>
          </div>

          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSaveFooter}
            loading={savingFooter}
          >
            {t('common.save')}
          </Button>
        </Space>
      </Card>

      <Card title={t('admin.branding.banner')} style={{ marginTop: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text strong>{t('admin.branding.bannerMessage')}</Text>
            <Input.TextArea
              value={bannerMessage}
              onChange={(e) => setBannerMessage(e.target.value)}
              placeholder={t('admin.branding.bannerPlaceholder')}
              maxLength={500}
              showCount
              rows={3}
              style={{ marginTop: 8 }}
            />
          </div>

          <div>
            <Text strong>{t('admin.branding.bannerColor')}</Text>
            <Select
              value={bannerColor}
              onChange={setBannerColor}
              style={{ width: '100%', marginTop: 8 }}
              options={COLOR_OPTIONS.map((o) => ({
                value: o.value,
                label: (
                  <span>
                    <span style={{
                      display: 'inline-block', width: 12, height: 12,
                      borderRadius: '50%', background: o.color,
                      marginRight: 8, verticalAlign: 'middle',
                    }} />
                    {o.label}
                  </span>
                ),
              }))}
            />
          </div>

          <div>
            <Text strong>{t('admin.branding.bannerVisibility')}</Text>
            <div style={{ marginTop: 8 }}>
              <Radio.Group value={bannerVisibility} onChange={(e) => setBannerVisibility(e.target.value)}>
                <Radio value="all">{t('admin.branding.visAll')}</Radio>
                <Radio value="admin">{t('admin.branding.visAdmin')}</Radio>
                <Radio value="none">{t('admin.branding.visNone')}</Radio>
              </Radio.Group>
            </div>
          </div>

          {bannerMessage && bannerVisibility !== 'none' && (
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>{t('admin.branding.preview')}</Text>
              <div style={{ marginTop: 4 }}>
                <Alert
                  banner
                  type={bannerTypeMap[bannerColor] || 'info'}
                  message={<strong>{bannerMessage}</strong>}
                  style={{
                    textAlign: 'center',
                    ...(bannerIsOther ? { background: tokens.otherBannerBg, borderColor: tokens.otherBannerBorder } : {}),
                  }}
                />
              </div>
            </div>
          )}

          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSaveBanner}
            loading={savingBanner}
          >
            {t('common.save')}
          </Button>
        </Space>
      </Card>
    </div>
  );
}
