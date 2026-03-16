import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Card, Descriptions, Divider, Tag, Row, Col, Spin, Alert, Typography } from 'antd';
import { ArrowLeftOutlined, CloseCircleOutlined, DownloadOutlined, PlusOutlined, BulbOutlined } from '@ant-design/icons';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry, type ColDef } from 'ag-grid-community';
import { useTranslation } from 'react-i18next';
import api from '../api/client';
import { exportToCsv } from '../utils/csvExport';
import PdfExportButton from '../components/PdfExportButton';
import { PdfReport } from '../utils/pdfExport';
import { getLogoDataUrl } from '../utils/pdfLogo';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import RuleCreateModal from '../components/RuleCreateModal';
import ProposeRuleModal from '../components/ProposeRuleModal';
import { themeQuartz } from 'ag-grid-community';

ModuleRegistry.registerModules([AllCommunityModule]);

const { Text, Paragraph } = Typography;

const SEVERITY_COLOR: Record<number, string> = {
  5: 'red', 4: 'orange', 3: 'gold', 2: 'blue', 1: 'green',
};

const TRACKING_COLORS = ['#1677ff', '#52c41a', '#faad14', '#cf1322', '#722ed1', '#8c8c8c'];

interface VulnInfo {
  qid: number;
  title: string;
  severity: number;
  type: string | null;
  category: string | null;
  cvss_base: string | null;
  cvss_temporal: string | null;
  cvss3_base: string | null;
  cvss3_temporal: string | null;
  bugtraq_id: string | null;
  threat: string | null;
  impact: string | null;
  solution: string | null;
  vendor_reference: string | null;
  cve_ids: string[] | null;
  affected_host_count: number;
  total_occurrences: number;
  layer_id: number | null;
  layer_name: string | null;
}

interface HostRow {
  ip: string;
  dns: string | null;
  os: string | null;
  port: number | null;
  protocol: string | null;
  vuln_status: string | null;
  first_detected: string | null;
  last_detected: string | null;
}

export default function VulnDetail() {
  const { t } = useTranslation();
  const { qid } = useParams<{ qid: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { tokens } = useTheme();
  const isAdmin = user?.profile === 'admin';
  const [info, setInfo] = useState<VulnInfo | null>(null);
  const [hosts, setHosts] = useState<HostRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const trackingChartRef = useRef<HTMLDivElement>(null);

  // Rule creation modal (admin only)
  const [ruleModalOpen, setRuleModalOpen] = useState(false);
  // Propose modal (non-admin)
  const [proposeModalOpen, setProposeModalOpen] = useState(false);

  const sevLabel = (n: number) => t(`severity.${n}`);
  const NA = <Text type="secondary">{t('common.notApplicable')}</Text>;

  useEffect(() => {
    if (!qid) return;
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [infoResp, hostsResp] = await Promise.all([
          api.get(`/vulnerabilities/${qid}`),
          api.get(`/vulnerabilities/${qid}/hosts?page_size=500`),
        ]);
        if (!cancelled) {
          setInfo(infoResp.data);
          setHosts(hostsResp.data.items);
        }
      } catch (err: any) {
        if (!cancelled) setError(err.response?.data?.detail || t('vulnList.loadError'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [qid]);

  // Reload data after rule creation + reclassify
  const handleRuleCreated = () => {
    setRuleModalOpen(false);
    // Reload vuln data to pick up new layer assignment after reclassify
    const reload = async () => {
      try {
        const [infoResp, hostsResp] = await Promise.all([
          api.get(`/vulnerabilities/${qid}`),
          api.get(`/vulnerabilities/${qid}/hosts?page_size=500`),
        ]);
        setInfo(infoResp.data);
        setHosts(hostsResp.data.items);
      } catch { /* ignore — data will refresh on next navigation */ }
    };
    // Small delay to let reclassify start processing
    setTimeout(reload, 2000);
  };

  if (loading) return <Spin style={{ display: 'block', margin: '80px auto' }} size="large" />;
  if (error) return <Alert message={t('common.error')} description={error} type="error" showIcon />;
  if (!info) return null;

  const tagColor = SEVERITY_COLOR[info.severity];
  const tagLabel = sevLabel(info.severity);

  // Tracking method distribution from hosts
  const unknownLabel = t('vulnDetail.unknown');
  const trackingMap: Record<string, number> = {};
  hosts.forEach((h) => {
    const key = h.vuln_status || unknownLabel;
    trackingMap[key] = (trackingMap[key] || 0) + 1;
  });
  const trackingData = Object.entries(trackingMap).map(([name, value]) => ({ name, value }));

  // Filter hosts by selected pie slice
  const filteredHosts = statusFilter
    ? hosts.filter((h) => (h.vuln_status || unknownLabel) === statusFilter)
    : hosts;

  const hostCols: ColDef<HostRow>[] = [
    { field: 'ip', headerName: t('hostList.ip'), width: 140 },
    { field: 'dns', headerName: t('hostList.dns'), flex: 1, minWidth: 180 },
    { field: 'os', headerName: t('hostList.os'), flex: 1, minWidth: 150 },
    { field: 'port', headerName: t('vulnDetail.port'), width: 80 },
    { field: 'protocol', headerName: t('vulnDetail.protocol'), width: 80 },
    { field: 'vuln_status', headerName: t('common.status'), width: 120 },
    { field: 'last_detected', headerName: t('vulnDetail.lastDetected'), width: 160 },
  ];

  const tableTitle = statusFilter
    ? (
      <span>
        {t('vulnDetail.affectedServers')} — {t('vulnDetail.filter')} <Tag color="blue" closable onClose={() => setStatusFilter(null)}>{statusFilter}</Tag>
      </span>
    )
    : t('vulnDetail.affectedServers');

  const handlePdfExport = async () => {
    const logo = await getLogoDataUrl();
    const pdf = new PdfReport(`QID ${info.qid} — ${info.title}`, logo);

    pdf.addDescriptions([
      { label: 'QID', value: String(info.qid) },
      { label: t('filters.severity'), value: tagLabel },
      { label: t('common.type'), value: info.type || '—' },
      { label: t('common.category'), value: info.category || '—' },
      { label: t('filters.categorization'), value: info.layer_name || '—' },
      { label: t('vulnDetail.hostsAffected'), value: String(info.affected_host_count) },
      { label: t('vulnDetail.totalOccurrences'), value: String(info.total_occurrences) },
      { label: 'CVSS Base', value: info.cvss_base || '—' },
      { label: 'CVSS Temporal', value: info.cvss_temporal || '—' },
      { label: 'CVSS3 Base', value: info.cvss3_base || '—' },
      { label: 'CVSS3 Temporal', value: info.cvss3_temporal || '—' },
      { label: t('vulnDetail.vendorRef'), value: info.vendor_reference || '—' },
      { label: 'Bugtraq ID', value: info.bugtraq_id || '—' },
      { label: 'CVE', value: info.cve_ids?.join(', ') || '—' },
    ]);

    pdf.addTextBlock(t('vulnDetail.threat'), info.threat);
    pdf.addTextBlock(t('vulnDetail.impact'), info.impact);
    pdf.addTextBlock(t('vulnDetail.solution'), info.solution);

    await pdf.addChartCapture(trackingChartRef.current);

    pdf.addSectionTitle(t('vulnDetail.affectedServers'));
    pdf.addTable(
      [
        { header: t('hostList.ip'), dataKey: 'ip' },
        { header: t('hostList.dns'), dataKey: 'dns' },
        { header: t('hostList.os'), dataKey: 'os' },
        { header: t('vulnDetail.port'), dataKey: 'port' },
        { header: t('vulnDetail.protocol'), dataKey: 'protocol' },
        { header: t('common.status'), dataKey: 'vuln_status' },
        { header: t('vulnDetail.lastDetected'), dataKey: 'last_detected' },
      ],
      filteredHosts,
    );

    pdf.save(`vuln-${info.qid}.pdf`);
  };

  return (
    <div>
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Button icon={<ArrowLeftOutlined />} type="link" onClick={() => navigate(-1)} style={{ padding: 0 }}>
          {t('common.back')}
        </Button>
        <PdfExportButton onExport={handlePdfExport} />
      </div>

      {/* Bandeau orange — fiche QID globale */}
      <div style={{
        background: tokens.bannerOrangeBg,
        border: `1px solid ${tokens.bannerOrangeBorder}`,
        borderRadius: 8,
        padding: '12px 20px',
        marginBottom: 16,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        flexWrap: 'wrap',
      }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          QID {info.qid} — {info.title}
        </Typography.Title>
        {tagColor && <Tag color={tagColor}>{tagLabel}</Tag>}
      </div>

      <Card style={{ marginBottom: 16 }}>
        <Descriptions column={{ xs: 1, sm: 2, lg: 3 }} size="small" bordered>
          <Descriptions.Item label="QID">{info.qid}</Descriptions.Item>
          <Descriptions.Item label={t('common.type')}>{info.type || '—'}</Descriptions.Item>
          <Descriptions.Item label={t('common.category')}>{info.category || '—'}</Descriptions.Item>

          <Descriptions.Item label={t('filters.categorization')}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              {info.layer_name || t('common.uncategorized')}
              {isAdmin && (
                <Button
                  size="small"
                  type="link"
                  icon={<PlusOutlined />}
                  onClick={() => setRuleModalOpen(true)}
                  style={{ padding: 0 }}
                >
                  {t('vulnDetail.createRule')}
                </Button>
              )}
              {!info.layer_id && (
                <Button
                  size="small"
                  type="link"
                  icon={<BulbOutlined />}
                  onClick={() => setProposeModalOpen(true)}
                  style={{ padding: 0 }}
                >
                  {t('proposals.propose')}
                </Button>
              )}
            </span>
          </Descriptions.Item>
          <Descriptions.Item label={t('common.status')}>{NA}</Descriptions.Item>
          <Descriptions.Item label={t('vulnDetail.port')}>{NA}</Descriptions.Item>

          <Descriptions.Item label={t('vulnDetail.protocol')}>{NA}</Descriptions.Item>
          <Descriptions.Item label={t('fullDetail.fqdn')}>{NA}</Descriptions.Item>
          <Descriptions.Item label={t('fullDetail.ssl')}>{NA}</Descriptions.Item>

          <Descriptions.Item label={t('vulnDetail.trackingMethod')}>{NA}</Descriptions.Item>
          <Descriptions.Item label={t('vulnDetail.hostsAffected')}>{info.affected_host_count}</Descriptions.Item>
          <Descriptions.Item label={t('vulnDetail.totalOccurrences')}>{info.total_occurrences}</Descriptions.Item>

          <Divider />

          <Descriptions.Item label={t('vulnDetail.firstDetected')}>{NA}</Descriptions.Item>
          <Descriptions.Item label={t('vulnDetail.lastDetected')}>{NA}</Descriptions.Item>
          <Descriptions.Item label={t('vulnDetail.timesDetected')}>{NA}</Descriptions.Item>

          <Descriptions.Item label={t('vulnDetail.lastFixed')}>{NA}</Descriptions.Item>
          <Descriptions.Item label={t('fullDetail.ticket')}>{NA}</Descriptions.Item>
          <Descriptions.Item label={t('fullDetail.pciVuln')}>{NA}</Descriptions.Item>

          <Divider />

          <Descriptions.Item label="CVSS Base">{info.cvss_base || '—'}</Descriptions.Item>
          <Descriptions.Item label="CVSS Temporal">{info.cvss_temporal || '—'}</Descriptions.Item>
          <Descriptions.Item label="CVSS3 Base">{info.cvss3_base || '—'}</Descriptions.Item>

          <Descriptions.Item label="CVSS3 Temporal">{info.cvss3_temporal || '—'}</Descriptions.Item>
          <Descriptions.Item label={t('vulnDetail.vendorRef')}>{info.vendor_reference || '—'}</Descriptions.Item>
          <Descriptions.Item label="Bugtraq ID">{info.bugtraq_id || '—'}</Descriptions.Item>

          <Descriptions.Item label="CVE" span={3}>
            {info.cve_ids?.length ? info.cve_ids.map((cve) => <Tag key={cve}>{cve}</Tag>) : '—'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {info.threat && (
          <Col xs={24} lg={8}>
            <Card title={t('vulnDetail.threat')} size="small">
              <Paragraph style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{info.threat}</Paragraph>
            </Card>
          </Col>
        )}
        {info.impact && (
          <Col xs={24} lg={8}>
            <Card title={t('vulnDetail.impact')} size="small">
              <Paragraph style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{info.impact}</Paragraph>
            </Card>
          </Col>
        )}
        {info.solution && (
          <Col xs={24} lg={8}>
            <Card title={t('vulnDetail.solution')} size="small">
              <Paragraph style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{info.solution}</Paragraph>
            </Card>
          </Col>
        )}
      </Row>

      <Card title={t('vulnDetail.scanResults')} size="small" style={{ marginBottom: 16 }}>
        <Paragraph style={{ whiteSpace: 'pre-wrap', margin: 0 }}>
          {NA}
        </Paragraph>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={16}>
          <Card
            title={tableTitle}
            size="small"
            extra={
              <Button
                icon={<DownloadOutlined />}
                size="small"
                onClick={() => exportToCsv(hostCols, filteredHosts, `serveurs-qid-${qid}.csv`)}
              >
                CSV
              </Button>
            }
          >
            <div style={{ height: 360 }}>
              <AgGridReact<HostRow>
                theme={themeQuartz.withParams({ colorScheme: tokens.agGridColorScheme })}
                rowData={filteredHosts}
                columnDefs={hostCols}
                domLayout="normal"
                rowHeight={36}
                headerHeight={38}
                onRowClicked={(e) => {
                  if (e.data) navigate(`/hosts/${e.data.ip}`);
                }}
                rowStyle={{ cursor: 'pointer' }}
              />
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          {trackingData.length > 0 && (
            <div ref={trackingChartRef}>
            <Card title={t('vulnDetail.detectionStatus')} size="small">
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={trackingData}
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    dataKey="value"
                    nameKey="name"
                    label
                    onClick={(entry) => {
                      setStatusFilter((prev) => prev === entry.name ? null : entry.name);
                    }}
                    style={{ cursor: 'pointer' }}
                  >
                    {trackingData.map((_, i) => (
                      <Cell key={i} fill={TRACKING_COLORS[i % TRACKING_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend
                    content={() => (
                      <div style={{ display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap', marginTop: 8 }}>
                        {trackingData.map((entry, i) => (
                          <span key={entry.name} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
                            <span style={{
                              display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
                              background: TRACKING_COLORS[i % TRACKING_COLORS.length],
                            }} />
                            {entry.name}
                          </span>
                        ))}
                      </div>
                    )}
                  />
                </PieChart>
              </ResponsiveContainer>
              {statusFilter && (
                <div style={{ textAlign: 'center', marginTop: 4 }}>
                  <Button size="small" icon={<CloseCircleOutlined />} onClick={() => setStatusFilter(null)}>
                    {t('common.reset')}
                  </Button>
                </div>
              )}
            </Card>
            </div>
          )}
        </Col>
      </Row>

      {isAdmin && (
        <RuleCreateModal
          open={ruleModalOpen}
          onClose={() => setRuleModalOpen(false)}
          onCreated={handleRuleCreated}
          defaultPattern={info.title}
          defaultMatchField="title"
          autoReclassify
        />
      )}

      <ProposeRuleModal
        open={proposeModalOpen}
        onClose={() => setProposeModalOpen(false)}
        onCreated={() => setProposeModalOpen(false)}
        defaultPattern={info.title}
        defaultMatchField="title"
      />
    </div>
  );
}
