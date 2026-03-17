import { useEffect, useState } from 'react';
import { Card, Checkbox, Button, message, Spin, Typography, Divider, InputNumber, Tooltip, Radio } from 'antd';
import { SaveOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import api from '../../api/client';

const { Text } = Typography;

interface LayerOption {
  id: number;
  name: string;
}

export default function EnterpriseRules() {
  const { t } = useTranslation();
  const [severities, setSeverities] = useState<number[]>([1, 2, 3, 4, 5]);
  const [types, setTypes] = useState<string[]>([]);
  const [layers, setLayers] = useState<number[]>([]);
  const [osClasses, setOsClasses] = useState<string[]>([]);
  const [freshness, setFreshness] = useState<string>('active');
  const [layerOptions, setLayerOptions] = useState<LayerOption[]>([]);
  const [staleDays, setStaleDays] = useState<number>(7);
  const [hideDays, setHideDays] = useState<number>(30);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const SEVERITY_OPTIONS = [
    { value: 1, label: t('severity.1') },
    { value: 2, label: t('severity.2') },
    { value: 3, label: t('severity.3') },
    { value: 4, label: t('severity.4') },
    { value: 5, label: t('severity.5') },
  ];

  const TYPE_OPTIONS = [
    { value: 'Vuln', label: t('admin.rules.typeVuln') },
    { value: 'Practice', label: t('admin.rules.typePractice') },
    { value: 'Ig', label: t('admin.rules.typeInfo') },
  ];

  const OS_CLASS_OPTIONS = [
    { value: 'windows', label: t('filters.osWindows') },
    { value: 'nix', label: t('filters.osNix') },
  ];

  const FRESHNESS_OPTIONS = [
    { value: 'active', label: t('admin.rules.freshnessActive') },
    { value: 'stale', label: t('admin.rules.freshnessStale') },
    { value: 'all', label: t('admin.rules.freshnessAll') },
  ];

  useEffect(() => {
    const load = async () => {
      try {
        const [presetResp, layersResp, freshnessResp] = await Promise.all([
          api.get('/presets/enterprise'),
          api.get('/layers'),
          api.get('/settings/freshness'),
        ]);
        setSeverities(presetResp.data.severities);
        setTypes(presetResp.data.types);
        setLayers(presetResp.data.layers || []);
        setOsClasses(presetResp.data.os_classes || []);
        setFreshness(presetResp.data.freshness || 'active');
        setLayerOptions(layersResp.data);
        setStaleDays(freshnessResp.data.stale_days ?? 7);
        setHideDays(freshnessResp.data.hide_days ?? 30);
      } catch {
        message.error(t('admin.rules.loadError'));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [t]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await Promise.all([
        api.put('/presets/enterprise', { severities, types, layers, os_classes: osClasses, freshness }),
        api.put('/settings/freshness', { stale_days: staleDays, hide_days: hideDays }),
      ]);
      message.success(t('admin.rules.saved'));
    } catch (err: any) {
      message.error(err.response?.data?.detail || t('common.error'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <Spin style={{ display: 'block', margin: '80px auto' }} size="large" />;

  return (
    <div>
      <Card
        title={t('admin.enterpriseRules')}
        extra={
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
            {t('common.save')}
          </Button>
        }
      >
        <Text type="secondary">
          {t('admin.rules.description')}
        </Text>

        <Divider titlePlacement="left">{t('admin.rules.severitySection')}</Divider>
        <Checkbox.Group
          value={severities}
          onChange={(vals) => setSeverities(vals as number[])}
          options={SEVERITY_OPTIONS.map((o) => ({ label: o.label, value: o.value }))}
        />

        <Divider titlePlacement="left">{t('admin.rules.typeSection')}</Divider>
        <Checkbox.Group
          value={types}
          onChange={(vals) => setTypes(vals as string[])}
          options={TYPE_OPTIONS.map((o) => ({ label: o.label, value: o.value }))}
        />
        {types.length === 0 && (
          <div style={{ marginTop: 8 }}>
            <Text type="secondary">{t('admin.rules.noTypeFilter')}</Text>
          </div>
        )}

        <Divider titlePlacement="left">{t('admin.rules.categorizationSection')}</Divider>
        <Checkbox.Group
          value={layers}
          onChange={(vals) => setLayers(vals as number[])}
          options={layerOptions.map((l) => ({ label: l.name, value: l.id }))}
        />
        {layers.length === 0 && (
          <div style={{ marginTop: 8 }}>
            <Text type="secondary">{t('admin.rules.noCategorizationFilter')}</Text>
          </div>
        )}

        <Divider titlePlacement="left">{t('admin.rules.osClassSection')}</Divider>
        <Checkbox.Group
          value={osClasses}
          onChange={(vals) => setOsClasses(vals as string[])}
          options={OS_CLASS_OPTIONS.map((o) => ({ label: o.label, value: o.value }))}
        />
        {osClasses.length === 0 && (
          <div style={{ marginTop: 8 }}>
            <Text type="secondary">{t('admin.rules.noOsClassFilter')}</Text>
          </div>
        )}

        <Divider titlePlacement="left">{t('admin.rules.freshnessSection')}</Divider>
        <Radio.Group
          value={freshness}
          onChange={(e) => setFreshness(e.target.value)}
          options={FRESHNESS_OPTIONS.map((o) => ({ label: o.label, value: o.value }))}
        />
        <div style={{ marginTop: 8 }}>
          <Text type="secondary">
            {t('admin.rules.freshnessDefault')}
          </Text>
        </div>

        <Divider titlePlacement="left">{t('admin.rules.freshnessThresholds')}</Divider>
        <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
          <div>
            <div style={{ marginBottom: 4 }}>
              <Text>{t('admin.rules.staleThreshold')}</Text>{' '}
              <Tooltip title={t('admin.rules.staleThresholdTooltip')}>
                <InfoCircleOutlined style={{ color: '#8c8c8c' }} />
              </Tooltip>
            </div>
            <InputNumber
              min={1}
              max={365}
              value={staleDays}
              onChange={(v) => setStaleDays(v ?? 7)}
              style={{ width: 120 }}
            />
          </div>
          <div>
            <div style={{ marginBottom: 4 }}>
              <Text>{t('admin.rules.hideThreshold')}</Text>{' '}
              <Tooltip title={t('admin.rules.hideThresholdTooltip')}>
                <InfoCircleOutlined style={{ color: '#8c8c8c' }} />
              </Tooltip>
            </div>
            <InputNumber
              min={1}
              max={3650}
              value={hideDays}
              onChange={(v) => setHideDays(v ?? 30)}
              style={{ width: 120 }}
            />
          </div>
        </div>
      </Card>
    </div>
  );
}
