import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { X, Copy, Check, Download, Wand2, Heart, MessageSquare, Send, Sparkles, Share2, Tag, Calendar, User, Cpu } from 'lucide-react';
import { downloadImage, toggleFavorite, isFavorite, API_BASE_URL, triggerConfetti } from '../utils';
import { useToast } from './Toast';

const LightboxModal = ({ isOpen, onClose, post, onPostUpdated }) => {
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [copied, setCopied] = useState(false);
  const [downloadFormat, setDownloadFormat] = useState('png');
  const [commentText, setCommentText] = useState('');
  const [commentUser, setCommentUser] = useState('');
  const [submittingComment, setSubmittingComment] = useState(false);
  const [reactions, setReactions] = useState(post?.reactions || { fire: 0, heart: 0, rocket: 0, mindblown: 0 });

  if (!isOpen || !post) return null;

  const isFav = isFavorite(post._id, post.photo);

  const handleCopyPrompt = () => {
    navigator.clipboard.writeText(post.prompt);
    setCopied(true);
    showToast('Prompt copied to clipboard!');
    setTimeout(() => setCopied(false), 2500);
  };

  const handleRemix = () => {
    onClose();
    navigate('/create-post', {
      state: {
        remixPrompt: post.prompt,
        remixStyle: post.style || 'photorealistic',
        remixModel: post.model || 'flux-schnell',
        remixAspectRatio: post.aspectRatio || '1:1'
      }
    });
    showToast('Prompt loaded into Studio! Tweak and generate iterations ✨', 'info');
  };

  const handleFavoriteToggle = () => {
    const result = toggleFavorite(post);
    if (result.isFavorite) {
      triggerConfetti();
      showToast('Saved to your Favorites collection! ❤️');
    } else {
      showToast('Removed from Favorites.');
    }
    if (onPostUpdated) onPostUpdated();
  };

  const handleDownload = () => {
    downloadImage(post._id, post.photo, downloadFormat, `aether-${post.name.toLowerCase().replace(/\s+/g, '-')}`);
    showToast(`Downloaded image as ${downloadFormat.toUpperCase()}!`);
  };

  const handleReaction = (type) => {
    setReactions((prev) => ({
      ...prev,
      [type]: (prev[type] || 0) + 1
    }));
    triggerConfetti();
    showToast(`Reacted with ${type === 'fire' ? '🔥' : type === 'heart' ? '❤️' : type === 'rocket' ? '🚀' : '🤯'}!`);
  };

  const handleAddComment = async (e) => {
    e.preventDefault();
    if (!commentText.trim()) return;

    setSubmittingComment(true);
    const author = commentUser.trim() || 'Creative Soul';
    const newCommentObj = {
      id: `comm-${Date.now()}`,
      user: author,
      text: commentText.trim(),
      time: 'Just now'
    };

    try {
      // Optimistic update
      if (!post.comments) post.comments = [];
      post.comments.push(newCommentObj);

      await fetch(`${API_BASE_URL}/post/${post._id}/comment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user: author, text: commentText.trim() })
      });

      setCommentText('');
      showToast('Comment posted!');
      if (onPostUpdated) onPostUpdated();
    } catch {
      showToast('Comment saved locally!');
    } finally {
      setSubmittingComment(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-black/90 backdrop-blur-2xl animate-fadeIn">
      <div className="relative w-full max-w-6xl max-h-[95vh] glass-panel rounded-2xl border border-white/15 shadow-2xl flex flex-col lg:flex-row overflow-hidden">
        {/* Close Button Top Right */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-20 p-2 rounded-xl bg-black/60 hover:bg-black/90 border border-white/10 text-white transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Left: Image Viewport */}
        <div className="flex-1 flex items-center justify-center p-4 sm:p-8 bg-black/60 overflow-hidden relative min-h-[320px] lg:min-h-[600px]">
          <img
            src={post.photo}
            alt={post.prompt}
            className="max-w-full max-h-[75vh] object-contain rounded-xl shadow-2xl border border-white/10"
          />

          {/* Quick Floating Action Bar */}
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-2 px-4 py-2 rounded-full glass-panel border border-white/15 shadow-2xl">
            <button
              onClick={handleFavoriteToggle}
              className={`p-2 rounded-full transition-all ${
                isFav ? 'bg-rose-500/20 text-rose-400' : 'text-slate-300 hover:text-white hover:bg-white/10'
              }`}
              title="Save to favorites"
            >
              <Heart className={`w-4 h-4 ${isFav ? 'fill-rose-500' : ''}`} />
            </button>
            <div className="w-px h-4 bg-white/15" />
            <button
              onClick={handleRemix}
              className="px-3 py-1.5 rounded-full text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition-colors flex items-center gap-1.5 shadow-lg"
            >
              <Wand2 className="w-3.5 h-3.5" /> Remix in Studio
            </button>
          </div>
        </div>

        {/* Right: Detailed Metadata & Social Sidebar */}
        <div className="w-full lg:w-[420px] flex flex-col bg-slate-950/80 border-t lg:border-t-0 lg:border-l border-white/10 overflow-y-auto max-h-[90vh]">
          {/* Author Header */}
          <div className="p-5 border-b border-white/10 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 to-pink-500 flex items-center justify-center text-white font-bold text-sm shadow-md">
                {post.name ? post.name[0].toUpperCase() : 'A'}
              </div>
              <div>
                <h3 className="font-bold text-sm text-white">{post.name || 'Anonymous Creator'}</h3>
                <p className="text-[11px] text-slate-400 flex items-center gap-1">
                  <Calendar className="w-3 h-3 text-slate-500" />
                  {post.createdAt ? new Date(post.createdAt).toLocaleDateString() : 'Recent'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-indigo-500/10 border border-indigo-500/30 text-indigo-300">
                {post.model || 'Flux.1'}
              </span>
            </div>
          </div>

          {/* Prompt Section */}
          <div className="p-5 border-b border-white/10 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-indigo-400" /> Prompt
              </span>
              <button
                onClick={handleCopyPrompt}
                className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-medium"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                {copied ? 'Copied' : 'Copy Prompt'}
              </button>
            </div>
            <p className="text-xs text-slate-200 leading-relaxed bg-black/40 p-3.5 rounded-xl border border-white/5 font-mono select-all">
              {post.prompt}
            </p>

            {/* Tags */}
            {post.tags && post.tags.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {post.tags.map((tag, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-white/5 border border-white/10 text-slate-300"
                  >
                    #{tag}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Generation Specs */}
          <div className="p-5 border-b border-white/10 grid grid-cols-2 gap-3 text-xs">
            <div className="p-2.5 rounded-xl bg-white/5 border border-white/5">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Aspect Ratio</span>
              <span className="font-semibold text-slate-200 mt-0.5 block">{post.aspectRatio || '1:1'}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-white/5 border border-white/5">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Style Preset</span>
              <span className="font-semibold text-slate-200 mt-0.5 block capitalize">{post.style || 'Photoreal'}</span>
            </div>
          </div>

          {/* Emoji Vibe Reactions */}
          <div className="p-5 border-b border-white/10 space-y-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Community Vibes
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleReaction('fire')}
                className="flex-1 py-1.5 px-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs flex items-center justify-center gap-1.5 transition-all hover:scale-105"
              >
                <span>🔥</span>
                <span className="font-semibold text-slate-300">{reactions.fire || 0}</span>
              </button>
              <button
                onClick={() => handleReaction('heart')}
                className="flex-1 py-1.5 px-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs flex items-center justify-center gap-1.5 transition-all hover:scale-105"
              >
                <span>❤️</span>
                <span className="font-semibold text-slate-300">{reactions.heart || 0}</span>
              </button>
              <button
                onClick={() => handleReaction('rocket')}
                className="flex-1 py-1.5 px-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs flex items-center justify-center gap-1.5 transition-all hover:scale-105"
              >
                <span>🚀</span>
                <span className="font-semibold text-slate-300">{reactions.rocket || 0}</span>
              </button>
              <button
                onClick={() => handleReaction('mindblown')}
                className="flex-1 py-1.5 px-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs flex items-center justify-center gap-1.5 transition-all hover:scale-105"
              >
                <span>🤯</span>
                <span className="font-semibold text-slate-300">{reactions.mindblown || 0}</span>
              </button>
            </div>
          </div>

          {/* Comments Section */}
          <div className="p-5 flex-1 flex flex-col">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5 mb-3">
              <MessageSquare className="w-3.5 h-3.5 text-indigo-400" />
              Comments ({post.comments?.length || 0})
            </span>

            {/* Comments List */}
            <div className="space-y-2.5 max-h-40 overflow-y-auto mb-3 pr-1">
              {post.comments && post.comments.length > 0 ? (
                post.comments.map((comm, idx) => (
                  <div key={idx} className="p-2.5 rounded-xl bg-white/5 border border-white/5 text-xs">
                    <div className="flex justify-between items-center text-slate-400 text-[10px] mb-1">
                      <span className="font-bold text-slate-300">{comm.user}</span>
                      <span>{comm.time || 'Recently'}</span>
                    </div>
                    <p className="text-slate-200 leading-snug">{comm.text}</p>
                  </div>
                ))
              ) : (
                <p className="text-xs text-slate-500 italic text-center py-2">No comments yet. Be the first to vibe!</p>
              )}
            </div>

            {/* Add Comment Input */}
            <form onSubmit={handleAddComment} className="mt-auto space-y-2">
              <input
                type="text"
                placeholder="Your display name (optional)"
                value={commentUser}
                onChange={(e) => setCommentUser(e.target.value)}
                className="w-full glass-input px-3 py-1.5 rounded-lg text-xs"
              />
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Leave a comment..."
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  className="flex-1 glass-input px-3 py-1.5 rounded-lg text-xs"
                />
                <button
                  type="submit"
                  disabled={submittingComment || !commentText.trim()}
                  className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold flex items-center justify-center transition-colors"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              </div>
            </form>
          </div>

          {/* Download Bar Footer */}
          <div className="p-4 border-t border-white/10 bg-black/60 flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] text-slate-400">Save as:</span>
              <select
                value={downloadFormat}
                onChange={(e) => setDownloadFormat(e.target.value)}
                className="bg-slate-900 border border-white/15 text-white text-xs rounded-lg px-2 py-1"
              >
                <option value="png">PNG HD</option>
                <option value="jpg">JPG</option>
                <option value="webp">WebP</option>
              </select>
            </div>

            <button
              onClick={handleDownload}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-white glow-btn flex items-center gap-1.5"
            >
              <Download className="w-3.5 h-3.5" /> Download
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LightboxModal;
