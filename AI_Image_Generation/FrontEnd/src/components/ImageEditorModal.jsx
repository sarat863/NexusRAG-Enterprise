import React, { useState, useRef, useEffect } from 'react';
import { Sliders, Download, Sparkles, X, RotateCcw, Type, Wand2, Layers, Check } from 'lucide-react';
import FileSaver from 'file-saver';
import { useToast } from './Toast';

const PRESET_FILTERS = [
  { id: 'normal', name: 'Original', brightness: 100, contrast: 100, saturation: 100, sepia: 0, grayscale: 0, hue: 0, blur: 0 },
  { id: 'cyberpunk', name: 'Cyberpunk Neon', brightness: 110, contrast: 135, saturation: 160, sepia: 0, grayscale: 0, hue: 320, blur: 0 },
  { id: 'vintage', name: 'Vintage 80s', brightness: 95, contrast: 90, saturation: 85, sepia: 45, grayscale: 0, hue: 15, blur: 0 },
  { id: 'noir', name: 'Dramatic Noir', brightness: 105, contrast: 150, saturation: 0, sepia: 0, grayscale: 100, hue: 0, blur: 0 },
  { id: 'sunset', name: 'Golden Sunset', brightness: 105, contrast: 110, saturation: 130, sepia: 25, grayscale: 0, hue: 350, blur: 0 },
  { id: 'hdr', name: 'Vivid HDR', brightness: 105, contrast: 125, saturation: 140, sepia: 0, grayscale: 0, hue: 0, blur: 0 },
  { id: 'emerald', name: 'Emerald Glow', brightness: 100, contrast: 120, saturation: 130, sepia: 0, grayscale: 0, hue: 90, blur: 0 }
];

const ImageEditorModal = ({ isOpen, onClose, imageSrc, prompt, onSaveEdited }) => {
  const { showToast } = useToast();
  const canvasRef = useRef(null);

  const [activeTab, setActiveTab] = useState('adjust'); // 'adjust', 'filters', 'watermark'
  const [brightness, setBrightness] = useState(100);
  const [contrast, setContrast] = useState(100);
  const [saturation, setSaturation] = useState(100);
  const [sepia, setSepia] = useState(0);
  const [grayscale, setGrayscale] = useState(0);
  const [hue, setHue] = useState(0);
  const [blur, setBlur] = useState(0);

  const [watermarkText, setWatermarkText] = useState('');
  const [watermarkPos, setWatermarkPos] = useState('bottom-right');
  const [exportFormat, setExportFormat] = useState('png');
  const [isUpscaled, setIsUpscaled] = useState(false);

  // Render to canvas whenever filters change
  useEffect(() => {
    if (!isOpen || !imageSrc) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = imageSrc;

    img.onload = () => {
      const scaleFactor = isUpscaled ? 2 : 1;
      canvas.width = (img.naturalWidth || 1024) * scaleFactor;
      canvas.height = (img.naturalHeight || 1024) * scaleFactor;

      ctx.save();
      ctx.filter = `brightness(${brightness}%) contrast(${contrast}%) saturate(${saturation}%) sepia(${sepia}%) grayscale(${grayscale}%) hue-rotate(${hue}deg) blur(${blur}px)`;
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      ctx.restore();

      // Draw watermark text if provided
      if (watermarkText.trim()) {
        ctx.save();
        const fontSize = Math.max(20, Math.floor(canvas.width * 0.035));
        ctx.font = `600 ${fontSize}px "Plus Jakarta Sans", sans-serif`;
        ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
        ctx.shadowColor = 'rgba(0, 0, 0, 0.8)';
        ctx.shadowBlur = 8;
        ctx.shadowOffsetX = 2;
        ctx.shadowOffsetY = 2;

        const textMetrics = ctx.measureText(watermarkText);
        const padding = 30;

        let x = canvas.width - textMetrics.width - padding;
        let y = canvas.height - padding;

        if (watermarkPos === 'top-left') {
          x = padding;
          y = padding + fontSize;
        } else if (watermarkPos === 'top-right') {
          x = canvas.width - textMetrics.width - padding;
          y = padding + fontSize;
        } else if (watermarkPos === 'bottom-left') {
          x = padding;
          y = canvas.height - padding;
        } else if (watermarkPos === 'center') {
          x = (canvas.width - textMetrics.width) / 2;
          y = canvas.height / 2;
        }

        ctx.fillText(watermarkText, x, y);
        ctx.restore();
      }
    };
  }, [isOpen, imageSrc, brightness, contrast, saturation, sepia, grayscale, hue, blur, watermarkText, watermarkPos, isUpscaled]);

  if (!isOpen || !imageSrc) return null;

  const handleApplyPreset = (preset) => {
    setBrightness(preset.brightness);
    setContrast(preset.contrast);
    setSaturation(preset.saturation);
    setSepia(preset.sepia);
    setGrayscale(preset.grayscale);
    setHue(preset.hue);
    setBlur(preset.blur);
  };

  const handleReset = () => {
    handleApplyPreset(PRESET_FILTERS[0]);
    setWatermarkText('');
    setIsUpscaled(false);
  };

  const handleExportDownload = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let mimeType = 'image/png';
    if (exportFormat === 'jpg') mimeType = 'image/jpeg';
    if (exportFormat === 'webp') mimeType = 'image/webp';

    canvas.toBlob((blob) => {
      if (blob) {
        FileSaver.saveAs(blob, `aether-edit-${Date.now()}.${exportFormat}`);
        showToast(`Exported as ${exportFormat.toUpperCase()} successfully!`);
      }
    }, mimeType, 0.95);
  };

  const handleSaveToStudio = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dataUrl = canvas.toDataURL('image/png', 0.95);
    if (onSaveEdited) {
      onSaveEdited(dataUrl);
    }
    showToast('Applied edited image to Studio!');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-xl animate-fadeIn">
      <div className="relative w-full max-w-5xl max-h-[92vh] glass-panel rounded-2xl border border-white/10 shadow-2xl flex flex-col overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">AI Canvas & Post-Processing Studio</h2>
              <p className="text-xs text-slate-400">Enhance colors, apply visual grading filters, add watermarks and upscale</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">
          {/* Left Canvas Viewport */}
          <div className="lg:col-span-7 p-6 flex flex-col items-center justify-center bg-black/50 overflow-hidden relative">
            <div className="w-full h-full max-h-[500px] flex items-center justify-center">
              <canvas
                ref={canvasRef}
                className="max-w-full max-h-full object-contain rounded-xl shadow-2xl border border-white/10"
              />
            </div>
            {isUpscaled && (
              <span className="absolute top-4 left-4 px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-500/20 border border-indigo-500/40 text-indigo-300">
                ✨ 2x Super-Res Enabled
              </span>
            )}
          </div>

          {/* Right Control Panel */}
          <div className="lg:col-span-5 p-6 border-t lg:border-t-0 lg:border-l border-white/10 flex flex-col overflow-y-auto max-h-[550px] bg-slate-900/40">
            {/* Tabs */}
            <div className="flex items-center gap-1 p-1 bg-black/40 rounded-xl border border-white/5 mb-5">
              <button
                onClick={() => setActiveTab('adjust')}
                className={`flex-1 py-1.5 px-3 text-xs font-semibold rounded-lg transition-all flex items-center justify-center gap-1.5 ${
                  activeTab === 'adjust' ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
                }`}
              >
                <Sliders className="w-3.5 h-3.5" /> Adjust
              </button>
              <button
                onClick={() => setActiveTab('filters')}
                className={`flex-1 py-1.5 px-3 text-xs font-semibold rounded-lg transition-all flex items-center justify-center gap-1.5 ${
                  activeTab === 'filters' ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
                }`}
              >
                <Sparkles className="w-3.5 h-3.5" /> Presets
              </button>
              <button
                onClick={() => setActiveTab('watermark')}
                className={`flex-1 py-1.5 px-3 text-xs font-semibold rounded-lg transition-all flex items-center justify-center gap-1.5 ${
                  activeTab === 'watermark' ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
                }`}
              >
                <Type className="w-3.5 h-3.5" /> Watermark
              </button>
            </div>

            {/* Tab 1: Manual Adjustments */}
            {activeTab === 'adjust' && (
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-xs font-medium text-slate-300 mb-1">
                    <span>Brightness</span>
                    <span>{brightness}%</span>
                  </div>
                  <input
                    type="range"
                    min="50"
                    max="160"
                    value={brightness}
                    onChange={(e) => setBrightness(Number(e.target.value))}
                    className="w-full accent-indigo-500 cursor-pointer"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-xs font-medium text-slate-300 mb-1">
                    <span>Contrast</span>
                    <span>{contrast}%</span>
                  </div>
                  <input
                    type="range"
                    min="50"
                    max="170"
                    value={contrast}
                    onChange={(e) => setContrast(Number(e.target.value))}
                    className="w-full accent-indigo-500 cursor-pointer"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-xs font-medium text-slate-300 mb-1">
                    <span>Saturation / Vibrance</span>
                    <span>{saturation}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="200"
                    value={saturation}
                    onChange={(e) => setSaturation(Number(e.target.value))}
                    className="w-full accent-indigo-500 cursor-pointer"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-xs font-medium text-slate-300 mb-1">
                    <span>Warmth / Sepia</span>
                    <span>{sepia}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={sepia}
                    onChange={(e) => setSepia(Number(e.target.value))}
                    className="w-full accent-indigo-500 cursor-pointer"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-xs font-medium text-slate-300 mb-1">
                    <span>Hue Shift</span>
                    <span>{hue}°</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="360"
                    value={hue}
                    onChange={(e) => setHue(Number(e.target.value))}
                    className="w-full accent-purple-500 cursor-pointer"
                  />
                </div>

                {/* 2x Super-Resolution Toggle */}
                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => setIsUpscaled(!isUpscaled)}
                    className={`w-full py-2 px-3 rounded-xl border text-xs font-semibold transition-all flex items-center justify-center gap-2 ${
                      isUpscaled
                        ? 'bg-purple-600/30 border-purple-500 text-purple-200 shadow-md'
                        : 'bg-white/5 border-white/10 text-slate-300 hover:bg-white/10'
                    }`}
                  >
                    <Wand2 className="w-3.5 h-3.5" /> {isUpscaled ? '2x Super-Res Active (HD)' : 'Enable 2x Super-Resolution'}
                  </button>
                </div>
              </div>
            )}

            {/* Tab 2: Filter Presets */}
            {activeTab === 'filters' && (
              <div className="grid grid-cols-2 gap-2.5">
                {PRESET_FILTERS.map((preset) => (
                  <button
                    key={preset.id}
                    onClick={() => handleApplyPreset(preset)}
                    className="p-3 text-left rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 transition-all hover:border-indigo-500/50 group"
                  >
                    <p className="text-xs font-bold text-white group-hover:text-indigo-400 transition-colors">
                      {preset.name}
                    </p>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      C:{preset.contrast}% S:{preset.saturation}%
                    </p>
                  </button>
                ))}
              </div>
            )}

            {/* Tab 3: Watermark */}
            {activeTab === 'watermark' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Watermark Text or Signature
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Created by Aria • 2026"
                    value={watermarkText}
                    onChange={(e) => setWatermarkText(e.target.value)}
                    className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Position
                  </label>
                  <select
                    value={watermarkPos}
                    onChange={(e) => setWatermarkPos(e.target.value)}
                    className="w-full glass-input px-3 py-2 rounded-xl text-xs bg-slate-900"
                  >
                    <option value="bottom-right">Bottom Right</option>
                    <option value="bottom-left">Bottom Left</option>
                    <option value="top-right">Top Right</option>
                    <option value="top-left">Top Left</option>
                    <option value="center">Center Subtle</option>
                  </select>
                </div>
              </div>
            )}

            {/* Quick Reset */}
            <div className="mt-auto pt-5 border-t border-white/10 flex items-center justify-between">
              <button
                onClick={handleReset}
                className="text-xs text-slate-400 hover:text-white flex items-center gap-1 transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" /> Reset All
              </button>

              <div className="flex items-center gap-1.5">
                <span className="text-[11px] text-slate-400">Format:</span>
                <select
                  value={exportFormat}
                  onChange={(e) => setExportFormat(e.target.value)}
                  className="bg-black/60 text-white border border-white/10 text-xs rounded-lg px-2 py-1"
                >
                  <option value="png">PNG</option>
                  <option value="jpg">JPG</option>
                  <option value="webp">WebP</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 border-t border-white/10 bg-slate-950/60 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <div className="flex items-center gap-3">
            <button
              onClick={handleExportDownload}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-white/10 hover:bg-white/20 border border-white/15 transition-all flex items-center gap-2"
            >
              <Download className="w-3.5 h-3.5" /> Download {exportFormat.toUpperCase()}
            </button>
            <button
              onClick={handleSaveToStudio}
              className="px-5 py-2 rounded-xl text-xs font-semibold text-white glow-btn flex items-center gap-2"
            >
              <Check className="w-3.5 h-3.5" /> Apply to Studio
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ImageEditorModal;
