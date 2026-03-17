import { createContext, useContext, useState, useMemo, type ReactNode } from 'react';

export interface ThemeTokens {
  // Surfaces
  headerBg: string;
  contentBg: string;
  surfaceSecondary: string;
  // Text
  textOnHeader: string;
  textSecondary: string;
  // Borders
  borderLight: string;
  borderDefault: string;
  // Bandeaux QID
  bannerOrangeBg: string;
  bannerOrangeBorder: string;
  bannerBlueBg: string;
  bannerBlueBorder: string;
  // Row highlight (FullDetail)
  rowHighlightBg: string;
  // Tooltip custom (Recharts)
  tooltipBg: string;
  tooltipBorder: string;
  tooltipText: string;
  // "Other" banner (AnnouncementBanner / Branding preview)
  otherBannerBg: string;
  otherBannerBorder: string;
  // AG Grid
  agGridColorScheme: 'light' | 'dark';
  // Ant Design token overrides (colorBgContainer, etc.)
  antColorBgContainer: string;
  antColorBgElevated: string;
  antColorBgLayout: string;
  antColorBorderSecondary: string;
}

const LIGHT_TOKENS: ThemeTokens = {
  headerBg: '#001529',
  contentBg: '#f0f2f5',
  surfaceSecondary: '#fafafa',
  textOnHeader: '#ffffff',
  textSecondary: '#8c8c8c',
  borderLight: '#f0f0f0',
  borderDefault: '#d9d9d9',
  bannerOrangeBg: '#fff7e6',
  bannerOrangeBorder: '#fa8c16',
  bannerBlueBg: '#e6f4ff',
  bannerBlueBorder: '#1677ff',
  rowHighlightBg: '#e6f4ff',
  tooltipBg: '#ffffff',
  tooltipBorder: '#d9d9d9',
  tooltipText: '#000000',
  otherBannerBg: '#f5f5f5',
  otherBannerBorder: '#d9d9d9',
  agGridColorScheme: 'light',
  antColorBgContainer: '',  // not used in light (Ant defaults)
  antColorBgElevated: '',
  antColorBgLayout: '',
  antColorBorderSecondary: '',
};

const DARK_TOKENS: ThemeTokens = {
  headerBg: '#0a1628',
  contentBg: '#081422',
  surfaceSecondary: '#0e1d35',
  textOnHeader: '#e0e0e0',
  textSecondary: '#8c9bb5',
  borderLight: '#1e2d42',
  borderDefault: '#2a3a50',
  bannerOrangeBg: '#2a1f0d',
  bannerOrangeBorder: '#d48806',
  bannerBlueBg: '#0d1f3c',
  bannerBlueBorder: '#1668dc',
  rowHighlightBg: '#0d1f3c',
  tooltipBg: '#1a2332',
  tooltipBorder: '#2a3a50',
  tooltipText: '#e0e0e0',
  otherBannerBg: '#1a2332',
  otherBannerBorder: '#2a3a50',
  agGridColorScheme: 'dark',
  antColorBgContainer: '#0e1d35',   // Cards, Tables, Inputs — navy blue
  antColorBgElevated: '#132a45',    // Modals, Dropdowns, Popovers
  antColorBgLayout: '#0a1628',      // Layout background
  antColorBorderSecondary: '#1c2d44',
};

interface ThemeContextType {
  isDark: boolean;
  toggleTheme: () => void;
  tokens: ThemeTokens;
}

const ThemeContext = createContext<ThemeContextType>({
  isDark: false,
  toggleTheme: () => {},
  tokens: LIGHT_TOKENS,
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [isDark, setIsDark] = useState(() => localStorage.getItem('q2h_theme') === 'dark');

  const toggleTheme = () => setIsDark((prev) => {
    const next = !prev;
    localStorage.setItem('q2h_theme', next ? 'dark' : 'light');
    return next;
  });

  const tokens = isDark ? DARK_TOKENS : LIGHT_TOKENS;
  const value = useMemo(() => ({ isDark, toggleTheme, tokens }), [isDark, tokens]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);
