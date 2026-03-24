import { useEffect, useState, useCallback, useRef } from 'react';
import {
  Card,
  Table,
  Tag,
  Button,
  Upload,
  message,
  Progress,
  Space,
  Typography,
  Popconfirm,
  Modal,
  Input,
  notification,
  Switch,
  Form,
  Badge,
  DatePicker,
} from 'antd';
import dayjs from 'dayjs';
import {
  UploadOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  DeleteOutlined,
  ExclamationCircleOutlined,
  PlusOutlined,
  EditOutlined,
  EyeOutlined,
  FolderOpenOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { ColumnsType } from 'antd/es/table';
import type { UploadProps } from 'antd';
import api from '../../api/client';

const { Text } = Typography;

// --- Watch path types ---

interface WatchPath {
  id: number;
  path: string;
  pattern: string;
  recursive: boolean;
  enabled: boolean;
  ignore_before: string | null;
  created_at: string;
  updated_at: string;
}

interface WatcherStatus {
  running: boolean;
  active_paths: number;
  known_files: number;
  scanning: boolean;
  importing: string | null;
  last_import: string | null;
  last_error: string | null;
  import_count: number;
}

// --- Import job types ---

interface ImportJob {
  id: number;
  scan_report_id: number;
  filename: string;
  source: string;
  report_date: string | null;
  status: string;
  progress: number;
  rows_processed: number;
  rows_total: number;
  started_at: string | null;
  ended_at: string | null;
  error_message: string | null;
}

const STATUS_TAG: Record<string, { color: string; icon: React.ReactNode }> = {
  done: { color: 'success', icon: <CheckCircleOutlined /> },
  processing: { color: 'processing', icon: <SyncOutlined spin /> },
  pending: { color: 'default', icon: <ClockCircleOutlined /> },
  error: { color: 'error', icon: <CloseCircleOutlined /> },
};

export default function ImportManager() {
  const { t } = useTranslation();

  // --- Watch paths state ---
  const [watchPaths, setWatchPaths] = useState<WatchPath[]>([]);
  const [watcherStatus, setWatcherStatus] = useState<WatcherStatus | null>(null);
  const [wpLoading, setWpLoading] = useState(false);
  const [wpModalOpen, setWpModalOpen] = useState(false);
  const [editingWp, setEditingWp] = useState<WatchPath | null>(null);
  const [wpForm] = Form.useForm();

  // --- Import jobs state ---
  const [jobs, setJobs] = useState<ImportJob[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [resetModalOpen, setResetModalOpen] = useState(false);
  const [resetConfirmText, setResetConfirmText] = useState('');

  // --- Watch paths API ---

  const fetchWatchPaths = useCallback(async () => {
    setWpLoading(true);
    try {
      const [pathsResp, statusResp] = await Promise.all([
        api.get('/watcher/paths'),
        api.get('/watcher/status'),
      ]);
      setWatchPaths(pathsResp.data);
      setWatcherStatus(statusResp.data);
    } catch {
      // User may not be admin — silently ignore
    } finally {
      setWpLoading(false);
    }
  }, []);

  const handleCreateOrUpdateWp = async () => {
    try {
      const values = await wpForm.validateFields();
      const payload = {
        ...values,
        ignore_before: values.ignore_before ? values.ignore_before.toISOString() : null,
      };
      if (editingWp) {
        await api.put(`/watcher/paths/${editingWp.id}`, payload);
        message.success(t('admin.import.dirUpdated'));
      } else {
        await api.post('/watcher/paths', payload);
        message.success(t('admin.import.dirAdded'));
      }
      setWpModalOpen(false);
      setEditingWp(null);
      wpForm.resetFields();
      fetchWatchPaths();
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || t('common.error');
      message.error(detail);
    }
  };

  const handleToggleWp = async (wp: WatchPath, enabled: boolean) => {
    try {
      await api.put(`/watcher/paths/${wp.id}`, { enabled });
      fetchWatchPaths();
    } catch {
      message.error(t('admin.import.updateError'));
    }
  };

  const handleDeleteWp = async (id: number) => {
    try {
      await api.delete(`/watcher/paths/${id}`);
      message.success(t('admin.import.dirDeleted'));
      fetchWatchPaths();
    } catch {
      message.error(t('admin.import.deleteError'));
    }
  };

  const openEditWp = (wp: WatchPath) => {
    setEditingWp(wp);
    wpForm.setFieldsValue({
      path: wp.path,
      pattern: wp.pattern,
      recursive: wp.recursive,
      enabled: wp.enabled,
      ignore_before: wp.ignore_before ? dayjs(wp.ignore_before) : null,
    });
    setWpModalOpen(true);
  };

  const openCreateWp = () => {
    setEditingWp(null);
    wpForm.resetFields();
    wpForm.setFieldsValue({ pattern: '*.csv', recursive: false, enabled: true });
    setWpModalOpen(true);
  };

  // --- Import jobs API ---

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await api.get(`/imports?page=${page}&page_size=15`);
      setJobs(resp.data.items);
      setTotal(resp.data.total);
    } catch {
      message.error(t('admin.import.loadError'));
    } finally {
      setLoading(false);
    }
  }, [page, t]);

  useEffect(() => {
    fetchWatchPaths();
    fetchJobs();
  }, [fetchWatchPaths, fetchJobs]);

  // Auto-refresh if any job is still processing
  useEffect(() => {
    const hasProcessing = jobs.some((j) => j.status === 'processing');
    if (!hasProcessing) return;
    const interval = setInterval(fetchJobs, 5000);
    return () => clearInterval(interval);
  }, [jobs, fetchJobs]);

  // Auto-refresh watcher status while scanning or importing (every 3s)
  const watcherActiveRef = useRef(false);
  watcherActiveRef.current = !!(watcherStatus?.scanning || watcherStatus?.importing);
  useEffect(() => {
    if (!watcherActiveRef.current) return;
    const interval = setInterval(async () => {
      try {
        const resp = await api.get('/watcher/status');
        setWatcherStatus(resp.data);
        // If import just finished, also refresh jobs list
        if (!resp.data.scanning && !resp.data.importing) {
          fetchJobs();
        }
      } catch { /* ignore */ }
    }, 3000);
    return () => clearInterval(interval);
  }, [watcherStatus?.scanning, watcherStatus?.importing, fetchJobs]);

  const uploadProps: UploadProps = {
    name: 'file',
    accept: '.csv',
    showUploadList: false,
    customRequest: async (options) => {
      const { file, onSuccess, onError } = options;
      setUploading(true);
      const formData = new FormData();
      formData.append('file', file as Blob);
      try {
        const token = localStorage.getItem('access_token');
        const resp = await fetch('/api/imports/upload', {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        });
        if (!resp.ok) {
          const err = await resp.json();
          throw new Error(err.detail || 'Upload failed');
        }
        const data = await resp.json();
        message.success(data.message || t('admin.import.importStarted'));
        onSuccess?.(data);
        fetchJobs();
      } catch (err: any) {
        notification.error({
          message: t('admin.import.importError'),
          description: err.message || t('admin.import.updateError'),
          duration: 0,
        });
        onError?.(err);
      } finally {
        setUploading(false);
      }
    },
  };

  const handleDeleteReport = async (reportId: number) => {
    try {
      await api.delete(`/imports/report/${reportId}`);
      message.success(t('admin.import.reportDeleted'));
      fetchJobs();
    } catch (err: any) {
      const detail = err.response?.data?.detail || t('admin.import.deleteError');
      message.error(detail);
    }
  };

  const handleResetAll = async () => {
    try {
      await api.delete('/imports/reset-all');
      message.success(t('admin.import.dbReset'));
      setResetModalOpen(false);
      setResetConfirmText('');
      fetchJobs();
    } catch (err: any) {
      const detail = err.response?.data?.detail || t('common.error');
      message.error(detail);
    }
  };

  // --- Watch paths columns ---

  const wpColumns: ColumnsType<WatchPath> = [
    {
      title: t('admin.import.path'),
      dataIndex: 'path',
      width: '40%',
      ellipsis: true,
      render: (p: string) => (
        <Space>
          <FolderOpenOutlined />
          <Text copyable style={{ fontFamily: 'monospace', fontSize: 12 }}>{p}</Text>
        </Space>
      ),
    },
    {
      title: 'Pattern',
      dataIndex: 'pattern',
      width: 150,
      render: (p: string) => <Text code>{p}</Text>,
    },
    {
      title: t('admin.import.recursive'),
      dataIndex: 'recursive',
      width: 90,
      align: 'center',
      render: (r: boolean) => (r ? <Tag color="blue">{t('common.yes')}</Tag> : <Tag>{t('common.no')}</Tag>),
    },
    {
      title: t('admin.import.ignoreBefore'),
      dataIndex: 'ignore_before',
      width: 130,
      render: (dt: string | null) => {
        if (!dt) return '\u2014';
        try {
          return new Date(dt).toLocaleDateString();
        } catch {
          return dt;
        }
      },
    },
    {
      title: t('admin.import.active'),
      dataIndex: 'enabled',
      width: 80,
      align: 'center',
      render: (enabled: boolean, record: WatchPath) => (
        <Switch
          checked={enabled}
          size="small"
          onChange={(checked) => handleToggleWp(record, checked)}
        />
      ),
    },
    {
      title: t('common.actions'),
      key: 'actions',
      width: 100,
      render: (_: unknown, record: WatchPath) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEditWp(record)}
          />
          <Popconfirm
            title={t('admin.import.deleteWatchedDir')}
            onConfirm={() => handleDeleteWp(record.id)}
            okText={t('common.delete')}
            okType="danger"
            cancelText={t('common.cancel')}
          >
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // --- Import jobs columns ---

  const columns: ColumnsType<ImportJob> = [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 60,
    },
    {
      title: t('admin.import.file'),
      dataIndex: 'filename',
      ellipsis: true,
    },
    {
      title: t('admin.import.source'),
      dataIndex: 'source',
      width: 90,
      render: (s: string) => (
        <Tag color={s === 'auto' ? 'blue' : 'green'}>{s === 'auto' ? t('admin.import.sourceAuto') : t('admin.import.sourceManual')}</Tag>
      ),
    },
    {
      title: t('admin.import.reportDate'),
      dataIndex: 'report_date',
      width: 130,
      render: (dt: string | null) => {
        if (!dt) return '—';
        try {
          return new Date(dt).toLocaleDateString();
        } catch {
          return dt;
        }
      },
    },
    {
      title: t('common.status'),
      dataIndex: 'status',
      width: 120,
      render: (status: string) => {
        const cfg = STATUS_TAG[status] || STATUS_TAG.pending;
        return (
          <Tag icon={cfg.icon} color={cfg.color}>
            {status}
          </Tag>
        );
      },
    },
    {
      title: t('admin.import.progress'),
      key: 'progress',
      width: 180,
      render: (_: unknown, record: ImportJob) => {
        if (record.status === 'done') {
          return <Text type="success">{record.rows_processed} {t('admin.import.lines')}</Text>;
        }
        if (record.status === 'error') {
          return <Text type="danger">{record.error_message || t('common.error')}</Text>;
        }
        return (
          <Progress
            percent={record.progress}
            size="small"
            format={() => `${record.rows_processed}/${record.rows_total}`}
          />
        );
      },
    },
    {
      title: t('admin.import.report'),
      dataIndex: 'scan_report_id',
      width: 80,
      render: (id: number) => `#${id}`,
    },
    {
      title: t('admin.import.importDate'),
      dataIndex: 'started_at',
      width: 170,
      render: (dt: string | null) => dt || '—',
    },
    {
      title: t('common.actions'),
      key: 'actions',
      width: 80,
      render: (_: unknown, record: ImportJob) => (
        <Popconfirm
          title={t('admin.import.deleteReport')}
          onConfirm={() => handleDeleteReport(record.scan_report_id)}
          okText={t('common.delete')}
          okType="danger"
          cancelText={t('common.cancel')}
        >
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            disabled={record.status === 'processing'}
          />
        </Popconfirm>
      ),
    },
  ];

  // --- Watcher status badge ---
  const statusBadge = watcherStatus ? (
    <Space direction="vertical" size={0} style={{ lineHeight: 1.4 }}>
      {watcherStatus.importing ? (
        <Badge
          status="warning"
          text={
            <span>
              <SyncOutlined spin style={{ color: '#fa8c16', marginRight: 4 }} />
              {t('admin.import.importInProgress')} <Text strong style={{ fontSize: 12 }}>{watcherStatus.importing}</Text>
            </span>
          }
        />
      ) : watcherStatus.scanning ? (
        <Badge
          status="processing"
          text={
            <span>
              <SyncOutlined spin style={{ color: '#1890ff', marginRight: 4 }} />
              {t('admin.import.scanInProgress')}
            </span>
          }
        />
      ) : watcherStatus.active_paths > 0 ? (
        <Badge
          status="success"
          text={
            <span>
              <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 4 }} />
              {t('admin.import.activeDirs', { count: watcherStatus.active_paths, imports: watcherStatus.import_count })}
            </span>
          }
        />
      ) : (
        <Badge status="default" text={t('admin.import.noWatchedDirStatus')} />
      )}
      {watcherStatus.last_error && (
        <Text type="danger" style={{ fontSize: 11 }}>
          {t('admin.import.lastError')} {watcherStatus.last_error}
        </Text>
      )}
    </Space>
  ) : null;

  return (
    <div>
      {/* Watch paths section */}
      <Card
        title={
          <Space>
            <EyeOutlined />
            <span>{t('admin.import.watchedDirs')}</span>
          </Space>
        }
        extra={
          <Space>
            {statusBadge}
            <Button
              type="primary"
              icon={<PlusOutlined />}
              size="small"
              onClick={openCreateWp}
            >
              {t('admin.import.addDir')}
            </Button>
          </Space>
        }
        style={{ marginBottom: 16 }}
        size="small"
      >
        <Table<WatchPath>
          dataSource={watchPaths}
          columns={wpColumns}
          rowKey="id"
          loading={wpLoading}
          size="small"
          pagination={false}
          locale={{ emptyText: t('admin.import.noWatchedDir') }}
        />
      </Card>

      {/* Import history section */}
      <Card
        title={t('admin.import.importManagement')}
        extra={
          <Space>
            <Upload {...uploadProps}>
              <Button icon={<UploadOutlined />} loading={uploading} type="primary">
                {t('admin.import.importCsv')}
              </Button>
            </Upload>
            <Button icon={<ReloadOutlined />} onClick={() => { fetchJobs(); fetchWatchPaths(); }} loading={loading}>
              {t('common.refresh')}
            </Button>
            <Button
              icon={<SyncOutlined />}
              onClick={() => {
                Modal.confirm({
                  title: t('admin.import.rescanTitle'),
                  content: t('admin.import.rescanContent'),
                  okText: t('common.confirm'),
                  onOk: async () => {
                    try {
                      await api.post('/watcher/rescan');
                      message.success(t('admin.import.rescanStarted'));
                    } catch {
                      message.error(t('common.error'));
                    }
                  },
                });
              }}
            >
              {t('admin.import.rescanSources')}
            </Button>
            <Button
              danger
              icon={<ExclamationCircleOutlined />}
              onClick={() => setResetModalOpen(true)}
            >
              {t('admin.import.resetAll')}
            </Button>
          </Space>
        }
      >
        <Table<ImportJob>
          dataSource={jobs}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="small"
          pagination={{
            current: page,
            total,
            pageSize: 15,
            showSizeChanger: false,
            onChange: setPage,
          }}
        />
      </Card>

      {/* Reset modal */}
      <Modal
        title={t('admin.import.resetTitle')}
        open={resetModalOpen}
        onCancel={() => {
          setResetModalOpen(false);
          setResetConfirmText('');
        }}
        okText={t('common.reset')}
        okType="danger"
        okButtonProps={{ disabled: resetConfirmText !== 'CONFIRMER' }}
        onOk={handleResetAll}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text type="danger" strong>
            {t('admin.import.resetWarning')}
          </Text>
          <Text>
            {t('admin.import.resetTypeConfirm').split('<1>')[0]}
            <Text code>CONFIRMER</Text>
            {t('admin.import.resetTypeConfirm').split('</1>')[1] || ''}
          </Text>
          <Input
            value={resetConfirmText}
            onChange={(e) => setResetConfirmText(e.target.value)}
            placeholder="CONFIRMER"
          />
        </Space>
      </Modal>

      {/* Watch path create/edit modal */}
      <Modal
        title={editingWp ? t('admin.import.editDir') : t('admin.import.addWatchedDir')}
        open={wpModalOpen}
        onCancel={() => {
          setWpModalOpen(false);
          setEditingWp(null);
          wpForm.resetFields();
        }}
        onOk={handleCreateOrUpdateWp}
        okText={editingWp ? t('common.save') : t('common.create')}
      >
        <Form form={wpForm} layout="vertical">
          <Form.Item
            name="path"
            label={t('admin.import.dirPath')}
            rules={[{ required: true, message: t('admin.import.dirPathRequired') }]}
          >
            <Input placeholder={t('admin.import.dirPathPlaceholder')} />
          </Form.Item>
          <Form.Item name="pattern" label={t('admin.import.filePattern')}>
            <Input placeholder="*.csv" />
          </Form.Item>
          <Form.Item name="recursive" label={t('admin.import.recursiveScan')} valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="ignore_before" label={t('admin.import.ignoreFilesBefore')}>
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="enabled" label={t('admin.import.active')} valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
