import { useEffect, useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card, Table, Button, Modal, Form, Input, InputNumber, Select,
  ColorPicker, Popconfirm, message, Space, Typography, Progress, Tag, Badge,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, SyncOutlined, CheckCircleOutlined, WarningOutlined, UnorderedListOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { ColumnsType } from 'antd/es/table';
import api from '../../api/client';
import PendingProposalsPanel from '../../components/PendingProposalsPanel';

const { Text } = Typography;

interface Layer {
  id: number;
  name: string;
  color: string;
  position: number;
}

interface Rule {
  id: number;
  layer_id: number;
  match_field: string;
  pattern: string;
  created_at: string;
}

export default function LayerRules() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [layers, setLayers] = useState<Layer[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [orphanCount, setOrphanCount] = useState(0);

  // Reclassify state
  const [reclassifying, setReclassifying] = useState(false);
  const [reclassifyProgress, setReclassifyProgress] = useState(0);
  const [reclassifyInfo, setReclassifyInfo] = useState('');
  const [dirty, setDirty] = useState<boolean | null>(null); // null = unknown
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Layer modal state
  const [layerModalOpen, setLayerModalOpen] = useState(false);
  const [editingLayer, setEditingLayer] = useState<Layer | null>(null);
  const [layerForm] = Form.useForm();

  // Rule modal state
  const [ruleModalOpen, setRuleModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<Rule | null>(null);
  const [ruleForm] = Form.useForm();

  const loadData = async () => {
    setLoading(true);
    try {
      const layersResp = await api.get('/layers');
      setLayers(layersResp.data);

      // Load rules for all layers in parallel
      const ruleResponses = await Promise.all(
        layersResp.data.map((layer: Layer) => api.get(`/layers/${layer.id}/rules`))
      );
      const allRules: Rule[] = ruleResponses.flatMap((r) => r.data);
      allRules.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      setRules(allRules);
    } catch {
      message.error(t('admin.layer.loadError'));
    } finally {
      setLoading(false);
    }
  };

  const loadDirtyStatus = async () => {
    try {
      const resp = await api.get('/layers/reclassify/status');
      setDirty(resp.data.dirty);
    } catch { /* ignore */ }
  };

  const loadOrphanCount = async () => {
    try {
      const resp = await api.get('/layers/orphans');
      setOrphanCount(resp.data.length);
    } catch { /* ignore */ }
  };

  useEffect(() => { loadData(); loadDirtyStatus(); loadOrphanCount(); }, []);

  // --- Layer CRUD ---

  const openLayerCreate = () => {
    setEditingLayer(null);
    layerForm.resetFields();
    layerForm.setFieldsValue({ color: '#1677ff', position: layers.length });
    setLayerModalOpen(true);
  };

  const openLayerEdit = (layer: Layer) => {
    setEditingLayer(layer);
    layerForm.setFieldsValue({ name: layer.name, color: layer.color, position: layer.position });
    setLayerModalOpen(true);
  };

  const handleLayerSave = async () => {
    try {
      const values = await layerForm.validateFields();
      const color = typeof values.color === 'string' ? values.color : values.color?.toHexString?.() || '#1677ff';
      const payload = { name: values.name, color, position: values.position };
      if (editingLayer) {
        await api.put(`/layers/${editingLayer.id}`, payload);
        message.success(t('admin.layer.modified'));
      } else {
        await api.post('/layers', payload);
        message.success(t('admin.layer.created'));
      }
      setLayerModalOpen(false);
      setDirty(true);
      loadData();
    } catch (err: any) {
      if (err.response) message.error(err.response.data?.detail || t('common.error'));
    }
  };

  const handleLayerDelete = async (id: number) => {
    try {
      await api.delete(`/layers/${id}`);
      message.success(t('admin.layer.deleted'));
      setDirty(true);
      loadData();
    } catch (err: any) {
      message.error(err.response?.data?.detail || t('common.error'));
    }
  };

  // --- Rule CRUD ---

  const openRuleCreate = () => {
    setEditingRule(null);
    ruleForm.resetFields();
    ruleForm.setFieldsValue({ match_field: 'title' });
    setRuleModalOpen(true);
  };

  const openRuleEdit = (rule: Rule) => {
    setEditingRule(rule);
    ruleForm.setFieldsValue({
      match_field: rule.match_field,
      pattern: rule.pattern,
      layer_id: rule.layer_id,
    });
    setRuleModalOpen(true);
  };

  const handleRuleSave = async () => {
    try {
      const values = await ruleForm.validateFields();
      if (editingRule) {
        await api.put(`/layers/rules/${editingRule.id}`, {
          match_field: values.match_field,
          pattern: values.pattern,
          layer_id: values.layer_id,
        });
        message.success(t('admin.layer.ruleModified'));
      } else {
        await api.post(`/layers/${values.layer_id}/rules`, {
          match_field: values.match_field,
          pattern: values.pattern,
        });
        message.success(t('admin.layer.ruleCreated'));
      }
      setRuleModalOpen(false);
      setDirty(true);
      loadData();
    } catch (err: any) {
      if (err.response) message.error(err.response.data?.detail || t('common.error'));
    }
  };

  const handleRuleDelete = async (id: number) => {
    try {
      await api.delete(`/layers/rules/${id}`);
      message.success(t('admin.layer.ruleDeleted'));
      setDirty(true);
      loadData();
    } catch (err: any) {
      message.error(err.response?.data?.detail || t('common.error'));
    }
  };

  // --- Reclassify with progress polling ---

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // Clean up polling on unmount
  useEffect(() => () => stopPolling(), [stopPolling]);

  const pollStatus = useCallback(() => {
    pollRef.current = setInterval(async () => {
      try {
        const resp = await api.get('/layers/reclassify/status');
        const { running, progress, rules_applied, total_rules, classified, error, dirty: d } = resp.data;
        setReclassifyProgress(progress);
        setReclassifyInfo(t('admin.layer.reclassProgress', { applied: rules_applied, total: total_rules, classified }));
        if (!running) {
          stopPolling();
          setReclassifying(false);
          setDirty(d);
          if (error) {
            message.error(t('admin.layer.reclassError', { error }));
          } else {
            message.success(t('admin.layer.reclassComplete', { count: classified }));
          }
        }
      } catch {
        stopPolling();
        setReclassifying(false);
      }
    }, 1000);
  }, [stopPolling, t]);

  const handleReclassify = () => {
    // Fire-and-forget so the Popconfirm closes immediately
    setReclassifying(true);
    setReclassifyProgress(0);
    setReclassifyInfo(t('admin.layer.starting'));
    api.post('/layers/reclassify').then((resp) => {
      if (!resp.data.started) {
        message.warning(resp.data.message);
        setReclassifying(false);
        return;
      }
      pollStatus();
    }).catch((err: any) => {
      message.error(err.response?.data?.detail || t('common.error'));
      setReclassifying(false);
    });
  };

  // --- Layer columns ---

  const layerColumns: ColumnsType<Layer> = [
    { title: t('common.name'), dataIndex: 'name', key: 'name' },
    {
      title: t('modals.color'), dataIndex: 'color', key: 'color',
      render: (color: string) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 20, height: 20, borderRadius: 4, background: color }} />
          <span>{color}</span>
        </div>
      ),
    },
    { title: t('modals.position'), dataIndex: 'position', key: 'position', width: 90 },
    {
      title: t('admin.layer.classificationRules'), key: 'ruleCount', width: 80,
      render: (_: unknown, record: Layer) => rules.filter((r) => r.layer_id === record.id).length,
    },
    {
      title: t('common.actions'), key: 'actions', width: 120,
      render: (_: unknown, record: Layer) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openLayerEdit(record)} />
          <Popconfirm title={t('admin.layer.deleteCategorization')} onConfirm={() => handleLayerDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // --- Rule columns ---

  const layerNameMap = Object.fromEntries(layers.map((l) => [l.id, l.name]));

  const ruleColumns: ColumnsType<Rule> = [
    {
      title: t('common.date'), dataIndex: 'created_at', key: 'created_at', width: 140,
      render: (val: string) => val ? new Date(val).toLocaleDateString() : '—',
      sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      defaultSortOrder: 'descend' as const,
    },
    { title: t('modals.targetField'), dataIndex: 'match_field', key: 'match_field', width: 100 },
    { title: t('modals.pattern'), dataIndex: 'pattern', key: 'pattern' },
    {
      title: t('filters.categorization'), key: 'layer', width: 130,
      render: (_: unknown, record: Rule) => layerNameMap[record.layer_id] || '—',
    },
    {
      title: t('common.actions'), key: 'actions', width: 120,
      render: (_: unknown, record: Rule) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openRuleEdit(record)} />
          <Popconfirm title={t('admin.layer.deleteRule')} onConfirm={() => handleRuleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PendingProposalsPanel layers={layers} onAction={(approved) => { loadData(); if (approved) setDirty(true); }} />

      <div style={{ marginBottom: 16 }}>
        <Space align="center">
          <Button type="primary" icon={<SyncOutlined spin={reclassifying} />} loading={reclassifying} disabled={reclassifying} onClick={handleReclassify}>
            {t('admin.layer.relaunchCategorization')}
          </Button>
          <Badge count={orphanCount} overflowCount={999}>
            <Button icon={<UnorderedListOutlined />} onClick={() => navigate('/admin/layers/orphans')}>
              {t('admin.layer.categorizeOrphans')}
            </Button>
          </Badge>
          {dirty === false && (
            <Tag icon={<CheckCircleOutlined />} color="success">{t('admin.layer.upToDate')}</Tag>
          )}
          {dirty === true && (
            <Tag icon={<WarningOutlined />} color="warning">{t('admin.layer.categorizationStale')}</Tag>
          )}
        </Space>
        {reclassifying && (
          <div style={{ marginTop: 12, maxWidth: 500 }}>
            <Progress percent={reclassifyProgress} status="active" />
            <Text type="secondary" style={{ fontSize: 12 }}>{reclassifyInfo}</Text>
          </div>
        )}
      </div>

      <Card
        title={t('admin.layer.categorizations')}
        extra={<Button icon={<PlusOutlined />} onClick={openLayerCreate}>{t('admin.layer.addCategorization')}</Button>}
        style={{ marginBottom: 16 }}
      >
        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          {t('admin.layer.categorizationDesc')}
        </Text>
        <Table
          columns={layerColumns}
          dataSource={layers}
          rowKey="id"
          loading={loading}
          pagination={false}
          size="small"
        />
      </Card>

      <Card
        title={t('admin.layer.classificationRules')}
        extra={<Button icon={<PlusOutlined />} onClick={openRuleCreate}>{t('admin.layer.addRule')}</Button>}
      >
        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          {t('admin.layer.ruleDesc')}
        </Text>
        <Table
          columns={ruleColumns}
          dataSource={rules}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 20 }}
          size="small"
        />
      </Card>

      {/* Layer modal */}
      <Modal
        title={editingLayer ? t('admin.layer.editCategorization') : t('admin.layer.newCategorization')}
        open={layerModalOpen}
        onOk={handleLayerSave}
        onCancel={() => setLayerModalOpen(false)}
        okText={t('common.save')}
        cancelText={t('common.cancel')}
      >
        <Form form={layerForm} layout="vertical">
          <Form.Item name="name" label={t('common.name')} rules={[{ required: true, message: t('admin.layer.nameRequired') }]}>
            <Input placeholder={t('admin.layer.namePlaceholder')} />
          </Form.Item>
          <Form.Item name="color" label={t('modals.color')}>
            <ColorPicker format="hex" />
          </Form.Item>
          <Form.Item name="position" label={t('modals.position')}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Rule modal */}
      <Modal
        title={editingRule ? t('admin.layer.editRule') : t('admin.layer.newRule')}
        open={ruleModalOpen}
        onOk={handleRuleSave}
        onCancel={() => setRuleModalOpen(false)}
        okText={t('common.save')}
        cancelText={t('common.cancel')}
      >
        <Form form={ruleForm} layout="vertical">
          <Form.Item name="layer_id" label={t('filters.categorization')} rules={[{ required: true, message: t('admin.layer.categorizationRequired') }]}>
            <Select
              placeholder={t('modals.selectCategory')}
              options={layers.map((l) => ({ label: l.name, value: l.id }))}
            />
          </Form.Item>
          <Form.Item name="match_field" label={t('modals.targetField')} rules={[{ required: true }]}>
            <Select options={[
              { label: t('modals.fieldTitle'), value: 'title' },
              { label: t('modals.fieldCategory'), value: 'category' },
            ]} />
          </Form.Item>
          <Form.Item name="pattern" label={t('modals.pattern')} rules={[{ required: true, message: t('admin.layer.patternRequired') }]}>
            <Input placeholder={t('modals.patternPlaceholder')} />
          </Form.Item>
        </Form>
      </Modal>

    </div>
  );
}
