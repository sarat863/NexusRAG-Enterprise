import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Heart, History, Trash2, Download, Wand2, Sparkles, FolderHeart, ArrowRight } from 'lucide-react';
import { getFavorites, getHistory, clearHistory, downloadImage } from '../utils';
import { Card, LightboxModal } from '../components';
import { useToast } from '../components/Toast';

const MyGallery = () => {
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [activeTab, setActiveTab] = useState('favorites'); // 'favorites', 'history'
  const [favorites, setFavorites] = useState([]);
  const [history, setHistory] = useState([]);
  const [selectedPost, setSelectedPost] = useState(null);

  const loadData = () => {
    setFavorites(getFavorites());
    setHistory(getHistory());
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleClearHistory = () => {
    if (window.confirm('Are you sure you want to clear your local generation history?')) {
      clearHistory();
      setHistory([]);
      showToast('Generation history cleared.');
    }
  };

  const handleRemix = (item) => {
    navigate('/create-post', {
      state: {
        remixPrompt: item.prompt,
        remixStyle: item.style || 'photorealistic',
        remixModel: item.model || 'flux-schnell',
        remixAspectRatio: item.aspectRatio || '1:1'
      }
    });
  };

  const activeItems = activeTab === 'favorites' ? favorites : history;

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-rose-400 uppercase tracking-wider mb-1">
            <FolderHeart className="w-4 h-4" /> Personal Vault
          </div>
          <h1 className="text-2xl sm:text-4xl font-extrabold text-white">My Gallery & Favorites</h1>
          <p className="mt-1 text-slate-400 text-xs sm:text-sm">
            Manage your bookmarked artworks, review session generation history, and download high-res exports.
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-2 p-1 bg-black/40 rounded-2xl border border-white/10 self-start sm:self-auto">
          <button
            onClick={() => setActiveTab('favorites')}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all flex items-center gap-2 ${
              activeTab === 'favorites'
                ? 'bg-rose-600 text-white shadow-lg shadow-rose-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Heart className="w-3.5 h-3.5" /> Bookmarks ({favorites.length})
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all flex items-center gap-2 ${
              activeTab === 'history'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <History className="w-3.5 h-3.5" /> Generations ({history.length})
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      {activeItems.length > 0 ? (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">
              Showing {activeItems.length} {activeTab === 'favorites' ? 'favorited creations' : 'generated creations'}
            </span>

            {activeTab === 'history' && history.length > 0 && (
              <button
                onClick={handleClearHistory}
                className="text-xs text-rose-400 hover:text-rose-300 flex items-center gap-1.5 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" /> Clear History
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 xs:grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-5">
            {activeItems.map((item, idx) => (
              <div key={item._id || item.id || idx}>
                {activeTab === 'favorites' ? (
                  <Card
                    {...item}
                    onOpenLightbox={() => setSelectedPost(item)}
                    onRemix={handleRemix}
                  />
                ) : (
                  <div className="glass-card rounded-2xl overflow-hidden border border-white/10 group relative flex flex-col">
                    <img
                      src={item.photo}
                      alt={item.prompt}
                      className="w-full aspect-square object-cover"
                    />
                    <div className="p-3.5 space-y-2 flex-1 flex flex-col justify-between bg-black/40">
                      <p className="text-xs text-slate-300 line-clamp-2 font-mono">{item.prompt}</p>
                      <div className="flex items-center justify-between pt-2 border-t border-white/5">
                        <button
                          onClick={() => handleRemix(item)}
                          className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-semibold"
                        >
                          <Wand2 className="w-3 h-3" /> Remix
                        </button>
                        <button
                          onClick={() => downloadImage(`hist-${idx}`, item.photo, 'png', 'my-creation')}
                          className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="py-24 text-center glass-panel rounded-3xl border border-white/10 p-8 space-y-4 max-w-md mx-auto">
          <div className="w-16 h-16 rounded-2xl bg-white/5 text-slate-400 flex items-center justify-center mx-auto border border-white/10">
            {activeTab === 'favorites' ? <Heart className="w-8 h-8 text-rose-400" /> : <Sparkles className="w-8 h-8 text-indigo-400" />}
          </div>
          <h3 className="text-lg font-bold text-white">
            {activeTab === 'favorites' ? 'No Bookmarked Artworks Yet' : 'No Generations Yet'}
          </h3>
          <p className="text-xs text-slate-400">
            {activeTab === 'favorites'
              ? 'Browse the Community Showcase and tap the heart icon on artworks you love to save them here.'
              : 'Head over to the Studio to start crafting your first AI masterpiece!'}
          </p>
          <div className="pt-2">
            <button
              onClick={() => navigate(activeTab === 'favorites' ? '/' : '/create-post')}
              className="px-5 py-2.5 rounded-xl text-xs font-semibold text-white glow-btn inline-flex items-center gap-2"
            >
              {activeTab === 'favorites' ? 'Explore Community Showcase' : 'Go to Studio'} <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Lightbox Modal */}
      {selectedPost && (
        <LightboxModal
          isOpen={Boolean(selectedPost)}
          post={selectedPost}
          onClose={() => setSelectedPost(null)}
          onPostUpdated={loadData}
        />
      )}
    </div>
  );
};

export default MyGallery;
