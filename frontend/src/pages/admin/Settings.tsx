import { useEffect, useState } from 'react';
import { Card, InputNumber, Button, Space, message, Spin, Form } from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import api from '../../api/client';

interface FreshnessValues {
  stale_days: number;
  hide_days: number;
}

interface RetentionValues {
  retention_months: number;
}

export default function Settings() {
  const { t } = useTranslation();
  const [freshnessForm] = Form.useForm<FreshnessValues>();
  const [retentionForm] = Form.useForm<RetentionValues>();
  const [loading, setLoading] = useState(true);
  const [savingFreshness, setSavingFreshness] = useState(false);
  const [savingRetention, setSavingRetention] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get('/settings/freshness'),
      api.get('/settings/retention'),
    ])
      .then(([freshResp, retResp]) => {
        freshnessForm.setFieldsValue(freshResp.data);
        retentionForm.setFieldsValue(retResp.data);
      })
      .catch(() => {
        message.error(t('settings.loadError'));
      })
      .finally(() => setLoading(false));
  }, [freshnessForm, retentionForm, t]);

  const handleSaveFreshness = async () => {
    try {
      const values = await freshnessForm.validateFields();
      setSavingFreshness(true);
      await api.put('/settings/freshness', values);
      message.success(t('settings.saveSuccess'));
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || t('common.error');
      message.error(detail);
    } finally {
      setSavingFreshness(false);
    }
  };

  const handleSaveRetention = async () => {
    try {
      const values = await retentionForm.validateFields();
      setSavingRetention(true);
      await api.put('/settings/retention', values);
      message.success(t('settings.retentionSaveSuccess'));
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || t('common.error');
      message.error(detail);
    } finally {
      setSavingRetention(false);
    }
  };

  return (
    <Spin spinning={loading}>
      <Card title={t('settings.freshnessTitle')} style={{ maxWidth: 600, marginBottom: 16 }}>
        <Form form={freshnessForm} layout="vertical" initialValues={{ stale_days: 7, hide_days: 30 }}>
          <Form.Item
            name="stale_days"
            label={t('settings.staleDays')}
            rules={[{ required: true, message: t('settings.required') }]}
            tooltip={t('settings.staleDaysTooltip')}
          >
            <InputNumber min={1} max={365} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            name="hide_days"
            label={t('settings.hideDays')}
            rules={[{ required: true, message: t('settings.required') }]}
            tooltip={t('settings.hideDaysTooltip')}
          >
            <InputNumber min={1} max={3650} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveFreshness} loading={savingFreshness}>
                {t('common.save')}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>

      <Card title={t('settings.retentionTitle')} style={{ maxWidth: 600 }}>
        <Form form={retentionForm} layout="vertical" initialValues={{ retention_months: 24 }}>
          <Form.Item
            name="retention_months"
            label={t('settings.retentionMonths')}
            rules={[{ required: true, message: t('settings.required') }]}
            tooltip={t('settings.retentionMonthsTooltip')}
          >
            <InputNumber min={6} max={120} style={{ width: '100%' }} addonAfter={t('settings.retentionUnit')} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveRetention} loading={savingRetention}>
                {t('common.save')}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </Spin>
  );
}
