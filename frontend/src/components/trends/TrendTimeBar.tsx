import { Segmented, DatePicker, Select, Space } from 'antd';
import { useTranslation } from 'react-i18next';
import dayjs, { type Dayjs } from 'dayjs';
import { useTheme } from '../../contexts/ThemeContext';

interface TrendTimeBarProps {
  dateFrom: Dayjs;
  dateTo: Dayjs;
  granularity: string;
  onDateChange: (from: Dayjs, to: Dayjs) => void;
  onGranularityChange: (g: string) => void;
}

export default function TrendTimeBar({
  dateFrom,
  dateTo,
  granularity,
  onDateChange,
  onGranularityChange,
}: TrendTimeBarProps) {
  const { t } = useTranslation();
  const { tokens } = useTheme();

  const PERIOD_OPTIONS = [
    { label: t('trends.period3m'), value: '3m' },
    { label: t('trends.period6m'), value: '6m' },
    { label: t('trends.period1y'), value: '1y' },
    { label: t('trends.periodCustom'), value: 'custom' },
  ];

  const GRANULARITY_OPTIONS = [
    { label: t('trends.day'), value: 'day' },
    { label: t('trends.week'), value: 'week' },
    { label: t('trends.month'), value: 'month' },
  ];

  // Derive which segment is active from the current dates
  const getActiveSegment = (): string => {
    const now = dayjs();
    const diffDays = now.diff(dateFrom, 'day');
    const isToToday = Math.abs(now.diff(dateTo, 'day')) <= 1;
    if (!isToToday) return 'custom';
    if (Math.abs(diffDays - 90) <= 2) return '3m';
    if (Math.abs(diffDays - 180) <= 2) return '6m';
    if (Math.abs(diffDays - 365) <= 2) return '1y';
    return 'custom';
  };

  const handleSegmentChange = (val: string | number) => {
    const now = dayjs();
    switch (val) {
      case '3m':
        onDateChange(now.subtract(3, 'month'), now);
        break;
      case '6m':
        onDateChange(now.subtract(6, 'month'), now);
        break;
      case '1y':
        onDateChange(now.subtract(1, 'year'), now);
        break;
      // 'custom' — don't change dates
    }
  };

  const handleRangeChange = (dates: [Dayjs | null, Dayjs | null] | null) => {
    if (dates && dates[0] && dates[1]) {
      onDateChange(dates[0], dates[1]);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        padding: '8px 16px',
        background: tokens.surfaceSecondary,
        borderRadius: 8,
        marginBottom: 16,
        flexWrap: 'wrap',
      }}
    >
      <Segmented
        options={PERIOD_OPTIONS}
        value={getActiveSegment()}
        onChange={handleSegmentChange}
      />
      <DatePicker.RangePicker
        value={[dateFrom, dateTo]}
        onChange={handleRangeChange}
        format="YYYY-MM-DD"
        allowClear={false}
      />
      <Space size={8}>
        <span style={{ fontSize: 12, fontWeight: 500, color: tokens.textSecondary }}>
          {t('trends.granularity')}
        </span>
        <Select
          value={granularity}
          onChange={onGranularityChange}
          options={GRANULARITY_OPTIONS}
          style={{ width: 110 }}
          size="small"
        />
      </Space>
    </div>
  );
}
