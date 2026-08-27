import React from 'react';
import { Sparkles } from 'lucide-react';

const Loader = ({ text = 'Generating masterpiece...' }) => (
  <div className="flex flex-col items-center justify-center gap-3 p-6 text-center">
    <div className="relative flex items-center justify-center">
      {/* Outer pulsing ring */}
      <div className="w-16 h-16 rounded-full border-2 border-indigo-500/20 animate-ping absolute" />
      {/* Spinning gradient ring */}
      <div className="w-14 h-14 rounded-full border-3 border-transparent border-t-indigo-500 border-r-purple-500 border-b-pink-500 animate-spin" />
      {/* Center glowing icon */}
      <div className="absolute inset-0 flex items-center justify-center">
        <Sparkles className="w-6 h-6 text-indigo-400 animate-pulse" />
      </div>
    </div>
    {text && (
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-300 animate-pulse">
        {text}
      </p>
    )}
  </div>
);

export default Loader;