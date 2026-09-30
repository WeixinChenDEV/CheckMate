import React, { useState, useEffect } from 'react';
import { Send, X, Bot } from 'lucide-react';
import { api } from '../api';
import { extractPackingItems } from "../packingItems";
import AssistantFormattedMessage from '../components/AssistantFormattedMessage';

const AIChatAssistant = ({
  isOpen,
  onClose,
  theme,
  scenarios = [],
  onCreateTripFromAssistant,
  onAppendAssistantItems,
  onOpenTrips,
  t = (k) => k,
}) => {
  const [messages, setMessages] = useState([
    {
      role: 'bot',
      content: "Hi! I'm your packing assistant. Ask about weather, flights, gym gear, or anything on your list.",
    },
  ]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [statusLine, setStatusLine] = useState('');
  const [importTripName, setImportTripName] = useState('');
  const [importTargetId, setImportTargetId] = useState('');
  const [importBusy, setImportBusy] = useState(false);
  const [importNote, setImportNote] = useState('');
  const [importNoteType, setImportNoteType] = useState('');
  const [selectedSuggestionIds, setSelectedSuggestionIds] = useState({});

  useEffect(() => {
    if (isOpen) {
      setMessages([
        {
          role: 'bot',
          content: "Hi! I'm your packing assistant. Ask about weather, flights, gym gear, or anything on your list.",
        },
      ]);
      setInput('');
      setStatusLine('');
      setImportTripName('');
      setImportTargetId('');
      setImportNote('');
      setImportNoteType('');
      setSelectedSuggestionIds({});
      (async () => {
        try {
          const s = await api.assistantStatus();
          const ids = [];
          if (s?.moonshot_configured) ids.push('moonshot');
          if (s?.deepseek_configured) ids.push('deepseek');
          if (s?.siliconflow_configured) ids.push('siliconflow');
          if (s?.dashscope_configured) ids.push('dashscope');
          if (s?.gemini_configured) ids.push('gemini');
          const labels = {
            moonshot: 'Moonshot (Kimi)',
            deepseek: 'DeepSeek',
            siliconflow: 'SiliconFlow',
            dashscope: 'DashScope (Qwen)',
            gemini: 'Gemini',
          };
          if (s?.ai_provider) {
            const forced = String(s.ai_provider).trim().toLowerCase();
            setStatusLine(t('assistantCurrentAi').replace('{name}', labels[forced] || s.ai_provider));
          } else if (ids.length) {
            const order = (s.auto_order || []).filter((n) => ids.includes(n));
            const current = order[0] || ids[0];
            setStatusLine(t('assistantCurrentAi').replace('{name}', labels[current] || current));
          } else {
            setStatusLine(t('assistantNoKeyHint'));
          }
        } catch {
          setStatusLine('');
        }
      })();
    }
  }, [isOpen]);

  const buildConversationForApi = () => {
    const core = messages.filter((m) => m.role === 'user' || m.role === 'bot');
    const withoutIntro = core.filter(
      (m, i) =>
        !(
          i === 0 &&
          m.role === 'bot' &&
          /Hi! I'm your packing assistant/i.test(m.content || '')
        ),
    );
    return withoutIntro.map((m) => ({
      role: m.role === 'bot' ? 'assistant' : 'user',
      content: m.content,
    }));
  };

  const latestSuggestion = [...messages]
    .reverse()
    .find((m) => m.role === 'bot' && extractPackingItems(m.content).length > 0);
  const suggestedItems = latestSuggestion ? extractPackingItems(latestSuggestion.content) : [];
  const suggestedItemsWithId = suggestedItems.map((it, idx) => ({
    ...it,
    sid: `${idx}_${it.critical ? 'c' : 'n'}_${it.text.toLowerCase()}`,
  }));
  const selectedItems = suggestedItemsWithId
    .filter((it) => selectedSuggestionIds[it.sid])
    .map(({ sid, ...rest }) => rest);
  const editableScenarios = scenarios.filter((s) => s.access !== 'shared');

  useEffect(() => {
    if (!isOpen) return;
    if (suggestedItems.length && !importTripName) {
      setImportTripName(t('aiImportDefaultTripName').replace('{date}', new Date().toLocaleDateString()));
    }
    if (editableScenarios.length && !importTargetId) {
      setImportTargetId(editableScenarios[0].id);
    }
  }, [editableScenarios, importTargetId, importTripName, isOpen, suggestedItems.length]);

  useEffect(() => {
    if (!isOpen) return;
    const next = {};
    suggestedItemsWithId.forEach((it) => {
      next[it.sid] = true;
    });
    setSelectedSuggestionIds(next);
  }, [isOpen, latestSuggestion]);

  const handleCreateTripFromSuggestion = () => {
    if (!selectedItems.length || !onCreateTripFromAssistant) return;
    setImportNote('');
    setImportNoteType('');
    try {
      onCreateTripFromAssistant({
        name: importTripName.trim(),
        items: selectedItems,
      });
    } catch (e) {
      setImportNote(e?.message || t('aiImportCreateFail'));
      setImportNoteType('error');
    }
  };

  const handleAppendToTrip = async () => {
    if (!selectedItems.length || !onAppendAssistantItems || !importTargetId) return;
    setImportBusy(true);
    setImportNote('');
    setImportNoteType('');
    try {
      await onAppendAssistantItems({
        scenarioId: importTargetId,
        items: selectedItems,
      });
      setImportNote(t('aiImportAddedOk').replace('{count}', String(selectedItems.length)));
      setImportNoteType('success');
    } catch (e) {
      setImportNote(e?.message || t('aiImportAddFail'));
      setImportNoteType('error');
    } finally {
      setImportBusy(false);
    }
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;
    const newMsgs = [...messages, { role: 'user', content: text }];
    setMessages(newMsgs);
    setInput('');
    setSending(true);
    try {
      const data = await api.assistantReply({
        message: text,
        conversation: buildConversationForApi(),
      });
      const reply =
        data?.reply ||
        [
          'Trip note: I did not get a full reply — try a short question about your trip.',
          '',
          'Critical Items',
          '- Phone, wallet, keys',
          '- Any daily medications',
          '',
          'Normal Items',
          '- Charger and cable',
          '- Reusable water bottle',
        ].join('\n');
      const source = data?.source || '';
      const hint = data?.hint;
      let full = reply;
      if (source === 'rules' && hint) {
        full += `\n\n${t('assistantOfflineFallbackHint').replace('{hint}', hint)}`;
      }
      setMessages((prev) => [...prev, { role: 'bot', content: full }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: 'bot',
          content: [
            'Trip note: The assistant service is unreachable from this device.',
            '',
            'Critical Items',
            '- Check your internet connection',
            '- Confirm the backend server is running',
            '',
            'Normal Items',
            '- Retry in a moment',
            '- Ask again with your destination or trip type',
          ].join('\n'),
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="absolute inset-0 z-50 flex flex-col justify-end bg-black/20 backdrop-blur-[2px] animate-fade-in">
      <div className="bg-white w-full h-[80%] rounded-t-[32px] shadow-2xl flex flex-col overflow-hidden animate-float-up">
        <div className={`p-6 border-b flex justify-between items-center ${theme.primaryLight}`}>
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-xl bg-white ${theme.primaryText}`}>
              <Bot size={24} />
            </div>
            <div>
              <h3 className={`font-bold ${theme.textMain}`}>{t('assistantTitle')}</h3>
              <p className="text-[10px] text-gray-500 font-medium uppercase tracking-widest">
                {t('assistantSmartHints')}
              </p>
              {statusLine ? (
                <p className="text-[10px] text-gray-400 mt-1 max-w-[220px] leading-snug">{statusLine}</p>
              ) : null}
            </div>
          </div>
          <button type="button" onClick={onClose} className="p-2 hover:bg-black/5 rounded-full transition-colors">
            <X size={24} className="text-gray-400" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4 no-scrollbar">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[80%] p-4 rounded-2xl text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-slate-900 text-white rounded-tr-none font-medium'
                    : 'bg-gray-100 text-gray-800 rounded-tl-none font-normal'
                }`}
              >
                {msg.role === 'user' ? (
                  msg.content
                ) : (
                  <AssistantFormattedMessage text={msg.content} theme={theme} />
                )}
              </div>
            </div>
          ))}
          {sending ? (
            <div className="flex justify-start">
              <div className="bg-gray-100 text-gray-500 text-xs font-medium px-4 py-2 rounded-2xl rounded-tl-none">
                {t('assistantThinking')}
              </div>
            </div>
          ) : null}
        </div>

        <div className="p-6 border-t bg-gray-50">
          {suggestedItems.length ? (
            <div className="mb-3 p-3.5 rounded-2xl border border-slate-200 bg-white shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <p className="text-[11px] font-bold tracking-wide uppercase text-slate-500">
                  {t('aiImportTitle')}
                </p>
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-semibold">
                  {selectedItems.length} / {suggestedItems.length} {t('aiImportSelectedCount')}
                </span>
              </div>

              <div className="mb-2.5 max-h-36 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50/70 p-2.5 space-y-1.5">
                <div className="flex items-center justify-between mb-1">
                  <button
                    type="button"
                    onClick={() => {
                      const next = {};
                      suggestedItemsWithId.forEach((it) => {
                        next[it.sid] = true;
                      });
                      setSelectedSuggestionIds(next);
                    }}
                    className="text-[11px] text-slate-600 font-semibold px-2 py-0.5 rounded-md hover:bg-slate-200/70"
                  >
                    {t('aiImportSelectAll')}
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedSuggestionIds({})}
                    className="text-[11px] text-slate-500 font-semibold px-2 py-0.5 rounded-md hover:bg-slate-200/70"
                  >
                    {t('aiImportClear')}
                  </button>
                </div>
                {suggestedItemsWithId.map((item) => (
                  <label
                    key={item.sid}
                    className="flex items-center gap-2.5 text-[12px] text-slate-700 bg-white border border-slate-200 rounded-lg px-2 py-1.5"
                  >
                    <input
                      type="checkbox"
                      checked={!!selectedSuggestionIds[item.sid]}
                      onChange={(e) =>
                        setSelectedSuggestionIds((prev) => ({ ...prev, [item.sid]: e.target.checked }))
                      }
                      className="accent-slate-900"
                    />
                    {item.critical ? (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-rose-100 text-rose-600 font-bold uppercase">
                        {t('aiImportMust')}
                      </span>
                    ) : (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-slate-100 text-slate-500 font-bold uppercase">
                        {t('aiImportNice')}
                      </span>
                    )}
                    <span className="leading-snug">{item.text}</span>
                  </label>
                ))}
              </div>

              <div className="space-y-2">
                <div className="grid grid-cols-1 gap-2">
                  <input
                    type="text"
                    value={importTripName}
                    onChange={(e) => setImportTripName(e.target.value)}
                    placeholder={t('aiImportNewTripPlaceholder')}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 text-sm outline-none focus:ring-2 focus:ring-slate-200"
                    disabled={importBusy}
                  />
                  <button
                    type="button"
                    onClick={handleCreateTripFromSuggestion}
                    disabled={importBusy || !importTripName.trim() || !selectedItems.length}
                    className={`w-full py-2.5 rounded-xl text-sm font-semibold transition-colors ${
                      importBusy || !importTripName.trim() || !selectedItems.length
                        ? 'bg-slate-200 text-slate-400'
                        : `${theme.primary} text-white`
                    }`}
                  >
                    {t('aiImportContinueToCreateBtn')}
                  </button>
                </div>

                <div className="flex gap-2">
                  <select
                    value={importTargetId}
                    onChange={(e) => setImportTargetId(e.target.value)}
                    disabled={importBusy || !editableScenarios.length}
                    className="flex-1 px-3 py-2 rounded-xl border border-slate-200 text-sm bg-white outline-none focus:ring-2 focus:ring-slate-200"
                  >
                    {editableScenarios.length ? (
                      editableScenarios.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))
                    ) : (
                      <option value="">{t('aiImportNoEditableTrips')}</option>
                    )}
                  </select>
                  <button
                    type="button"
                    onClick={handleAppendToTrip}
                    disabled={importBusy || !importTargetId || !selectedItems.length}
                    className={`px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
                      importBusy || !importTargetId || !selectedItems.length
                        ? 'bg-slate-200 text-slate-400'
                        : 'bg-slate-900 text-white'
                    }`}
                  >
                    {t('aiImportAddBtn')}
                  </button>
                </div>
              </div>

              {importNote ? (
                <div
                  className={`mt-2.5 p-2.5 rounded-xl text-[11px] ${
                    importNoteType === 'success'
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : importNoteType === 'error'
                        ? 'bg-rose-50 text-rose-700 border border-rose-200'
                        : 'bg-gray-50 text-gray-600 border border-gray-200'
                  }`}
                >
                  <p className="font-medium">{importNote}</p>
                  {importNoteType === 'success' && onOpenTrips ? (
                    <button
                      type="button"
                      onClick={onOpenTrips}
                      className="mt-1.5 text-[11px] underline font-semibold"
                    >
                      {t('aiImportOpenTrips')}
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="flex items-center bg-white border rounded-2xl p-2 shadow-sm focus-within:ring-2 focus-within:ring-slate-800 transition-all">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder={t('askAnything')}
              disabled={sending}
              className="flex-1 px-4 outline-none text-sm bg-transparent disabled:opacity-50"
            />
            <button
              type="button"
              onClick={handleSend}
              disabled={sending || !input.trim()}
              className={`p-3 rounded-xl ${theme.primary} text-white shadow-lg active:scale-95 transition-all disabled:opacity-40`}
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AIChatAssistant;
