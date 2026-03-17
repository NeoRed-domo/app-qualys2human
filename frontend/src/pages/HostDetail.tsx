import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Card, Descriptions, Tag, Row, Col, Spin, Alert, Segmented } from 'antd';
import { ArrowLeftOutlined, CloseCircleOutlined, DownloadOutlined } from '@ant-design/icons';
import { useFilters } from '../contexts/FilterContext';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry, themeQuartz, type ColDef } from 'ag-grid-community';
import { useTranslation } from 'react-i18next';
import api from '../api/client';
import { useTheme } from '../contexts/ThemeContext';
import { exportToCsv } from '../utils/csvExport';
import PdfExportButton from '../components/PdfExportButton';
import { PdfReport } from '../utils/pdfExport';
import { getLogoDataUrl } from '../utils/pdfLogo';

ModuleRegistry.registerModules([AllCommunityModule]);

const SEVERITY_COLORS: Record<number, string> = {
  5: '#cf1322', 4: '#fa541c', 3: '#faad14', 2: '#1677ff', 1: '#52c41a',
};
const SEVERITY_TAG_COLORS: Record<number, string> = {
  5: 'red', 4: 'orange', 3: 'gold', 2: 'blue', 1: 'green',
};
const TRACKING_COLORS = ['#1677ff', '#52c41a', '#faad14', '#cf1322', '#722ed1', '#8c8c8c'];

interface HostInfo {
  ip: string;
  dns: string | null;
  netbios: string | null;
  os: string | null;
  os_cpe: string | null;
  first_seen: string | null;
  last_seen: string | null;
  vuln_count: number;
}

interface VulnRow {
  qid: number;
  title: string;
  severity: number;
  type: string | null;
  category: string | null;
  vuln_status: string | null;
  port: number | null;
  protocol: string | null;
  first_detected: string | null;
  last_detected: string | null;
  tracking_method: string | null;
  layer_name: string | null;
  layer_color: string | null;
}

export default function HostDetail() {
  const { t } = useTranslation();
  const { ip } = useParams<{ ip: string }>();
  const navigate = useNavigate();
  const { tokens } = useTheme();
  const [info, setInfo] = useState<HostInfo | null>(null);
  const [vulns, setVulns] = useState<VulnRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sevFilter, setSevFilter] = useState<number | null>(null);
  const [trackFilter, setTrackFilter] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'filtered' | 'all'>('filtered');
  const { severities: globalSev, types: globalTypes, freshness: globalFreshness } = useFilters();
  const [freshThresholds, setFreshThresholds] = useState<{ stale_days: number; hide_days: number } | null>(null);
  const sevChartRef = useRef<HTMLDivElement>(null);
  const trackChartRef = useRef<HTMLDivElement>(null);

  const sevLabel = (n: number) => t(`severity.${n}`);
  const unknownLabel = t('vulnDetail.unknown');

  useEffect(() => {
    if (!ip) return;
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [infoResp, vulnsResp, freshResp] = await Promise.all([
          api.get(`/hosts/${ip}`),
          api.get(`/hosts/${ip}/vulnerabilities?page_size=500`),
          api.get('/settings/freshness'),
        ]);
        if (!cancelled) {
          setInfo(infoResp.data);
          setVulns(vulnsResp.data.items);
          setFreshThresholds(freshResp.data);
        }
      } catch (err: any) {
        if (!cancelled) setError(err.response?.data?.detail || t('vulnList.loadError'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [ip]);

  if (loading) return <Spin style={{ display: 'block', margin: '80px auto' }} size="large" />;
  if (error) return <Alert message={t('common.error')} description={error} type="error" showIcon />;
  if (!info) return null;

  // Apply global filters (if filtered view)
  const freshActive = globalFreshness && globalFreshness !== '' && globalFreshness !== 'all';
  const hasGlobalFilters = globalSev.length > 0 || globalTypes.length > 0 || freshActive;
  let baseVulns = vulns;
  if (viewMode === 'filtered') {
    if (globalSev.length > 0) baseVulns = baseVulns.filter(v => globalSev.includes(v.severity));
    if (globalTypes.length > 0) baseVulns = baseVulns.filter(v => v.type != null && globalTypes.includes(v.type));
    if (freshActive && freshThresholds) {
      const now = Date.now();
      const staleCutoff = now - freshThresholds.stale_days * 86400000;
      const hideCutoff = now - freshThresholds.hide_days * 86400000;
      baseVulns = baseVulns.filter(v => {
        if (!v.last_detected) return false;
        const ts = new Date(v.last_detected).getTime();
        if (globalFreshness === 'active') return ts >= staleCutoff;
        if (globalFreshness === 'stale') return ts < staleCutoff && ts >= hideCutoff;
        return true;
      });
    }
  }

  // Severity distribution (on globally filtered data)
  const sevMap: Record<number, number> = {};
  baseVulns.forEach((v) => { sevMap[v.severity] = (sevMap[v.severity] || 0) + 1; });
  const sevData = Object.entries(sevMap)
    .map(([sev, count]) => ({
      name: sevLabel(Number(sev)),
      value: count,
      severity: Number(sev),
    }))
    .sort((a, b) => b.severity - a.severity);

  // Tracking method distribution (on globally filtered data)
  const trackMap: Record<string, number> = {};
  baseVulns.forEach((v) => {
    const key = v.tracking_method || unknownLabel;
    trackMap[key] = (trackMap[key] || 0) + 1;
  });
  const trackData = Object.entries(trackMap).map(([name, value]) => ({ name, value }));

  // Apply local filters from pie chart clicks
  let filteredVulns = baseVulns;
  if (sevFilter !== null) {
    filteredVulns = filteredVulns.filter((v) => v.severity === sevFilter);
  }
  if (trackFilter !== null) {
    filteredVulns = filteredVulns.filter((v) => (v.tracking_method || unknownLabel) === trackFilter);
  }

  const hasFilter = sevFilter !== null || trackFilter !== null;

  const vulnCols: ColDef<VulnRow>[] = [
    { field: 'qid', headerName: 'QID', width: 90 },
    { field: 'title', headerName: t('common.title'), flex: 1, minWidth: 200 },
    {
      field: 'severity', headerName: t('filters.severity'), width: 120,
      valueFormatter: (p) => sevLabel(p.value as number),
      cellRenderer: (p: any) => {
        const color = SEVERITY_TAG_COLORS[p.value];
        return color ? <Tag color={color}>{sevLabel(p.value)}</Tag> : p.value;
      },
      sort: 'desc',
    },
    {
      field: 'layer_name', headerName: t('filters.categorization'), width: 180,
      valueFormatter: (p) => (p.data as VulnRow)?.layer_name || '',
      cellRenderer: (p: any) => {
        const name = p.data?.layer_name;
        const color = p.data?.layer_color || '#8c8c8c';
        if (!name) return <span style={{ color: '#8c8c8c' }}>—</span>;
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{
              display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
              background: color, flexShrink: 0,
            }} />
            {name}
          </span>
        );
      },
    },
    { field: 'port', headerName: t('vulnDetail.port'), width: 80 },
    { field: 'vuln_status', headerName: t('common.status'), width: 110 },
    { field: 'last_detected', headerName: t('vulnDetail.lastDetected'), width: 160 },
  ];

  const filterTags = (
    <span>
      {sevFilter !== null && (
        <Tag color="blue" closable onClose={() => setSevFilter(null)}>
          {sevLabel(sevFilter)}
        </Tag>
      )}
      {trackFilter !== null && (
        <Tag color="blue" closable onClose={() => setTrackFilter(null)}>
          {trackFilter}
        </Tag>
      )}
    </span>
  );

  const tableTitle = hasFilter
    ? <span>{t('hostDetail.vulnsFilter')} {filterTags}</span>
    : t('hostList.vulns');

  const handlePdfExport = async () => {
    const logo = await getLogoDataUrl();
    const pdf = new PdfReport(`${t('hostDetail.title')} ${info.ip}`, logo);

    pdf.addDescriptions([
      { label: t('hostList.ip'), value: info.ip },
      { label: t('hostList.dns'), value: info.dns || '—' },
      { label: t('hostDetail.netbios'), value: info.netbios || '—' },
      { label: t('hostList.os'), value: info.os || '—' },
      { label: t('hostDetail.osCpe'), value: info.os_cpe || '—' },
      { label: t('hostList.vulns'), value: String(info.vuln_count) },
      { label: t('hostDetail.firstSeen'), value: info.first_seen || '—' },
      { label: t('hostDetail.lastSeen'), value: info.last_seen || '—' },
    ]);

    await pdf.addChartPair(sevChartRef.current, trackChartRef.current);

    pdf.addSectionTitle(t('hostList.vulns'));
    pdf.addTable(
      [
        { header: 'QID', dataKey: 'qid' },
        { header: t('common.title'), dataKey: 'title' },
        { header: t('filters.severity'), dataKey: 'severityLabel' },
        { header: t('filters.categorization'), dataKey: 'layer_name' },
        { header: t('vulnDetail.port'), dataKey: 'port' },
        { header: t('common.status'), dataKey: 'vuln_status' },
        { header: t('vulnDetail.lastDetected'), dataKey: 'last_detected' },
      ],
      filteredVulns.map((v) => ({
        ...v,
        severityLabel: sevLabel(v.severity),
      })),
    );

    pdf.save(`hote-${info.ip}.pdf`);
  };

  return (
    <div>
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Button icon={<ArrowLeftOutlined />} type="link" onClick={() => navigate(-1)} style={{ padding: 0 }}>
          {t('common.back')}
        </Button>
        <PdfExportButton onExport={handlePdfExport} />
      </div>

      <Card title={`${t('hostDetail.title')} ${info.ip}`} style={{ marginBottom: 16 }}>
        <Descriptions column={{ xs: 1, sm: 2, lg: 3 }} size="small">
          <Descriptions.Item label={t('hostList.ip')}>{info.ip}</Descriptions.Item>
          <Descriptions.Item label={t('hostList.dns')}>{info.dns || '—'}</Descriptions.Item>
          <Descriptions.Item label={t('hostDetail.netbios')}>{info.netbios || '—'}</Descriptions.Item>
          <Descriptions.Item label={t('hostList.os')}>{info.os || '—'}</Descriptions.Item>
          <Descriptions.Item label={t('hostDetail.osCpe')}>{info.os_cpe || '—'}</Descriptions.Item>
          <Descriptions.Item label={t('hostList.vulns')}>
            {viewMode === 'filtered' && hasGlobalFilters
              ? `${baseVulns.length} / ${info.vuln_count}`
              : info.vuln_count}
          </Descriptions.Item>
          <Descriptions.Item label={t('hostDetail.firstSeen')}>{info.first_seen || '—'}</Descriptions.Item>
          <Descriptions.Item label={t('hostDetail.lastSeen')}>{info.last_seen || '—'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <Segmented
          value={viewMode}
          onChange={(v) => { setViewMode(v as 'filtered' | 'all'); setSevFilter(null); setTrackFilter(null); }}
          options={[
            { label: t('hostDetail.filteredView'), value: 'filtered' },
            { label: t('hostDetail.showAll'), value: 'all' },
          ]}
        />
        {viewMode === 'filtered' && hasGlobalFilters && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
            {t('hostDetail.filters')}
            {globalSev.length > 0 && <Tag>{t('hostDetail.sevLabel')} {globalSev.join(', ')}</Tag>}
            {globalTypes.length > 0 && <Tag>{t('hostDetail.typesLabel')} {globalTypes.join(', ')}</Tag>}
            {freshActive && freshThresholds && globalFreshness === 'active' && (
              <Tag>{t('hostDetail.detectedLessThan', { days: freshThresholds.stale_days })}</Tag>
            )}
            {freshActive && freshThresholds && globalFreshness === 'stale' && (
              <Tag>{t('hostDetail.detectedBetween', { staleDays: freshThresholds.stale_days, hideDays: freshThresholds.hide_days })}</Tag>
            )}
          </span>
        )}
        {viewMode === 'filtered' && !hasGlobalFilters && (
          <span style={{ color: '#8c8c8c', fontSize: 13 }}>{t('hostDetail.noActiveFilter')}</span>
        )}
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={12}>
          <div ref={sevChartRef}>
          <Card title={t('hostDetail.severitiesChart')} size="small">
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={sevData}
                  cx="50%" cy="50%"
                  innerRadius={50} outerRadius={85}
                  dataKey="value" nameKey="name"
                  onClick={(entry) => {
                    setSevFilter((prev) => prev === entry.severity ? null : entry.severity);
                  }}
                  style={{ cursor: 'pointer' }}
                >
                  {sevData.map((entry, i) => (
                    <Cell key={i} fill={SEVERITY_COLORS[entry.severity] || '#8c8c8c'} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend
                  content={() => (
                    <div style={{ display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap', marginTop: 8 }}>
                      {sevData.map((entry) => (
                        <span key={entry.severity} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
                          <span style={{
                            display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
                            background: SEVERITY_COLORS[entry.severity] || '#8c8c8c',
                          }} />
                          {entry.name}
                        </span>
                      ))}
                    </div>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
            {sevFilter !== null && (
              <div style={{ textAlign: 'center', marginTop: 4 }}>
                <Button size="small" icon={<CloseCircleOutlined />} onClick={() => setSevFilter(null)}>
                  {t('common.reset')}
                </Button>
              </div>
            )}
          </Card>
          </div>
        </Col>
        <Col xs={24} lg={12}>
          {trackData.length > 0 && (
            <div ref={trackChartRef}>
            <Card title={t('hostDetail.trackingMethods')} size="small">
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={trackData}
                    cx="50%" cy="50%"
                    outerRadius={85}
                    dataKey="value" nameKey="name"
                    label
                    onClick={(entry) => {
                      setTrackFilter((prev) => prev === entry.name ? null : entry.name);
                    }}
                    style={{ cursor: 'pointer' }}
                  >
                    {trackData.map((_, i) => (
                      <Cell key={i} fill={TRACKING_COLORS[i % TRACKING_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend
                    content={() => (
                      <div style={{ display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap', marginTop: 8 }}>
                        {trackData.map((entry, i) => (
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
              {trackFilter !== null && (
                <div style={{ textAlign: 'center', marginTop: 4 }}>
                  <Button size="small" icon={<CloseCircleOutlined />} onClick={() => setTrackFilter(null)}>
                    {t('common.reset')}
                  </Button>
                </div>
              )}
            </Card>
            </div>
          )}
        </Col>
      </Row>

      <Card
        title={tableTitle}
        size="small"
        extra={
          <Button
            icon={<DownloadOutlined />}
            size="small"
            onClick={() => exportToCsv(vulnCols, filteredVulns, `vulnerabilites-${ip}.csv`)}
          >
            CSV
          </Button>
        }
      >
        <div style={{ height: 400 }}>
          <AgGridReact<VulnRow>
            theme={themeQuartz.withParams({ colorScheme: tokens.agGridColorScheme })}
            rowData={filteredVulns}
            columnDefs={vulnCols}
            domLayout="normal"
            rowHeight={36}
            headerHeight={38}
            onRowClicked={(e) => {
              if (e.data && ip) navigate(`/hosts/${ip}/vulnerabilities/${e.data.qid}`);
            }}
            rowStyle={{ cursor: 'pointer' }}
          />
        </div>
      </Card>
    </div>
  );
}
