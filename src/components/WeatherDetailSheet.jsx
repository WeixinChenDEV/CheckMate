import React, { useEffect, useMemo, useState } from 'react';
import { X, Cloud, CloudFog, CloudRain, CloudSun, Snowflake, Sun, Zap, Droplets } from 'lucide-react';
import { api } from '../api';

const Glyph = ({ iconKey, className, size = 28 }) => {
  const p = { size, strokeWidth: 1.5, className };
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

function formatHour(iso, locale) {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString(locale, { hour: 'numeric', minute: '2-digit' });
  } catch {
    return iso;
  }
}

function formatDay(dateStr, locale) {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString(locale, { weekday: 'short', month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
}

export default function WeatherDetailSheet({ open, onClose, theme, weatherFetchParams, language = 'en' }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);
  const locale = language === 'zh' ? 'zh-CN' : 'en-US';

  const fetchKey = useMemo(() => {
    const p = weatherFetchParams || {};
    return [p.lat, p.lon, p.label, p.city].map((x) => (x == null ? '' : String(x))).join('|');
  }, [weatherFetchParams]);

  useEffect(() => {
    if (!open) {
      setDetail(null);
      setErr(null);
      return undefined;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setErr(null);
      try {
        const d = await api.getWeatherDetail(weatherFetchParams || {});
        if (!cancelled) setDetail(d);
      } catch (e) {
        if (!cancelled) setErr(e?.message || 'Could not load forecast.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, fetchKey]);

  if (!open) return null;

  const c = detail;

  return (
    <div
      className="fixed inset-0 z-[80] flex flex-col justify-end bg-black/35 backdrop-blur-[3px] animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-label="Weather details"
    >
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        aria-label="Close"
        onClick={onClose}
      />
      <div className="relative max-h-[88vh] w-full max-w-md mx-auto rounded-t-[28px] bg-gradient-to-b from-[#f8fbff] to-white shadow-2xl overflow-hidden flex flex-col animate-float-up border-t border-white/80">
        <div className="h-1.5 w-10 bg-gray-200/90 rounded-full mx-auto mt-3 shrink-0" />
        <div className="flex items-center justify-between px-5 pt-2 pb-3 border-b border-gray-100/80 shrink-0">
          <h2 className={`text-sm font-bold uppercase tracking-wider ${theme.textSub}`}>Weather</h2>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-600 transition-colors"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        <div className="overflow-y-auto flex-1 px-5 pb-10 no-scrollbar">
          {loading && !c ? (
            <div className="py-16 flex flex-col items-center gap-3">
              <div className="h-9 w-9 rounded-full border-2 border-gray-200 border-t-sky-500 animate-spin" />
              <p className={`text-sm ${theme.textSub}`}>Loading forecast…</p>
            </div>
          ) : null}

          {err ? (
            <p className="text-sm text-red-600/90 py-8 text-center">{err}</p>
          ) : null}

          {c ? (
            <>
              <div className="pt-5 pb-6">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className={`text-xl font-bold ${theme.textMain} leading-tight`}>{c.location}</p>
                    {c.locationDetail ? (
                      <p className={`text-sm font-medium ${theme.primaryText} mt-1`}>{c.locationDetail}</p>
                    ) : null}
                    <p className={`text-[11px] ${theme.textSub} mt-2 font-mono`}>{c.coordinatesLabel}</p>
                    {c.timezone ? (
                      <p className={`text-[10px] ${theme.textSub} mt-0.5`}>Timezone: {c.timezone}</p>
                    ) : null}
                  </div>
                  <div className="flex flex-col items-center shrink-0">
                    <Glyph iconKey={c.iconKey} className={theme.primaryText} />
                    <span className={`text-4xl font-bold ${theme.textMain} mt-1`}>{c.temp ?? '—'}°</span>
                    <span className={`text-xs ${theme.textSub}`}>{c.condition}</span>
                  </div>
                </div>
                <p className={`text-xs leading-relaxed ${theme.textMain} mt-4 p-3 rounded-2xl bg-sky-50/80 border border-sky-100/60`}>
                  {c.packingHint}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-2 mb-6">
                {[
                  { label: 'Feels like', val: c.apparentTemp != null ? `${c.apparentTemp}°` : '—' },
                  { label: 'Humidity', val: c.humidity != null ? `${c.humidity}%` : '—' },
                  { label: 'Wind', val: c.windKmh != null ? `${c.windKmh} km/h` : '—' },
                  { label: 'UV index', val: c.uvIndex != null ? String(c.uvIndex) : '—' },
                ].map((row) => (
                  <div key={row.label} className="rounded-2xl bg-white border border-gray-100 px-3 py-2.5 shadow-sm">
                    <p className={`text-[10px] font-bold uppercase tracking-wide ${theme.textSub}`}>{row.label}</p>
                    <p className={`text-sm font-bold ${theme.textMain} mt-0.5`}>{row.val}</p>
                  </div>
                ))}
              </div>

              <div className="mb-2">
                <h3 className={`text-xs font-bold uppercase tracking-wider ${theme.textSub} mb-3`}>Next 24 hours</h3>
                <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1 no-scrollbar">
                  {(c.hourly || []).map((h, i) => (
                    <div
                      key={`${h.time}-${i}`}
                      className="shrink-0 w-[72px] rounded-2xl bg-white border border-gray-100/90 py-2.5 px-1 flex flex-col items-center shadow-sm"
                    >
                      <span className={`text-[10px] font-bold ${theme.textSub}`}>{formatHour(h.time, locale)}</span>
                      <Glyph iconKey={h.iconKey} size={22} className={`${theme.primaryText} my-1`} />
                      <span className={`text-sm font-bold ${theme.textMain}`}>{h.temp}°</span>
                      {h.precipProb != null && h.precipProb > 0 ? (
                        <span className="text-[9px] text-sky-600 font-semibold flex items-center gap-0.5 mt-0.5">
                          <Droplets size={10} />
                          {h.precipProb}%
                        </span>
                      ) : (
                        <span className="text-[9px] text-transparent mt-0.5">.</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h3 className={`text-xs font-bold uppercase tracking-wider ${theme.textSub} mb-3`}>7-day outlook</h3>
                <div className="space-y-2">
                  {(c.daily || []).map((d) => (
                    <div
                      key={d.date}
                      className="flex items-center gap-3 rounded-2xl bg-white border border-gray-100 px-3 py-2.5 shadow-sm"
                    >
                      <div className="w-24 shrink-0">
                        <p className={`text-xs font-bold ${theme.textMain}`}>{formatDay(d.date, locale)}</p>
                        {d.sunrise && d.sunset ? (
                          <p className={`text-[9px] ${theme.textSub} mt-0.5`}>
                            ↑ {formatHour(d.sunrise, locale)} · ↓ {formatHour(d.sunset, locale)}
                          </p>
                        ) : null}
                      </div>
                      <Glyph iconKey={d.iconKey} size={24} className={`${theme.primaryText} shrink-0`} />
                      <div className="flex-1 min-w-0">
                        <p className={`text-[11px] ${theme.textSub} truncate`}>{d.condition}</p>
                        <div className="flex items-baseline gap-2 mt-0.5">
                          <span className={`text-sm font-bold ${theme.textMain}`}>{d.max}°</span>
                          <span className={`text-xs ${theme.textSub}`}>{d.min}°</span>
                          {d.precipMm != null && d.precipMm > 0 ? (
                            <span className="text-[10px] text-sky-600 flex items-center gap-0.5">
                              <Droplets size={11} />
                              {d.precipMm} mm
                            </span>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
