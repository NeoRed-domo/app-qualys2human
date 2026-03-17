import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Modal, Form, Input, Select, Typography, message,
} from 'antd';
import { useTranslation } from 'react-i18next';
import api from '../api/client';

const { Text } = Typography;

interface LayerOption {
  id: number;
  name: string;
  color: string;
}

export interface ProposeRuleModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
  defaultPattern?: string;
  defaultMatchField?: string;
  orphanRows?: Array<{ title: string; category: string }>;
}

export default function ProposeRuleModal({
  open,
  onClose,
  onCreated,
  defaultPattern = '',
  defaultMatchField = 'title',
  orphanRows,
}: ProposeRuleModalProps) {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [layers, setLayers] = useState<LayerOption[]>([]);
  const [saving, setSaving] = useState(false);
  const [matchCount, setMatchCount] = useState(0);

  // Fetch layers on open
  useEffect(() => {
    if (!open) return;
    api.get('/layers').then((r) => setLayers(r.data)).catch(() => {});
    form.resetFields();
    form.setFieldsValue({
      pattern: defaultPattern,
      match_field: defaultMatchField,
    });
    // Compute initial match count
    if (orphanRows) {
      setMatchCount(computeCount(defaultPattern, defaultMatchField, orphanRows));
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  // Client-side match count computation
  const computeCount = (pattern: string, matchField: string, rows: Array<{ title: string; category: string }>) => {
    if (!pattern) return 0;
    const p = pattern.toLowerCase();
    return rows.filter((r) => {
      const value = matchField === 'title' ? r.title : r.category;
      return (value || '').toLowerCase().includes(p);
    }).length;
  };

  const handleFormChange = useCallback(() => {
    if (!orphanRows) return;
    const pattern = form.getFieldValue('pattern') || '';
    const matchField = form.getFieldValue('match_field') || 'title';
    setMatchCount(computeCount(pattern, matchField, orphanRows));
  }, [form, orphanRows]);

  // Layer select options with color dots
  const layerSelectOptions = useMemo(() =>
    layers.map((l) => ({
      value: l.id,
      label: (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
            background: l.color, flexShrink: 0,
          }} />
          {l.name}
        </span>
      ),
    })),
  [layers]);

  // Submit proposal
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      await api.post('/rules/proposals', {
        pattern: values.pattern,
        match_field: values.match_field,
        layer_id: values.layer_id,
      });
      message.success(t('proposals.created'));
      onCreated();
      onClose();
    } catch (err: any) {
      if (err.response?.status === 409 && err.response?.data?.detail === 'DUPLICATE_PROPOSAL') {
        message.warning(t('proposals.duplicateWarning'));
      } else if (err.response) {
        message.error(err.response.data?.detail || t('common.error'));
      }
      // If validateFields failed (no response), do nothing — form shows inline errors
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={t('proposals.modalTitle')}
      open={open}
      onOk={handleSubmit}
      onCancel={onClose}
      confirmLoading={saving}
      okText={t('proposals.submitBtn')}
      cancelText={t('common.cancel')}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        onValuesChange={handleFormChange}
      >
        <Form.Item
          name="pattern"
          label={t('modals.pattern')}
          rules={[{ required: true, message: t('admin.layer.patternRequired') }]}
        >
          <Input placeholder={t('modals.patternPlaceholder')} />
        </Form.Item>
        <Form.Item
          name="match_field"
          label={t('modals.targetField')}
          rules={[{ required: true }]}
        >
          <Select options={[
            { label: t('modals.fieldTitle'), value: 'title' },
            { label: t('modals.fieldCategory'), value: 'category' },
          ]} />
        </Form.Item>
        <Form.Item
          name="layer_id"
          label={t('filters.categorization')}
          rules={[{ required: true, message: t('admin.layer.categorizationRequired') }]}
        >
          <Select
            placeholder={t('modals.selectCategory')}
            options={layerSelectOptions}
          />
        </Form.Item>
      </Form>
      {orphanRows && matchCount > 0 && (
        <div style={{ padding: '8px 0', borderTop: '1px solid #f0f0f0' }}>
          <Text>
            {t('modals.matchCount', { count: matchCount })}
          </Text>
        </div>
      )}
    </Modal>
  );
}
