import React from 'react';
import { Sparkles } from 'lucide-react';

const FormField = ({
  LabelName,
  type = 'text',
  name,
  placeholder,
  value,
  handleChange,
  isSurpriseMe,
  handleSurpriseMe,
  isMagicWand,
  handleMagicWand,
  isEnhancing = false,
  rows,
  helperText
}) => {
  return (
    <div className="w-full">
      <div className="flex items-center justify-between gap-2 mb-2">
        <label
          htmlFor={name}
          className="block text-xs font-semibold uppercase tracking-wider text-slate-300"
        >
          {LabelName}
        </label>
        
        <div className="flex items-center gap-2">
          {isMagicWand && (
            <button
              type="button"
              onClick={handleMagicWand}
              disabled={isEnhancing || !value}
              className="text-xs font-semibold py-1 px-2.5 rounded-lg bg-gradient-to-r from-indigo-500/20 to-pink-500/20 hover:from-indigo-500/30 hover:to-pink-500/30 border border-indigo-500/40 text-indigo-300 flex items-center gap-1.5 transition-all disabled:opacity-40"
            >
              <Sparkles className={`w-3.5 h-3.5 ${isEnhancing ? 'animate-spin' : ''}`} />
              {isEnhancing ? 'Enhancing...' : 'Magic Prompt'}
            </button>
          )}

          {isSurpriseMe && (
            <button
              type="button"
              onClick={handleSurpriseMe}
              className="text-xs font-semibold py-1 px-2.5 rounded-lg bg-white/10 hover:bg-white/15 border border-white/10 text-slate-200 transition-colors"
            >
              🎲 Surprise me
            </button>
          )}
        </div>
      </div>

      {rows ? (
        <textarea
          id={name}
          name={name}
          rows={rows}
          placeholder={placeholder}
          value={value}
          onChange={handleChange}
          required
          className="w-full glass-input px-4 py-3 rounded-xl text-sm placeholder:text-slate-500 resize-none transition-all"
        />
      ) : (
        <input
          type={type}
          id={name}
          name={name}
          placeholder={placeholder}
          value={value}
          onChange={handleChange}
          required
          className="w-full glass-input px-4 py-3 rounded-xl text-sm placeholder:text-slate-500 transition-all"
        />
      )}

      {helperText && (
        <p className="mt-1.5 text-[11px] text-slate-400">{helperText}</p>
      )}
    </div>
  );
};

export default FormField;