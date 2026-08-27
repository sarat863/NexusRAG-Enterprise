import React, { useState, useEffect } from 'react';
import { Settings, Key, Cpu, Sparkles, X, Check, ShieldCheck, RefreshCw } from 'lucide-react';
import { getApiSettings, saveApiSettings } from '../utils';
import { useToast } from './Toast';

const ApiSettingsModal = ({ isOpen, onClose }) => {
  const { showToast } = useToast();
  const [settings, setSettings] = useState({
    openaiApiKey: '',
    preferredModel: 'flux-schnell',
    defaultAspectRatio: '1:1',
    customBackendUrl: ''
  });

  useEffect(() => {
    if (isOpen) {
      setSettings(getApiSettings());
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSave = (e) => {
    e.preventDefault();
    saveApiSettings(settings);
    showToast('Engine & API settings saved successfully!');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
      <div className="relative w-full max-w-lg glass-panel rounded-2xl p-6 border border-white/10 shadow-2xl overflow-hidden">
        {/* Decorative Top Gradient */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500" />

        <div className="flex items-center justify-between pb-4 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <Settings className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">AI Engine & Model Settings</h2>
              <p className="text-xs text-slate-400">Configure provider keys, default generation models & aspect ratios</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSave} className="mt-5 space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Cpu className="w-4 h-4 text-indigo-400" /> Default AI Model
            </label>
            <select
              value={settings.preferredModel || 'flux-schnell'}
              onChange={(e) => setSettings({ ...settings, preferredModel: e.target.value })}
              className="w-full glass-input px-3.5 py-2.5 rounded-xl text-sm focus:border-indigo-500 bg-slate-900/90 text-white"
            >
              <option value="flux-schnell">Flux.1 Schnell (Fast, Free & Ultra HD)</option>
              <option value="stable-diffusion-xl">Stable Diffusion XL Turbo (High Detail)</option>
              <option value="dalle-3">OpenAI DALL·E 3 (Requires OpenAI Key)</option>
              <option value="dalle-2">OpenAI DALL·E 2 (Standard)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Key className="w-4 h-4 text-purple-400" /> OpenAI API Key (Optional)
            </label>
            <input
              type="password"
              placeholder="sk-..."
              value={settings.openaiApiKey || ''}
              onChange={(e) => setSettings({ ...settings, openaiApiKey: e.target.value })}
              className="w-full glass-input px-3.5 py-2.5 rounded-xl text-sm focus:border-indigo-500"
            />
            <p className="mt-1 text-[11px] text-slate-400 flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              Stored strictly in your local browser storage. If omitted, the app uses high-speed Flux.1 engine.
            </p>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-pink-400" /> Default Aspect Ratio
            </label>
            <select
              value={settings.defaultAspectRatio || '1:1'}
              onChange={(e) => setSettings({ ...settings, defaultAspectRatio: e.target.value })}
              className="w-full glass-input px-3.5 py-2.5 rounded-xl text-sm focus:border-indigo-500 bg-slate-900/90 text-white"
            >
              <option value="1:1">1:1 Square (1024 x 1024)</option>
              <option value="16:9">16:9 Landscape (1792 x 1024)</option>
              <option value="9:16">9:16 Portrait / Story (1024 x 1792)</option>
              <option value="4:3">4:3 Classic (1024 x 768)</option>
              <option value="21:9">21:9 Ultrawide (1792 x 768)</option>
            </select>
          </div>

          <div className="pt-4 flex items-center justify-end gap-3 border-t border-white/10">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-slate-300 hover:text-white rounded-xl hover:bg-white/5 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 text-sm font-semibold text-white rounded-xl glow-btn flex items-center gap-2"
            >
              <Check className="w-4 h-4" /> Save Preferences
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ApiSettingsModal;
