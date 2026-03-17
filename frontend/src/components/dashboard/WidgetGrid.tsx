import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Button, Tooltip } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import api from '../../api/client';
import { useTheme } from '../../contexts/ThemeContext';

export interface WidgetDef {
  key: string;
  label: string;
  content: ReactNode;
}

const DEFAULT_ORDER = ['kpi', 'distributions', 'category', 'topVulns', 'topHosts'];
const WIDGET_GAP = 16;

interface WidgetGridProps {
  widgets: WidgetDef[];
}

export default function WidgetGrid({ widgets }: WidgetGridProps) {
  const { t } = useTranslation();
  const { tokens } = useTheme();
  const [order, setOrder] = useState<string[]>(DEFAULT_ORDER);
  const [loaded, setLoaded] = useState(false);
  const [dragKey, setDragKey] = useState<string | null>(null);

  // Load saved order from preferences (backward-compatible with old layout format)
  useEffect(() => {
    api.get('/user/preferences')
      .then((resp) => {
        const saved = resp.data.layout;
        if (saved && Array.isArray(saved) && saved.length > 0) {
          const sorted = [...saved].sort((a: any, b: any) => a.y - b.y);
          setOrder(sorted.map((l: any) => l.i));
        }
      })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  const saveOrder = useCallback((newOrder: string[]) => {
    // Save as layout format for backward compatibility
    const layout = newOrder.map((key, i) => ({
      i: key, x: 0, y: i, w: 12, h: 1,
    }));
    api.put('/user/preferences', { layout }).catch(() => {});
  }, []);

  const handleReorder = useCallback((fromKey: string, toKey: string) => {
    setOrder((prev) => {
      const fromIdx = prev.indexOf(fromKey);
      const toIdx = prev.indexOf(toKey);
      if (fromIdx === -1 || toIdx === -1 || fromIdx === toIdx) return prev;
      const newOrder = [...prev];
      newOrder.splice(fromIdx, 1);
      newOrder.splice(toIdx, 0, fromKey);
      saveOrder(newOrder);
      return newOrder;
    });
  }, [saveOrder]);

  const handleReset = useCallback(() => {
    setOrder(DEFAULT_ORDER);
    api.delete('/user/preferences/layout').catch(() => {});
  }, []);

  const widgetMap = new Map(widgets.map((w) => [w.key, w]));

  if (!loaded) return null;

  // Ensure all widget keys are in the order (handles new widgets added later)
  const orderedKeys = [
    ...order.filter((k) => widgetMap.has(k)),
    ...widgets.map((w) => w.key).filter((k) => !order.includes(k)),
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 4 }}>
        <Tooltip title={t('trends.resetLayout')}>
          <Button size="small" icon={<ReloadOutlined />} onClick={handleReset}>
            {t('trends.defaultLayout')}
          </Button>
        </Tooltip>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: WIDGET_GAP }}>
        {orderedKeys.map((key) => {
          const widget = widgetMap.get(key);
          if (!widget) return null;
          return (
            <div
              key={key}
              style={{ opacity: dragKey === key ? 0.5 : 1, transition: 'opacity 0.15s' }}
            >
              <div
                className="widget-drag-handle"
                draggable
                onDragStart={(e) => {
                  setDragKey(key);
                  e.dataTransfer.effectAllowed = 'move';
                }}
                onDragEnd={() => setDragKey(null)}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.dataTransfer.dropEffect = 'move';
                }}
                onDrop={() => {
                  if (dragKey && dragKey !== key) {
                    handleReorder(dragKey, key);
                  }
                  setDragKey(null);
                }}
                style={{
                  cursor: 'grab',
                  padding: '4px 12px',
                  fontSize: 12,
                  color: tokens.textSecondary,
                  borderBottom: `1px solid ${tokens.borderLight}`,
                  background: tokens.surfaceSecondary,
                  borderRadius: '8px 8px 0 0',
                  userSelect: 'none',
                  fontWeight: 500,
                }}
              >
                &#9776; {widget.label}
              </div>
              <div style={{ padding: 12 }}>
                {widget.content}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
