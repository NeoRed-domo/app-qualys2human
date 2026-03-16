import { useEffect, useRef, useState } from 'react';
import { Alert, Progress } from 'antd';
import { SyncOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import api from '../api/client';

interface Operation {
  type: string;
  progress: number;
  detail: string;
}

interface StatusData {
  busy: boolean;
  operations: Operation[];
}

export default function BusyBanner() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<StatusData | null>(null);
  const wasBusyRef = useRef(false);

  const OP_LABELS: Record<string, string> = {
    import: t('modals.busyImport'),
    reclassify: t('modals.busyCategorization'),
  };

  useEffect(() => {
    let timer: ReturnType<typeof setInterval>;
    let cancelled = false;

    const poll = async () => {
      try {
        const r = await api.get('/settings/status');
        if (cancelled) return;
        const data: StatusData = r.data;

        // If just finished being busy → reload page to refresh all data
        if (wasBusyRef.current && !data.busy) {
          wasBusyRef.current = false;
          setStatus(null);
          window.location.reload();
          return;
        }

        wasBusyRef.current = data.busy;
        setStatus(data);
      } catch {
        // silently ignore
      }
    };

    poll();
    timer = setInterval(poll, 3000);
    return () => { cancelled = true; clearInterval(timer); };
  }, []);

  if (!status?.busy) return null;

  const descriptions = status.operations.map((op) => {
    const label = OP_LABELS[op.type] || op.type;
    return `${label} (${op.progress}%)${op.detail ? ` — ${op.detail}` : ''}`;
  });

  const avgProgress = Math.round(
    status.operations.reduce((sum, op) => sum + op.progress, 0) / status.operations.length,
  );

  return (
    <Alert
      banner
      type="info"
      icon={<SyncOutlined spin />}
      message={
        <span style={{ display: 'flex', alignItems: 'center', gap: 16, justifyContent: 'center' }}>
          <strong>{descriptions.join(' | ')}</strong>
          <Progress
            percent={avgProgress}
            size="small"
            style={{ width: 120, marginBottom: 0 }}
            strokeColor="#1677ff"
          />
        </span>
      }
    />
  );
}
