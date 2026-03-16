import { forwardRef, useMemo } from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { useTranslation } from 'react-i18next';

// Class colors (same as original OsClassDonut)
const CLASS_COLORS: Record<string, string> = {
  Windows: '#1677ff',
  NIX: '#52c41a',
  Autre: '#8c8c8c',
};

// Type colors — shades derived from their parent class
const TYPE_COLORS: Record<string, string> = {
  'Windows Server': '#1677ff',
  'Windows Desktop': '#4d9aff',
  Ubuntu: '#52c41a',
  RHEL: '#73d13d',
  CentOS: '#95de64',
  Debian: '#389e0d',
  SUSE: '#5cb85c',
  Fedora: '#b7eb8f',
  Linux: '#a0d911',
  Unix: '#7cb305',
  AIX: '#3f8600',
  Solaris: '#d4b106',
  FreeBSD: '#faad14',
  Other: '#8c8c8c',
};

interface OsTypeItem {
  os_class: string;
  os_type: string;
  count: number;
}

interface OsDistributionDonutProps {
  data: OsTypeItem[];
  onClickType?: (osType: string) => void;
}

const OsDistributionDonut = forwardRef<HTMLDivElement, OsDistributionDonutProps>(
  function OsDistributionDonut({ data, onClickType }, ref) {
    const { t } = useTranslation();

    // Inner ring: aggregate by class
    const classData = useMemo(() => {
      const map = new Map<string, number>();
      for (const d of data) {
        map.set(d.os_class, (map.get(d.os_class) || 0) + d.count);
      }
      return Array.from(map.entries())
        .map(([name, value]) => ({ name, value }))
        .sort((a, b) => b.value - a.value);
    }, [data]);

    // Outer ring: individual types, sorted by class then count
    const typeData = useMemo(() => {
      return [...data]
        .sort((a, b) => {
          // Group by class order (Windows first, then NIX, then Autre)
          const classOrder = ['Windows', 'NIX', 'Autre'];
          const ci = classOrder.indexOf(a.os_class) - classOrder.indexOf(b.os_class);
          if (ci !== 0) return ci;
          return b.count - a.count;
        })
        .map((d) => ({
          name: d.os_type,
          value: d.count,
          os_class: d.os_class,
        }));
    }, [data]);

    const formatLabel = (name: string) =>
      name === 'Autre' ? t('common.other') : name;

    return (
      <div ref={ref}>
        <ResponsiveContainer width="100%" height={340}>
          <PieChart>
            {/* Inner ring: OS Class */}
            <Pie
              data={classData}
              cx="50%"
              cy="50%"
              innerRadius={45}
              outerRadius={75}
              dataKey="value"
              nameKey="name"
              isAnimationActive={false}
            >
              {classData.map((entry, i) => (
                <Cell
                  key={`class-${i}`}
                  fill={CLASS_COLORS[entry.name] || '#8c8c8c'}
                  stroke="#fff"
                  strokeWidth={1}
                />
              ))}
            </Pie>

            {/* Outer ring: OS Type */}
            <Pie
              data={typeData}
              cx="50%"
              cy="50%"
              innerRadius={80}
              outerRadius={110}
              dataKey="value"
              nameKey="name"
              onClick={(entry) => onClickType?.(entry.name)}
              style={{ cursor: onClickType ? 'pointer' : 'default' }}
              isAnimationActive={false}
            >
              {typeData.map((entry, i) => (
                <Cell
                  key={`type-${i}`}
                  fill={TYPE_COLORS[entry.name] || CLASS_COLORS[entry.os_class] || '#8c8c8c'}
                  stroke="#fff"
                  strokeWidth={1}
                />
              ))}
            </Pie>

            <Tooltip
              formatter={(value: number, name: string) => [
                value,
                formatLabel(name),
              ]}
            />

            <Legend
              content={() => (
                <div style={{ display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap', marginTop: 8 }}>
                  {typeData.map((entry) => (
                    <span
                      key={entry.name}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11 }}
                    >
                      <span
                        style={{
                          display: 'inline-block',
                          width: 8,
                          height: 8,
                          borderRadius: '50%',
                          background: TYPE_COLORS[entry.name] || CLASS_COLORS[entry.os_class] || '#8c8c8c',
                        }}
                      />
                      {formatLabel(entry.name)} ({entry.value})
                    </span>
                  ))}
                </div>
              )}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  },
);

export default OsDistributionDonut;
