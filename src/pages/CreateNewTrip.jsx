import React, { useEffect, useState } from 'react';
import { Plus, Trash2, AlertCircle, Circle } from 'lucide-react';
import { uiT } from '../uiCopy';
import { toLocalDateTimeInput } from '../tripDates';

const CreateNewTrip = ({
  onBack,
  onSave,
  theme,
  initialTrip = null,
  language = 'en',
  isSaving = false,
  saveError = null,
}) => {
  const t = uiT(language);
  const [name, setName] = useState('');
  const [tripStartAt, setTripStartAt] = useState('');
  const [tripEndAt, setTripEndAt] = useState('');
  const [items, setItems] = useState([]);
  const [criticalInput, setCriticalInput] = useState('');
  const [optionalInput, setOptionalInput] = useState('');
  const inputLocale = language === 'zh' ? 'zh-CN' : 'en-US';
  const minDateTime = toLocalDateTimeInput();

  useEffect(() => {
    if (!initialTrip) {
      setName('');
      setTripStartAt('');
      setTripEndAt('');
      setItems([]);
      return;
    }
    setName(String(initialTrip.name || '').trim());
    setTripStartAt(initialTrip.trip_start_at ? String(initialTrip.trip_start_at).slice(0, 16) : '');
    setTripEndAt(initialTrip.trip_end_at ? String(initialTrip.trip_end_at).slice(0, 16) : '');
    const seededItems = (Array.isArray(initialTrip.items) ? initialTrip.items : []).map((it, idx) => ({
      id: it?.id || `draft_${Date.now()}_${idx}_${Math.random().toString(36).slice(2, 7)}`,
      text: String(it?.text || '').trim(),
      critical: !!it?.critical,
      assignedTo: 'me',
    })).filter((it) => it.text);
    setItems(seededItems);
  }, [initialTrip]);

  const addItem = (text, critical) => {
    const v = String(text || '').trim();
    if (!v) return;
    setItems((prev) => [
      ...prev,
      {
        id: Date.now() + Math.random(),
        text: v,
        critical,
        assignedTo: 'me',
      },
    ]);
    if (critical) setCriticalInput('');
    else setOptionalInput('');
  };

  const handleSave = async () => {
    if (isSaving) return;
    if (!name || items.length === 0) return;
    if (tripStartAt && new Date(tripStartAt) < new Date()) {
      window.alert(t('tripStartPastError'));
      return;
    }
    if (tripEndAt && (!tripStartAt || new Date(tripEndAt) < new Date(tripStartAt))) {
      window.alert(t('tripEndBeforeStartError'));
      return;
    }
    const payload = {
      id: Date.now().toString(),
      name,
      icon: initialTrip?.icon || 'Backpack',
      theme: initialTrip?.theme || { bg: theme.primaryLight, text: theme.primaryText },
      items,
      trip_start_at: tripStartAt || null,
      trip_end_at: tripEndAt || null,
    };
    await onSave(payload);
  };

  const criticalItems = items.filter((i) => i.critical);
  const optionalItems = items.filter((i) => !i.critical);

  return (
    <div className={`min-h-screen ${theme.bg} flex flex-col`}>
      <div className={`sticky top-0 z-20 ${theme.bg}/90 backdrop-blur-md px-4 h-16 flex items-center justify-between border-b border-[#F0F0F0]`}>
        <button type="button" onClick={onBack} disabled={isSaving} className={`font-medium ${isSaving ? 'text-[#D1D1D1] cursor-not-allowed' : 'text-[#9A9A9A]'}`}>
          {t('commonCancel')}
        </button>
        <span className={`font-bold ${theme.textMain}`}>{t('createTripTitle')}</span>
        <button
          type="button"
          onClick={handleSave}
          disabled={isSaving || !name || items.length === 0}
          className={`font-bold ${isSaving || !name || items.length === 0 ? 'text-[#D1D1D1] cursor-not-allowed' : theme.primaryText}`}
        >
          {isSaving ? (language === 'zh' ? '保存中…' : 'Saving…') : t('commonSave')}
        </button>
      </div>
      {saveError ? (
        <div className="px-6 pt-4">
          <div className={`rounded-2xl px-4 py-3 text-xs font-semibold ${
            theme.isDark ? 'bg-rose-950/40 text-rose-200 border border-rose-900/40' : 'bg-rose-50 text-rose-800 border border-rose-100'
          }`}>
            {language === 'zh' ? `保存失败：${saveError}` : `Save failed: ${saveError}`}
          </div>
        </div>
      ) : null}
      <div className="p-6 space-y-8 pb-32 overflow-y-auto">
        <div>
          <label className={`block text-xs font-bold ${theme.textSub} mb-3 ml-1`}>{t('tripNameLabel')}</label>
          <input
            type="text"
            placeholder={t('tripNamePlaceholder')}
            className={`input-soft w-full text-xl py-3 px-4 ${theme.cardBg} ${theme.textMain} placeholder-[#D1D1D1]`}
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={isSaving}
          />
        </div>
        <div>
          <label className={`block text-xs font-bold ${theme.textSub} mb-3 ml-1`}>{t('tripDateTimeLabel')}</label>
          <div>
            <p className={`text-[11px] ${theme.textSub} mb-1.5`}>{t('tripDateStart')}</p>
            <input
              type="datetime-local"
              lang={inputLocale}
              min={minDateTime}
              className={`input-soft w-full py-3 px-4 ${theme.cardBg} ${theme.textMain}`}
              value={tripStartAt}
              onChange={(e) => setTripStartAt(e.target.value)}
              disabled={isSaving}
            />
          </div>
          <div className="mt-3">
            <p className={`text-[11px] ${theme.textSub} mb-1.5`}>{t('tripDateEnd')}</p>
            <input
              type="datetime-local"
              lang={inputLocale}
              aria-label={t('tripDateEnd')}
              min={tripStartAt || minDateTime}
              className={`input-soft w-full py-3 px-4 ${theme.cardBg} ${theme.textMain}`}
              value={tripEndAt}
              onChange={(e) => setTripEndAt(e.target.value)}
              disabled={isSaving}
            />
          </div>
        </div>
        <div>
          <label className={`block text-xs font-bold ${theme.textSub} mb-3 ml-1`}>{t('tripChecklistLabel')}</label>

          <div className={`${theme.cardBg} rounded-2xl p-4 shadow-sm border ${theme.isDark ? 'border-slate-700/60' : 'border-[#F3F3F3]'} space-y-3`}>
            <div className="flex items-center justify-between">
              <p className={`text-sm font-bold ${theme.textMain} flex items-center gap-1.5`}>
                <AlertCircle size={14} className={theme.isDark ? 'text-rose-300' : 'text-[#D98282]'} />
                {t('tripMustBring')}
              </p>
              <span className={`text-[11px] ${theme.textSub}`}>{t('tripItemsCount').replace('{count}', String(criticalItems.length))}</span>
            </div>
            <div className={`rounded-xl border px-2 py-1.5 flex items-center ${theme.isDark ? 'border-slate-600 bg-slate-900/60' : 'border-[#EAEAEA] bg-white'}`}>
              <input
                type="text"
                placeholder={t('tripAddMustPlaceholder')}
                className={`flex-1 bg-transparent px-2 outline-none text-sm ${theme.textMain}`}
                value={criticalInput}
                onChange={(e) => setCriticalInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addItem(criticalInput, true)}
                disabled={isSaving}
              />
              <button
                type="button"
                onClick={() => addItem(criticalInput, true)}
                disabled={isSaving || !criticalInput.trim()}
                className={`p-2 rounded-lg ${criticalInput.trim() ? `btn-primary-soft ${theme.primary} text-white` : 'bg-[#F5F5F5] text-[#D1D1D1]'}`}
              >
                <Plus size={16} />
              </button>
            </div>
          </div>

          <div className={`${theme.cardBg} rounded-2xl p-4 shadow-sm border ${theme.isDark ? 'border-slate-700/60' : 'border-[#F3F3F3]'} space-y-3 mt-4`}>
            <div className="flex items-center justify-between">
              <p className={`text-sm font-bold ${theme.textMain} flex items-center gap-1.5`}>
                <Circle size={13} className={theme.isDark ? 'text-slate-300' : 'text-[#9A9A9A]'} />
                {t('tripOptional')}
              </p>
              <span className={`text-[11px] ${theme.textSub}`}>{t('tripItemsCount').replace('{count}', String(optionalItems.length))}</span>
            </div>
            <div className={`rounded-xl border px-2 py-1.5 flex items-center ${theme.isDark ? 'border-slate-600 bg-slate-900/60' : 'border-[#EAEAEA] bg-white'}`}>
              <input
                type="text"
                placeholder={t('tripAddOptionalPlaceholder')}
                className={`flex-1 bg-transparent px-2 outline-none text-sm ${theme.textMain}`}
                value={optionalInput}
                onChange={(e) => setOptionalInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addItem(optionalInput, false)}
                disabled={isSaving}
              />
              <button
                type="button"
                onClick={() => addItem(optionalInput, false)}
                disabled={isSaving || !optionalInput.trim()}
                className={`p-2 rounded-lg ${optionalInput.trim() ? `btn-primary-soft ${theme.primary} text-white` : 'bg-[#F5F5F5] text-[#D1D1D1]'}`}
              >
                <Plus size={16} />
              </button>
            </div>
          </div>

          <div className="space-y-2.5 mt-4">
            {items.map((item) => (
              <div
                key={item.id}
                className={`flex items-center gap-2 justify-between ${theme.cardBg} p-3 rounded-2xl border ${theme.isDark ? 'border-slate-700/60' : 'border-[#F4F4F4]'} shadow-sm`}
              >
                <div className="min-w-0">
                  <p className={`${theme.textMain} text-sm font-semibold truncate`}>{item.text}</p>
                  <p className={`text-[11px] ${item.critical ? (theme.isDark ? 'text-rose-300' : 'text-[#D98282]') : theme.textSub}`}>
                    {item.critical ? t('tripMustBring') : t('tripOptional')}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => !isSaving && setItems(items.filter((i) => i.id !== item.id))}
                  disabled={isSaving}
                  className="btn-ghost-soft text-[#D1D1D1] hover:text-[#D98282] p-1 rounded-lg"
                >
                  <Trash2 size={17} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
      {isSaving ? (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/20">
          <div className={`${theme.cardBg} rounded-3xl px-5 py-4 shadow-xl border ${
            theme.isDark ? 'border-slate-700/60' : 'border-gray-100'
          } flex items-center gap-3`}>
            <div className={`h-5 w-5 rounded-full border-2 animate-spin ${theme.isDark ? 'border-slate-500 border-t-transparent' : 'border-gray-400 border-t-transparent'}`} />
            <p className={`text-sm font-semibold ${theme.textMain}`}>
              {language === 'zh' ? '正在保存…' : 'Saving…'}
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default CreateNewTrip;
