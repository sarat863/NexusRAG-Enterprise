import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Wand2, Compass, Shuffle, Copy, Check, ArrowRight, Dna, Layers, Zap } from 'lucide-react';
import { inspirationCategories, stylePresets, lightingModifiers, cameraModifiers } from '../constants';
import { useToast } from '../components/Toast';
import { triggerConfetti } from '../utils';

const KEYWORD_SUBJECTS = [
  'Cybernetic Samurai',
  'Ancient Mythical Dragon',
  'Deep Space Explorer Astronaut',
  'Whimsical Steampunk Owl',
  'Solarpunk Treehouse Metropolis',
  'Bioluminescent Jellyfish Castle',
  'Futuristic Concept Supercar',
  'Ethereal Celestial Goddess'
];

const KEYWORD_ENVIRONMENTS = [
  'in a neon-soaked Tokyo rainstorm',
  'perched atop floating crystal sky islands',
  'inside an ancient overgrown gothic cathedral',
  'submerged beneath a glowing coral ocean',
  'wandering across the crimson sands of Mars',
  'in a cozy sunlit Victorian greenhouse library'
];

const InspirationLab = () => {
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [activeCategory, setActiveCategory] = useState('scifi');
  const [copiedIndex, setCopiedIndex] = useState(null);

  // Keyword Matrix Builder State
  const [selectedSubject, setSelectedSubject] = useState(KEYWORD_SUBJECTS[0]);
  const [selectedEnv, setSelectedEnv] = useState(KEYWORD_ENVIRONMENTS[0]);
  const [selectedStyle, setSelectedStyle] = useState('cyberpunk');
  const [selectedLight, setSelectedLight] = useState('Cyberpunk Neon Lighting');
  const [selectedCam, setSelectedCam] = useState('85mm f/1.4 Portrait Lens');
  const [isSpinning, setIsSpinning] = useState(false);

  const constructedPrompt = `${selectedSubject} ${selectedEnv}, in ${selectedStyle} style, illuminated by ${selectedLight.toLowerCase()}, captured on ${selectedCam}, hyperrealistic 8k resolution, cinematic masterpiece`;

  const handleCopy = (text, idx) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(idx);
    showToast('Prompt copied to clipboard!');
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handleSendToStudio = (promptText, styleId = 'photorealistic') => {
    navigate('/create-post', {
      state: {
        remixPrompt: promptText,
        remixStyle: styleId
      }
    });
    showToast('Prompt loaded into Studio! ✨', 'info');
  };

  const handleRouletteSpin = () => {
    setIsSpinning(true);
    triggerConfetti();

    setTimeout(() => {
      const randSub = KEYWORD_SUBJECTS[Math.floor(Math.random() * KEYWORD_SUBJECTS.length)];
      const randEnv = KEYWORD_ENVIRONMENTS[Math.floor(Math.random() * KEYWORD_ENVIRONMENTS.length)];
      const randStyle = stylePresets[Math.floor(Math.random() * stylePresets.length)].id;
      const randLight = lightingModifiers[Math.floor(Math.random() * lightingModifiers.length)];
      const randCam = cameraModifiers[Math.floor(Math.random() * cameraModifiers.length)];

      setSelectedSubject(randSub);
      setSelectedEnv(randEnv);
      setSelectedStyle(randStyle);
      setSelectedLight(randLight);
      setSelectedCam(randCam);
      setIsSpinning(false);
      showToast('Roulette generated a fresh vision! 🎲');
    }, 600);
  };

  const currentCategoryData = inspirationCategories.find((c) => c.id === activeCategory) || inspirationCategories[0];

  return (
    <div className="max-w-7xl mx-auto space-y-10">
      {/* Header */}
      <div className="text-center max-w-3xl mx-auto space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-pink-500/10 border border-pink-500/30 text-pink-300">
          <Dna className="w-3.5 h-3.5" /> Prompt Engineering Laboratory
        </div>
        <h1 className="text-3xl sm:text-5xl font-extrabold text-white">
          Prompt Inspiration & <span className="text-gradient">Keyword Matrix</span>
        </h1>
        <p className="text-sm sm:text-base text-slate-300">
          Explore structured prompt recipes, spin the prompt roulette, or assemble prompt elements block-by-block.
        </p>
      </div>

      {/* Interactive Keyword Matrix Builder */}
      <div className="glass-panel rounded-3xl p-6 sm:p-8 border border-white/10 shadow-2xl space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <Zap className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Prompt Matrix Composer</h2>
              <p className="text-xs text-slate-400">Click chips to synthesize an intricate prompt recipe</p>
            </div>
          </div>

          <button
            onClick={handleRouletteSpin}
            disabled={isSpinning}
            className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 flex items-center gap-2 shadow-lg transition-all active:scale-95 disabled:opacity-50"
          >
            <Shuffle className={`w-3.5 h-3.5 ${isSpinning ? 'animate-spin' : ''}`} />
            {isSpinning ? 'Spinning...' : '🎲 Spin Roulette'}
          </button>
        </div>

        {/* Matrix Chips Selectors */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Subject */}
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-300 block">
              1. Hero Subject
            </label>
            <div className="flex flex-wrap gap-1.5">
              {KEYWORD_SUBJECTS.map((sub, i) => (
                <button
                  key={i}
                  onClick={() => setSelectedSubject(sub)}
                  className={`px-2.5 py-1.5 rounded-xl text-xs transition-all ${
                    selectedSubject === sub
                      ? 'bg-indigo-600 text-white font-semibold shadow-md'
                      : 'bg-white/5 text-slate-400 hover:text-white border border-white/5'
                  }`}
                >
                  {sub}
                </button>
              ))}
            </div>
          </div>

          {/* Environment */}
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-300 block">
              2. Setting & Environment
            </label>
            <div className="flex flex-wrap gap-1.5">
              {KEYWORD_ENVIRONMENTS.map((env, i) => (
                <button
                  key={i}
                  onClick={() => setSelectedEnv(env)}
                  className={`px-2.5 py-1.5 rounded-xl text-xs transition-all ${
                    selectedEnv === env
                      ? 'bg-pink-600 text-white font-semibold shadow-md'
                      : 'bg-white/5 text-slate-400 hover:text-white border border-white/5'
                  }`}
                >
                  {env}
                </button>
              ))}
            </div>
          </div>

          {/* Style & Lighting */}
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-300 block">
              3. Style & Lighting
            </label>
            <div className="flex flex-wrap gap-1.5">
              {stylePresets.slice(0, 6).map((style) => (
                <button
                  key={style.id}
                  onClick={() => setSelectedStyle(style.id)}
                  className={`px-2.5 py-1.5 rounded-xl text-xs transition-all ${
                    selectedStyle === style.id
                      ? 'bg-cyan-600 text-white font-semibold shadow-md'
                      : 'bg-white/5 text-slate-400 hover:text-white border border-white/5'
                  }`}
                >
                  {style.icon} {style.name}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Live Composed Output Box */}
        <div className="p-4 sm:p-5 rounded-2xl bg-black/50 border border-white/10 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-indigo-400 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5" /> Synthesized Prompt Recipe
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleCopy(constructedPrompt, 'matrix')}
                className="text-xs text-slate-400 hover:text-white flex items-center gap-1 font-medium"
              >
                {copiedIndex === 'matrix' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                {copiedIndex === 'matrix' ? 'Copied' : 'Copy'}
              </button>
            </div>
          </div>

          <p className="text-xs sm:text-sm text-slate-200 font-mono leading-relaxed bg-slate-900/60 p-3.5 rounded-xl border border-white/5">
            {constructedPrompt}
          </p>

          <div className="flex justify-end pt-1">
            <button
              onClick={() => handleSendToStudio(constructedPrompt, selectedStyle)}
              className="px-5 py-2.5 rounded-xl text-xs font-semibold text-white glow-btn flex items-center gap-2"
            >
              <Wand2 className="w-4 h-4" /> Load in Studio & Generate
            </button>
          </div>
        </div>
      </div>

      {/* Curated Categorized Prompt Decks */}
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-white">Curated Recipe Decks</h2>
            <p className="text-xs text-slate-400">Tested and verified prompts across popular AI genres</p>
          </div>

          <div className="flex items-center gap-2 overflow-x-auto pb-1">
            {inspirationCategories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setActiveCategory(cat.id)}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all flex items-center gap-1.5 border ${
                  activeCategory === cat.id
                    ? 'bg-white/15 text-white border-white/30'
                    : 'bg-black/20 text-slate-400 border-white/5 hover:text-white'
                }`}
              >
                <span>{cat.icon}</span>
                <span>{cat.name}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Prompt Deck Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {currentCategoryData.prompts.map((item, idx) => (
            <div
              key={idx}
              className="glass-card rounded-2xl p-5 border border-white/10 flex flex-col justify-between space-y-4 group"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-sm text-white group-hover:text-indigo-400 transition-colors">
                    {item.title}
                  </h3>
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-white/10 text-indigo-300 capitalize">
                    {item.style}
                  </span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed font-mono bg-black/40 p-3 rounded-xl border border-white/5 line-clamp-4">
                  {item.prompt}
                </p>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-white/5">
                <button
                  onClick={() => handleCopy(item.prompt, idx)}
                  className="text-xs text-slate-400 hover:text-white flex items-center gap-1"
                >
                  {copiedIndex === idx ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  {copiedIndex === idx ? 'Copied' : 'Copy'}
                </button>

                <button
                  onClick={() => handleSendToStudio(item.prompt, item.style)}
                  className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                >
                  Use in Studio <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default InspirationLab;
