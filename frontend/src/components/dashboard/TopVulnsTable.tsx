import { useNavigate } from 'react-router-dom';
import { Button, Card, Tag } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry, themeQuartz, type ColDef } from 'ag-grid-community';
import { useTheme } from '../../contexts/ThemeContext';
import { exportToCsv } from '../../utils/csvExport';

ModuleRegistry.registerModules([AllCommunityModule]);

interface TopVuln {
  qid: number;
  title: string;
  severity: number;
  count: number;
  layer_name: string | null;
  layer_color: string | null;
}

interface TopVulnsTableProps {
  data: TopVuln[];
}

const SEVERITY_COLORS: Record<number, string> = {
  5: 'red',
  4: 'orange',
  3: 'gold',
  2: 'blue',
  1: 'green',
};

export default function TopVulnsTable({ data }: TopVulnsTableProps) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { tokens } = useTheme();

  const severityLabel = (sev: number) => t(`severity.${sev}`);

  const colDefs: ColDef<TopVuln>[] = [
    { field: 'qid', headerName: 'QID', width: 90 },
    { field: 'title', headerName: t('common.title'), flex: 1, minWidth: 200 },
    {
      field: 'severity',
      headerName: t('filters.severity'),
      width: 120,
      valueFormatter: (p) => {
        return severityLabel(p.value as number);
      },
      cellRenderer: (params: any) => {
        const color = SEVERITY_COLORS[params.value];
        const label = severityLabel(params.value);
        return color ? <Tag color={color}>{label}</Tag> : params.value;
      },
    },
    {
      field: 'layer_name', headerName: t('filters.categorization'), width: 180,
      valueFormatter: (p) => (p.data as TopVuln)?.layer_name || '',
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
    { field: 'count', headerName: t('overview.occurrences'), width: 120, sort: 'desc' },
  ];

  return (
    <Card
      title={t('overview.topVulnsTable')}
      size="small"
      extra={
        <Button
          icon={<DownloadOutlined />}
          size="small"
          onClick={() => exportToCsv(colDefs, data, 'top-vulnerabilites.csv')}
        >
          CSV
        </Button>
      }
    >
      <AgGridReact<TopVuln>
        theme={themeQuartz.withParams({ colorScheme: tokens.agGridColorScheme })}
        rowData={data}
        columnDefs={colDefs}
        domLayout="autoHeight"
        rowHeight={36}
        headerHeight={38}
        onRowClicked={(e) => {
          if (e.data) navigate(`/vulnerabilities/${e.data.qid}`);
        }}
        rowStyle={{ cursor: 'pointer' }}
      />
    </Card>
  );
}
