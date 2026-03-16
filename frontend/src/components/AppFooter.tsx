import { useEffect, useState } from 'react';
import { Layout, Typography } from 'antd';
import { useTheme } from '../contexts/ThemeContext';

const { Text } = Typography;

export default function AppFooter({ showVersion = true }: { showVersion?: boolean }) {
  const { tokens } = useTheme();
  const [footerText, setFooterText] = useState('');
  const [version, setVersion] = useState('');

  useEffect(() => {
    fetch('/api/branding/settings')
      .then((resp) => {
        if (!resp.ok) throw new Error('Failed to load settings');
        return resp.json();
      })
      .then((data) => setFooterText(data.footer_text || ''))
      .catch(() => setFooterText(''));

    fetch('/api/health')
      .then((resp) => resp.json())
      .then((data) => setVersion(data.version || ''))
      .catch(() => {});
  }, []);

  const displayText = footerText || 'Qualys2Human';
  const year = new Date().getFullYear();

  return (
    <Layout.Footer style={{ textAlign: 'center', padding: '12px 24px', background: tokens.contentBg }}>
      <Text type="secondary" style={{ fontSize: 13 }}>
        {displayText} - NeoRed - Since 2026 - {year}
        {showVersion && version && <> - v{version}</>}
      </Text>
    </Layout.Footer>
  );
}
