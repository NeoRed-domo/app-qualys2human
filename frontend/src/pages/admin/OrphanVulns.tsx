import { useEffect, useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button, Tag, Spin, Alert, Typography, message, Modal, Form, Input,
  InputNumber, Select, ColorPicker, Space,
} from 'antd';
import { ArrowLeftOutlined, PlusOutlined, SyncOutlined, BulbOutlined, SearchOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry, themeQuartz, type ColDef } from 'ag-grid-community';
import api from '../../api/client';
import { useTheme } from '../../contexts/ThemeContext';
import { useAuth } from '../../contexts/AuthContext';
import { useFilters } from '../../contexts/FilterContext';
import ProposeRuleModal from '../../components/ProposeRuleModal';
import PendingProposalsPanel from '../../components/PendingProposalsPanel';
import HelpTooltip from '../../components/help/HelpTooltip';

ModuleRegistry.registerModules([AllCommunityModule]);

const { Title, Text } = Typography;

interface OrphanRow {
  qid: number;
  title: string | null;
  category: string | null;
  type: string | null;
  severity: number;
  occurrences: number;
}

interface LayerOption {
  id: number;
  name: string;
  color: string;
  position: number;
}

const CREATE_LAYER_VALUE = -1;

export default function OrphanVulns() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { tokens } = useTheme();
  const { user } = useAuth();
  const globalFilters = useFilters();
  const isAdmin = user?.profile === 'admin';
  const [rows, setRows] = useState<OrphanRow[]>([]);
  const [layers, setLayers] = useState<LayerOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Local filters (synced from global/enterprise preset once loaded)
  const [selectedSeverities, setSelectedSeverities] = useState<number[]>(globalFilters.severities);
  const [selectedTypes, setSelectedTypes] = useState<string[]>(globalFilters.types);
  const [searchText, setSearchText] = useState('');
  const [filtersInitialized, setFiltersInitialized] = useState(globalFilters.severities.length > 0 || globalFilters.types.length > 0);

  // Sync once when FilterContext finishes loading the enterprise preset
  useEffect(() => {
    if (!filtersInitialized && (globalFilters.severities.length > 0 || globalFilters.types.length > 0)) {
      setSelectedSeverities(globalFilters.severities);
      setSelectedTypes(globalFilters.types);
      setFiltersInitialized(true);
    }
  }, [globalFilters.severities, globalFilters.types, filtersInitialized]);

  // Propose modal (user mode)
  const [proposeModalOpen, setProposeModalOpen] = useState(false);
  const [proposePattern, setProposePattern] = useState('');

  // Rule modal
  const [ruleModalOpen, setRuleModalOpen] = useState(false);
  const [selectedOrphan, setSelectedOrphan] = useState<OrphanRow | null>(null);
  const [ruleForm] = Form.useForm();
  const [matchCount, setMatchCount] = useState(0);
  const [ruleSaving, setRuleSaving] = useState(false);

  // Layer creation mini-modal
  const [layerModalOpen, setLayerModalOpen] = useState(false);
  const [layerForm] = Form.useForm();
  const [layerSaving, setLayerSaving] = useState(false);

  // Track rules created this session
  const [rulesCreatedCount, setRulesCreatedCount] = useState(0);

  // Derive available types from data
  const availableTypes = useMemo(() => {
    const set = new Set<string>();
    rows.forEach((r) => { if (r.type) set.add(r.type); });
    return Array.from(set).sort();
  }, [rows]);

  // Filtered rows
  const filteredRows = useMemo(() => {
    return rows.filter((r) => {
      if (selectedSeverities.length > 0 && !selectedSeverities.includes(r.severity)) return false;
      if (selectedTypes.length > 0 && !selectedTypes.includes(r.type || '')) return false;
      if (searchText) {
        const q = searchText.toLowerCase();
        if (!(r.title || '').toLowerCase().includes(q) && !(r.category || '').toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [rows, selectedSeverities, selectedTypes, searchText]);

  const SEVERITY_TAG: Record<number, { color: string; label: string }> = {
    5: { color: 'red', label: t('severity.5') },
    4: { color: 'orange', label: t('severity.4') },
    3: { color: 'gold', label: t('severity.3') },
    2: { color: 'blue', label: t('severity.2') },
    1: { color: 'green', label: t('severity.1') },
  };

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [orphansResp, layersResp] = await Promise.all([
        api.get('/layers/orphans'),
        api.get('/layers'),
      ]);
      setRows(orphansResp.data);
      setLayers(layersResp.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('admin.layer.loadError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // --- Match count computation ---

  const computeMatchCount = useCallback((pattern: string, matchField: string) => {
    if (!pattern) return 0;
    const p = pattern.toLowerCase();
    return rows.filter((r) => {
      const value = matchField === 'title' ? r.title : r.category;
      return (value || '').toLowerCase().includes(p);
    }).length;
  }, [rows]);

  const handleFormChange = useCallback(() => {
    const pattern = ruleForm.getFieldValue('pattern') || '';
    const matchField = ruleForm.getFieldValue('match_field') || 'title';
    setMatchCount(computeMatchCount(pattern, matchField));
  }, [ruleForm, computeMatchCount]);

  // --- Open rule modal ---

  const openRuleModal = useCallback((orphan: OrphanRow) => {
    setSelectedOrphan(orphan);
    ruleForm.resetFields();
    ruleForm.setFieldsValue({
      pattern: orphan.title || '',
      match_field: 'title',
    });
    const count = computeMatchCount(orphan.title || '', 'title');
    setMatchCount(count);
    setRuleModalOpen(true);
  }, [ruleForm, computeMatchCount]);

  // --- Layer select options ---

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
    ...(isAdmin ? [{ value: CREATE_LAYER_VALUE, label: t('admin.layer.createCategory') }] : []),
  ], [layers, t, isAdmin]);

  // --- Handle layer_id change (detect "create new") ---

  const handleLayerIdChange = useCallback((value: number) => {
    if (value === CREATE_LAYER_VALUE) {
      // Reset the select so it doesn't stay on the placeholder
      ruleForm.setFieldValue('layer_id', undefined);
      // Open layer creation modal
      layerForm.resetFields();
      layerForm.setFieldsValue({ color: '#1677ff', position: layers.length });
      setLayerModalOpen(true);
    }
  }, [ruleForm, layerForm, layers.length]);

  // --- Save new layer ---

  const handleLayerSave = async () => {
    try {
      const values = await layerForm.validateFields();
      const color = typeof values.color === 'string' ? values.color : values.color?.toHexString?.() || '#1677ff';
      setLayerSaving(true);
      const resp = await api.post('/layers', { name: values.name, color, position: values.position });
      const newLayer: LayerOption = resp.data;
      setLayers((prev) => [...prev, newLayer]);
      // Auto-select the new layer in the rule form
      ruleForm.setFieldValue('layer_id', newLayer.id);
      setLayerModalOpen(false);
      message.success(t('admin.layer.created'));
    } catch (err: any) {
      if (err.response) message.error(err.response.data?.detail || t('common.error'));
    } finally {
      setLayerSaving(false);
    }
  };

  // --- Save rule ---

  const handleRuleSave = async () => {
    try {
      const values = await ruleForm.validateFields();
      setRuleSaving(true);
      await api.post(`/layers/${values.layer_id}/rules`, {
        match_field: values.match_field,
        pattern: values.pattern,
      });
      message.success(t('admin.layer.ruleCreated'));
      setRulesCreatedCount((c) => c + 1);
      setRuleModalOpen(false);

      // Remove matched rows from display
      const pattern = values.pattern.toLowerCase();
      const matchField = values.match_field;
      setRows((prev) => prev.filter((r) => {
        const value = matchField === 'title' ? r.title : r.category;
        return !(value || '').toLowerCase().includes(pattern);
      }));
    } catch (err: any) {
      if (err.response) message.error(err.response.data?.detail || t('common.error'));
    } finally {
      setRuleSaving(false);
    }
  };

  // --- Reclassify ---

  const handleReclassify = async () => {
    try {
      await api.post('/layers/reclassify');
      message.info(t('admin.layer.reclassStarted'));
      navigate('/admin/layers');
    } catch (err: any) {
      message.error(err.response?.data?.detail || t('common.error'));
    }
  };

  // --- AG Grid columns ---

  const columns: ColDef<OrphanRow>[] = [
    { field: 'qid', headerName: 'QID', width: 90, filter: 'agNumberColumnFilter', sortable: true },
    {
      field: 'title', headerName: t('common.title'), flex: 2, minWidth: 120,
      wrapText: true, autoHeight: true, filter: 'agTextColumnFilter', sortable: true,
    },
    { field: 'category', headerName: t('common.category'), flex: 1, minWidth: 100, filter: 'agTextColumnFilter', sortable: true },
    { field: 'type', headerName: t('common.type'), width: 110, filter: 'agTextColumnFilter', sortable: true },
    {
      field: 'severity', headerName: t('filters.severity'), width: 120, sortable: true, sort: 'desc',
      filter: 'agNumberColumnFilter',
      cellRenderer: (p: any) => {
        const tag = SEVERITY_TAG[p.value];
        return tag ? <Tag color={tag.color}>{tag.label}</Tag> : p.value;
      },
    },
    { field: 'occurrences', headerName: t('overview.occurrences'), width: 100, sortable: true },
    {
      headerName: t('common.actions'),
      minWidth: 160,
      width: 160,
      suppressSizeToFit: true,
      pinned: 'right',
      cellRenderer: (p: any) => {
        const row = p.data as OrphanRow;
        if (!row) return null;
        if (isAdmin) {
          return (
            <Button
              size="small"
              icon={<PlusOutlined />}
              onClick={() => openRuleModal(row)}
            >
              {t('vulnDetail.createRule')}
            </Button>
          );
        }
        return (
          <Button
            size="small"
            icon={<BulbOutlined />}
            title={t('proposals.propose')}
            onClick={() => {
              setProposePattern(row.title || '');
              setProposeModalOpen(true);
            }}
          >
            {t('proposals.proposeShort')}
          </Button>
        );
      },
    },
  ];

  if (error) {
    return <Alert message={t('common.error')} description={error} type="error" showIcon />;
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          type="link"
          onClick={() => navigate(isAdmin ? '/admin/layers' : '/')}
          style={{ padding: 0 }}
        >
          {t('common.back')}
        </Button>
        <Title level={4} style={{ margin: 0 }}>{t('admin.layer.uncategorizedVulns')}</Title>
        <Text type="secondary">
          {filteredRows.length !== rows.length
            ? `${filteredRows.length} / ${rows.length} QIDs`
            : `${rows.length} QID${rows.length > 1 ? 's' : ''}`}
        </Text>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 'auto' }}>
          {isAdmin && rulesCreatedCount > 0 && (
            <Button
              type="primary"
              icon={<SyncOutlined />}
              onClick={handleReclassify}
            >
              {t('admin.layer.launchReclassification', { count: rulesCreatedCount })}
            </Button>
          )}
          <HelpTooltip topic="orphans" />
        </span>
      </div>

      {isAdmin && (
        <PendingProposalsPanel
          layers={layers}
          onAction={(approved) => {
            fetchData();
            if (approved) setRulesCreatedCount((c) => c + 1);
          }}
        />
      )}

      {/* Filter bar */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <Input
          placeholder={t('common.search')}
          prefix={<SearchOutlined />}
          allowClear
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          style={{ width: 260 }}
        />
        <Select
          mode="multiple"
          allowClear
          placeholder={t('filters.severity')}
          value={selectedSeverities}
          onChange={setSelectedSeverities}
          style={{ minWidth: 200 }}
          options={[5, 4, 3, 2, 1].map((s) => ({
            value: s,
            label: <Tag color={SEVERITY_TAG[s]?.color}>{SEVERITY_TAG[s]?.label}</Tag>,
          }))}
        />
        <Select
          mode="multiple"
          allowClear
          placeholder={t('common.type')}
          value={selectedTypes}
          onChange={setSelectedTypes}
          style={{ minWidth: 180 }}
          options={availableTypes.map((t) => ({ value: t, label: t }))}
        />
      </div>

      <Spin spinning={loading}>
        <div style={{ height: 'calc(100vh - 320px)' }}>
          <AgGridReact<OrphanRow>
            theme={themeQuartz.withParams({ colorScheme: tokens.agGridColorScheme })}
            rowData={filteredRows}
            columnDefs={columns}
            domLayout="normal"
            rowHeight={42}
            headerHeight={38}
            getRowId={(p) => String(p.data.qid)}
          />
        </div>
      </Spin>

      {/* Rule creation modal */}
      <Modal
        title={selectedOrphan ? `${t('modals.createRule')} — QID ${selectedOrphan.qid}` : t('modals.createRule')}
        open={ruleModalOpen}
        onOk={handleRuleSave}
        onCancel={() => setRuleModalOpen(false)}
        confirmLoading={ruleSaving}
        okText={t('modals.createRuleBtn')}
        cancelText={t('common.cancel')}
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
            {t('modals.matchCount', { count: matchCount })}
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

      {/* Propose rule modal (user mode) */}
      <ProposeRuleModal
        open={proposeModalOpen}
        onClose={() => setProposeModalOpen(false)}
        onCreated={() => setProposeModalOpen(false)}
        defaultPattern={proposePattern}
        defaultMatchField="title"
        orphanRows={rows.map((r) => ({ title: r.title || '', category: r.category || '' }))}
      />
    </div>
  );
}
