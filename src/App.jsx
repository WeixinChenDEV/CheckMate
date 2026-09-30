import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Home as HomeIcon, User, Sparkles, LayoutGrid, CalendarDays } from 'lucide-react';

import { THEMES, WEATHER_FALLBACK, buildDisplayTheme, DEFAULT_APP_PREFS } from './constants/data';
import { api, clearToken, getToken } from './api';

import UserLogin from './pages/UserLogin';
import HomeDashboard from './pages/HomeDashboard';
import QuickScenariosPage from './pages/QuickScenariosPage';
import CalendarPage from './pages/CalendarPage';
import MyProfileAndLibrary from './pages/MyProfileAndLibrary';
import SystemSettings from './pages/SystemSettings';
import ChecklistDetail from './pages/ChecklistDetail';
import CreateNewTrip from './pages/CreateNewTrip';
import PackingSuccess from './pages/PackingSuccess';
import AIChatAssistant from './pages/AIChatAssistant';
import { uiT } from './uiCopy';

const NavItem = ({ icon: Icon, label, active, onClick, theme }) => (
  <button
    onClick={onClick}
    className={`flex flex-col items-center space-y-1 transition-all duration-300 ${
      active ? `${theme.primaryText} scale-105` : `${theme.navMuted} hover:opacity-95`
    }`}
  >
    <Icon size={26} strokeWidth={active ? 2.5 : 2} />
    <span className="text-[10px] font-bold tracking-wide uppercase">{label}</span>
  </button>
);

const ensureUniqueItemIds = (items) => {
  const seen = new Set();
  return (Array.isArray(items) ? items : []).map((it, idx) => {
    const rawId = it?.id;
    const normalized = rawId == null ? '' : String(rawId).trim();
    let nextId = normalized;
    if (!nextId || seen.has(nextId)) {
      nextId = `it_${Date.now()}_${idx}_${Math.random().toString(36).slice(2, 8)}`;
    }
    seen.add(nextId);
    return { ...(it || {}), id: nextId };
  });
};

/** 接口返回的 items 不含 checked；合并时保留当前列表里已勾选状态，避免反复丢状态 */
const mergeItemsPreserveCheckedFromLocal = (localItems, serverItems) => {
  const checkedById = new Map();
  (localItems || []).forEach((it) => {
    if (it && it.id != null && it.checked) checkedById.set(String(it.id), true);
  });
  return (serverItems || []).map((it) => {
    if (!it || it.id == null) return it;
    const id = String(it.id);
    if (checkedById.get(id)) return { ...it, checked: true };
    return it;
  });
};

export default function App() {
  const [currentView, setCurrentView] = useState('login');
  const [scenarios, setScenarios] = useState([]);
  const [friends, setFriends] = useState([]);
  const [history, setHistory] = useState([]);
  const [activeScenarioId, setActiveScenarioId] = useState(null);
  /** null = my list; number = shared list owner's user id */
  const [activeScenarioOwnerId, setActiveScenarioOwnerId] = useState(null);
  /** 仅当从「我的」页进入清单详情时为 true，用于限制增删改物品仅在该入口可用 */
  const [detailAllowManageItems, setDetailAllowManageItems] = useState(false);
  const [checkedItems, setCheckedItems] = useState({});
  const [activeTab, setActiveTab] = useState('home');
  const [currentThemeKey, setCurrentThemeKey] = useState('cinnamon');
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [sessionRestoring, setSessionRestoring] = useState(() => !!getToken());
  const [weather, setWeather] = useState(WEATHER_FALLBACK);
  const [weatherLoading, setWeatherLoading] = useState(false);
  const [weatherError, setWeatherError] = useState(null);
  /** Same query params as last /api/weather call — used for /api/weather/detail. */
  const [weatherFetchParams, setWeatherFetchParams] = useState({});
  const [weatherDetail, setWeatherDetail] = useState(null);
  const [appPrefs, setAppPrefs] = useState(DEFAULT_APP_PREFS);
  const [meInitialSegment, setMeInitialSegment] = useState(null);
  const [lastPacked, setLastPacked] = useState(null);
  const [quickTemplateDraft, setQuickTemplateDraft] = useState(null);
  const [createTripSaving, setCreateTripSaving] = useState(false);
  const [createTripError, setCreateTripError] = useState(null);
  const [scenarioSavingId, setScenarioSavingId] = useState(null);
  const [scenarioSaveError, setScenarioSaveError] = useState(null);
  const appPrefsRef = useRef(DEFAULT_APP_PREFS);
  const currentThemeKeyRef = useRef(currentThemeKey);
  const scenarioUpdateStateRef = useRef({});

  const t = useMemo(() => uiT(appPrefs?.language || 'en'), [appPrefs?.language]);

  const THEME = useMemo(
    () => buildDisplayTheme(currentThemeKey, appPrefs.dark_mode),
    [currentThemeKey, appPrefs.dark_mode],
  );

  useEffect(() => {
    currentThemeKeyRef.current = currentThemeKey;
  }, [currentThemeKey]);

  useEffect(() => {
    appPrefsRef.current = appPrefs;
  }, [appPrefs]);

  useEffect(() => {
    document.body.style.backgroundColor = appPrefs.dark_mode ? '#0f0e0c' : '#FFFBF5';
    return () => {
      document.body.style.backgroundColor = '';
    };
  }, [appPrefs.dark_mode]);

  const loadWeather = useCallback(async () => {
    setWeatherLoading(true);
    setWeatherError(null);
    const coords = await new Promise((resolve) => {
      if (!appPrefsRef.current.auto_location) {
        resolve(null);
        return;
      }
      if (typeof navigator === 'undefined' || !navigator.geolocation) {
        resolve(null);
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) =>
          resolve({
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            label: 'Near you',
          }),
        () => resolve(null),
        { enableHighAccuracy: false, timeout: 12000, maximumAge: 600000 },
      );
    });
    try {
      const params = coords ? { lat: coords.lat, lon: coords.lon, label: coords.label } : {};
      const [weatherRes, detailRes] = await Promise.allSettled([
        api.getWeather(params),
        api.getWeatherDetail(params),
      ]);
      if (weatherRes.status !== 'fulfilled') {
        throw weatherRes.reason || new Error('Weather could not be loaded.');
      }
      const data = weatherRes.value;
      const detail = detailRes.status === 'fulfilled' ? detailRes.value : null;
      setWeatherFetchParams(params);
      setWeather({ ...WEATHER_FALLBACK, ...data });
      setWeatherDetail(detail || null);
    } catch (e) {
      const msg = e?.message || 'Weather could not be loaded.';
      setWeatherError(msg);
      setWeatherDetail(null);
      setWeather((prev) =>
        prev && prev.location && prev.location !== WEATHER_FALLBACK.location ? prev : WEATHER_FALLBACK,
      );
    } finally {
      setWeatherLoading(false);
    }
  }, []);

  const refreshData = useCallback(async () => {
    const [scenariosData, friendsData, historyData, prefs] = await Promise.all([
      api.getScenarios(),
      api.getFriends(),
      api.getHistory(),
      api.getPreferences(),
    ]);
    const normalizedScenarios = (Array.isArray(scenariosData) ? scenariosData : []).map((s) => ({
      ...s,
      items: ensureUniqueItemIds(s?.items),
    }));
    setScenarios(normalizedScenarios);
    setFriends(Array.isArray(friendsData) ? friendsData : []);
    setHistory(Array.isArray(historyData) ? historyData : []);
    if (prefs && prefs.theme_key && THEMES[prefs.theme_key]) {
      setCurrentThemeKey(prefs.theme_key);
    }
    const nextPrefs = {
      notifications: prefs?.notifications !== false,
      sounds: prefs?.sounds !== false,
      auto_location: prefs?.auto_location !== false,
      dark_mode: !!prefs?.dark_mode,
      language: prefs?.language === 'zh' ? 'zh' : 'en',
    };
    setAppPrefs(nextPrefs);
    appPrefsRef.current = nextPrefs;
    return nextPrefs;
  }, []);

  useEffect(() => {
    let cancelled = false;
    const token = getToken();
    if (!token) {
      setSessionRestoring(false);
      return undefined;
    }

    (async () => {
      try {
        const user = await api.getMe();
        if (cancelled) return;
        setCurrentUser(user);
        await refreshData();
        await loadWeather();
        setCurrentView('home');
      } catch {
        if (!cancelled) clearToken();
      } finally {
        if (!cancelled) setSessionRestoring(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [refreshData, loadWeather]);

  /** 切回浏览器标签或窗口时同步好友、行程等（避免需手动整页刷新） */
  const lastVisibilityRefreshRef = useRef(0);
  useEffect(() => {
    if (!currentUser) return undefined;
    const onVisible = () => {
      if (document.visibilityState !== 'visible') return;
      const now = Date.now();
      if (now - lastVisibilityRefreshRef.current < 2500) return;
      lastVisibilityRefreshRef.current = now;
      void refreshData();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [currentUser, refreshData]);

  /** 在主界面停留时定期拉取数据，便于跨账号协作（如好友通过申请）尽快反映 */
  useEffect(() => {
    if (!currentUser || sessionRestoring) return undefined;
    if (!['home', 'me', 'quick', 'calendar'].includes(currentView)) return undefined;
    const id = setInterval(() => {
      void refreshData();
    }, 8000);
    return () => clearInterval(id);
  }, [currentUser, currentView, sessionRestoring, refreshData]);

  const handleAuth = useCallback(
    async ({ username, password, mode }) => {
      if (mode === 'register') {
        const data = await api.register({ username, password });
        setCurrentUser(data.user);
      } else {
        const data = await api.login({ username, password });
        setCurrentUser(data.user);
      }
      await refreshData();
      await loadWeather();
      setCurrentView('home');
    },
    [refreshData, loadWeather],
  );

  const handleSelectScenario = useCallback(
    (id, ownerUserId = null, allowManageItems = false) => {
      setActiveScenarioId(id);
      setActiveScenarioOwnerId(ownerUserId);
      setDetailAllowManageItems(!!allowManageItems);
      const sc = scenarios.find(
        (s) => s.id === id && (s.owner_user_id ?? null) === (ownerUserId ?? null),
      );
      const next = {};
      (sc?.items || []).forEach((it) => {
        if (it && it.id != null && it.checked) next[it.id] = true;
      });
      setCheckedItems(next);
      setCurrentView('detail');
    },
    [scenarios],
  );

  const handleTabChange = useCallback(
    (tab) => {
      setActiveTab(tab);
      setCurrentView(tab);
      if (tab === 'me' && currentUser) {
        void refreshData();
      }
    },
    [currentUser, refreshData],
  );

  const handleLogout = useCallback(() => {
    api.logout();
    setCurrentUser(null);
    setScenarios([]);
    setFriends([]);
    setHistory([]);
    setWeather(WEATHER_FALLBACK);
    setWeatherFetchParams({});
    setWeatherDetail(null);
    setWeatherError(null);
    setWeatherLoading(false);
    setActiveScenarioOwnerId(null);
    setDetailAllowManageItems(false);
    setAppPrefs(DEFAULT_APP_PREFS);
    appPrefsRef.current = DEFAULT_APP_PREFS;
    setCurrentThemeKey('cinnamon');
    currentThemeKeyRef.current = 'cinnamon';
    setCurrentView('login');
    setActiveTab('home');
    setSessionRestoring(false);
    setMeInitialSegment(null);
    setLastPacked(null);
    setQuickTemplateDraft(null);
  }, []);

  const handleChangeTheme = async (key) => {
    setCurrentThemeKey(key);
    currentThemeKeyRef.current = key;
    try {
      await api.putPreferences({ theme_key: key });
    } catch {
      /* keep local theme if API fails */
    }
  };

  const handleChangeAppPrefs = useCallback(async (partial) => {
    const prev = appPrefsRef.current;
    const next = { ...prev, ...partial };
    setAppPrefs(next);
    appPrefsRef.current = next;
    try {
      await api.putPreferences({ theme_key: currentThemeKeyRef.current, ...partial });
    } catch {
      try {
        const prefs = await api.getPreferences();
        const restored = {
          notifications: prefs?.notifications !== false,
          sounds: prefs?.sounds !== false,
          auto_location: prefs?.auto_location !== false,
          dark_mode: !!prefs?.dark_mode,
          language: prefs?.language === 'zh' ? 'zh' : 'en',
        };
        setAppPrefs(restored);
        appPrefsRef.current = restored;
        if (prefs?.theme_key && THEMES[prefs.theme_key]) {
          setCurrentThemeKey(prefs.theme_key);
          currentThemeKeyRef.current = prefs.theme_key;
        }
      } catch {
        setAppPrefs(prev);
        appPrefsRef.current = prev;
      }
    }
  }, []);

  const handleSaveProfile = useCallback(async ({ displayName, avatarStyle }) => {
    if (!currentUser?.username) return;
    const user = await api.putMe({ display_name: displayName, avatar_style: avatarStyle });
    setCurrentUser(user);
  }, [currentUser]);

  const handleChangePassword = useCallback(async ({ currentPassword, newPassword }) => {
    await api.putPassword({
      current_password: currentPassword,
      new_password: newPassword,
    });
  }, []);

  const handleDeleteAccount = useCallback(async () => {
    await api.deleteAccount();
    handleLogout();
  }, [handleLogout]);

  const handleDeleteScenario = async (id) => {
    await api.deleteScenario(id);
    await refreshData();
  };

  const handleDeleteScenariosBatch = useCallback(
    async (ids) => {
      const clean = Array.from(new Set((Array.isArray(ids) ? ids : []).filter(Boolean)));
      if (!clean.length) return;
      await Promise.all(clean.map((id) => api.deleteScenario(id)));
      await refreshData();
    },
    [refreshData],
  );

  const handleDeleteFriend = async (id) => {
    await api.deleteFriend(id);
    await refreshData();
  };

  const handleSaveTrip = async (newScenario) => {
    await api.createScenario({
      id: newScenario.id,
      name: newScenario.name,
      icon: newScenario.icon,
      theme: newScenario.theme,
      items: newScenario.items,
      trip_start_at: newScenario.trip_start_at ?? null,
      trip_end_at: newScenario.trip_end_at ?? null,
    });
    await refreshData();
  };

  /** 带着 AI 所选物品进入「新建行程」页，由用户填写出发时间后再保存 */
  const handleCreateTripFromAssistant = useCallback(
    ({ name, items }) => {
      const cleanName = String(name || '').trim() || `AI Trip ${new Date().toLocaleDateString()}`;
      const cleanItems = ensureUniqueItemIds(Array.isArray(items) ? items : []);
      if (!cleanItems.length) return;
      setQuickTemplateDraft({
        name: cleanName,
        icon: 'Backpack',
        theme: { bg: THEME.primaryLight, text: THEME.primaryText },
        items: cleanItems,
        trip_start_at: null,
        trip_end_at: null,
      });
      setIsChatOpen(false);
      setCurrentView('create');
    },
    [THEME.primaryLight, THEME.primaryText],
  );

  const handleAppendAssistantItems = useCallback(
    async ({ scenarioId, items }) => {
      const target = scenarios.find((s) => s.id === scenarioId);
      if (!target) throw new Error('Trip not found.');
      if (target.access === 'shared') throw new Error('This trip is view-only.');

      const incoming = Array.isArray(items) ? items : [];
      if (!incoming.length) throw new Error('No items to import.');

      const normalize = (v) => String(v || '').trim().toLowerCase().replace(/\s+/g, ' ');
      const exists = new Set((target.items || []).map((it) => normalize(it?.text)));
      const nextItems = ensureUniqueItemIds(target.items || []);
      const defaultAssignee =
        target.access === 'shared_edit' && currentUser?.db_id != null
          ? `u${currentUser.db_id}`
          : 'me';
      incoming.forEach((it) => {
        const text = String(it?.text || '').trim();
        if (!text) return;
        const key = normalize(text);
        if (exists.has(key)) return;
        exists.add(key);
        nextItems.push({
          id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
          text,
          critical: !!it?.critical,
          assignedTo: defaultAssignee,
        });
      });

      await api.updateScenario(scenarioId, { items: nextItems });
      await refreshData();
    },
    [currentUser?.db_id, refreshData, scenarios],
  );

  const handleAppendWeatherItems = useCallback(
    async ({ scenarioId, items, tipDate }) => {
      const target = scenarios.find((s) => s.id === scenarioId);
      if (!target) throw new Error('Trip not found.');
      if (target.access === 'shared') throw new Error('This trip is view-only.');
      const targetDate = tipDate ? new Date(tipDate) : new Date();
      const startAt = target.trip_start_at ? new Date(target.trip_start_at) : null;
      const isToday =
        !!startAt &&
        !Number.isNaN(targetDate.getTime()) &&
        !Number.isNaN(startAt.getTime()) &&
        startAt.getFullYear() === targetDate.getFullYear() &&
        startAt.getMonth() === targetDate.getMonth() &&
        startAt.getDate() === targetDate.getDate();
      if (!isToday) throw new Error('Weather tips can only be added to trips on the selected date.');

      const incoming = Array.isArray(items) ? items : [];
      if (!incoming.length) throw new Error('No items to import.');

      const normalize = (v) => String(v || '').trim().toLowerCase().replace(/\s+/g, ' ');
      const exists = new Set((target.items || []).map((it) => normalize(it?.text)));
      const nextItems = ensureUniqueItemIds(target.items || []);
      const defaultAssignee =
        target.access === 'shared_edit' && currentUser?.db_id != null
          ? `u${currentUser.db_id}`
          : 'me';
      incoming.forEach((it) => {
        const text = String(it?.text || '').trim();
        if (!text) return;
        const key = normalize(text);
        if (exists.has(key)) return;
        exists.add(key);
        nextItems.push({
          id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
          text,
          critical: !!it?.critical,
          assignedTo: defaultAssignee,
        });
      });

      await api.updateScenario(scenarioId, { items: nextItems });
      await refreshData();
    },
    [currentUser?.db_id, refreshData, scenarios],
  );

  const handleOpenTripsFromAssistant = useCallback(() => {
    setIsChatOpen(false);
    setActiveTab('me');
    setMeInitialSegment('scenarios');
    setCurrentView('me');
  }, []);

  const handleUpdateScenario = async (updated) => {
    const id = updated?.id;
    if (!id) return;

    // Optimistic UI update so the user sees changes immediately.
    setScenarios((prev) =>
      prev.map((s) => {
        if (s.id !== id) return s;
        if ((s.owner_user_id ?? null) !== (activeScenarioOwnerId ?? null)) return s;
        return { ...s, ...updated };
      }),
    );

    const existing = scenarioUpdateStateRef.current[id] || { inFlight: false, next: null };
    if (existing.inFlight) {
      scenarioUpdateStateRef.current[id] = { ...existing, next: updated };
      return;
    }

    scenarioUpdateStateRef.current[id] = { inFlight: true, next: null };
    setScenarioSavingId(id);
    setScenarioSaveError(null);

    let current = updated;
    try {
      while (current) {
        const isSharedEdit =
          current?.access === 'shared_edit' || (activeScenarioOwnerId ?? null) !== null;
        const payload = isSharedEdit ? { items: current.items } : current;
        const saved = await api.updateScenario(id, payload);
        setScenarios((prev) =>
          prev.map((s) => {
            if (s.id !== id) return s;
            if ((s.owner_user_id ?? null) !== (activeScenarioOwnerId ?? null)) return s;
            const mergedItems = mergeItemsPreserveCheckedFromLocal(s.items, saved.items);
            return {
              ...saved,
              items: mergedItems,
              owner_user_id: s.owner_user_id,
              access: s.access,
              owner_username: s.owner_username,
              owner_avatar: s.owner_avatar,
              share_recipients: s.share_recipients,
            };
          }),
        );

        const st = scenarioUpdateStateRef.current[id] || { inFlight: true, next: null };
        current = st.next;
        scenarioUpdateStateRef.current[id] = { ...st, next: null };
      }
    } catch (e) {
      const msg = e?.message || '保存失败，请稍后重试。';
      setScenarioSaveError(msg);
    } finally {
      const st = scenarioUpdateStateRef.current[id] || { inFlight: true, next: null };
      scenarioUpdateStateRef.current[id] = { ...st, inFlight: false, next: null };
      setScenarioSavingId((prev) => (prev === id ? null : prev));
    }
  };

  const handleUpdateScenarioSchedule = useCallback(
    async (scenarioId, payload) => {
      await api.updateScenario(scenarioId, payload);
      await refreshData();
    },
    [refreshData],
  );

  const handleCreateTripAtDate = useCallback((isoDate) => {
    const d = isoDate ? new Date(isoDate) : new Date();
    const label = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    setQuickTemplateDraft({
      name: `Trip ${label}`,
      icon: 'Backpack',
      theme: { bg: THEME.primaryLight, text: THEME.primaryText },
      items: [],
      trip_start_at: isoDate || null,
      trip_end_at: null,
    });
    setCurrentView('create');
  }, [THEME.primaryLight, THEME.primaryText]);

  const handleShareScenario = useCallback(
    async (scenarioId, username, canEdit = false) => {
      await api.shareScenario(scenarioId, username, canEdit);
      await refreshData();
    },
    [refreshData],
  );

  const handleUnshareScenario = useCallback(
    async (scenarioId, username) => {
      await api.unshareScenario(scenarioId, username);
      await refreshData();
    },
    [refreshData],
  );

  const handleDeleteHistoryRecord = useCallback(
    async (recordId) => {
      await api.deleteHistoryRecord(recordId);
      await refreshData();
    },
    [refreshData],
  );

  const handleClearHistory = useCallback(async () => {
    await api.clearHistory();
    await refreshData();
  }, [refreshData]);

  const handleFinishPacking = async () => {
    const sc = scenarios.find(
      (s) => s.id === activeScenarioId && (s.owner_user_id ?? null) === (activeScenarioOwnerId ?? null),
    );
    if (sc?.access === 'shared') return;
    if (sc) {
      if (sc.access === 'owner') {
        const now = new Date();
        const start = sc.trip_start_at ? new Date(sc.trip_start_at) : null;
        const end = sc.trip_end_at ? new Date(sc.trip_end_at) : null;
        const cutoff = end && !Number.isNaN(end.getTime()) ? end : start;
        const shouldRecordHistory = !!(cutoff && !Number.isNaN(cutoff.getTime()) && now >= cutoff);

        // Keep trips reusable/editable in My Trips; only log history when scheduled date has passed.
        if (shouldRecordHistory) {
          await api.addHistory({ name: sc.name, scenario_id: sc.id });
          await api.updateScenario(sc.id, { archived: true });
          setLastPacked({ name: sc.name, at: new Date().toISOString() });
        } else {
          setLastPacked(null);
        }
        await refreshData();
      }
    }
    setCurrentView('success');
  };

  const handleReuseHistoryTrip = useCallback(
    async (scenarioId) => {
      const sid = String(scenarioId || '').trim();
      if (!sid) return;
      const scenario = await api.getScenario(sid);
      setActiveScenarioId(null);
      setActiveScenarioOwnerId(null);
      setMeInitialSegment('scenarios');
      setActiveTab('me');
      setQuickTemplateDraft({
        name: scenario?.name || 'Trip',
        icon: scenario?.icon || 'Backpack',
        theme: scenario?.theme || { bg: THEME.primaryLight, text: THEME.primaryText },
        items: Array.isArray(scenario?.items)
          ? scenario.items.map((it) => ({
              id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
              text: String(it?.text || '').trim(),
              critical: !!it?.critical,
              assignedTo: 'me',
            }))
          : [],
        trip_start_at: null,
        trip_end_at: null,
      });
      setCurrentView('create');
    },
    [THEME.primaryLight, THEME.primaryText],
  );

  const meProfile = useMemo(() => {
    if (!currentUser) {
      return { id: 'me', name: 'Me', username: '', avatar: '', db_id: null };
    }
    return currentUser;
  }, [currentUser]);

  const renderView = () => {
    switch (currentView) {
      case 'login':
        return <UserLogin onAuth={handleAuth} theme={THEME} t={t} />;

      case 'home':
        return (
          <HomeDashboard
            scenarios={scenarios}
            onSelect={handleSelectScenario}
            onSettingsClick={() => setCurrentView('settings')}
            onAddWeatherItems={handleAppendWeatherItems}
            weather={weather}
            weatherLoading={weatherLoading}
            weatherError={weatherError}
            onRefreshWeather={loadWeather}
            weatherFetchParams={weatherFetchParams}
            weatherDetail={weatherDetail}
            language={appPrefs?.language || 'en'}
            theme={THEME}
            t={t}
          />
        );

      case 'me':
        return (
          <MyProfileAndLibrary
            scenarios={scenarios}
            friends={friends}
            history={history}
            onSelect={handleSelectScenario}
            onDelete={handleDeleteScenario}
            onDeleteMany={handleDeleteScenariosBatch}
            onCreateClick={() => {
              setQuickTemplateDraft(null);
              setCurrentView('create');
            }}
            onDeleteFriend={handleDeleteFriend}
            onRefresh={refreshData}
            onDeleteHistoryRecord={handleDeleteHistoryRecord}
            onClearHistory={handleClearHistory}
            onReuseHistoryTrip={handleReuseHistoryTrip}
            initialSegment={meInitialSegment}
            theme={THEME}
            t={t}
          />
        );

      case 'quick':
        return (
          <QuickScenariosPage
            scenarios={scenarios}
            onCreateFromTemplate={async (template) => {
              setQuickTemplateDraft(template || null);
              setCurrentView('create');
            }}
            theme={THEME}
            t={t}
            language={appPrefs?.language || 'en'}
          />
        );

      case 'calendar':
        return (
          <CalendarPage
            scenarios={scenarios}
            onSelect={handleSelectScenario}
            onUpdateScenarioSchedule={handleUpdateScenarioSchedule}
            onCreateTripAtDate={handleCreateTripAtDate}
            language={appPrefs?.language || 'en'}
            theme={THEME}
            t={t}
          />
        );

      case 'settings':
        return (
          <SystemSettings
            onBack={() => setCurrentView(activeTab)}
            onLogout={handleLogout}
            theme={THEME}
            currentThemeKey={currentThemeKey}
            onChangeTheme={handleChangeTheme}
            currentUser={meProfile}
            onSaveProfileDisplayName={handleSaveProfile}
            onChangePassword={handleChangePassword}
            onDeleteAccount={handleDeleteAccount}
            appPrefs={appPrefs}
            onAppPrefsChange={handleChangeAppPrefs}
          />
        );

      case 'detail': {
        const scenario = scenarios.find(
          (s) => s.id === activeScenarioId && (s.owner_user_id ?? null) === (activeScenarioOwnerId ?? null),
        );
        if (!scenario) {
          return (
            <div className={`p-8 ${THEME.textMain}`}>
              <p className="text-center text-sm">{t('scenarioNotFound') || "We couldn't find that scenario. Go back and try again."}</p>
              <button
                type="button"
                onClick={() => setCurrentView(activeTab)}
                className={`mt-6 w-full py-3 rounded-xl font-bold ${THEME.primary} text-white`}
              >
                {t('goBack') || 'Go back'}
              </button>
            </div>
          );
        }
        return (
          <ChecklistDetail
            scenario={scenario}
            friends={friends}
            updateScenario={handleUpdateScenario}
            isSaving={scenarioSavingId === scenario.id}
            saveError={scenarioSaveError}
            checkedItems={checkedItems}
            setCheckedItems={setCheckedItems}
            onBack={() => setCurrentView(activeTab)}
            onFinish={handleFinishPacking}
            weather={weather}
            theme={THEME}
            meUser={meProfile}
            onShareScenario={handleShareScenario}
            onUnshareScenario={handleUnshareScenario}
            allowManageItems={detailAllowManageItems}
            t={t}
          />
        );
      }

      case 'create':
        return (
          <CreateNewTrip
            initialTrip={quickTemplateDraft}
            language={appPrefs?.language || 'en'}
            onBack={() => {
              setQuickTemplateDraft(null);
              setCurrentView(activeTab);
            }}
            onSave={async (payload) => {
              if (createTripSaving) return;
              setCreateTripSaving(true);
              setCreateTripError(null);
              try {
                await handleSaveTrip({ ...payload, type: 'custom' });
                setQuickTemplateDraft(null);
                setMeInitialSegment('scenarios');
                setActiveTab('me');
                setCurrentView('me');
              } catch (e) {
                setCreateTripError(e?.message || '保存失败，请稍后重试。');
              } finally {
                setCreateTripSaving(false);
              }
            }}
            isSaving={createTripSaving}
            saveError={createTripError}
            theme={THEME}
          />
        );

      case 'success':
        return (
          <PackingSuccess
            onHome={() => {
              setCurrentView('home');
              setActiveTab('home');
            }}
            onViewHistory={() => {
              setMeInitialSegment('history');
              setActiveTab('me');
              setCurrentView('me');
            }}
            lastPacked={lastPacked}
            theme={THEME}
            t={t}
          />
        );

      default:
        return <UserLogin onAuth={handleAuth} theme={THEME} t={t} />;
    }
  };

  return (
    <div className={`w-full h-screen flex flex-col items-center justify-center overflow-hidden font-sans ${THEME.textMain} ${THEME.bg} transition-colors duration-500 relative`}>
      <style>{`
        @keyframes fade-in { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
        @keyframes float-up { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .animate-fade-in { animation: fade-in 0.6s ease-out forwards; }
        .animate-float { animation: float 4s ease-in-out infinite; }
        .animate-float-up { animation: float-up 0.3s ease-out forwards; }
        .no-scrollbar::-webkit-scrollbar { display: none; }
      `}</style>

      <div className={`w-full h-full max-w-md ${THEME.bg} shadow-2xl relative flex flex-col overflow-hidden transition-colors duration-500 border-x border-gray-100`}>
        {sessionRestoring ? (
          <div
            className={`absolute inset-0 z-[60] flex flex-col items-center justify-center gap-3 ${THEME.sessionMask}`}
          >
            <div className={`h-8 w-8 rounded-full border-2 animate-spin ${THEME.sessionSpinner}`} />
            <p className={`text-sm font-semibold ${THEME.textMain}`}>{t('pleaseWaitText')}</p>
          </div>
        ) : null}

        <div className="flex-1 overflow-y-auto no-scrollbar scroll-smooth">
          {renderView()}
        </div>

        <AIChatAssistant
          isOpen={isChatOpen}
          onClose={() => setIsChatOpen(false)}
          theme={THEME}
          scenarios={scenarios}
          onCreateTripFromAssistant={handleCreateTripFromAssistant}
          onAppendAssistantItems={handleAppendAssistantItems}
          onOpenTrips={handleOpenTripsFromAssistant}
          t={t}
        />

        {['home', 'quick', 'calendar', 'me'].includes(currentView) && (
          <div
            className={`h-24 ${THEME.shell} flex justify-around items-center pb-6 px-6 absolute bottom-0 w-full z-10 rounded-t-3xl shadow-[0_-5px_20px_rgba(0,0,0,0.02)]`}
          >
            <NavItem
              icon={HomeIcon}
              label={t('navHome')}
              active={activeTab === 'home'}
              onClick={() => handleTabChange('home')}
              theme={THEME}
            />

            <NavItem
              icon={LayoutGrid}
              label={t('navQuick')}
              active={activeTab === 'quick'}
              onClick={() => handleTabChange('quick')}
              theme={THEME}
            />

            <div className="relative -top-8 group">
              <button
                type="button"
                onClick={() => setIsChatOpen(true)}
                className={`btn-primary-soft w-16 h-16 ${THEME.primary} rounded-full flex items-center justify-center shadow-lg shadow-[#E6B89C]/40 group-hover:scale-[1.06] border-4 ${THEME.fabRing}`}
              >
                <Sparkles className="text-white w-7 h-7" />
              </button>
            </div>

            <NavItem
              icon={CalendarDays}
              label={t('navCalendar')}
              active={activeTab === 'calendar'}
              onClick={() => handleTabChange('calendar')}
              theme={THEME}
            />

            <NavItem
              icon={User}
              label={t('navMe')}
              active={activeTab === 'me'}
              onClick={() => handleTabChange('me')}
              theme={THEME}
            />
          </div>
        )}
      </div>
    </div>
  );
}
