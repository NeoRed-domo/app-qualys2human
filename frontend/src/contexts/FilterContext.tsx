import { createContext, useContext, useState, useCallback, useEffect, useRef, type ReactNode } from 'react';
import api from '../api/client';
import { useAuth } from './AuthContext';

const STORAGE_KEY_PREFIX = 'q2h_filters_';
const LEGACY_STORAGE_KEY = 'q2h_filters';

function getStorageKey(username: string): string {
  return STORAGE_KEY_PREFIX + username;
}

interface FilterState {
  severities: number[];
  types: string[];
  layers: number[];
  osClasses: string[];
  freshness: string;
  dateFrom: string | null;
  dateTo: string | null;
  reportId: number | null;
}

interface FilterContextValue extends FilterState {
  setSeverities: (s: number[]) => void;
  setTypes: (t: string[]) => void;
  setLayers: (l: number[]) => void;
  setOsClasses: (o: string[]) => void;
  setFreshness: (f: string) => void;
  setDateFrom: (d: string | null) => void;
  setDateTo: (d: string | null) => void;
  setReportId: (id: number | null) => void;
  resetFilters: () => void;
  applyEnterprisePreset: () => Promise<void>;
  toQueryString: () => string;
  ready: boolean;
}

const FilterContext = createContext<FilterContextValue | undefined>(undefined);

export function FilterProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [severities, setSeverities] = useState<number[]>([]);
  const [types, setTypes] = useState<string[]>([]);
  const [layers, setLayers] = useState<number[]>([]);
  const [osClasses, setOsClasses] = useState<string[]>([]);
  const [freshness, setFreshness] = useState<string>('active');
  const [dateFrom, setDateFrom] = useState<string | null>(null);
  const [dateTo, setDateTo] = useState<string | null>(null);
  const [reportId, setReportId] = useState<number | null>(null);
  const [ready, setReady] = useState(false);

  // Track current username for use in callbacks
  const usernameRef = useRef<string | null>(null);
  usernameRef.current = user?.username ?? null;

  // Store enterprise defaults so resetFilters can restore them
  const enterpriseDefaults = useRef<{ severities: number[]; types: string[]; layers: number[]; osClasses: string[]; freshness: string }>({
    severities: [],
    types: [],
    layers: [],
    osClasses: [],
    freshness: 'active',
  });

  // Load filters when user changes: localStorage (returning user) or enterprise preset (new user)
  useEffect(() => {
    if (!user) {
      setReady(false);
      return;
    }

    const load = async () => {
      // Always fetch enterprise preset (needed for resetFilters)
      try {
        const resp = await api.get('/presets/enterprise');
        const { severities: sev, types: typ, layers: lay, os_classes: osc, freshness: fr } = resp.data;
        enterpriseDefaults.current = {
          severities: Array.isArray(sev) ? sev : [],
          types: Array.isArray(typ) ? typ : [],
          layers: Array.isArray(lay) ? lay : [],
          osClasses: Array.isArray(osc) ? osc : [],
          freshness: typeof fr === 'string' ? fr : 'active',
        };
      } catch {
        // keep empty defaults
      }

      const key = getStorageKey(user.username);

      // Migration: if legacy key exists and no per-user key, migrate
      const legacy = localStorage.getItem(LEGACY_STORAGE_KEY);
      if (legacy && !localStorage.getItem(key)) {
        localStorage.setItem(key, legacy);
        localStorage.removeItem(LEGACY_STORAGE_KEY);
      }

      // Check localStorage for user's saved filters
      const saved = localStorage.getItem(key);
      if (saved) {
        try {
          const p = JSON.parse(saved);
          if (Array.isArray(p.severities)) setSeverities(p.severities);
          if (Array.isArray(p.types)) setTypes(p.types);
          if (Array.isArray(p.layers)) setLayers(p.layers);
          if (Array.isArray(p.osClasses)) setOsClasses(p.osClasses);
          if (typeof p.freshness === 'string') setFreshness(p.freshness);
        } catch {
          // Corrupted — fall through to enterprise defaults
          applyEnterprise();
        }
      } else {
        // First visit — apply enterprise preset
        applyEnterprise();
      }

      setReady(true);
    };

    const applyEnterprise = () => {
      const d = enterpriseDefaults.current;
      if (d.severities.length > 0) setSeverities(d.severities);
      if (d.types.length > 0) setTypes(d.types);
      if (d.layers.length > 0) setLayers(d.layers);
      setOsClasses(d.osClasses);
      setFreshness(d.freshness);
    };

    load();
  }, [user?.username]);

  // Persist filters to localStorage whenever they change (per-user)
  useEffect(() => {
    if (!ready || !user) return;
    localStorage.setItem(getStorageKey(user.username), JSON.stringify({
      severities, types, layers, osClasses, freshness,
    }));
  }, [severities, types, layers, osClasses, freshness, ready, user]);

  const resetFilters = useCallback(() => {
    // Reset to enterprise defaults and clear saved preferences
    const username = usernameRef.current;
    if (username) localStorage.removeItem(getStorageKey(username));
    setSeverities(enterpriseDefaults.current.severities);
    setTypes(enterpriseDefaults.current.types);
    setLayers(enterpriseDefaults.current.layers);
    setOsClasses(enterpriseDefaults.current.osClasses);
    setFreshness(enterpriseDefaults.current.freshness);
    setDateFrom(null);
    setDateTo(null);
    setReportId(null);
  }, []);

  const applyEnterprisePreset = useCallback(async () => {
    // Re-fetch enterprise preset to get latest version
    try {
      const resp = await api.get('/presets/enterprise');
      const { severities: sev, types: typ, layers: lay, os_classes: osc, freshness: fr } = resp.data;
      enterpriseDefaults.current = {
        severities: Array.isArray(sev) ? sev : [],
        types: Array.isArray(typ) ? typ : [],
        layers: Array.isArray(lay) ? lay : [],
        osClasses: Array.isArray(osc) ? osc : [],
        freshness: typeof fr === 'string' ? fr : 'active',
      };
    } catch {
      // Use cached defaults
    }

    const d = enterpriseDefaults.current;
    setSeverities(d.severities);
    setTypes(d.types);
    setLayers(d.layers);
    setOsClasses(d.osClasses);
    setFreshness(d.freshness);
    setDateFrom(null);
    setDateTo(null);
    setReportId(null);

    // Clear per-user storage (will be recreated by persist effect)
    const username = usernameRef.current;
    if (username) localStorage.removeItem(getStorageKey(username));
  }, []);

  const toQueryString = useCallback(() => {
    const params = new URLSearchParams();
    if (severities.length > 0) params.set('severities', severities.join(','));
    if (types.length > 0) params.set('types', types.join(','));
    if (layers.length > 0) params.set('layers', layers.join(','));
    if (osClasses.length > 0) params.set('os_classes', osClasses.join(','));
    if (freshness && freshness !== 'active') params.set('freshness', freshness);
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    if (reportId) params.set('report_id', String(reportId));
    return params.toString();
  }, [severities, types, layers, osClasses, freshness, dateFrom, dateTo, reportId]);

  return (
    <FilterContext.Provider
      value={{
        severities, types, layers, osClasses, freshness, dateFrom, dateTo, reportId,
        setSeverities, setTypes, setLayers, setOsClasses, setFreshness, setDateFrom, setDateTo, setReportId,
        resetFilters, applyEnterprisePreset, toQueryString, ready,
      }}
    >
      {children}
    </FilterContext.Provider>
  );
}

export function useFilters() {
  const ctx = useContext(FilterContext);
  if (!ctx) throw new Error('useFilters must be used within FilterProvider');
  return ctx;
}
