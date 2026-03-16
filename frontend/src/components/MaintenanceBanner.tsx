import { useEffect, useState } from 'react';
import { Alert, Button, Space } from 'antd';
import { ToolOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';

interface ScheduleInfo {
  scheduled: boolean;
  id?: number;
  target_version?: string;
  scheduled_at?: string;
  notification_thresholds?: { minutes_before: number; level: string }[];
  status?: string;
  recent_failure?: { target_version: string; error: string; failed_at: string };
}

export default function MaintenanceBanner() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [schedule, setSchedule] = useState<ScheduleInfo | null>(null);
  const [dismissed, setDismissed] = useState<string | null>(null);
  const [currentTier, setCurrentTier] = useState<string | null>(null);

  // Poll schedule (10s when upgrade running, 60s otherwise)
  useEffect(() => {
    let timer: ReturnType<typeof setInterval>;

    const fetchSchedule = async () => {
      try {
        const resp = await api.get('/upgrade/schedule');
        setSchedule(resp.data);
      } catch {
        setSchedule(null);
      }
    };

    fetchSchedule();
    const interval = schedule?.status === 'running' ? 10_000 : 60_000;
    timer = setInterval(fetchSchedule, interval);
    return () => clearInterval(timer);
  }, [schedule?.status]);

  // Compute current notification tier
  useEffect(() => {
    if (!schedule?.scheduled || !schedule.scheduled_at || !schedule.notification_thresholds) {
      setCurrentTier(null);
      return;
    }

    const update = () => {
      const scheduledAt = new Date(schedule.scheduled_at!);
      const now = new Date();
      const minutesUntil = (scheduledAt.getTime() - now.getTime()) / 60_000;

      if (minutesUntil <= 0) {
        setCurrentTier('danger');
        return;
      }

      // Find the most urgent matching tier (smallest minutes_before that applies)
      const sorted = [...schedule.notification_thresholds!].sort(
        (a, b) => a.minutes_before - b.minutes_before
      );
      const matching = sorted.filter(t => minutesUntil <= t.minutes_before);
      setCurrentTier(matching.length > 0 ? matching[0].level : null);
    };

    update();
    const timer = setInterval(update, 30_000); // Update every 30s
    return () => clearInterval(timer);
  }, [schedule]);

  // Show "upgrade in progress" banner when status is running
  if (schedule?.scheduled && schedule.status === 'running') {
    return (
      <Alert
        banner
        type="warning"
        icon={<ToolOutlined />}
        message={<strong>{t('maintenance.upgradeInProgress')}</strong>}
        style={{ borderRadius: 0 }}
      />
    );
  }

  // Show recent failure banner (admin only)
  if (!schedule?.scheduled && schedule?.recent_failure && user?.profile === 'admin') {
    if (dismissed === 'failure') return null;
    return (
      <Alert
        banner
        type="error"
        icon={<ToolOutlined />}
        message={
          <strong>
            {t('maintenance.upgradeFailed', { error: schedule.recent_failure.error })}
          </strong>
        }
        closable
        onClose={() => setDismissed('failure')}
        style={{ borderRadius: 0 }}
      />
    );
  }

  if (!schedule?.scheduled || !currentTier) return null;

  // Check if user dismissed this tier
  if (dismissed === currentTier) return null;

  const scheduledAt = new Date(schedule.scheduled_at!);
  const now = new Date();
  const totalMinutes = Math.max(0, Math.round((scheduledAt.getTime() - now.getTime()) / 60_000));
  const hours = Math.floor(totalMinutes / 60);
  const mins = totalMinutes % 60;

  const timeStr = scheduledAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const dateStr = scheduledAt.toLocaleDateString();

  // Build human-readable countdown: "1h28", "28 min", or "< 1 min"
  let countdown: string;
  if (totalMinutes < 1) {
    countdown = t('maintenance.lessThanMinute');
  } else if (hours >= 1) {
    countdown = mins > 0 ? `${hours}h${String(mins).padStart(2, '0')}` : `${hours}h`;
  } else {
    countdown = `${mins} min`;
  }

  let message: string;
  let type: 'info' | 'warning' | 'error';

  if (currentTier === 'danger' || totalMinutes <= 15) {
    message = t('maintenance.imminent', { countdown, time: timeStr });
    type = 'error';
  } else if (currentTier === 'warning' || totalMinutes <= 120) {
    message = t('maintenance.warning', { countdown, time: timeStr });
    type = 'warning';
  } else {
    message = t('maintenance.scheduled', { date: dateStr, time: timeStr });
    type = 'info';
  }

  const isAdmin = user?.profile === 'admin';

  const handleCancel = async () => {
    try {
      await api.delete('/upgrade/schedule');
      setSchedule(null);
    } catch {
      // ignore
    }
  };

  return (
    <Alert
      banner
      type={type}
      icon={<ToolOutlined />}
      message={
        <Space>
          <strong>{message}</strong>
          {isAdmin && (
            <Button size="small" danger onClick={handleCancel}>
              {t('maintenance.cancel')}
            </Button>
          )}
        </Space>
      }
      closable
      onClose={() => setDismissed(currentTier)}
      style={{ borderRadius: 0 }}
    />
  );
}
