import React, { useEffect, useMemo, useState } from 'react';
import {
  Settings,
  MapPin,
  Sun,
  Zap,
  ChevronRight,
  Cloud,
  CloudRain,
  CloudSun,
  CloudFog,
  Snowflake,
  RefreshCw,
} from 'lucide-react';
import { IconMap } from '../constants/data';
import WeatherDetailSheet from '../components/WeatherDetailSheet';

const WeatherGlyph = ({ iconKey, className = '' }) => {
  const p = { size: 28, strokeWidth: 1.5, className: className || undefined };
  switch (iconKey) {
    case 'clear':
      return <Sun {...p} />;
    case 'partly_cloudy':
      return <CloudSun {...p} />;
    case 'overcast':
    case 'cloud':
      return <Cloud {...p} />;
    case 'rain':
      return <CloudRain {...p} />;
    case 'snow':
      return <Snowflake {...p} />;
    case 'fog':
      return <CloudFog {...p} />;
    case 'storm':
      return <Zap {...p} />;
    default:
      return <Cloud {...p} />;
  }
};

const getLocalDateKey = (dateLike = new Date()) => {
  const d = new Date(dateLike);
  if (Number.isNaN(d.getTime())) return '';
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};

const HomeDashboard = ({
  scenarios,
  onSelect,
  onSettingsClick,
  onAddWeatherItems,
  weather,
  weatherLoading,
  weatherError,
  onRefreshWeather,
  weatherFetchParams,
  weatherDetail,
  language = 'en',
  theme,
  t,
}) => {
  const [detailOpen, setDetailOpen] = useState(false);
  const [tipsExpanded, setTipsExpanded] = useState(false);
  const [weatherTargetTripId, setWeatherTargetTripId] = useState('');
  const [weatherAddBusy, setWeatherAddBusy] = useState(false);
  const [weatherAddMsg, setWeatherAddMsg] = useState('');
  const [selectedWeatherTipTexts, setSelectedWeatherTipTexts] = useState([]);
  const [selectedWeatherTipDate, setSelectedWeatherTipDate] = useState('');

  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    if (hour < 12) return t?.('greetingMorning');
    if (hour < 18) return t?.('greetingAfternoon');
    return t?.('greetingEvening');
  }, [t]);

  const comfort = weather?.comfort || '—';
  const live =
    weather?.source === 'open-meteo' || weather?.source === 'weatherapi' || weather?.source === 'tomorrowio';
  const weatherSourceLabel = useMemo(() => {
    const source = String(weather?.source || '').toLowerCase();
    if (source === 'open-meteo') return 'Open-Meteo';
    if (source === 'weatherapi') return 'WeatherAPI.com';
    if (source === 'tomorrowio') return 'Tomorrow.io';
    if (source === 'system-fallback') return t?.('weatherSourceFallback');
    return t?.('weatherSourceUnknown');
  }, [weather?.source, t]);
  const hint = weather?.packingHint || (weatherLoading ? t?.('fetchingForecast') : t?.('tapRefreshWeather'));
  const tempUnit = weather?.tempUnit || 'C';
  const tipTargetDate = selectedWeatherTipDate || getLocalDateKey();
  const locale = language === 'zh' ? 'zh-CN' : 'en-US';
  const tipDateLabel = useMemo(() => {
    try {
      return new Date(tipTargetDate).toLocaleDateString(locale, { weekday: 'short', month: 'short', day: 'numeric' });
    } catch {
      return tipTargetDate;
    }
  }, [tipTargetDate, locale]);
  const weatherTipDays = useMemo(() => {
    const days = Array.isArray(weatherDetail?.daily) ? weatherDetail.daily : [];
    return days.slice(0, 7);
  }, [weatherDetail]);
  const selectedTipDayWeather = useMemo(
    () => weatherTipDays.find((d) => d?.date === tipTargetDate) || null,
    [weatherTipDays, tipTargetDate],
  );
  const weatherTipSummary = useMemo(() => {
    if (selectedTipDayWeather) {
      const parts = [];
      if (selectedTipDayWeather.condition) parts.push(selectedTipDayWeather.condition);
      if (selectedTipDayWeather.max != null || selectedTipDayWeather.min != null) {
        parts.push(
          t?.('weatherSummaryHighLow')
            .replace('{max}', String(selectedTipDayWeather.max ?? '—'))
            .replace('{min}', String(selectedTipDayWeather.min ?? '—')),
        );
      }
      if (selectedTipDayWeather.uvIndexMax != null) {
        parts.push(`UV ${selectedTipDayWeather.uvIndexMax}`);
      }
      if (selectedTipDayWeather.precipProbMax != null) {
        parts.push(t?.('weatherSummaryRainChance').replace('{value}', String(selectedTipDayWeather.precipProbMax)));
      }
      return parts.length ? parts.join(' · ') : t?.('weatherSmartTipsDesc');
    }
    const fallback = [];
    if (weather?.condition) fallback.push(weather.condition);
    if (weather?.temp != null) fallback.push(`${weather.temp}°${tempUnit}`);
    if (weather?.windKmh != null) fallback.push(t?.('weatherSummaryWind').replace('{value}', String(weather.windKmh)));
    if (weather?.humidity != null) fallback.push(t?.('weatherSummaryHumidity').replace('{value}', String(weather.humidity)));
    if (weather?.uvIndex != null) fallback.push(`UV ${weather.uvIndex}`);
    return fallback.length ? fallback.join(' · ') : t?.('weatherSummaryBasedOnForecast');
  }, [selectedTipDayWeather, t, tempUnit, weather]);
  const myTrips = useMemo(
    () => scenarios.filter((s) => s.type === 'custom' && !s.archived),
    [scenarios],
  );
  const weatherEligibleTrips = useMemo(() => {
    const target = new Date(tipTargetDate);
    if (Number.isNaN(target.getTime())) return [];
    const isSameLocalDate = (dateLike) => {
      if (!dateLike) return false;
      const d = new Date(dateLike);
      if (Number.isNaN(d.getTime())) return false;
      return (
        d.getFullYear() === target.getFullYear() &&
        d.getMonth() === target.getMonth() &&
        d.getDate() === target.getDate()
      );
    };
    // 仅查看的共享清单不能写入天气建议，与 App 内 handleAppendWeatherItems 一致
    return myTrips.filter((s) => s.access !== 'shared' && isSameLocalDate(s.trip_start_at));
  }, [myTrips, tipTargetDate]);
  const weatherPackingItems = useMemo(() => {
    if (weather?.source === 'system-fallback' && !selectedTipDayWeather) return [];
    const out = [];
    const isZh = (t?.('navHome') || '') === '首页';
    const tip = {
      sunscreen: isZh ? '防晒霜（SPF 30+）' : 'Sunscreen (SPF 30+)',
      sunglasses: isZh ? '防紫外线太阳镜' : 'UV-protection sunglasses',
      hat: isZh ? '帽子（棒球帽或遮阳帽）' : 'Cap or sun hat',
      quickDry: isZh ? '速干上衣' : 'Quick-dry shirt',
      towel: isZh ? '吸汗小毛巾' : 'Small absorbent towel',
      windproof: isZh ? '防风外套' : 'Windproof outer layer',
      midLayer: isZh ? '保暖中层（抓绒/卫衣）' : 'Warm mid-layer or fleece',
      gloves: isZh ? '轻薄手套' : 'Light gloves',
      scarf: isZh ? '薄围巾或脖套' : 'Light scarf or neck gaiter',
      bottle: isZh ? '可重复使用水杯' : 'Reusable water bottle',
      breathable: isZh ? '透气轻薄衣物' : 'Breathable light clothing',
      sunSleeve: isZh ? '防晒外套/防晒袖' : 'Sun-protective layer',
      umbrella: isZh ? '便携雨伞' : 'Compact umbrella',
      raincoat: isZh ? '轻便雨衣' : 'Light rain jacket',
      waterResistantShoes: isZh ? '防水或速干鞋' : 'Water-resistant or quick-dry shoes',
      thermal: isZh ? '保暖打底层' : 'Thermal base layer',
      warmSocks: isZh ? '保暖袜' : 'Warm socks',
      tractionShoes: isZh ? '防滑鞋底鞋' : 'Shoes with good traction',
    };
    const push = (text, critical = false) => {
      if (!text) return;
      if (out.some((x) => x.text.toLowerCase() === text.toLowerCase())) return;
      out.push({ text, critical, assignedTo: 'me' });
    };
    const isTodaySelected = tipTargetDate === getLocalDateKey();
    const uv = Number(selectedTipDayWeather?.uvIndexMax ?? weather?.uvIndex);
    const humidity = Number(isTodaySelected ? weather?.humidity : undefined);
    const wind = Number(isTodaySelected ? weather?.windKmh : undefined);
    const temperature = selectedTipDayWeather?.max ?? weather?.temp;
    const temp = temperature == null ? NaN : Number(temperature);
    const code = Number(selectedTipDayWeather?.weatherCode ?? weather?.weatherCode);

    if (!Number.isNaN(uv) && uv >= 6) {
      push(tip.sunscreen, true);
      push(tip.sunglasses, false);
      push(tip.hat, false);
    }
    if (!Number.isNaN(humidity) && humidity >= 80) {
      push(tip.quickDry, false);
      push(tip.towel, false);
    }
    if (!Number.isNaN(wind) && wind >= 30) {
      push(tip.windproof, false);
    }
    if (!Number.isNaN(temp) && temp <= 10) {
      push(tip.midLayer, true);
      push(tip.gloves, false);
      if (!Number.isNaN(wind) && wind >= 20) push(tip.scarf, false);
    }
    if (!Number.isNaN(temp) && temp >= 30) {
      push(tip.bottle, true);
      push(tip.breathable, false);
      if (!Number.isNaN(uv) && uv >= 6) push(tip.sunSleeve, false);
    }
    if ([51, 53, 55, 61, 63, 65, 80, 81, 82].includes(code)) {
      push(tip.umbrella, true);
      push(tip.raincoat, false);
      push(tip.waterResistantShoes, false);
    }
    if ([71, 73, 75, 85, 86].includes(code)) {
      push(tip.thermal, true);
      push(tip.warmSocks, false);
      push(tip.tractionShoes, false);
    }
    return out.slice(0, 6);
  }, [selectedTipDayWeather, tipTargetDate, weather]);
  const selectedWeatherPackingItems = useMemo(
    () => weatherPackingItems.filter((it) => selectedWeatherTipTexts.includes(it.text)),
    [weatherPackingItems, selectedWeatherTipTexts],
  );

  useEffect(() => {
    if (!weatherEligibleTrips.length) {
      setWeatherTargetTripId('');
      return;
    }
    if (weatherEligibleTrips.some((s) => s.id === weatherTargetTripId)) return;
    setWeatherTargetTripId(weatherEligibleTrips[0].id);
  }, [weatherEligibleTrips, weatherTargetTripId]);

  useEffect(() => {
    const allTipTexts = weatherPackingItems.map((it) => it.text);
    setSelectedWeatherTipTexts((prev) => {
      const kept = prev.filter((text) => allTipTexts.includes(text));
      if (kept.length) return kept;
      return allTipTexts;
    });
  }, [weatherPackingItems]);

  useEffect(() => {
    const today = getLocalDateKey();
    if (!weatherTipDays.length) {
      setSelectedWeatherTipDate(today);
      return;
    }
    if (weatherTipDays.some((d) => d?.date === selectedWeatherTipDate)) return;
    const defaultDay = weatherTipDays.find((d) => d?.date === today)?.date || weatherTipDays[0]?.date || today;
    setSelectedWeatherTipDate(defaultDay);
  }, [weatherTipDays, selectedWeatherTipDate]);

  return (
    <div className="p-6 pb-28 space-y-6 animate-fade-in">
      <header className="mt-4 flex justify-between items-center">
        <div>
          <h1 className={`text-2xl font-bold ${theme.textMain} tracking-tight`}>
            {greeting}
            <br />
            <span className={`${theme.primaryText} text-3xl`}>{t?.('whereToToday')}</span>
          </h1>
        </div>
        <button
          type="button"
          onClick={onSettingsClick}
          className="btn-icon-soft w-10 h-10 rounded-full flex items-center justify-center"
        >
          <Settings size={20} className="text-[#9A9A9A]" />
        </button>
      </header>

      <div className="relative rounded-[28px] overflow-hidden shadow-[0_12px_40px_rgba(15,23,42,0.08)] border border-white/70 ring-1 ring-slate-200/40">
        <div className="absolute inset-0 bg-gradient-to-br from-sky-50 via-white to-indigo-50/90" />
        <div className="absolute -right-8 -top-12 w-40 h-40 rounded-full bg-sky-200/25 blur-3xl" />
        <div className="absolute -left-6 bottom-0 w-32 h-32 rounded-full bg-indigo-200/20 blur-2xl" />

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRefreshWeather();
          }}
          disabled={weatherLoading}
          className="btn-secondary-soft absolute top-3 right-3 z-20 p-2.5 rounded-2xl text-slate-600 disabled:opacity-50"
          title={t?.('refreshWeather')}
          aria-label={t?.('refreshWeather')}
        >
          <RefreshCw size={18} className={weatherLoading ? 'animate-spin' : ''} />
        </button>

        <button
          type="button"
          onClick={() => live && setDetailOpen(true)}
          disabled={!live}
          className={`relative z-10 w-full text-left p-5 pt-7 transition-transform ${
            live ? 'active:scale-[0.99]' : 'cursor-default'
          }`}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex items-center gap-1.5 text-sky-700/90 flex-wrap">
                <MapPin size={14} className="shrink-0" strokeWidth={2.5} />
                <span className="text-[11px] font-bold uppercase tracking-wider">{t?.('now')}</span>
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-[9px] font-bold tracking-wide uppercase border ${
                    theme.isDark
                      ? 'bg-slate-800/70 text-slate-200 border-slate-700/80'
                      : 'bg-white/85 text-slate-600 border-slate-200/90'
                  }`}
                  title={`Data by ${weatherSourceLabel}`}
                >
                  {weatherSourceLabel}
                </span>
              </div>
              <h2 className={`text-lg sm:text-xl font-bold ${theme.textMain} leading-snug break-words`}>
                {weather?.location || '—'}
              </h2>
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 pt-1.5">
                <span className={`text-5xl font-bold tracking-tight ${theme.textMain}`}>
                  {!live && weatherLoading ? '—' : `${weather?.temp ?? '—'}°`}
                </span>
                <span className="text-slate-500 text-sm font-semibold">{tempUnit}</span>
                <span className={`text-sm font-medium text-slate-600 w-full sm:w-auto`}>
                  {!live && weatherLoading ? '…' : weather?.condition || ''}
                </span>
              </div>
              <p className={`text-xs font-semibold text-sky-800/70 pt-1`}>
                {live && weather?.windKmh != null
                  ? ` · ${t?.('weatherSummaryWind').replace('{value}', String(weather.windKmh))}`
                  : ''}
                {live && weather?.humidity != null
                  ? ` · ${t?.('weatherSummaryHumidity').replace('{value}', String(weather.humidity))}`
                  : ''}
                {live && weather?.isDay && weather?.uvIndex != null
                  ? ` · ${t?.('weatherSummaryUv').replace('{value}', String(weather.uvIndex))}`
                  : ''}
                {!live && !weatherLoading ? ` · ${comfort}` : ''}
              </p>
            </div>
            <div className="w-16 h-16 rounded-2xl bg-white/60 backdrop-blur-md shadow-inner border border-white/80 flex items-center justify-center shrink-0">
              <WeatherGlyph iconKey={weather?.iconKey} className={theme.primaryText} />
            </div>
          </div>

          {live ? (
            <div className="mt-3 flex items-center justify-between text-sky-900/50 px-0.5">
              <span className="text-[11px] font-bold uppercase tracking-wider">{t?.('fullForecast')}</span>
              <ChevronRight size={18} className="text-sky-700/40" />
            </div>
          ) : null}
        </button>
      </div>

      <WeatherDetailSheet
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        theme={theme}
        weatherFetchParams={weatherFetchParams}
        language={language}
      />

      <div className={`rounded-xl p-3 border ${theme.isDark ? 'border-slate-700/60 bg-slate-900/40' : 'border-[#EFEFEF] bg-white'} shadow-sm`}>
        <div className="flex items-center justify-between mb-1.5">
          <h3 className={`text-sm font-bold ${theme.textMain}`}>{t?.('weatherSmartTipsTitle')}</h3>
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-bold px-2 py-1 rounded-full ${theme.primaryLight} ${theme.primaryText}`}>
              {weatherPackingItems.length} {t?.('weatherItemsLabel')}
            </span>
            <button
              type="button"
              onClick={() => setTipsExpanded((v) => !v)}
              className={`btn-secondary-soft text-[11px] font-bold px-2.5 py-1 rounded-lg ${
                theme.isDark ? 'bg-slate-800 text-slate-200' : 'bg-slate-100 text-slate-600'
              }`}
            >
              {tipsExpanded ? t?.('weatherTipsCollapse') : t?.('weatherTipsExpand')}
            </button>
          </div>
        </div>
        {tipsExpanded ? (
          <>
            <p className={`text-[11px] ${theme.textSub} mb-2`}>
              {weatherTipSummary}
            </p>
            {weatherTipDays.length ? (
              <div className="mb-2">
                <div className="flex gap-1.5 overflow-x-auto no-scrollbar pb-1">
                  {weatherTipDays.map((d) => {
                    const active = d.date === tipTargetDate;
                    return (
                      <button
                        key={d.date}
                        type="button"
                        onClick={() => setSelectedWeatherTipDate(d.date)}
                        className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold border transition-colors ${
                          active
                            ? `${theme.primary} text-white border-transparent`
                            : theme.isDark
                              ? 'bg-slate-800 text-slate-200 border-slate-700'
                              : 'bg-slate-50 text-slate-700 border-slate-200'
                        }`}
                      >
                        {new Date(d.date).toLocaleDateString(locale, { weekday: 'short', day: 'numeric' })}
                      </button>
                    );
                  })}
                </div>
                <p className={`text-[10px] mt-1 ${theme.textSub}`}>
                  {t?.('weatherTipsForDate').replace('{date}', tipDateLabel)}
                </p>
              </div>
            ) : null}
            {weatherPackingItems.length > 0 ? (
              <div className="space-y-1 mb-2">
                {weatherPackingItems.map((it) => (
                  <label
                    key={it.text}
                    className={`text-[11px] rounded-md px-2 py-1.5 border flex items-start gap-2 cursor-pointer ${
                      it.critical
                        ? theme.isDark
                          ? 'border-rose-900/60 bg-rose-950/30 text-rose-200'
                          : 'border-rose-200 bg-rose-50 text-rose-700'
                        : theme.isDark
                          ? 'border-slate-700 bg-slate-800/70 text-slate-200'
                          : 'border-slate-200 bg-slate-50 text-slate-700'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedWeatherTipTexts.includes(it.text)}
                      onChange={(e) => {
                        setSelectedWeatherTipTexts((prev) =>
                          e.target.checked ? [...prev, it.text] : prev.filter((text) => text !== it.text),
                        );
                      }}
                      className="mt-0.5 h-3.5 w-3.5 rounded border-slate-300"
                    />
                    <span>
                      {it.critical ? t?.('weatherTipMustPrefix') : t?.('weatherTipOptionalPrefix')}
                      {it.text}
                    </span>
                  </label>
                ))}
              </div>
            ) : (
              <p className={`text-[11px] ${theme.textSub} mb-2`}>
                {t?.('weatherSmartNoExtra')}
              </p>
            )}
            {weatherPackingItems.length > 0 ? (
              <div className="mb-2 text-[11px]">
                <span className={`${theme.textSub}`}>
                  {selectedWeatherPackingItems.length}/{weatherPackingItems.length}
                </span>
              </div>
            ) : null}
            <div className="flex gap-2">
              <select
                value={weatherTargetTripId}
                onChange={(e) => setWeatherTargetTripId(e.target.value)}
                disabled={!weatherEligibleTrips.length || weatherAddBusy}
                className="flex-1 px-2.5 py-2 rounded-xl border text-xs bg-white"
              >
                {weatherEligibleTrips.length ? (
                  weatherEligibleTrips.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))
                ) : (
                  <option value="">{t?.('weatherNoTripOption')}</option>
                )}
              </select>
              <button
                type="button"
                disabled={!weatherTargetTripId || !selectedWeatherPackingItems.length || weatherAddBusy}
                onClick={() => {
                  void (async () => {
                    if (!onAddWeatherItems) return;
                    setWeatherAddBusy(true);
                    setWeatherAddMsg('');
                    try {
                      await onAddWeatherItems({
                        scenarioId: weatherTargetTripId,
                        items: selectedWeatherPackingItems,
                        tipDate: tipTargetDate,
                      });
                      setWeatherAddMsg(t?.('weatherAddOk'));
                    } catch (e) {
                      setWeatherAddMsg(e?.message || t?.('weatherAddFail'));
                    } finally {
                      setWeatherAddBusy(false);
                    }
                  })();
                }}
                className={`px-3 py-2 rounded-xl text-xs font-bold ${
                  !weatherTargetTripId || !selectedWeatherPackingItems.length || weatherAddBusy
                    ? 'bg-slate-200 text-slate-400'
                    : `btn-primary-soft ${theme.primary} text-white`
                }`}
              >
                {t?.('weatherAddBtn')}
              </button>
            </div>
            {weatherAddMsg ? <p className={`text-[11px] mt-2 ${theme.textSub}`}>{weatherAddMsg}</p> : null}
          </>
        ) : null}
      </div>

      <div>
        <div className="flex justify-between items-end mb-4">
          <h2 className={`text-lg font-bold ${theme.textMain}`}>{t?.('myTrips')}</h2>
        </div>

        {myTrips.length ? (
          <div className="grid grid-cols-2 gap-4">
            {myTrips.map((scenario) => {
              const Icon = IconMap[scenario.icon] || IconMap.Briefcase;
              const cardTheme = scenario.theme || { bg: 'bg-white', text: 'text-gray-500' };
              const listKey =
                scenario.access === 'shared'
                  ? `shared-${scenario.owner_user_id}-${scenario.id}`
                  : scenario.id;
              return (
                <button
                  key={listKey}
                  type="button"
                  onClick={() => onSelect(scenario.id, scenario.owner_user_id ?? null)}
                  className="group relative bg-white rounded-[24px] p-5 h-40 flex flex-col justify-between items-start shadow-[0_4px_20px_rgba(0,0,0,0.03)] hover:shadow-[0_8px_25px_rgba(0,0,0,0.05)] transition-all active:scale-98 text-left border border-transparent hover:border-[#F0F0F0]"
                >
                  <div
                    className={`w-12 h-12 rounded-2xl ${cardTheme.bg} ${cardTheme.text} flex items-center justify-center transition-colors`}
                  >
                    <Icon size={24} strokeWidth={1.5} />
                  </div>
                  <div>
                    {scenario.access === 'shared' || scenario.access === 'shared_edit' ? (
                      <div className="flex items-center gap-1.5 mb-0.5">
                        {scenario.owner_avatar ? (
                          <img src={scenario.owner_avatar} alt="" className="w-4 h-4 rounded-full bg-white object-cover" />
                        ) : null}
                        <p className="text-[10px] font-bold text-sky-600 uppercase tracking-wide">
                          {t?.('fromUser')} @{scenario.owner_username}
                        </p>
                      </div>
                    ) : null}
                    {scenario.trip_start_at ? (
                      <p
                        className={`text-[10px] font-bold uppercase tracking-wide mb-0.5 ${
                          theme.isDark ? 'text-emerald-300' : 'text-emerald-600'
                        }`}
                      >
                        {t?.('tripScheduledTag')}
                      </p>
                    ) : null}
                    <h3 className={`font-bold ${theme.textMain} text-lg`}>{scenario.name}</h3>
                    <p className={`text-xs ${theme.textSub} mt-1 font-medium`}>
                      {scenario.items.length} {t?.('weatherItemsLabel')}
                    </p>
                  </div>

                  <div className="absolute bottom-5 right-5 opacity-0 group-hover:opacity-100 transition-all transform group-hover:translate-x-0 translate-x-2">
                    <div className="bg-[#F5F5F5] rounded-full p-1.5">
                      <ChevronRight size={14} className="text-[#9A9A9A]" />
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <div
            className={`rounded-2xl border px-4 py-6 text-center ${
              theme.isDark ? 'border-slate-700/70 bg-slate-900/40' : 'border-[#EFEFEF] bg-white'
            }`}
          >
            <p className={`text-sm font-semibold ${theme.textMain}`}>
              {t?.('myTripsEmptyTitle')}
            </p>
            <p className={`text-xs mt-1 ${theme.textSub}`}>
              {t?.('myTripsEmptyDesc')}
            </p>
          </div>
        )}
      </div>

    </div>
  );
};

export default HomeDashboard;
