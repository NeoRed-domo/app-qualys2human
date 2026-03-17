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

const OS_CLASS_TAG: Record<string, { color: string; label: string }> = {
  windows: { color: 'blue', label: 'Windows' },
  nix: { color: 'green', label: 'NIX' },
  autre: { color: 'default', label: 'Autre' },
};

interface HostRow {
  ip: string;
  dns: string | null;
  os: string | null;
  vuln_count: number;
}

export default function HostList() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { tokens } = useTheme();
  const [data, setData] = useState<HostRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const osClass = searchParams.get('os_class');

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        if (osClass) params.set('os_class', osClass);
        const qs = params.toString();
        const resp = await api.get(`/hosts${qs ? '?' + qs : ''}`);
        if (!cancelled) setData(resp.data.items);
      } catch (err: any) {
        if (!cancelled) setError(err.response?.data?.detail || t('vulnList.loadError'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [osClass]);

  const classTag = osClass ? OS_CLASS_TAG[osClass.toLowerCase()] : null;

  const title = classTag
    ? <>{t('hostList.title')} <Tag color={classTag.color}>{classTag.label}</Tag> ({data.length})</>
    : <>{t('hostList.allHosts')} ({data.length})</>;

  const colDefs: ColDef<HostRow>[] = [
    { field: 'ip', headerName: t('hostList.ip'), width: 140 },
    { field: 'dns', headerName: t('hostList.dns'), flex: 1, minWidth: 200 },
    { field: 'os', headerName: t('hostList.os'), flex: 1, minWidth: 200 },
    { field: 'vuln_count', headerName: t('hostList.vulns'), width: 140, sort: 'desc' },
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
                const titleText = classTag
                  ? `${t('hostList.title')} ${classTag.label}`
                  : t('hostList.allHosts');
                const pdf = new PdfReport(titleText, logo);
                pdf.addTable(
                  [
                    { header: t('hostList.ip'), dataKey: 'ip' },
                    { header: t('hostList.dns'), dataKey: 'dns' },
                    { header: t('hostList.os'), dataKey: 'os' },
                    { header: t('hostList.vulns'), dataKey: 'vuln_count' },
                  ],
                  data,
                );
                pdf.save('serveurs.pdf');
              }} />
              <Button
                icon={<DownloadOutlined />}
                size="small"
                onClick={() => exportToCsv(colDefs, data, 'serveurs.csv')}
              >
                CSV
              </Button>
            </span>
          }
        >
          <div style={{ height: 'calc(100vh - 220px)', minHeight: 400 }}>
            <AgGridReact<HostRow>
              theme={themeQuartz.withParams({ colorScheme: tokens.agGridColorScheme })}
              rowData={data}
              columnDefs={colDefs}
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
      </Spin>
    </div>
  );
}
