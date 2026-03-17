import { useEffect, useState, useCallback } from 'react';
import { Card, Row, Col, Spin, Alert, Tag, Progress, Statistic, List, Button, Descriptions, Typography, Modal, message } from 'antd';
import {
  CheckCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
  ReloadOutlined,
  DatabaseOutlined,
  CloudServerOutlined,
  HddOutlined,
  ClockCircleOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';
import HelpTooltip from '../components/help/HelpTooltip';

const { Text } = Typography;

interface ServiceStatus {
  name: string;
  status: string;
  detail: string | null;
}

interface SystemMetrics {
  cpu_percent: number;
  memory_percent: number;
  memory_used_mb: number;
  memory_total_mb: number;
  disk_percent: number;
  disk_used_gb: number;
  disk_total_gb: number;
}

interface DbPoolInfo {
  pool_size: number;
  checked_out: number;
  overflow: number;
  checked_in: number;
}

interface ActivitySummary {
  total_reports: number;
  total_users: number;
  db_size_mb: number;
  last_import_status: string | null;
  purgeable_reports_count: number;
}

interface AlertItem {
  level: string;
  message: string;
}

interface MonitoringData {
  uptime_seconds: number;
  platform: string;
  python_version: string;
  services: ServiceStatus[];
  system: SystemMetrics;
  db_pool: DbPoolInfo | null;
  activity: ActivitySummary;
  alerts: AlertItem[];
}

function formatUptime(seconds: number, t: (key: string) => string): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const parts = [];
  if (d > 0) parts.push(`${d}${t('monitoring.uptimeDays')}`);
  if (h > 0) parts.push(`${h}${t('monitoring.uptimeHours')}`);
  parts.push(`${m}${t('monitoring.uptimeMinutes')}`);
  return parts.join(' ');
}

function statusIcon(status: string) {
  if (status === 'ok') return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
  if (status === 'warning') return <WarningOutlined style={{ color: '#faad14' }} />;
  return <CloseCircleOutlined style={{ color: '#cf1322' }} />;
}

function metricColor(percent: number): string {
  if (percent >= 90) return '#cf1322';
  if (percent >= 75) return '#faad14';
  return '#52c41a';
}

export default function Monitoring() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const isAdmin = user?.profile === 'admin';
  const [data, setData] = useState<MonitoringData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [purging, setPurging] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get('/monitoring');
      setData(resp.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('monitoring.loadError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  const handlePurge = () => {
    if (!data || data.activity.purgeable_reports_count === 0) {
      message.info(t('monitoring.purgeNone'));
      return;
    }
    Modal.confirm({
      title: t('monitoring.purgeConfirmTitle'),
      content: t('monitoring.purgeConfirmContent', { count: data.activity.purgeable_reports_count }),
      okText: t('common.confirm'),
      okType: 'danger',
      cancelText: t('common.cancel'),
      onOk: async () => {
        try {
          setPurging(true);
          const resp = await api.post('/monitoring/purge');
          message.success(t('monitoring.purgeResult', {
            reports: resp.data.reports_deleted,
            vulns: resp.data.vulns_deleted,
          }));
          fetchData();
        } catch (err: any) {
          const detail = err.response?.data?.detail;
          if (detail === 'IMPORT_IN_PROGRESS') {
            message.error(t('monitoring.purgeImportConflict'));
          } else {
            message.error(detail || t('common.error'));
          }
        } finally {
          setPurging(false);
        }
      },
    });
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // refresh every 30s
    return () => clearInterval(interval);
  }, [fetchData]);

  if (error) return <Alert message={t('common.error')} description={error} type="error" showIcon />;
  if (!data && loading) return <Spin style={{ display: 'block', margin: '80px auto' }} size="large" />;
  if (!data) return null;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <Text type="secondary">
          <ClockCircleOutlined /> {t('monitoring.uptime')} {formatUptime(data.uptime_seconds, t)} | {data.platform} | Python {data.python_version}
        </Text>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <HelpTooltip topic="monitoring" />
          <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
            {t('common.refresh')}
          </Button>
        </div>
      </div>

      {/* Alerts */}
      {data.alerts.length > 0 && (
        <Card title={t('monitoring.alerts')} size="small" style={{ marginBottom: 16 }}>
          <List
            size="small"
            dataSource={data.alerts}
            renderItem={(alert) => (
              <List.Item>
                <Tag
                  color={alert.level === 'error' ? 'error' : 'warning'}
                  icon={alert.level === 'error' ? <CloseCircleOutlined /> : <WarningOutlined />}
                >
                  {alert.level.toUpperCase()}
                </Tag>
                {(() => {
                  const parts = alert.message.split(':');
                  const code = parts[0];
                  const value = parts.slice(1).join(':');
                  const translated = t(`errors.${code}`, { value, defaultValue: '' });
                  return translated || alert.message;
                })()}
              </List.Item>
            )}
          />
        </Card>
      )}

      <Row gutter={[16, 16]}>
        {/* Services */}
        <Col xs={24} lg={8}>
          <Card title={<><CloudServerOutlined /> {t('monitoring.services')}</>} size="small">
            <List
              size="small"
              dataSource={data.services}
              renderItem={(svc) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={statusIcon(svc.status)}
                    title={svc.name}
                    description={svc.detail}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>

        {/* System Metrics */}
        <Col xs={24} lg={8}>
          <Card title={<><HddOutlined /> {t('monitoring.systemResources')}</>} size="small">
            <div style={{ marginBottom: 16 }}>
              <Text>{t('monitoring.cpu')}</Text>
              <Progress
                percent={Math.round(data.system.cpu_percent)}
                strokeColor={metricColor(data.system.cpu_percent)}
                size="small"
              />
            </div>
            <div style={{ marginBottom: 16 }}>
              <Text>{t('monitoring.memory')} ({data.system.memory_used_mb} / {data.system.memory_total_mb} {t('monitoring.unitMb')})</Text>
              <Progress
                percent={Math.round(data.system.memory_percent)}
                strokeColor={metricColor(data.system.memory_percent)}
                size="small"
              />
            </div>
            <div>
              <Text>{t('monitoring.disk')} ({data.system.disk_used_gb} / {data.system.disk_total_gb} {t('monitoring.unitGb')})</Text>
              <Progress
                percent={Math.round(data.system.disk_percent)}
                strokeColor={metricColor(data.system.disk_percent)}
                size="small"
              />
            </div>
          </Card>
        </Col>

        {/* DB Pool */}
        <Col xs={24} lg={8}>
          <Card title={<><DatabaseOutlined /> {t('monitoring.connectionPool')}</>} size="small">
            {data.db_pool ? (
              <Descriptions column={1} size="small">
                <Descriptions.Item label={t('monitoring.poolSize')}>{data.db_pool.pool_size}</Descriptions.Item>
                <Descriptions.Item label={t('monitoring.activeConnections')}>{data.db_pool.checked_out}</Descriptions.Item>
                <Descriptions.Item label={t('monitoring.available')}>{data.db_pool.checked_in}</Descriptions.Item>
                <Descriptions.Item label={t('monitoring.overflow')}>{data.db_pool.overflow}</Descriptions.Item>
              </Descriptions>
            ) : (
              <Text type="secondary">{t('monitoring.infoUnavailable')}</Text>
            )}
          </Card>
        </Col>
      </Row>

      {/* Activity Summary */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24}>
          <Card title={t('monitoring.activity')} size="small">
            <Row gutter={16}>
              <Col xs={12} sm={6}>
                <Statistic title={t('monitoring.importedReports')} value={data.activity.total_reports} />
              </Col>
              <Col xs={12} sm={6}>
                <Statistic title={t('monitoring.users')} value={data.activity.total_users} />
              </Col>
              <Col xs={12} sm={6}>
                <Statistic
                  title={t('monitoring.dbSize')}
                  value={data.activity.db_size_mb >= 1024
                    ? `${(data.activity.db_size_mb / 1024).toFixed(1)} ${t('monitoring.unitGb')}`
                    : `${data.activity.db_size_mb} ${t('monitoring.unitMb')}`}
                />
              </Col>
              <Col xs={12} sm={6}>
                <Statistic
                  title={t('monitoring.lastImportStatus')}
                  value={data.activity.last_import_status || '—'}
                  styles={{
                    content: {
                      fontSize: 14,
                      color: data.activity.last_import_status === 'done' ? '#52c41a' : undefined,
                    },
                  }}
                />
              </Col>
            </Row>
            {isAdmin && data.activity.purgeable_reports_count > 0 && (
              <Alert
                type="info"
                showIcon
                style={{ marginTop: 16 }}
                message={t('monitoring.purgeableWarning', { count: data.activity.purgeable_reports_count })}
                action={
                  <Button
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={handlePurge}
                    loading={purging}
                  >
                    {t('monitoring.purgeButton')}
                  </Button>
                }
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
