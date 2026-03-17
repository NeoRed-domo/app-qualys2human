import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Button, Card, Spin, Alert, Tag } from 'antd';
import { ArrowLeftOutlined, DownloadOutlined } from '@ant-design/icons';
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

const SEVERITY_COLOR: Record<number, string> = {
  5: 'red',
  4: 'orange',
  3: 'gold',
  2: 'blue',
  1: 'green',
};

interface VulnRow {
  qid: number;
  title: string;
  severity: number;
  type: string | null;
  category: string | null;
  host_count: number;
  occurrence_count: number;
  layer_name: string | null;
  layer_color: string | null;
}

export default function VulnList() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { tokens } = useTheme();
  const [data, setData] = useState<VulnRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const severity = searchParams.get('severity');
  const layer = searchParams.get('layer');
  const layerName = searchParams.get('layer_name');
  const freshness = searchParams.get('freshness') || 'active';

  const sevLabel = (n: number) => t(`severity.${n}`);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        if (severity) params.set('severity', severity);
        if (layer) params.set('layer', layer);
        params.set('freshness', freshness);
        const qs = params.toString();
        const resp = await api.get(`/vulnerabilities${qs ? '?' + qs : ''}`);
        if (!cancelled) setData(resp.data.items);
      } catch (err: any) {
        if (!cancelled) setError(err.response?.data?.detail || t('vulnList.loadError'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [severity, layer, freshness]);

  const sevColor = severity ? SEVERITY_COLOR[Number(severity)] : null;
  const sevTagLabel = severity ? sevLabel(Number(severity)) : null;
  const freshnessLabel = t(`freshness.${freshness}`) || freshness;

  const filterLabel = layerName
    ? <> — {t('filters.categorization')} <Tag>{layerName}</Tag></>
    : null;

  const title = (sevColor && sevTagLabel)
    ? <>{t('vulnList.title')} <Tag color={sevColor}>{sevTagLabel}</Tag>{filterLabel} — {freshnessLabel} ({data.length})</>
    : <>{t('vulnList.allVulns')}{filterLabel} — {freshnessLabel} ({data.length})</>;

  const colDefs: ColDef<VulnRow>[] = [
    { field: 'qid', headerName: 'QID', width: 90 },
    { field: 'title', headerName: t('common.title'), flex: 1, minWidth: 300 },
    {
      field: 'severity', headerName: t('filters.severity'), width: 120,
      valueFormatter: (p) => sevLabel(p.value as number),
      cellRenderer: (p: any) => {
        const color = SEVERITY_COLOR[p.value];
        return color ? <Tag color={color}>{sevLabel(p.value)}</Tag> : p.value;
      },
    },
    { field: 'type', headerName: t('common.type'), width: 120 },
    { field: 'category', headerName: t('common.category'), width: 160 },
    {
      field: 'layer_name', headerName: t('filters.categorization'), width: 180,
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
    { field: 'host_count', headerName: t('vulnList.hosts'), width: 100, sort: 'desc' },
    { field: 'occurrence_count', headerName: t('overview.occurrences'), width: 120 },
  ];

  if (error) return <Alert message={t('common.error')} description={error} type="error" showIcon />;

  return (
    <div>
      <Button
        icon={<ArrowLeftOutlined />}
        type="link"
        onClick={() => navigate('/')}
        style={{ padding: 0, marginBottom: 12 }}
      >
        {t('common.backToOverview')}
      </Button>

      <Spin spinning={loading}>
        <Card
          title={title}
          size="small"
          extra={
            <span style={{ display: 'flex', gap: 8 }}>
              <PdfExportButton onExport={async () => {
                const logo = await getLogoDataUrl();
                const titleText = (sevColor && sevTagLabel)
                  ? `${t('vulnList.title')} ${sevTagLabel} — ${freshnessLabel}`
                  : `${t('vulnList.allVulns')} — ${freshnessLabel}`;
                const pdf = new PdfReport(titleText, logo);
                pdf.addTable(
                  [
                    { header: 'QID', dataKey: 'qid' },
                    { header: t('common.title'), dataKey: 'title' },
                    { header: t('filters.severity'), dataKey: 'severityLabel' },
                    { header: t('common.type'), dataKey: 'type' },
                    { header: t('common.category'), dataKey: 'category' },
                    { header: t('vulnList.hosts'), dataKey: 'host_count' },
                    { header: t('overview.occurrences'), dataKey: 'occurrence_count' },
                  ],
                  data.map((r) => ({
                    ...r,
                    severityLabel: sevLabel(r.severity),
                  })),
                );
                pdf.save('vulnerabilites.pdf');
              }} />
              <Button
                icon={<DownloadOutlined />}
                size="small"
                onClick={() => exportToCsv(colDefs, data, 'vulnerabilites.csv')}
              >
                CSV
              </Button>
            </span>
          }
        >
          <div style={{ height: 'calc(100vh - 220px)', minHeight: 400 }}>
            <AgGridReact<VulnRow>
              theme={themeQuartz.withParams({ colorScheme: tokens.agGridColorScheme })}
              rowData={data}
              columnDefs={colDefs}
              domLayout="normal"
              rowHeight={36}
              headerHeight={38}
              onRowClicked={(e) => {
                if (e.data) navigate(`/vulnerabilities/${e.data.qid}`);
              }}
              rowStyle={{ cursor: 'pointer' }}
            />
          </div>
        </Card>
      </Spin>
    </div>
  );
}
