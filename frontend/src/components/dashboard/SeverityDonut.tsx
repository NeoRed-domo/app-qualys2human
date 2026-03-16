import { forwardRef } from 'react';
import { useTranslation } from 'react-i18next';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const SEVERITY_COLORS: Record<number, string> = {
  5: '#cf1322',
  4: '#fa541c',
  3: '#faad14',
  2: '#1677ff',
  1: '#52c41a',
  0: '#8c8c8c',
};

interface SeverityItem {
  severity: number;
  count: number;
}

interface SeverityDonutProps {
  data: SeverityItem[];
  onClickSeverity?: (severity: number) => void;
}

const SeverityDonut = forwardRef<HTMLDivElement, SeverityDonutProps>(function SeverityDonut({ data, onClickSeverity }, ref) {
  const { t } = useTranslation();
  // Sort descending: Urgent (5) → Minimal (1)
  const chartData = [...data]
    .sort((a, b) => b.severity - a.severity)
    .map((d) => ({
      name: t(`severity.${d.severity}`, { defaultValue: `Sev ${d.severity}` }),
      value: d.count,
      severity: d.severity,
    }));

  return (
    <div ref={ref}>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={100}
            dataKey="value"
            nameKey="name"
            onClick={(entry) => onClickSeverity?.(entry.severity)}
            style={{ cursor: onClickSeverity ? 'pointer' : 'default' }}
          >
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={SEVERITY_COLORS[entry.severity] || '#8c8c8c'}
              />
            ))}
          </Pie>
          <Tooltip formatter={(value: number | undefined, name: string) => [value ?? 0, name]} />
          <Legend
            content={() => (
              <div style={{ display: 'flex', justifyContent: 'center', gap: 16, flexWrap: 'wrap', marginTop: 8 }}>
                {chartData.map((entry) => (
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
    </div>
  );
});

export default SeverityDonut;
