import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Input, Radio, Spin, Alert, Tag, Empty } from 'antd';
import { useTranslation } from 'react-i18next';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry, themeQuartz, type ColDef } from 'ag-grid-community';
import api from '../../api/client';
import { useTheme } from '../../contexts/ThemeContext';

ModuleRegistry.registerModules([AllCommunityModule]);

interface VulnRow {
  qid: number;
  title: string;
  severity: number;
  type: string | null;
  category: string | null;
  host_count: number;
  layer_name: string | null;
  layer_color: string | null;
}

interface HostRow {
  ip: string;
  dns: string | null;
  os: string | null;
  vuln_count: number;
}

type SearchType = 'vuln' | 'host';

export default function BasicSearch() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { tokens } = useTheme();
  const [searchType, setSearchType] = useState<SearchType>('vuln');
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  const SEVERITY_TAG: Record<number, { color: string; label: string }> = {
    5: { color: 'red', label: t('severity.5') },
    4: { color: 'orange', label: t('severity.4') },
    3: { color: 'gold', label: t('severity.3') },
    2: { color: 'blue', label: t('severity.2') },
    1: { color: 'green', label: t('severity.1') },
  };

  const vulnColDefs: ColDef<VulnRow>[] = [
    { field: 'qid', headerName: 'QID', width: 90 },
    { field: 'title', headerName: t('common.title'), flex: 1, minWidth: 300 },
    {
      field: 'severity', headerName: t('filters.severity'), width: 130,
      cellRenderer: (p: any) => {
        const tag = SEVERITY_TAG[p.value];
        return tag ? <Tag color={tag.color}>{tag.label}</Tag> : p.value;
      },
    },
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
    { field: 'host_count', headerName: t('vulnList.hosts'), width: 100 },
  ];

  const hostColDefs: ColDef<HostRow>[] = [
    { field: 'ip', headerName: t('hostList.ip'), width: 160 },
    { field: 'dns', headerName: t('hostList.dns'), flex: 1, minWidth: 250 },
    { field: 'os', headerName: t('hostList.os'), flex: 1, minWidth: 200 },
    { field: 'vuln_count', headerName: t('hostList.vulns'), width: 100, sort: 'desc' },
  ];

  const handleSearch = useCallback(async (value: string) => {
    const term = value.trim();
    if (!term) return;

    setLoading(true);
    setError(null);
    setSearched(true);
    try {
      const resp = await api.get('/search', { params: { q: term, type: searchType } });
      const results = resp.data.items;

      if (results.length === 1) {
        if (searchType === 'vuln') {
          navigate(`/vulnerabilities/${results[0].qid}`);
        } else {
          navigate(`/hosts/${results[0].ip}`);
        }
        return;
      }

      setItems(results);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('common.error'));
    } finally {
      setLoading(false);
    }
  }, [searchType, navigate, t]);

  const handleRowClick = useCallback((e: any) => {
    if (!e.data) return;
    if (searchType === 'vuln') {
      navigate(`/vulnerabilities/${e.data.qid}`);
    } else {
      navigate(`/hosts/${e.data.ip}`);
    }
  }, [searchType, navigate]);

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          <Radio.Group
            value={searchType}
            onChange={(e) => { setSearchType(e.target.value); setItems([]); setSearched(false); }}
            optionType="button"
            buttonStyle="solid"
          >
            <Radio.Button value="vuln">{t('search.vulnerability')}</Radio.Button>
            <Radio.Button value="host">{t('search.server')}</Radio.Button>
          </Radio.Group>

          <Input.Search
            placeholder={searchType === 'vuln' ? t('search.vulnPlaceholder') : t('search.hostPlaceholder')}
            allowClear
            enterButton={t('common.search')}
            onSearch={handleSearch}
            style={{ maxWidth: 500, flex: 1 }}
            size="middle"
          />
        </div>
      </Card>

      {error && <Alert message={t('common.error')} description={error} type="error" showIcon style={{ marginBottom: 16 }} />}

      <Spin spinning={loading}>
        {searched && !loading && items.length === 0 && !error ? (
          <Card>
            <Empty description={t('search.noResults')} />
          </Card>
        ) : items.length > 0 ? (
          <Card title={`${t('search.results')} (${items.length})`} size="small">
            <div style={{ height: 'calc(100vh - 280px)', minHeight: 300 }}>
              <AgGridReact
                theme={themeQuartz.withParams({ colorScheme: tokens.agGridColorScheme })}
                rowData={items}
                columnDefs={searchType === 'vuln' ? vulnColDefs : hostColDefs}
                domLayout="normal"
                rowHeight={36}
                headerHeight={38}
                onRowClicked={handleRowClick}
                rowStyle={{ cursor: 'pointer' }}
              />
            </div>
          </Card>
        ) : null}
      </Spin>
    </div>
  );
}
