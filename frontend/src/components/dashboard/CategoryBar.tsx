import { forwardRef } from 'react';
import { Card } from 'antd';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../../contexts/ThemeContext';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
} from 'recharts';

interface TopVuln {
  qid: number;
  title: string;
  severity: number;
  count: number;
  layer_name: string | null;
  layer_color: string | null;
}

interface CategoryBarProps {
  data: TopVuln[];
  onClickBar?: (qid: number) => void;
}

const SEVERITY_COLORS: Record<number, string> = {
  5: '#cf1322',
  4: '#fa541c',
  3: '#faad14',
  2: '#1677ff',
  1: '#52c41a',
};

interface ChartItem {
  name: string;
  fullTitle: string;
  count: number;
  qid: number;
  severity: number;
  fill: string;
}

function CustomTooltip({ active, payload, tooltipBg, tooltipBorder, tooltipText, textSecondary, tooltipOccurrencesLabel }: any) {
  if (!active || !payload?.[0]) return null;
  const item: ChartItem = payload[0].payload;
  return (
    <div
      style={{
        background: tooltipBg,
        border: `1px solid ${tooltipBorder}`,
        borderRadius: 6,
        padding: '8px 12px',
        maxWidth: 360,
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        color: tooltipText,
      }}
    >
      <div style={{ fontWeight: 600, fontSize: 12, color: '#1677ff' }}>
        QID {item.qid}
      </div>
      <div
        style={{
          whiteSpace: 'normal',
          wordBreak: 'break-word',
          fontSize: 13,
          marginBottom: 6,
        }}
      >
        {item.fullTitle}
      </div>
      <div style={{ fontSize: 12, color: textSecondary }}>
        {tooltipOccurrencesLabel} : <strong style={{ color: item.fill }}>{item.count}</strong>
      </div>
    </div>
  );
}

/** Custom bar shape — native SVG rect with its own onClick.
 *  Only the colored bar rectangle is clickable, not the full chart row. */
function ClickableBar(props: any) {
  const { fill, x, y, width, height, payload, onBarClick } = props;
  return (
    <rect
      x={x}
      y={y}
      width={width}
      height={height}
      fill={fill}
      rx={4}
      ry={4}
      style={{ cursor: onBarClick ? 'pointer' : 'default' }}
      onClick={onBarClick ? () => onBarClick(payload.qid) : undefined}
    />
  );
}

const CategoryBar = forwardRef<HTMLDivElement, CategoryBarProps>(function CategoryBar({ data, onClickBar }, ref) {
  const { t } = useTranslation();
  const { tokens } = useTheme();
  const chartData: ChartItem[] = data.slice(0, 10).map((d) => ({
    name: d.title.length > 60 ? d.title.slice(0, 57) + '...' : d.title,
    fullTitle: d.title,
    count: d.count,
    qid: d.qid,
    severity: d.severity,
    fill: SEVERITY_COLORS[d.severity] || '#8c8c8c',
  }));

  return (
    <div ref={ref}>
    <Card title={t('overview.topVulnsChart')} size="small">
      <ResponsiveContainer width="100%" height={380}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ left: 20, right: 20, top: 5, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" />
          <YAxis type="category" dataKey="name" width={280} tick={{ fontSize: 11 }} />
          <Tooltip
            content={<CustomTooltip tooltipBg={tokens.tooltipBg} tooltipBorder={tokens.tooltipBorder} tooltipText={tokens.tooltipText} textSecondary={tokens.textSecondary} tooltipOccurrencesLabel={t('overview.occurrences')} />}
            cursor={false}
            wrapperStyle={{ pointerEvents: 'none' }}
          />
          <Bar dataKey="count" shape={(props: any) => <ClickableBar {...props} onBarClick={onClickBar} />}>
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
    </div>
  );
});

export default CategoryBar;
