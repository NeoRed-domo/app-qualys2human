import './i18n';
import { BrowserRouter } from 'react-router-dom';
import { ConfigProvider, theme as antTheme } from 'antd';
import { useTranslation } from 'react-i18next';
import frFR from 'antd/locale/fr_FR';
import enUS from 'antd/locale/en_US';
import esES from 'antd/locale/es_ES';
import deDE from 'antd/locale/de_DE';
import { AuthProvider } from './contexts/AuthContext';
import { ThemeProvider, useTheme } from './contexts/ThemeContext';
import AppRouter from './router';

const ANTD_LOCALES: Record<string, typeof enUS> = { fr: frFR, en: enUS, es: esES, de: deDE };

function ThemedApp() {
  const { isDark, tokens } = useTheme();
  const { i18n } = useTranslation();
  const antdLocale = ANTD_LOCALES[i18n.language?.slice(0, 2)] || enUS;
  return (
    <ConfigProvider locale={antdLocale} theme={{
      algorithm: isDark ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
      ...(isDark ? {
        token: {
          colorBgContainer: tokens.antColorBgContainer,
          colorBgElevated: tokens.antColorBgElevated,
          colorBgLayout: tokens.antColorBgLayout,
          colorBorderSecondary: tokens.antColorBorderSecondary,
        },
      } : {}),
    }}>
      <BrowserRouter>
        <AuthProvider>
          <AppRouter />
        </AuthProvider>
      </BrowserRouter>
    </ConfigProvider>
  );
}

function App() {
  return (
    <ThemeProvider>
      <ThemedApp />
    </ThemeProvider>
  );
}

export default App;
