import { useEffect, useState } from 'react';
import { Alert } from 'antd';
import api from '../api/client';
import { useTheme } from '../contexts/ThemeContext';

interface Props {
  userProfile?: string;
  username?: string;
}

const DISMISS_KEY = (u: string) => `q2h_banner_dismissed_${u}`;

export default function AnnouncementBanner({ userProfile, username }: Props) {
  const { tokens } = useTheme();
  const [banner, setBanner] = useState<{ message: string; color: string; visibility: string } | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.get('/settings/banner')
      .then((r) => { if (!cancelled) setBanner(r.data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!banner || !username) return;
    const stored = localStorage.getItem(DISMISS_KEY(username));
    setDismissed(stored === banner.message);
  }, [banner, username]);

  if (!banner || !banner.message || banner.visibility === 'none') return null;
  if (banner.visibility === 'admin' && userProfile !== 'admin') return null;
  if (dismissed) return null;

  const handleClose = () => {
    if (username) localStorage.setItem(DISMISS_KEY(username), banner.message);
    setDismissed(true);
  };

  const isOther = banner.color === 'other';
  const typeMap: Record<string, 'info' | 'warning' | 'error'> = {
    info: 'info',
    warning: 'warning',
    alert: 'error',
    other: 'info',
  };

  return (
    <Alert
      banner
      type={typeMap[banner.color] || 'info'}
      message={<strong>{banner.message}</strong>}
      closable
      onClose={handleClose}
      style={{
        textAlign: 'center',
        ...(isOther ? { background: tokens.otherBannerBg, borderColor: tokens.otherBannerBorder } : {}),
      }}
    />
  );
}
