import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Button, Tooltip, Switch, Popover, Tag } from 'antd';
import { ReloadOutlined, SettingOutlined, EyeOutlined, EyeInvisibleOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import api from '../../api/client';
import { useTheme } from '../../contexts/ThemeContext';

export interface TrendWidgetDef {
  key: string;
  label: string;
  content: ReactNode;
}

interface SavedTrendWidget {
  i: string;
  y: number;
  visible: boolean;
}

const WIDGET_GAP = 16;

interface TrendWidgetGridProps {
  widgets: TrendWidgetDef[];
  isAdmin?: boolean;
  hiddenForUsers?: Set<string>;
  onToggleVisibility?: (key: string, visible: boolean) => void;
  userViewMode?: boolean;
}

export default function TrendWidgetGrid({
  widgets,
  isAdmin = false,
  hiddenForUsers = new Set(),
  onToggleVisibility,
  userViewMode = false,
}: TrendWidgetGridProps) {
  const { t } = useTranslation();
  const { tokens } = useTheme();
  const [order, setOrder] = useState<string[]>([]);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [loaded, setLoaded] = useState(false);
  const [dragKey, setDragKey] = useState<string | null>(null);

  const defaultOrder = useMemo(() => widgets.map((w) => w.key), [widgets]);

  // Refs to avoid stale closures in save callbacks
  const orderRef = useRef(order);
  orderRef.current = order;
  const hiddenRef = useRef(hidden);
  hiddenRef.current = hidden;

  useEffect(() => {
    api
      .get('/user/preferences')
      .then((resp) => {
        const saved: SavedTrendWidget[] | undefined = resp.data.trends_layout;
        if (saved && Array.isArray(saved) && saved.length > 0) {
          const sorted = [...saved].sort((a, b) => a.y - b.y);
          setOrder(sorted.map((s) => s.i));
          setHidden(new Set(sorted.filter((s) => !s.visible).map((s) => s.i)));
        } else {
          setOrder(defaultOrder);
        }
      })
      .catch(() => setOrder(defaultOrder))
      .finally(() => setLoaded(true));
  }, []);

  const save = useCallback(
    (newOrder: string[], newHidden: Set<string>) => {
      const trendsLayout = newOrder.map((key, i) => ({
        i: key,
        y: i,
        visible: !newHidden.has(key),
      }));
      api.put('/user/preferences', { trends_layout: trendsLayout }).catch(() => {});
    },
    [],
  );

  const handleReorder = useCallback(
    (fromKey: string, toKey: string) => {
      setOrder((prev) => {
        const fromIdx = prev.indexOf(fromKey);
        const toIdx = prev.indexOf(toKey);
        if (fromIdx === -1 || toIdx === -1 || fromIdx === toIdx) return prev;
        const newOrder = [...prev];
        newOrder.splice(fromIdx, 1);
        newOrder.splice(toIdx, 0, fromKey);
        save(newOrder, hiddenRef.current);
        return newOrder;
      });
    },
    [save],
  );

  const handleToggle = useCallback(
    (key: string, visible: boolean) => {
      setHidden((prev) => {
        const next = new Set(prev);
        if (visible) {
          next.delete(key);
        } else {
          next.add(key);
        }
        save(orderRef.current, next);
        return next;
      });
    },
    [save],
  );

  const handleReset = useCallback(() => {
    setOrder(defaultOrder);
    setHidden(new Set());
    api.delete('/user/preferences/trends-layout').catch(() => {});
  }, [defaultOrder]);

  const widgetMap = new Map(widgets.map((w) => [w.key, w]));

  if (!loaded) return null;

  const orderedKeys = [
    ...order.filter((k) => widgetMap.has(k)),
    ...widgets.map((w) => w.key).filter((k) => !order.includes(k)),
  ];

  const settingsContent = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {orderedKeys.map((key) => {
        const widget = widgetMap.get(key);
        if (!widget) return null;
        return (
          <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Switch
              size="small"
              checked={!hidden.has(key)}
              onChange={(checked) => handleToggle(key, checked)}
            />
            <span style={{ fontSize: 13 }}>{widget.label}</span>
          </div>
        );
      })}
    </div>
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginBottom: 4 }}>
        <Popover content={settingsContent} title={t('trends.chartsVisible')} trigger="click" placement="bottomRight">
          <Button size="small" icon={<SettingOutlined />}>
            {t('trends.display')}
          </Button>
        </Popover>
        <Tooltip title={t('trends.resetLayout')}>
          <Button size="small" icon={<ReloadOutlined />} onClick={handleReset}>
            {t('trends.defaultLayout')}
          </Button>
        </Tooltip>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: WIDGET_GAP }}>
        {orderedKeys.map((key) => {
          if (hidden.has(key)) return null;
          const widget = widgetMap.get(key);
          if (!widget) return null;
          const isHiddenForUsers = hiddenForUsers.has(key);

          // In user-view mode (admin simulating), skip hidden widgets
          if (userViewMode && isHiddenForUsers) return null;

          return (
            <div
              key={key}
              style={{
                opacity: dragKey === key ? 0.3 : isHiddenForUsers && isAdmin ? 0.5 : 1,
                transition: 'opacity 0.15s',
              }}
            >
              <div
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
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <span>&#9776; {widget.label}</span>
                {isAdmin && !userViewMode && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {isHiddenForUsers && (
                      <Tag color="orange" style={{ margin: 0, fontSize: 11 }}>
                        {t('trends.hiddenForUsers')}
                      </Tag>
                    )}
                    <Tooltip title={isHiddenForUsers ? t('trends.showToUsers') : t('trends.hideFromUsers')}>
                      <Switch
                        size="small"
                        checked={!isHiddenForUsers}
                        onChange={(checked) => onToggleVisibility?.(key, checked)}
                      />
                    </Tooltip>
                  </span>
                )}
              </div>
              {widget.content}
            </div>
          );
        })}
      </div>
    </div>
  );
}
