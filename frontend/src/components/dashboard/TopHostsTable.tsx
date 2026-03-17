import { useNavigate } from 'react-router-dom';
import { Button, Card } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry, themeQuartz, type ColDef } from 'ag-grid-community';
import { useTheme } from '../../contexts/ThemeContext';
import { exportToCsv } from '../../utils/csvExport';

ModuleRegistry.registerModules([AllCommunityModule]);

interface TopHost {
  ip: string;
  dns: string | null;
  os: string | null;
  host_count: number;
}

interface TopHostsTableProps {
  data: TopHost[];
}

export default function TopHostsTable({ data }: TopHostsTableProps) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { tokens } = useTheme();

  const colDefs: ColDef<TopHost>[] = [
    { field: 'ip', headerName: 'IP', width: 140 },
    { field: 'dns', headerName: 'DNS', flex: 1, minWidth: 180 },
    { field: 'os', headerName: 'OS', flex: 1, minWidth: 150 },
    { field: 'host_count', headerName: t('hostList.vulns'), width: 130, sort: 'desc' },
  ];

  return (
    <Card
      title={t('overview.topHosts')}
      size="small"
      extra={
        <Button
          icon={<DownloadOutlined />}
          size="small"
          onClick={() => exportToCsv(colDefs, data, 'top-hotes.csv')}
        >
          CSV
        </Button>
      }
    >
      <AgGridReact<TopHost>
        theme={themeQuartz.withParams({ colorScheme: tokens.agGridColorScheme })}
        rowData={data}
        columnDefs={colDefs}
        domLayout="autoHeight"
        rowHeight={36}
        headerHeight={38}
        onRowClicked={(e) => {
          if (e.data) navigate(`/hosts/${e.data.ip}`);
        }}
        rowStyle={{ cursor: 'pointer' }}
      />
    </Card>
  );
}
