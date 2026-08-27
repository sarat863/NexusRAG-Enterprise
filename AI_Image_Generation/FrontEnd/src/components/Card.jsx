import React, { useState } from 'react';
import { Download, Heart, Wand2, Copy, Check, Sparkles, Maximize2 } from 'lucide-react';
import { downloadImage, toggleFavorite, isFavorite, API_BASE_URL, triggerConfetti } from '../utils';
import { useToast } from './Toast';

const Card = ({ _id, name, prompt, photo, model, style, aspectRatio, likes: initialLikes = 0, onOpenLightbox, onRemix }) => {
  const { showToast } = useToast();
  const [likes, setLikes] = useState(initialLikes);
  const [hasLiked, setHasLiked] = useState(false);
  const [copied, setCopied] = useState(false);

  const isFav = isFavorite(_id, photo);

  const handleLike = async (e) => {
    e.stopPropagation();
    const newLikedState = !hasLiked;
    setHasLiked(newLikedState);
    const newLikesCount = newLikedState ? likes + 1 : Math.max(0, likes - 1);
    setLikes(newLikesCount);

    if (newLikedState) {
      triggerConfetti();
    }

    try {
      await fetch(`${API_BASE_URL}/post/${_id}/like`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: newLikedState ? 'like' : 'unlike' })
      });
    } catch {
      // Optimistic state remains
    }
  };

  const handleCopyPrompt = (e) => {
    e.stopPropagation();
    navigator.clipboard.writeText(prompt);
    setCopied(true);
    showToast('Prompt copied to clipboard!');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = (e) => {
    e.stopPropagation();
    downloadImage(_id, photo, 'png', `aether-${name?.toLowerCase().replace(/\s+/g, '-') || 'art'}`);
    showToast('Downloading image...');
  };

  const handleRemixClick = (e) => {
    e.stopPropagation();
    if (onRemix) {
      onRemix({ prompt, model, style, aspectRatio });
    }
  };

  return (
    <div
      onClick={onOpenLightbox}
      className="group relative rounded-2xl overflow-hidden glass-card cursor-pointer border border-white/10 hover:border-indigo-500/40 transition-all duration-300 transform hover:-translate-y-1 hover:shadow-2xl masonry-card bg-slate-950/40"
    >
      {/* Background Image */}
      <img
        src={photo}
        alt={prompt}
        loading="lazy"
        className="w-full h-auto object-cover transition-transform duration-500 group-hover:scale-105"
      />

      {/* Top Badges Overlay */}
      <div className="absolute top-3 left-3 right-3 flex items-center justify-between pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-10">
        <span className="px-2.5 py-1 rounded-full text-[10px] font-semibold tracking-wider uppercase bg-black/70 backdrop-blur-md text-indigo-300 border border-white/15 shadow-lg">
          {model || 'Flux.1'}
        </span>
        <button
          onClick={handleLike}
          className={`pointer-events-auto p-1.5 rounded-full backdrop-blur-md border border-white/15 transition-transform active:scale-90 ${
            hasLiked || isFav ? 'bg-rose-500 text-white' : 'bg-black/60 text-white hover:bg-black/80'
          }`}
        >
          <Heart className={`w-3.5 h-3.5 ${hasLiked || isFav ? 'fill-current' : ''}`} />
        </button>
      </div>

      {/* Hover Info Overlay */}
      <div className="absolute inset-x-0 bottom-0 p-4 bg-gradient-to-t from-black/95 via-black/80 to-transparent translate-y-2 group-hover:translate-y-0 opacity-0 group-hover:opacity-100 transition-all duration-300 flex flex-col justify-end">
        {/* Prompt snippet */}
        <p className="text-xs text-slate-200 line-clamp-2 font-medium leading-relaxed drop-shadow">
          {prompt}
        </p>

        {/* Footer info: author, likes, and actions */}
        <div className="mt-3 pt-2.5 border-t border-white/10 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-indigo-500 to-pink-500 flex items-center justify-center text-white text-[10px] font-bold shadow">
              {name ? name[0].toUpperCase() : 'A'}
            </div>
            <span className="text-xs text-slate-300 font-semibold truncate max-w-[90px]">{name}</span>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={handleCopyPrompt}
              title="Copy prompt"
              className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white transition-colors"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            </button>

            <button
              onClick={handleRemixClick}
              title="Remix prompt in studio"
              className="p-1.5 rounded-lg bg-indigo-600/80 hover:bg-indigo-600 text-white transition-colors"
            >
              <Wand2 className="w-3.5 h-3.5" />
            </button>

            <button
              onClick={handleDownload}
              title="Download image"
              className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Card;