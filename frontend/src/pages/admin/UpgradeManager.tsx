import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Card,
  Tag,
  Space,
  Button,
  Descriptions,
  Modal,
  message,
  Table,
  Tooltip,
  Progress,
  DatePicker,
  InputNumber,
  Select as AntSelect,
  Alert,
  Typography,
  Divider,
} from 'antd';
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  SyncOutlined,
  RocketOutlined,
  UploadOutlined,
  SafetyCertificateOutlined,
  CloseCircleOutlined,
  FileZipOutlined,
  CheckOutlined,
  CloseOutlined,
  DeleteOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import dayjs, { type Dayjs } from 'dayjs';
import api from '../../api/client';

const { Text } = Typography;

// ── Types ─────────────────────────────────────────────────────────────────────

interface NotificationThreshold {
  minutes_before: number;
  level: 'info' | 'warning' | 'danger';
}

interface ScheduleInfo {
  scheduled: boolean;
  status?: 'pending' | 'running' | 'completed' | 'failed' | 'rolled_back' | 'cancelled';
  target_version?: string;
  scheduled_at?: string;
  upload_id?: string;
}

interface ValidationResult {
  valid: boolean;
  signature_ok: boolean;
  version_ok: boolean;
  target_version?: string;
  current_version?: string;
  error?: string;
}

interface HistoryEntry {
  id: number;
  source_version: string;
  target_version: string;
  started_at: string;
  completed_at?: string;
  duration_seconds?: number;
  status: 'completed' | 'failed' | 'rolled_back' | 'cancelled' | 'pending' | 'running';
  initiated_by_username?: string;
  error_message?: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

const CHUNK_SIZE = 2 * 1024 * 1024; // 2 MB

async function sha256Hex(buffer: ArrayBuffer): Promise<string> {
  // crypto.subtle is only available in secure contexts (HTTPS/localhost).
  // For air-gapped HTTP deployments, fall back to a simple checksum.
  if (crypto.subtle) {
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
    return Array.from(new Uint8Array(hashBuffer))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
  }
  // Fallback: FNV-1a-like hash (not cryptographic, but server validates independently)
  const bytes = new Uint8Array(buffer);
  let h = 0x811c9dc5;
  for (let i = 0; i < bytes.length; i++) {
    h ^= bytes[i];
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16).padStart(8, '0');
}

function formatDuration(seconds: number | undefined): string {
  if (seconds == null) return '—';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m === 0) return `${s}s`;
  return `${m}m ${s}s`;
}

function getErrorCode(err: unknown): string {
  const e = err as { response?: { data?: { detail?: string } } };
  return e?.response?.data?.detail ?? 'UNKNOWN_ERROR';
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function UpgradeManager() {
  const { t } = useTranslation();

  // ── State — schedule ──────────────────────────────────────────────────────
  const [schedule, setSchedule] = useState<ScheduleInfo | null>(null);
  const [scheduleLoading, setScheduleLoading] = useState(true);
  const [cancellingSchedule, setCancellingSchedule] = useState(false);

  // ── State — history ───────────────────────────────────────────────────────
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  // ── State — upload ────────────────────────────────────────────────────────
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadPercent, setUploadPercent] = useState(0);
  const [uploadSentMB, setUploadSentMB] = useState(0);
  const [uploadTotalMB, setUploadTotalMB] = useState(0);
  const [uploadComplete, setUploadComplete] = useState(false);
  const [sigFile, setSigFile] = useState<File | null>(null);
  const [sigUploading, setSigUploading] = useState(false);
  const cancelUploadRef = useRef(false);

  // ── State — validation ────────────────────────────────────────────────────
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);

  // ── State — scheduling form ───────────────────────────────────────────────
  const [scheduledAt, setScheduledAt] = useState<Dayjs | null>(null);
  const [thresholds, setThresholds] = useState<NotificationThreshold[]>([]);
  const [scheduling, setScheduling] = useState(false);
  const [launchingNow, setLaunchingNow] = useState(false);

  // ── State — current version ──────────────────────────────────────────────
  const [currentVersion, setCurrentVersion] = useState<string>('—');

  // ── State — settings ──────────────────────────────────────────────────────
  const [defaultThresholds, setDefaultThresholds] = useState<NotificationThreshold[]>([]);
  const [savingSettings, setSavingSettings] = useState(false);

  // ── File input refs ───────────────────────────────────────────────────────
  const zipInputRef = useRef<HTMLInputElement>(null);
  const sigInputRef = useRef<HTMLInputElement>(null);

  // ── Auto-refresh when running ─────────────────────────────────────────────
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Fetch helpers ─────────────────────────────────────────────────────────

  const fetchSchedule = useCallback(async () => {
    try {
      const r = await api.get<ScheduleInfo>('/upgrade/schedule');
      setSchedule(r.data);
    } catch {
      setSchedule({ scheduled: false });
    } finally {
      setScheduleLoading(false);
    }
  }, []);

  const fetchHistory = useCallback(async () => {
    try {
      const r = await api.get<HistoryEntry[]>('/upgrade/history');
      setHistory(r.data);
    } catch {
      // silently ignore
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const fetchSettings = useCallback(async () => {
    try {
      const r = await api.get<{ default_thresholds: NotificationThreshold[] }>('/upgrade/settings');
      setDefaultThresholds(r.data.default_thresholds ?? []);
      setThresholds(r.data.default_thresholds ?? []);
    } catch {
      // silently ignore
    }
  }, []);

  const fetchVersion = useCallback(async () => {
    try {
      const r = await api.get<{ current: string }>('/version');
      if (r.data.current) {
        setCurrentVersion(r.data.current);
        return;
      }
    } catch { /* fallback below */ }
    // Fallback: try /health which also returns version
    try {
      const r = await api.get<{ version: string }>('/health');
      if (r.data.version) setCurrentVersion(r.data.version);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchVersion();
    fetchSchedule();
    fetchHistory();
    fetchSettings();
  }, [fetchVersion, fetchSchedule, fetchHistory, fetchSettings]);

  // Poll when running
  useEffect(() => {
    const isRunning = schedule?.status === 'running';
    if (isRunning && !pollIntervalRef.current) {
      pollIntervalRef.current = setInterval(() => {
        fetchSchedule();
        fetchHistory();
      }, 10_000);
    } else if (!isRunning && pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [schedule?.status, fetchSchedule, fetchHistory]);

  // ── Upload logic ──────────────────────────────────────────────────────────

  const handleZipSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.zip')) {
      message.error(t('admin.upgrade.errors.INVALID_ZIP_FILE'));
      e.target.value = '';
      return;
    }
    setUploadFile(file);
    startChunkedUpload(file);
    // Reset input so same file can be re-selected
    e.target.value = '';
  };

  const startChunkedUpload = async (file: File) => {
    const id = crypto.randomUUID();
    setUploadId(id);
    setUploading(true);
    setUploadPercent(0);
    setUploadSentMB(0);
    setUploadTotalMB(file.size / (1024 * 1024));
    setUploadComplete(false);
    setSigFile(null);
    setValidationResult(null);
    cancelUploadRef.current = false;

    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

    try {
      for (let i = 0; i < totalChunks; i++) {
        if (cancelUploadRef.current) {
          // Cancel on server
          await api.delete(`/upgrade/upload/${id}`).catch(() => {});
          setUploading(false);
          setUploadId(null);
          setUploadFile(null);
          return;
        }

        const start = i * CHUNK_SIZE;
        const end = Math.min(start + CHUNK_SIZE, file.size);
        const chunkBuffer = await file.slice(start, end).arrayBuffer();
        const checksum = await sha256Hex(chunkBuffer);

        const formData = new FormData();
        formData.append('file', new Blob([chunkBuffer]), file.name);

        await api.post('/upgrade/upload', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
            'X-Upload-Id': id,
            'X-Chunk-Index': String(i),
            'X-Chunk-Total': String(totalChunks),
            'X-Checksum': checksum,
            'X-Filename': file.name,
          },
        });

        const sent = end / (1024 * 1024);
        const percent = Math.round(((i + 1) / totalChunks) * 100);
        setUploadPercent(percent);
        setUploadSentMB(sent);
      }

      setUploading(false);
      setUploadComplete(true);
      message.success(t('admin.upgrade.uploadComplete'));
    } catch (err) {
      if (cancelUploadRef.current) return;
      setUploading(false);
      setUploadId(null);
      setUploadFile(null);
      const code = getErrorCode(err);
      message.error(t(`admin.upgrade.errors.${code}`, code));
    }
  };

  const handleCancelUpload = () => {
    cancelUploadRef.current = true;
    message.info(t('admin.upgrade.uploadCancel'));
  };

  const handleSigSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !uploadId) return;
    setSigUploading(true);
    setSigFile(file);
    try {
      const formData = new FormData();
      formData.append('file', file, file.name);
      await api.post(`/upgrade/upload-sig/${uploadId}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    } catch (err) {
      setSigFile(null);
      const code = getErrorCode(err);
      message.error(t(`admin.upgrade.errors.${code}`, code));
    } finally {
      setSigUploading(false);
      e.target.value = '';
    }
  };

  const handleValidate = async () => {
    if (!uploadId) return;
    setValidating(true);
    setValidationResult(null);
    try {
      const r = await api.post<ValidationResult>(`/upgrade/validate/${uploadId}`);
      setValidationResult(r.data);
    } catch (err) {
      const code = getErrorCode(err);
      message.error(t(`admin.upgrade.errors.${code}`, code));
    } finally {
      setValidating(false);
    }
  };

  const handleNewUpload = () => {
    if (uploadId) {
      api.delete(`/upgrade/upload/${uploadId}`).catch(() => {});
    }
    setUploadId(null);
    setUploadFile(null);
    setUploading(false);
    setUploadPercent(0);
    setUploadComplete(false);
    setSigFile(null);
    setValidationResult(null);
    setScheduledAt(null);
  };

  // ── Schedule / Launch ─────────────────────────────────────────────────────

  const handleSchedule = async () => {
    if (!scheduledAt) return;
    setScheduling(true);
    try {
      await api.post('/upgrade/schedule', {
        scheduled_at: scheduledAt.toISOString(),
        notification_thresholds: thresholds,
      });
      message.success(t('admin.upgrade.scheduleCreated'));
      fetchSchedule();
      // Reset upload zone
      handleNewUpload();
    } catch (err) {
      const code = getErrorCode(err);
      message.error(t(`admin.upgrade.errors.${code}`, code));
    } finally {
      setScheduling(false);
    }
  };

  const handleLaunchNow = () => {
    Modal.confirm({
      title: t('admin.upgrade.launchNowTitle'),
      icon: <RocketOutlined style={{ color: '#ff4d4f' }} />,
      content: t('admin.upgrade.launchNowConfirm'),
      okType: 'danger',
      okText: t('admin.upgrade.launchNow'),
      onOk: async () => {
        setLaunchingNow(true);
        try {
          await api.post('/upgrade/launch-now');
          message.success(t('admin.upgrade.scheduleCreated'));
          fetchSchedule();
          handleNewUpload();
        } catch (err) {
          const code = getErrorCode(err);
          message.error(t(`admin.upgrade.errors.${code}`, code));
        } finally {
          setLaunchingNow(false);
        }
      },
    });
  };

  const handleCancelSchedule = async () => {
    setCancellingSchedule(true);
    try {
      await api.delete('/upgrade/schedule');
      message.success(t('admin.upgrade.scheduleCancelled'));
      fetchSchedule();
    } catch (err) {
      const code = getErrorCode(err);
      message.error(t(`admin.upgrade.errors.${code}`, code));
    } finally {
      setCancellingSchedule(false);
    }
  };

  const handleResetState = async () => {
    try {
      const resp = await api.post('/upgrade/reset-state');
      message.success(t('admin.upgrade.stateReset', { count: resp.data.reset_count }));
      fetchSchedule();
      fetchHistory();
    } catch (err) {
      const code = getErrorCode(err);
      message.error(t(`admin.upgrade.errors.${code}`, code));
    }
  };

  // ── Settings ──────────────────────────────────────────────────────────────

  const handleSaveSettings = async () => {
    setSavingSettings(true);
    try {
      await api.put('/upgrade/settings', { default_thresholds: defaultThresholds });
      message.success(t('admin.upgrade.settingsSaved'));
    } catch (err) {
      const code = getErrorCode(err);
      message.error(t(`admin.upgrade.errors.${code}`, code));
    } finally {
      setSavingSettings(false);
    }
  };

  // ── Threshold helpers ─────────────────────────────────────────────────────

  const addThreshold = (
    list: NotificationThreshold[],
    setList: React.Dispatch<React.SetStateAction<NotificationThreshold[]>>
  ) => {
    setList([...list, { minutes_before: 30, level: 'info' }]);
  };

  const removeThreshold = (
    idx: number,
    list: NotificationThreshold[],
    setList: React.Dispatch<React.SetStateAction<NotificationThreshold[]>>
  ) => {
    setList(list.filter((_, i) => i !== idx));
  };

  const updateThreshold = (
    idx: number,
    field: keyof NotificationThreshold,
    value: number | string,
    list: NotificationThreshold[],
    setList: React.Dispatch<React.SetStateAction<NotificationThreshold[]>>
  ) => {
    setList(list.map((item, i) => (i === idx ? { ...item, [field]: value } : item)));
  };

  // ── Derived booleans ──────────────────────────────────────────────────────

  const isRunning = schedule?.status === 'running';
  const isPending = schedule?.scheduled && schedule?.status === 'pending';
  const hasActiveSchedule = isRunning || isPending;
  const validationPassed =
    validationResult?.valid &&
    validationResult?.signature_ok &&
    validationResult?.version_ok;

  // ── Render helpers ────────────────────────────────────────────────────────

  const renderScheduleStateTag = () => {
    if (isRunning)
      return (
        <Tag icon={<SyncOutlined spin />} color="processing">
          {t('admin.upgrade.statusRunning')}
        </Tag>
      );
    if (isPending)
      return (
        <Tag icon={<ClockCircleOutlined />} color="warning">
          {t('admin.upgrade.statusScheduled')}
        </Tag>
      );
    return (
      <Tag icon={<CheckCircleOutlined />} color="success">
        {t('admin.upgrade.statusUpToDate')}
      </Tag>
    );
  };

  const lastUpgrade = history.find((h) => h.status === 'completed');

  const levelOptions: { value: NotificationThreshold['level']; label: string }[] = [
    { value: 'info', label: t('admin.upgrade.levelInfo') },
    { value: 'warning', label: t('admin.upgrade.levelWarning') },
    { value: 'danger', label: t('admin.upgrade.levelDanger') },
  ];

  const renderThresholdList = (
    list: NotificationThreshold[],
    setList: React.Dispatch<React.SetStateAction<NotificationThreshold[]>>
  ) => (
    <Space direction="vertical" style={{ width: '100%' }} size={8}>
      {list.map((thr, idx) => (
        <Space key={idx} wrap>
          <InputNumber
            min={1}
            max={10080}
            value={thr.minutes_before}
            onChange={(v) => updateThreshold(idx, 'minutes_before', v ?? 30, list, setList)}
            addonAfter={t('admin.upgrade.minutesBefore')}
            style={{ width: 220 }}
          />
          <AntSelect
            value={thr.level}
            onChange={(v) => updateThreshold(idx, 'level', v, list, setList)}
            style={{ width: 140 }}
            options={levelOptions}
          />
          <Button
            icon={<DeleteOutlined />}
            danger
            size="small"
            onClick={() => removeThreshold(idx, list, setList)}
          >
            {t('admin.upgrade.removeThreshold')}
          </Button>
        </Space>
      ))}
      <Button
        icon={<PlusOutlined />}
        size="small"
        onClick={() => addThreshold(list, setList)}
      >
        {t('admin.upgrade.addThreshold')}
      </Button>
    </Space>
  );

  // ── History table columns ─────────────────────────────────────────────────

  const statusTagMap: Record<string, { color: string; label: string }> = {
    completed: { color: 'success', label: t('admin.upgrade.statusCompleted') },
    failed: { color: 'error', label: t('admin.upgrade.statusFailed') },
    rolled_back: { color: 'warning', label: t('admin.upgrade.statusRolledBack') },
    cancelled: { color: 'default', label: t('admin.upgrade.statusCancelled') },
    pending: { color: 'blue', label: t('admin.upgrade.statusPending') },
    running: { color: 'processing', label: t('admin.upgrade.statusRunning') },
  };

  const historyColumns = [
    {
      title: t('admin.upgrade.historyDate'),
      dataIndex: 'started_at',
      key: 'started_at',
      render: (v: string) => dayjs(v).format('DD/MM/YYYY HH:mm'),
      sorter: (a: HistoryEntry, b: HistoryEntry) =>
        dayjs(a.started_at).unix() - dayjs(b.started_at).unix(),
      defaultSortOrder: 'descend' as const,
    },
    {
      title: t('admin.upgrade.historySourceVersion'),
      dataIndex: 'source_version',
      key: 'source_version',
    },
    {
      title: t('admin.upgrade.historyTargetVersion'),
      dataIndex: 'target_version',
      key: 'target_version',
    },
    {
      title: t('admin.upgrade.historyDuration'),
      dataIndex: 'duration_seconds',
      key: 'duration_seconds',
      render: (v: number | undefined) => formatDuration(v),
    },
    {
      title: t('admin.upgrade.historyStatus'),
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => {
        const info = statusTagMap[v];
        if (!info) return <Tag>{v}</Tag>;
        if (v === 'running')
          return (
            <Tag icon={<SyncOutlined spin />} color="processing">
              {info.label}
            </Tag>
          );
        return <Tag color={info.color}>{info.label}</Tag>;
      },
    },
    {
      title: t('admin.upgrade.historyInitiatedBy'),
      dataIndex: 'initiated_by_username',
      key: 'initiated_by_username',
      render: (v: string | undefined) => v ?? '—',
    },
    {
      title: t('admin.upgrade.historyError'),
      dataIndex: 'error_message',
      key: 'error_message',
      render: (v: string | undefined) =>
        v ? (
          <Tooltip title={v}>
            <Tag color="error" style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {v}
            </Tag>
          </Tooltip>
        ) : (
          '—'
        ),
    },
  ];

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div>
      {/* Hidden file inputs */}
      <input
        ref={zipInputRef}
        type="file"
        accept=".zip"
        style={{ display: 'none' }}
        onChange={handleZipSelect}
      />
      <input
        ref={sigInputRef}
        type="file"
        accept=".sig"
        style={{ display: 'none' }}
        onChange={handleSigSelect}
      />

      {/* ── Zone 1 — Current State ────────────────────────────────────────── */}
      <Card title={t('admin.upgrade.currentState')} loading={scheduleLoading}>
        <Descriptions bordered column={2} size="small">
          <Descriptions.Item label={t('admin.upgrade.currentVersion')}>
            <Tag color="blue">{currentVersion}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label={t('admin.upgrade.lastUpgrade')}>
            {lastUpgrade
              ? `${dayjs(lastUpgrade.started_at).format('DD/MM/YYYY HH:mm')} (v${lastUpgrade.target_version})`
              : '—'}
          </Descriptions.Item>
          <Descriptions.Item label={t('admin.upgrade.historyStatus')} span={2}>
            <Space size="middle" align="center">
              {renderScheduleStateTag()}
              {isPending && schedule && (
                <>
                  <Text>
                    {t('admin.upgrade.scheduledFor', {
                      date: dayjs(schedule.scheduled_at).format('DD/MM/YYYY'),
                      time: dayjs(schedule.scheduled_at).format('HH:mm'),
                    })}
                  </Text>
                  <Button
                    danger
                    size="small"
                    icon={<CloseCircleOutlined />}
                    loading={cancellingSchedule}
                    onClick={handleCancelSchedule}
                  >
                    {t('admin.upgrade.cancelSchedule')}
                  </Button>
                  <Button
                    type="primary"
                    size="small"
                    icon={<RocketOutlined />}
                    loading={launchingNow}
                    onClick={handleLaunchNow}
                  >
                    {t('admin.upgrade.launchNowBtn')}
                  </Button>
                </>
              )}
              {isRunning && schedule && (
                <>
                  <Text>
                    {t('admin.upgrade.targetVersion')}: <Tag color="blue">{schedule.target_version}</Tag>
                  </Text>
                  <Button
                    danger
                    size="small"
                    onClick={() => {
                      Modal.confirm({
                        title: t('admin.upgrade.resetStateConfirmTitle'),
                        content: t('admin.upgrade.resetStateConfirmContent'),
                        okText: t('common.confirm'),
                        okType: 'danger',
                        onOk: handleResetState,
                      });
                    }}
                  >
                    {t('admin.upgrade.resetState')}
                  </Button>
                </>
              )}
            </Space>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* ── Zone 2 — Upload & Schedule ───────────────────────────────────── */}
      <Card title={t('admin.upgrade.uploadAndSchedule')} style={{ marginTop: 16 }}>
        {hasActiveSchedule ? (
          <Alert
            type={isRunning ? 'warning' : 'info'}
            icon={isRunning ? <SyncOutlined spin /> : <ClockCircleOutlined />}
            showIcon
            message={isRunning ? t('admin.upgrade.statusRunning') : t('admin.upgrade.statusScheduled')}
          />
        ) : (
          <>
            {/* ── Step 1 & 2: Upload .zip ─────────────────────────────── */}
            {!uploadComplete && !uploading && (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Button
                  type="primary"
                  icon={<UploadOutlined />}
                  onClick={() => zipInputRef.current?.click()}
                >
                  {t('admin.upgrade.selectPackage')}
                </Button>
              </Space>
            )}

            {uploading && (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Text>{t('admin.upgrade.uploading')}</Text>
                <Progress percent={uploadPercent} status="active" />
                <Text type="secondary">
                  {t('admin.upgrade.uploadProgress', {
                    percent: uploadPercent,
                    sent: uploadSentMB.toFixed(1),
                    total: uploadTotalMB.toFixed(1),
                  })}
                </Text>
                <Button
                  danger
                  icon={<CloseOutlined />}
                  onClick={handleCancelUpload}
                >
                  {t('admin.upgrade.uploadCancel')}
                </Button>
              </Space>
            )}

            {/* ── Step 3: Upload complete — .sig + Validate ──────────── */}
            {uploadComplete && !validationResult && (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Space wrap>
                  <Tag icon={<FileZipOutlined />} color="success">
                    {uploadFile?.name}
                  </Tag>
                  {sigFile ? (
                    <Tag icon={<SafetyCertificateOutlined />} color="success">
                      {sigFile.name}
                    </Tag>
                  ) : (
                    <Button
                      icon={<SafetyCertificateOutlined />}
                      loading={sigUploading}
                      onClick={() => sigInputRef.current?.click()}
                    >
                      {t('admin.upgrade.selectSignature')}
                    </Button>
                  )}
                </Space>

                <Space>
                  <Button
                    type="primary"
                    icon={<CheckOutlined />}
                    loading={validating}
                    disabled={!sigFile}
                    onClick={handleValidate}
                  >
                    {validating ? t('admin.upgrade.validating') : t('admin.upgrade.validate')}
                  </Button>
                  <Button icon={<CloseOutlined />} onClick={handleNewUpload}>
                    {t('admin.upgrade.newUpload')}
                  </Button>
                </Space>
              </Space>
            )}

            {/* ── Step 4: Validation failed ──────────────────────────── */}
            {validationResult && !validationPassed && (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Text strong>{t('admin.upgrade.validationResult')}</Text>
                <Space wrap>
                  <Tag
                    icon={validationResult.valid ? <CheckOutlined /> : <CloseOutlined />}
                    color={validationResult.valid ? 'success' : 'error'}
                  >
                    {validationResult.valid ? t('admin.upgrade.zipOk') : t('admin.upgrade.zipFail')}
                  </Tag>
                  <Tag
                    icon={validationResult.signature_ok ? <CheckOutlined /> : <CloseOutlined />}
                    color={validationResult.signature_ok ? 'success' : 'error'}
                  >
                    {validationResult.signature_ok
                      ? t('admin.upgrade.signatureOk')
                      : t('admin.upgrade.signatureFail')}
                  </Tag>
                  <Tag
                    icon={validationResult.version_ok ? <CheckOutlined /> : <CloseOutlined />}
                    color={validationResult.version_ok ? 'success' : 'error'}
                  >
                    {validationResult.version_ok
                      ? t('admin.upgrade.versionOk')
                      : t('admin.upgrade.versionFail')}
                  </Tag>
                </Space>
                <Button icon={<UploadOutlined />} onClick={handleNewUpload}>
                  {t('admin.upgrade.newUpload')}
                </Button>
              </Space>
            )}

            {/* ── Step 5: Validation passed — Schedule form ─────────── */}
            {validationResult && validationPassed && (
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                {/* Summary */}
                <Space wrap>
                  <Tag icon={<CheckCircleOutlined />} color="success">
                    {t('admin.upgrade.packageReady')}
                  </Tag>
                  <Text>
                    {t('admin.upgrade.targetVersion')}:{' '}
                    <Tag color="blue">{validationResult.target_version}</Tag>
                  </Text>
                </Space>

                <Divider style={{ margin: '0 0 8px' }} />

                {/* Date picker */}
                <div>
                  <Text strong>{t('admin.upgrade.scheduledAt')}</Text>
                  <div style={{ marginTop: 8 }}>
                    <DatePicker
                      showTime
                      format="DD/MM/YYYY HH:mm"
                      value={scheduledAt}
                      onChange={setScheduledAt}
                      disabledDate={(d) => d.isBefore(dayjs().add(15, 'minute'), 'minute')}
                      style={{ width: 280 }}
                    />
                  </div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {t('admin.upgrade.scheduleMinTime')}
                  </Text>
                </div>

                {/* Notification thresholds */}
                <div>
                  <Text strong>{t('admin.upgrade.notificationThresholds')}</Text>
                  <div style={{ marginTop: 8 }}>
                    {renderThresholdList(thresholds, setThresholds)}
                  </div>
                </div>

                {/* Action buttons */}
                <Space wrap>
                  <Button
                    type="primary"
                    icon={<ClockCircleOutlined />}
                    loading={scheduling}
                    disabled={!scheduledAt}
                    onClick={handleSchedule}
                  >
                    {t('admin.upgrade.schedule')}
                  </Button>
                  <Button
                    type="default"
                    danger
                    icon={<RocketOutlined />}
                    loading={launchingNow}
                    onClick={handleLaunchNow}
                  >
                    {t('admin.upgrade.launchNow')}
                  </Button>
                  <Button icon={<CloseOutlined />} onClick={handleNewUpload}>
                    {t('admin.upgrade.newUpload')}
                  </Button>
                </Space>
              </Space>
            )}
          </>
        )}
      </Card>

      {/* ── Zone 3 — History ─────────────────────────────────────────────── */}
      <Card title={t('admin.upgrade.history')} style={{ marginTop: 16 }}>
        <Table<HistoryEntry>
          dataSource={history}
          columns={historyColumns}
          rowKey="id"
          loading={historyLoading}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          locale={{ emptyText: t('admin.upgrade.noHistory') }}
          size="small"
        />
      </Card>

      {/* ── Zone 4 — Default notification settings ───────────────────────── */}
      <Card title={t('admin.upgrade.settings')} style={{ marginTop: 16 }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Text strong>{t('admin.upgrade.defaultThresholds')}</Text>
          {renderThresholdList(defaultThresholds, setDefaultThresholds)}
          <Button type="primary" loading={savingSettings} onClick={handleSaveSettings}>
            {t('common.save')}
          </Button>
        </Space>
      </Card>
    </div>
  );
}
