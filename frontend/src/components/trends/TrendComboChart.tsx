import { forwardRef } from 'react';
import { Card, Empty } from 'antd';
import { useTranslation } from 'react-i18next';
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface DataPoint {
  date: string;
  lineValue: number;
  barValue: number;
}

interface TrendComboChartProps {
  data: DataPoint[];
  title?: string;
  lineLabel: string;
  barLabel: string;
}

const formatValue = (v: number) => Number(v).toFixed(1);

const TrendComboChart = forwardRef<HTMLDivElement, TrendComboChartProps>(
  function TrendComboChart({ data, title, lineLabel, barLabel }, ref) {
    const { t } = useTranslation();
    const displayTitle = title || t('trends.title');

    if (data.length === 0) {
      return (
        <Card title={displayTitle} size="small">
          <Empty description={t('trends.noData')} />
        </Card>
      );
    }

    return (
      <div ref={ref}>
        <Card title={displayTitle} size="small">
          <ResponsiveContainer width="100%" height={400}>
            <ComposedChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis
                yAxisId="left"
                tickFormatter={formatValue}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                tickFormatter={(v: number) => Math.round(v).toString()}
              />
              <Tooltip
                formatter={(val: number, name: string) =>
                  name === 'barValue'
                    ? [Math.round(val), barLabel]
                    : [formatValue(val), lineLabel]
                }
              />
              <Legend
                formatter={(value: string) =>
                  value === 'barValue' ? barLabel : lineLabel
                }
              />
              <Bar
                yAxisId="right"
                dataKey="barValue"
                fill="#8c8c8c"
                fillOpacity={0.3}
                stroke="#8c8c8c"
                strokeOpacity={0.5}
                name="barValue"
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="lineValue"
                stroke="#1677ff"
                strokeWidth={2}
                dot={{ r: 3 }}
                name="lineValue"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>
      </div>
    );
  },
);

export default TrendComboChart;
