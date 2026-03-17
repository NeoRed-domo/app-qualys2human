import { forwardRef } from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const OS_COLORS: Record<string, string> = {
  Windows: '#1677ff',
  NIX: '#52c41a',
  Autre: '#8c8c8c',
};

interface OsClassItem {
  name: string;
  count: number;
}

interface OsClassDonutProps {
  data: OsClassItem[];
  onClickClass?: (className: string) => void;
}

const OsClassDonut = forwardRef<HTMLDivElement, OsClassDonutProps>(function OsClassDonut({ data, onClickClass }, ref) {
  const chartData = data.map((d) => ({
    name: d.name,
    value: d.count,
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
            onClick={(entry) => onClickClass?.(entry.name)}
            style={{ cursor: onClickClass ? 'pointer' : 'default' }}
          >
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={OS_COLORS[entry.name] || '#8c8c8c'}
              />
            ))}
          </Pie>
          <Tooltip formatter={(value: number | undefined, name: string) => [value ?? 0, name]} />
          <Legend
            content={() => (
              <div style={{ display: 'flex', justifyContent: 'center', gap: 16, flexWrap: 'wrap', marginTop: 8 }}>
                {chartData.map((entry) => (
                  <span key={entry.name} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
                    <span style={{
                      display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
                      background: OS_COLORS[entry.name] || '#8c8c8c',
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

export default OsClassDonut;
