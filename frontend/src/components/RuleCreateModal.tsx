import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Modal, Form, Input, InputNumber, Select, ColorPicker, Typography, message,
} from 'antd';
import { useTranslation } from 'react-i18next';
import api from '../api/client';

const { Text } = Typography;

interface LayerOption {
  id: number;
  name: string;
  color: string;
}

export interface RuleCreateModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
  defaultPattern?: string;
  defaultMatchField?: string;
  autoReclassify?: boolean;
}

const CREATE_LAYER_VALUE = -1;

export default function RuleCreateModal({
  open,
  onClose,
  onCreated,
  defaultPattern = '',
  defaultMatchField = 'title',
  autoReclassify = false,
}: RuleCreateModalProps) {
  const { t } = useTranslation();
  const [ruleForm] = Form.useForm();
  const [layers, setLayers] = useState<LayerOption[]>([]);
  const [matchCount, setMatchCount] = useState<number | null>(null);
  const [ruleSaving, setRuleSaving] = useState(false);

  // Layer creation mini-modal
  const [layerModalOpen, setLayerModalOpen] = useState(false);
  const [layerForm] = Form.useForm();
  const [layerSaving, setLayerSaving] = useState(false);

  // Debounce timer ref
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch layers on open
  useEffect(() => {
    if (!open) return;
    api.get('/layers').then((r) => setLayers(r.data)).catch(() => {});
    ruleForm.resetFields();
    ruleForm.setFieldsValue({
      pattern: defaultPattern,
      match_field: defaultMatchField,
    });
    setMatchCount(null);
    // Trigger initial count
    fetchMatchCount(defaultPattern, defaultMatchField);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchMatchCount = useCallback((pattern: string, matchField: string) => {
    if (!pattern) {
      setMatchCount(0);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const resp = await api.get('/layers/match-count', {
          params: { pattern, match_field: matchField },
        });
        setMatchCount(resp.data.count);
      } catch {
        setMatchCount(null);
      }
    }, 300);
  }, []);

  const handleFormChange = useCallback(() => {
    const pattern = ruleForm.getFieldValue('pattern') || '';
    const matchField = ruleForm.getFieldValue('match_field') || 'title';
    fetchMatchCount(pattern, matchField);
  }, [ruleForm, fetchMatchCount]);

  // Layer select options
  const layerSelectOptions = useMemo(() => [
    ...layers.map((l) => ({
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
    { value: CREATE_LAYER_VALUE, label: t('admin.layer.createCategory') },
  ], [layers, t]);

  const handleLayerIdChange = useCallback((value: number) => {
    if (value === CREATE_LAYER_VALUE) {
      ruleForm.setFieldValue('layer_id', undefined);
      layerForm.resetFields();
      layerForm.setFieldsValue({ color: '#1677ff', position: layers.length });
      setLayerModalOpen(true);
    }
  }, [ruleForm, layerForm, layers.length]);

  // Save new layer
  const handleLayerSave = async () => {
    try {
      const values = await layerForm.validateFields();
      const color = typeof values.color === 'string'
        ? values.color
        : values.color?.toHexString?.() || '#1677ff';
      setLayerSaving(true);
      const resp = await api.post('/layers', { name: values.name, color, position: values.position });
      const newLayer: LayerOption = resp.data;
      setLayers((prev) => [...prev, newLayer]);
      ruleForm.setFieldValue('layer_id', newLayer.id);
      setLayerModalOpen(false);
      message.success(t('admin.layer.created'));
    } catch (err: any) {
      if (err.response) message.error(err.response.data?.detail || t('common.error'));
    } finally {
      setLayerSaving(false);
    }
  };

  // Save rule
  const handleRuleSave = async () => {
    try {
      const values = await ruleForm.validateFields();
      setRuleSaving(true);
      await api.post(`/layers/${values.layer_id}/rules`, {
        match_field: values.match_field,
        pattern: values.pattern,
      });
      message.success(t('admin.layer.ruleCreated'));

      if (autoReclassify) {
        try {
          await api.post('/layers/reclassify');
          message.info(t('admin.layer.reclassStarted'));
        } catch {
          message.warning(t('admin.layer.ruleCreated'));
        }
      }

      onCreated();
      onClose();
    } catch (err: any) {
      if (err.response) message.error(err.response.data?.detail || t('common.error'));
    } finally {
      setRuleSaving(false);
    }
  };

  return (
    <>
      <Modal
        title={t('modals.createRule')}
        open={open}
        onOk={handleRuleSave}
        onCancel={onClose}
        confirmLoading={ruleSaving}
        okText={t('modals.createRuleBtn')}
        cancelText={t('common.cancel')}
        destroyOnClose
      >
        <Form
          form={ruleForm}
          layout="vertical"
          onValuesChange={handleFormChange}
        >
          <Form.Item name="pattern" label={t('modals.pattern')} rules={[{ required: true, message: t('admin.layer.patternRequired') }]}>
            <Input placeholder={t('modals.patternPlaceholder')} />
          </Form.Item>
          <Form.Item name="match_field" label={t('modals.targetField')} rules={[{ required: true }]}>
            <Select options={[
              { label: t('modals.fieldTitle'), value: 'title' },
              { label: t('modals.fieldCategory'), value: 'category' },
            ]} />
          </Form.Item>
          <Form.Item name="layer_id" label={t('filters.categorization')} rules={[{ required: true, message: t('admin.layer.categorizationRequired') }]}>
            <Select
              placeholder={t('modals.selectCategory')}
              options={layerSelectOptions}
              onChange={handleLayerIdChange}
            />
          </Form.Item>
        </Form>
        <div style={{ padding: '8px 0', borderTop: '1px solid #f0f0f0' }}>
          <Text>
            {t('modals.matchCount', { count: matchCount ?? '...' })}
          </Text>
        </div>
      </Modal>

      {/* Layer creation mini-modal */}
      <Modal
        title={t('modals.newCategory')}
        open={layerModalOpen}
        onOk={handleLayerSave}
        onCancel={() => setLayerModalOpen(false)}
        confirmLoading={layerSaving}
        okText={t('common.create')}
        cancelText={t('common.cancel')}
      >
        <Form form={layerForm} layout="vertical">
          <Form.Item name="name" label={t('modals.categoryName')} rules={[{ required: true, message: t('modals.categoryNameRequired') }]}>
            <Input placeholder={t('modals.categoryNamePlaceholder')} />
          </Form.Item>
          <Form.Item name="color" label={t('modals.color')}>
            <ColorPicker format="hex" />
          </Form.Item>
          <Form.Item name="position" label={t('modals.position')}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
