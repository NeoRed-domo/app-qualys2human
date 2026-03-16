import { useEffect, useState } from 'react';
import { Row, Col, Checkbox, Select, DatePicker, Button, Card, Space, Tooltip, message } from 'antd';
import { ClearOutlined, BankOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useFilters } from '../../contexts/FilterContext';
import PresetSelector from './PresetSelector';
import api from '../../api/client';
import dayjs from 'dayjs';

interface LayerOption {
  label: string;
  value: number;
}

interface FilterBarProps {
  extra?: React.ReactNode;
}

export default function FilterBar({ extra }: FilterBarProps) {
  const { t } = useTranslation();
  const {
    severities, types, layers, osClasses, freshness, dateFrom, dateTo,
    setSeverities, setTypes, setLayers, setOsClasses, setFreshness, setDateFrom, setDateTo,
    resetFilters, applyEnterprisePreset,
  } = useFilters();
  const [layerOptions, setLayerOptions] = useState<LayerOption[]>([]);

  const SEVERITY_OPTIONS = [
    { label: t('severity.5'), value: 5 },
    { label: t('severity.4'), value: 4 },
    { label: t('severity.3'), value: 3 },
    { label: t('severity.2'), value: 2 },
    { label: t('severity.1'), value: 1 },
  ];

  const TYPE_OPTIONS = [
    { label: 'Vuln', value: 'Vuln' },
    { label: 'Practice', value: 'Practice' },
    { label: 'Info', value: 'Ig' },
  ];

  const OS_CLASS_OPTIONS = [
    { label: t('filters.osWindows'), value: 'windows' },
    { label: t('filters.osNix'), value: 'nix' },
  ];

  useEffect(() => {
    api.get('/layers').then((resp) => {
      setLayerOptions(
        resp.data.map((l: { id: number; name: string }) => ({ label: l.name, value: l.id }))
      );
    }).catch(() => {});
  }, []);

  const handleApplyEnterprise = async () => {
    await applyEnterprisePreset();
    message.success(t('filters.enterpriseApplied'));
  };

  return (
    <Card size="small" style={{ marginBottom: 16 }}>
      <Row gutter={[16, 12]} align="middle">
        <Col xs={24} md={10}>
          <div style={{ marginBottom: 4, fontWeight: 500, fontSize: 12 }}>{t('filters.severity')}</div>
          <Checkbox.Group
            options={SEVERITY_OPTIONS}
            value={severities}
            onChange={(val) => setSeverities(val as number[])}
          />
        </Col>

        <Col xs={24} md={5}>
          <div style={{ marginBottom: 4, fontWeight: 500, fontSize: 12 }}>{t('filters.type')}</div>
          <Select
            mode="multiple"
            style={{ width: '100%' }}
            placeholder={t('filters.allTypes')}
            options={TYPE_OPTIONS}
            value={types}
            onChange={setTypes}
            allowClear
          />
        </Col>

        <Col xs={24} md={4}>
          <div style={{ marginBottom: 4, fontWeight: 500, fontSize: 12 }}>{t('filters.categorization')}</div>
          <Select
            mode="multiple"
            style={{ width: '100%' }}
            placeholder={t('filters.allCategories')}
            options={[...layerOptions, { label: t('common.uncategorized'), value: 0 }]}
            value={layers}
            onChange={setLayers}
            allowClear
          />
        </Col>

        <Col xs={24} md={3}>
          <div style={{ marginBottom: 4, fontWeight: 500, fontSize: 12 }}>{t('filters.osClass')}</div>
          <Select
            mode="multiple"
            style={{ width: '100%' }}
            placeholder={t('filters.allOsClasses')}
            options={OS_CLASS_OPTIONS}
            value={osClasses}
            onChange={setOsClasses}
            allowClear
          />
        </Col>

        <Col xs={24} md={2}>
          <div style={{ marginBottom: 4, fontWeight: 500, fontSize: 12 }}>{t('filters.freshness')}</div>
          <Select
            style={{ width: '100%' }}
            value={freshness}
            onChange={setFreshness}
            options={[
              { label: t('freshness.active'), value: 'active' },
              { label: t('freshness.stale'), value: 'stale' },
              { label: t('freshness.all'), value: 'all' },
            ]}
          />
        </Col>

        <Col xs={12} md={3}>
          <div style={{ marginBottom: 4, fontWeight: 500, fontSize: 12 }}>{t('filters.dateFrom')}</div>
          <DatePicker
            style={{ width: '100%' }}
            value={dateFrom ? dayjs(dateFrom) : null}
            onChange={(d) => setDateFrom(d ? d.format('YYYY-MM-DD') : null)}
          />
        </Col>

        <Col xs={12} md={3}>
          <div style={{ marginBottom: 4, fontWeight: 500, fontSize: 12 }}>{t('filters.dateTo')}</div>
          <DatePicker
            style={{ width: '100%' }}
            value={dateTo ? dayjs(dateTo) : null}
            onChange={(d) => setDateTo(d ? d.format('YYYY-MM-DD') : null)}
          />
        </Col>

        <Col xs={24} md={2}>
          <div style={{ marginBottom: 4, fontWeight: 500, fontSize: 12 }}>&nbsp;</div>
          <Space size={4}>
            <Tooltip title={t('filters.resetTooltip')}>
              <Button icon={<ClearOutlined />} onClick={resetFilters} />
            </Tooltip>
            <Tooltip title={t('filters.enterpriseTooltip')}>
              <Button icon={<BankOutlined />} onClick={handleApplyEnterprise} />
            </Tooltip>
            <PresetSelector />
          </Space>
        </Col>

        {extra && (
          <Col flex="auto" style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'flex-end' }}>
            {extra}
          </Col>
        )}
      </Row>
    </Card>
  );
}
