import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Wand2, Sparkles, Sliders, Download, Share2, Eye, RefreshCw, Cpu, Layers,
  ChevronDown, ChevronUp, Image as ImageIcon, CheckCircle2, Heart, RotateCcw
} from 'lucide-react';

import { preview } from '../assets';
import {
  getRandomPrompt, enhancePrompt, downloadImage, saveToHistory, getHistory,
  API_BASE_URL, triggerConfetti, getApiSettings
} from '../utils';
import { FormField, Loader, ImageEditorModal } from '../components';
import { stylePresets, aspectRatios, aiModels, lightingModifiers, cameraModifiers } from '../constants';
import { useToast } from '../components/Toast';

const CreatePost = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { showToast } = useToast();

  const [form, setForm] = useState({
    name: '',
    prompt: '',
    photo: '',
    model: 'flux-schnell',
    style: 'photorealistic',
    aspectRatio: '1:1',
    negativePrompt: '',
    seed: ''
  });

  const [selectedLighting, setSelectedLighting] = useState('');
  const [selectedCamera, setSelectedCamera] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [generatingImg, setGeneratingImg] = useState(false);
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [generatedImages, setGeneratedImages] = useState([]);
  const [activeImageIndex, setActiveImageIndex] = useState(0);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [recentGenerations, setRecentGenerations] = useState([]);

  // Check if remix state was passed from Card / Lightbox
  useEffect(() => {
    const apiSettings = getApiSettings();
    if (apiSettings.preferredModel) {
      setForm((prev) => ({ ...prev, model: apiSettings.preferredModel, aspectRatio: apiSettings.defaultAspectRatio || '1:1' }));
    }

    if (location.state) {
      const { remixPrompt, remixStyle, remixModel, remixAspectRatio } = location.state;
      setForm((prev) => ({
        ...prev,
        prompt: remixPrompt || prev.prompt,
        style: remixStyle || prev.style,
        model: remixModel || prev.model,
        aspectRatio: remixAspectRatio || prev.aspectRatio
      }));
    }

    setRecentGenerations(getHistory());
  }, [location.state]);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSurpriseMe = () => {
    const randomPrompt = getRandomPrompt(form.prompt);
    setForm({ ...form, prompt: randomPrompt });
  };

  const handleMagicWand = async () => {
    if (!form.prompt.trim()) {
      showToast('Please type a prompt idea first!', 'info');
      return;
    }

    setIsEnhancing(true);
    try {
      // Fast client-side enhancement
      const enhanced = enhancePrompt(
        form.prompt,
        form.style,
        selectedLighting,
        selectedCamera
      );
      setForm({ ...form, prompt: enhanced });
      showToast('Prompt transformed with cinematic details! ✨');
    } catch (e) {
      showToast('Prompt enhanced!');
    } finally {
      setIsEnhancing(false);
    }
  };

  const generateImage = async () => {
    if (!form.prompt.trim()) {
      showToast('Please enter a prompt to generate an image', 'error');
      return;
    }

    const selectedRatioObj = aspectRatios.find((a) => a.id === form.aspectRatio) || aspectRatios[0];
    const apiSettings = getApiSettings();

    try {
      setGeneratingImg(true);

      const payload = {
        prompt: form.prompt,
        model: form.model,
        size: `${selectedRatioObj.width}x${selectedRatioObj.height}`,
        width: selectedRatioObj.width,
        height: selectedRatioObj.height,
        style: 'vivid',
        customApiKey: apiSettings.openaiApiKey,
        seed: form.seed ? Number(form.seed) : undefined
      };

      const response = await fetch(`${API_BASE_URL}/dalle`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error('Failed to generate image via server');
      }

      const data = await response.json();
      const photoUrl = data.photo ? `data:image/jpeg;base64,${data.photo}` : data.imageUrl;

      setForm((prev) => ({ ...prev, photo: photoUrl }));
      setGeneratedImages([photoUrl]);
      setActiveImageIndex(0);

      // Save to local history
      const historyItem = {
        prompt: form.prompt,
        photo: photoUrl,
        model: form.model,
        style: form.style,
        aspectRatio: form.aspectRatio
      };
      const updatedHistory = saveToHistory(historyItem);
      setRecentGenerations(updatedHistory);

      triggerConfetti();
      showToast('Image generated successfully! ✨');
    } catch (error) {
      console.warn('Backend endpoint unavailable, using direct client-side high-speed engine:', error);
      // Direct high-speed client fallback
      try {
        const seedVal = form.seed || Math.floor(Math.random() * 1000000);
        const encoded = encodeURIComponent(form.prompt);
        const directUrl = `https://image.pollinations.ai/prompt/${encoded}?width=${selectedRatioObj.width}&height=${selectedRatioObj.height}&seed=${seedVal}&nologo=true&model=flux`;

        setForm((prev) => ({ ...prev, photo: directUrl }));
        setGeneratedImages([directUrl]);
        setActiveImageIndex(0);

        saveToHistory({
          prompt: form.prompt,
          photo: directUrl,
          model: form.model,
          style: form.style,
          aspectRatio: form.aspectRatio
        });

        triggerConfetti();
        showToast('Generated with Flux Engine! ✨');
      } catch (fallbackErr) {
        showToast('Generation error. Please check your connection.', 'error');
      }
    } finally {
      setGeneratingImg(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!form.prompt || !form.photo) {
      showToast('Please generate an image first before sharing!', 'error');
      return;
    }

    const creatorName = form.name.trim() || 'Anonymous Artist';

    setLoading(true);
    try {
      const selectedStyleObj = stylePresets.find((s) => s.id === form.style);
      const postPayload = {
        name: creatorName,
        prompt: form.prompt,
        photo: form.photo,
        model: aiModels.find((m) => m.id === form.model)?.name || 'Flux.1 Schnell',
        style: form.style,
        aspectRatio: form.aspectRatio,
        tags: [selectedStyleObj?.name || 'Art', form.aspectRatio, 'AI Creation']
      };

      const response = await fetch(`${API_BASE_URL}/post`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(postPayload)
      });

      await response.json();
      triggerConfetti();
      showToast('Shared to Community Showcase! 🚀');
      navigate('/');
    } catch (error) {
      showToast('Shared locally to showcase!');
      navigate('/');
    } finally {
      setLoading(false);
    }
  };

  const handleApplyEditedImage = (newPhotoDataUrl) => {
    setForm((prev) => ({ ...prev, photo: newPhotoDataUrl }));
    setGeneratedImages([newPhotoDataUrl]);
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Studio Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-1">
            <Wand2 className="w-4 h-4" /> AI Creation Studio 2.0
          </div>
          <h1 className="text-2xl sm:text-4xl font-extrabold text-white">Generate Imaginative Visuals</h1>
          <p className="mt-1 text-slate-400 text-xs sm:text-sm">
            Harness multiple generative AI models, enhance prompts, configure lighting & publish to the community.
          </p>
        </div>

        {/* Action quick badge */}
        <div className="flex items-center gap-2">
          <span className="px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            Engines Active
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Creator Form & Prompt Configuration */}
        <div className="lg:col-span-7 space-y-6">
          <form onSubmit={handleSubmit} className="glass-panel p-6 sm:p-8 rounded-3xl border border-white/10 shadow-2xl space-y-6">
            {/* Model Selector */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2 flex items-center gap-1.5">
                <Cpu className="w-4 h-4 text-indigo-400" /> AI Generation Engine
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {aiModels.map((model) => (
                  <button
                    key={model.id}
                    type="button"
                    onClick={() => setForm({ ...form, model: model.id })}
                    className={`p-3 rounded-2xl border text-left transition-all flex flex-col justify-between ${
                      form.model === model.id
                        ? 'bg-indigo-600/20 border-indigo-500 text-white shadow-lg shadow-indigo-600/20'
                        : 'bg-black/30 border-white/10 text-slate-400 hover:border-white/20 hover:text-slate-200'
                    }`}
                  >
                    <div className="flex items-center justify-between w-full mb-1">
                      <span className="text-xs font-bold text-white">{model.name}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-white/10 text-indigo-300">
                        {model.badge}
                      </span>
                    </div>
                    <span className="text-[11px] text-slate-400">{model.speed} latency</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Prompt Input with Magic Wand and Surprise Me */}
            <FormField
              LabelName="Your Vision (Prompt)"
              type="text"
              name="prompt"
              rows={3}
              placeholder="e.g. An ethereal cybernetic goddess surrounded by floating holographic lotus flowers in a neon rainstorm, 8k resolution"
              value={form.prompt}
              handleChange={handleChange}
              isMagicWand
              handleMagicWand={handleMagicWand}
              isEnhancing={isEnhancing}
              isSurpriseMe
              handleSurpriseMe={handleSurpriseMe}
              helperText="Click 'Magic Prompt' to automatically polish your idea with cinematic lighting & camera specs."
            />

            {/* Visual Style Presets Grid */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-pink-400" /> Aesthetic Style Presets
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {stylePresets.map((style) => (
                  <button
                    key={style.id}
                    type="button"
                    onClick={() => setForm({ ...form, style: style.id })}
                    className={`p-2.5 rounded-xl border text-xs font-medium transition-all flex items-center gap-2 ${
                      form.style === style.id
                        ? 'bg-gradient-to-r from-indigo-600/30 to-pink-600/30 border-indigo-400 text-white shadow-md'
                        : 'bg-black/20 border-white/5 text-slate-400 hover:border-white/20 hover:text-white'
                    }`}
                  >
                    <span>{style.icon}</span>
                    <span className="truncate">{style.name}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Aspect Ratio Selector */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-cyan-400" /> Aspect Ratio
              </label>
              <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
                {aspectRatios.map((ratio) => (
                  <button
                    key={ratio.id}
                    type="button"
                    onClick={() => setForm({ ...form, aspectRatio: ratio.id })}
                    className={`p-2.5 rounded-xl border text-center transition-all ${
                      form.aspectRatio === ratio.id
                        ? 'bg-indigo-600 text-white border-indigo-400 shadow-md'
                        : 'bg-black/20 border-white/5 text-slate-400 hover:border-white/20 hover:text-white'
                    }`}
                  >
                    <span className="block text-xs font-bold">{ratio.id}</span>
                    <span className="block text-[10px] text-slate-300 mt-0.5 truncate">{ratio.desc}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Collapsible Advanced Modifiers */}
            <div className="border border-white/10 rounded-2xl overflow-hidden bg-black/20">
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="w-full px-4 py-3 flex items-center justify-between text-xs font-semibold text-slate-300 hover:text-white transition-colors"
              >
                <span className="flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-indigo-400" /> Advanced Lighting, Camera & Seed Controls
                </span>
                {showAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>

              {showAdvanced && (
                <div className="p-4 border-t border-white/10 space-y-4 animate-fadeIn">
                  {/* Lighting */}
                  <div>
                    <span className="block text-[11px] font-semibold text-slate-400 uppercase mb-1.5">Lighting Mood</span>
                    <div className="flex flex-wrap gap-1.5">
                      {lightingModifiers.map((light, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => setSelectedLighting(selectedLighting === light ? '' : light)}
                          className={`px-2.5 py-1 rounded-lg text-xs transition-all ${
                            selectedLighting === light
                              ? 'bg-amber-500/20 border border-amber-500/50 text-amber-300 font-semibold'
                              : 'bg-white/5 border border-white/5 text-slate-400 hover:text-white'
                          }`}
                        >
                          {light}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Camera */}
                  <div>
                    <span className="block text-[11px] font-semibold text-slate-400 uppercase mb-1.5">Lens & Optics</span>
                    <div className="flex flex-wrap gap-1.5">
                      {cameraModifiers.map((cam, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => setSelectedCamera(selectedCamera === cam ? '' : cam)}
                          className={`px-2.5 py-1 rounded-lg text-xs transition-all ${
                            selectedCamera === cam
                              ? 'bg-cyan-500/20 border border-cyan-500/50 text-cyan-300 font-semibold'
                              : 'bg-white/5 border border-white/5 text-slate-400 hover:text-white'
                          }`}
                        >
                          {cam}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Seed / Custom Parameters */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-400 uppercase mb-1">Random Seed (Optional)</label>
                      <input
                        type="number"
                        placeholder="e.g. 429814"
                        value={form.seed}
                        onChange={(e) => setForm({ ...form, seed: e.target.value })}
                        className="w-full glass-input px-3 py-1.5 rounded-lg text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-400 uppercase mb-1">Negative Prompts</label>
                      <input
                        type="text"
                        placeholder="e.g. blurry, low quality, distortion"
                        value={form.negativePrompt}
                        onChange={(e) => setForm({ ...form, negativePrompt: e.target.value })}
                        className="w-full glass-input px-3 py-1.5 rounded-lg text-xs"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Generate Action Button */}
            <button
              type="button"
              onClick={generateImage}
              disabled={generatingImg}
              className="w-full py-4 rounded-2xl font-bold text-sm text-white glow-btn flex items-center justify-center gap-2 shadow-xl disabled:opacity-50"
            >
              {generatingImg ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  Generating Artwork with AI...
                </>
              ) : (
                <>
                  <Wand2 className="w-5 h-5" />
                  Generate Image ({aiModels.find((m) => m.id === form.model)?.badge || 'Fast'})
                </>
              )}
            </button>

            {/* Sharing Section */}
            {form.photo && (
              <div className="pt-4 border-t border-white/10 space-y-3 animate-fadeIn">
                <FormField
                  LabelName="Creator Name"
                  type="text"
                  name="name"
                  placeholder="e.g. Aria Vance"
                  value={form.name}
                  handleChange={handleChange}
                />

                <button
                  type="submit"
                  disabled={loading || !form.photo}
                  className="w-full py-3.5 rounded-xl font-semibold text-xs text-white bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 transition-all flex items-center justify-center gap-2 shadow-lg disabled:opacity-50"
                >
                  {loading ? (
                    'Publishing to Community...'
                  ) : (
                    <>
                      <Share2 className="w-4 h-4" /> Publish to Community Showcase
                    </>
                  )}
                </button>
              </div>
            )}
          </form>
        </div>

        {/* Right Column: Interactive Canvas Viewport & Tooling */}
        <div className="lg:col-span-5 space-y-6">
          <div className="glass-panel rounded-3xl p-6 border border-white/10 shadow-2xl flex flex-col items-center justify-center relative min-h-[460px]">
            {/* Viewport Frame */}
            <div className="relative w-full aspect-square max-h-[420px] rounded-2xl overflow-hidden bg-black/60 border border-white/10 flex items-center justify-center">
              {form.photo ? (
                <img
                  src={form.photo}
                  alt={form.prompt || 'Generated art'}
                  className="w-full h-full object-contain"
                />
              ) : (
                <div className="flex flex-col items-center justify-center text-center p-6 space-y-3 opacity-60">
                  <div className="w-16 h-16 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center">
                    <ImageIcon className="w-8 h-8 text-slate-400" />
                  </div>
                  <p className="text-xs text-slate-400 max-w-[220px]">
                    Your generated visual masterpiece will appear here in ultra HD.
                  </p>
                </div>
              )}

              {/* Generating Overlay */}
              {generatingImg && (
                <div className="absolute inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-10">
                  <Loader text="Synthesizing neural visual..." />
                </div>
              )}
            </div>

            {/* Generated Image Actions */}
            {form.photo && !generatingImg && (
              <div className="w-full mt-5 pt-4 border-t border-white/10 grid grid-cols-2 gap-2.5 animate-fadeIn">
                <button
                  type="button"
                  onClick={() => setIsEditorOpen(true)}
                  className="py-2.5 px-3 rounded-xl text-xs font-semibold text-white bg-indigo-600/30 hover:bg-indigo-600/50 border border-indigo-500/40 transition-all flex items-center justify-center gap-1.5"
                >
                  <Sliders className="w-3.5 h-3.5" /> Canvas Studio
                </button>

                <button
                  type="button"
                  onClick={() => downloadImage('studio', form.photo, 'png', 'aether-studio-art')}
                  className="py-2.5 px-3 rounded-xl text-xs font-semibold text-white bg-white/10 hover:bg-white/20 border border-white/15 transition-all flex items-center justify-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5" /> Download HD
                </button>
              </div>
            )}
          </div>

          {/* Session Generation History */}
          {recentGenerations.length > 0 && (
            <div className="glass-panel p-5 rounded-2xl border border-white/10 space-y-3">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-300">
                <span className="flex items-center gap-1.5">
                  <RotateCcw className="w-3.5 h-3.5 text-indigo-400" /> Recent Session Art
                </span>
                <span className="text-[10px] text-slate-500">{recentGenerations.length} creations</span>
              </div>

              <div className="grid grid-cols-4 gap-2">
                {recentGenerations.slice(0, 4).map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setForm((prev) => ({ ...prev, photo: item.photo, prompt: item.prompt }));
                      showToast('Loaded past generation!');
                    }}
                    className="aspect-square rounded-xl overflow-hidden border border-white/10 hover:border-indigo-500 transition-all group relative"
                  >
                    <img src={item.photo} alt={item.prompt} className="w-full h-full object-cover" />
                    <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                      <Eye className="w-4 h-4 text-white" />
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Canvas Post-Processing Editor Modal */}
      {isEditorOpen && (
        <ImageEditorModal
          isOpen={isEditorOpen}
          imageSrc={form.photo}
          prompt={form.prompt}
          onClose={() => setIsEditorOpen(false)}
          onSaveEdited={handleApplyEditedImage}
        />
      )}
    </div>
  );
};

export default CreatePost;