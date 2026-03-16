import { forwardRef } from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';

interface LayerItem {
  id: number | null;
  name: string | null;
  color: string | null;
  count: number;
}

interface LayerDonutProps {
  data: LayerItem[];
  onClickLayer?: (layerId: number | null) => void;
}

const UNCLASSIFIED_COLOR = '#8c8c8c';

const LayerDonut = forwardRef<HTMLDivElement, LayerDonutProps>(function LayerDonut({ data, onClickLayer }, ref) {
  const chartData = data.map((d) => ({
    name: d.name || 'Autre',
    value: d.count,
    color: d.color || UNCLASSIFIED_COLOR,
    layerId: d.id,
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
            onClick={(entry) => onClickLayer?.(entry.layerId)}
            style={{ cursor: onClickLayer ? 'pointer' : 'default' }}
          >
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip formatter={(value: number | undefined, name: string) => [value ?? 0, name]} />
          <Legend
            content={() => (
              <div style={{ display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap', marginTop: 8 }}>
                {chartData.map((entry) => (
                  <span key={entry.name} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
                    <span style={{
                      display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
                      background: entry.color,
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

export default LayerDonut;
