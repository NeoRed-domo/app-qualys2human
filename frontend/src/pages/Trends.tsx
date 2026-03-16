import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Progress, message, Typography, Button, Tooltip } from 'antd';
import { EyeOutlined, EyeInvisibleOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import dayjs, { type Dayjs } from 'dayjs';
import api from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useFilters } from '../contexts/FilterContext';
import FilterBar from '../components/filters/FilterBar';
import TrendTimeBar from '../components/trends/TrendTimeBar';
import TrendWidgetGrid, { type TrendWidgetDef } from '../components/trends/TrendWidgetGrid';
import TrendChart from '../components/trends/TrendChart';
import TrendComboChart from '../components/trends/TrendComboChart';
import HelpTooltip from '../components/help/HelpTooltip';
import PdfExportButton from '../components/PdfExportButton';
import { PdfReport } from '../utils/pdfExport';
import { getLogoDataUrl } from '../utils/pdfLogo';

interface DataPoint {
  date: string;
  value: number;
  group: string | null;
}

interface ComboPoint {
  date: string;
  lineValue: number;
  barValue: number;
}

export default function Trends() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const isAdmin = user?.profile === 'admin';
  const { severities, types, layers, osClasses, ready } = useFilters();

  const [dateFrom, setDateFrom] = useState<Dayjs>(dayjs().subtract(6, 'month'));
  const [dateTo, setDateTo] = useState<Dayjs>(dayjs());
  const [granularity, setGranularity] = useState<string>('week');
  const [granularityLoaded, setGranularityLoaded] = useState(false);

  // Admin widget visibility
  const [hiddenForUsers, setHiddenForUsers] = useState<Set<string>>(new Set());
  const [userViewMode, setUserViewMode] = useState(false);

  // Chart data
  const [avgVulnsData, setAvgVulnsData] = useState<DataPoint[]>([]);
  const [hostCountData, setHostCountData] = useState<DataPoint[]>([]);
  const [comboData, setComboData] = useState<ComboPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const progressRef = useRef<ReturnType<typeof setInterval>>();

  const comboRef = useRef<HTMLDivElement>(null);
  const hostCountRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // New metric data
  const [criticalData, setCriticalData] = useState<DataPoint[]>([]);
  const [remediationRateData, setRemediationRateData] = useState<DataPoint[]>([]);
  const [avgRemediationData, setAvgRemediationData] = useState<DataPoint[]>([]);
  const [avgOpenAgeData, setAvgOpenAgeData] = useState<DataPoint[]>([]);
  const [categoryData, setCategoryData] = useState<DataPoint[]>([]);

  const criticalRef = useRef<HTMLDivElement>(null);
  const remediationRateRef = useRef<HTMLDivElement>(null);
  const avgRemediationRef = useRef<HTMLDivElement>(null);
  const avgOpenAgeRef = useRef<HTMLDivElement>(null);
  const categoryRef = useRef<HTMLDivElement>(null);

  // Layer name resolution for category breakdown
  const [layerNames, setLayerNames] = useState<Record<string, string>>({});

  // Load default granularity from enterprise settings
  useEffect(() => {
    api
      .get('/trends/default-granularity')
      .then((resp) => setGranularity(resp.data.granularity || 'week'))
      .catch(() => {})
      .finally(() => setGranularityLoaded(true));
  }, []);

  // Load admin widget visibility settings
  useEffect(() => {
    api.get('/settings/trends-widgets')
      .then((resp) => setHiddenForUsers(new Set(resp.data.hidden_widgets || [])))
      .catch(() => {});
  }, []);

  useEffect(() => {
    api.get('/layers').then((resp) => {
      const map: Record<string, string> = { unclassified: t('common.other') };
      for (const layer of resp.data) {
        map[String(layer.id)] = layer.name;
      }
      setLayerNames(map);
    }).catch(() => {});
  }, [t]);

  // Resolve layer IDs to names in category data
  const resolvedCategoryData = useMemo(() =>
    categoryData.map((d) => ({
      ...d,
      group: d.group ? (layerNames[d.group] || d.group) : d.group,
    })),
    [categoryData, layerNames],
  );

  // Batch fetch all metrics in a single request
  const fetchCharts = useCallback(async () => {
    if (!ready || !granularityLoaded) return;
    setLoading(true);
    setProgress(0);

    // Simulated progress: fast to 30%, then slow crawl to 80%
    if (progressRef.current) clearInterval(progressRef.current);
    let p = 0;
    progressRef.current = setInterval(() => {
      p += p < 30 ? 5 : p < 60 ? 2 : p < 80 ? 0.5 : 0;
      if (p > 80) p = 80;
      setProgress(Math.round(p));
    }, 200);

    try {
      const baseParams = {
        date_from: dateFrom.format('YYYY-MM-DD'),
        date_to: dateTo.format('YYYY-MM-DD'),
        granularity,
        severities: severities.length > 0 ? severities : undefined,
        types: types.length > 0 ? types : undefined,
        layers: layers.length > 0 ? layers : undefined,
        os_classes: osClasses.length > 0 ? osClasses : undefined,
        freshness: 'all',
      };

      // Batch: all scalar metrics + category breakdown in parallel
      const [batchResp, categoryResp] = await Promise.all([
        api.post('/trends/query', {
          ...baseParams,
          metrics: [
            'avg_vulns_per_host', 'host_count', 'critical_count',
            'avg_remediation_days', 'remediation_rate', 'avg_open_age_days',
          ],
        }),
        api.post('/trends/query', {
          ...baseParams,
          metric: 'total_vulns',
          group_by: 'layer',
        }),
      ]);

      const results = batchResp.data.results;
      const avgData: DataPoint[] = results.avg_vulns_per_host || [];
      const hostData: DataPoint[] = results.host_count || [];
      setAvgVulnsData(avgData);
      setHostCountData(hostData);
      setCriticalData(results.critical_count || []);
      setRemediationRateData(results.remediation_rate || []);
      setAvgRemediationData(results.avg_remediation_days || []);
      setAvgOpenAgeData(results.avg_open_age_days || []);
      setCategoryData(categoryResp.data.results.total_vulns || []);

      // Build combo data
      const hostMap = new Map(hostData.map((d: DataPoint) => [d.date, d.value]));
      setComboData(
        avgData.map((d: DataPoint) => ({
          date: d.date,
          lineValue: d.value,
          barValue: hostMap.get(d.date) ?? 0,
        })),
      );
    } catch (err: any) {
      message.error(err.response?.data?.detail || t('trends.loadError'));
    } finally {
      if (progressRef.current) clearInterval(progressRef.current);
      setProgress(100);
      // Brief pause at 100% before hiding
      setTimeout(() => setLoading(false), 300);
    }
  }, [ready, granularityLoaded, dateFrom, dateTo, granularity, severities, types, layers, osClasses, t]);

  // Admin: toggle widget visibility for users
  const handleToggleVisibility = useCallback((key: string, visible: boolean) => {
    setHiddenForUsers((prev) => {
      const next = new Set(prev);
      if (visible) {
        next.delete(key);
      } else {
        next.add(key);
      }
      api.put('/settings/trends-widgets', { hidden_widgets: [...next] }).catch(() => {});
      return next;
    });
  }, []);

  // Auto-fetch with debounce when deps change
  useEffect(() => {
    if (!ready || !granularityLoaded) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(fetchCharts, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [fetchCharts]);

  const handleDateChange = (from: Dayjs, to: Dayjs) => {
    setDateFrom(from);
    setDateTo(to);
  };

  const handlePdfExport = async () => {
    const logo = await getLogoDataUrl();
    const pdf = new PdfReport(t('trends.title'), logo);
    const refs = [comboRef, hostCountRef, criticalRef, remediationRateRef, avgRemediationRef, avgOpenAgeRef, categoryRef];
    for (const ref of refs) {
      if (ref.current) await pdf.addChartCapture(ref.current);
    }
    pdf.save('tendances.pdf');
  };

  const hasData = avgVulnsData.length > 0 || hostCountData.length > 0
    || criticalData.length > 0 || remediationRateData.length > 0
    || avgRemediationData.length > 0 || avgOpenAgeData.length > 0
    || categoryData.length > 0;

  const widgets: TrendWidgetDef[] = [
    {
      key: 'avgVulnsPerHost',
      label: t('trends.avgVulnsPerHost'),
      content: (
        <TrendComboChart
          ref={comboRef}
          data={comboData}
          title={t('trends.avgVulnsPerHost')}
          lineLabel={t('trends.avgVulnsPerHost')}
          barLabel={t('trends.hostCount')}
        />
      ),
    },
    {
      key: 'hostCount',
      label: t('trends.hostCount'),
      content: <TrendChart ref={hostCountRef} data={hostCountData} title={t('trends.hostCount')} />,
    },
    {
      key: 'criticalCount',
      label: t('trends.criticalCount'),
      content: <TrendChart ref={criticalRef} data={criticalData} title={t('trends.criticalCount')} />,
    },
    {
      key: 'remediationRate',
      label: t('trends.remediationRate'),
      content: <TrendChart ref={remediationRateRef} data={remediationRateData} title={t('trends.remediationRate')} />,
    },
    {
      key: 'avgRemediationDays',
      label: t('trends.avgRemediationDays'),
      content: <TrendChart ref={avgRemediationRef} data={avgRemediationData} title={t('trends.avgRemediationDays')} />,
    },
    {
      key: 'avgOpenAgeDays',
      label: t('trends.avgOpenAgeDays'),
      content: <TrendChart ref={avgOpenAgeRef} data={avgOpenAgeData} title={t('trends.avgOpenAgeDays')} />,
    },
    {
      key: 'categoryBreakdown',
      label: t('trends.categoryBreakdown'),
      content: <TrendChart ref={categoryRef} data={resolvedCategoryData} title={t('trends.categoryBreakdown')} />,
    },
  ];

  // For non-admin users: filter out hidden widgets entirely
  const visibleWidgets = isAdmin
    ? widgets
    : widgets.filter((w) => !hiddenForUsers.has(w.key));

  return (
    <div>
      <FilterBar
        extra={
          <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {isAdmin && (
              <Tooltip title={userViewMode ? t('trends.adminView') : t('trends.userView')}>
                <Button
                  size="small"
                  icon={userViewMode ? <EyeOutlined /> : <EyeInvisibleOutlined />}
                  type={userViewMode ? 'primary' : 'default'}
                  onClick={() => setUserViewMode((prev) => !prev)}
                />
              </Tooltip>
            )}
            {hasData && (
              <PdfExportButton onExport={handlePdfExport} />
            )}
            <HelpTooltip topic="trends" />
          </span>
        }
      />

      <TrendTimeBar
        dateFrom={dateFrom}
        dateTo={dateTo}
        granularity={granularity}
        onDateChange={handleDateChange}
        onGranularityChange={setGranularity}
      />

      {loading ? (
        <div style={{ textAlign: 'center', padding: '80px 24px' }}>
          <Progress
            percent={progress}
            status="active"
            strokeColor={{ from: '#1677ff', to: '#52c41a' }}
            style={{ maxWidth: 420, margin: '0 auto 16px' }}
          />
          <Typography.Text type="secondary" style={{ fontSize: 14 }}>
            {progress < 30
              ? t('trends.loadingMetrics')
              : progress < 80
                ? t('trends.loadingComputing')
                : t('trends.loadingCharts')}
          </Typography.Text>
        </div>
      ) : (
        <TrendWidgetGrid
          widgets={visibleWidgets}
          isAdmin={isAdmin}
          hiddenForUsers={hiddenForUsers}
          onToggleVisibility={handleToggleVisibility}
          userViewMode={userViewMode}
        />
      )}
    </div>
  );
}
