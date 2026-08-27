import React, { useState } from 'react';
import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router-dom';
import { Sparkles, Wand2, Compass, FolderHeart, Dna, Settings, Cpu, ShieldCheck } from 'lucide-react';
import { Home, CreatePost, InspirationLab, MyGallery } from './pages';
import { ToastProvider, ApiSettingsModal } from './components';

const NavigationHeader = ({ onOpenSettings }) => {
  const location = useLocation();

  const navLinks = [
    { to: '/', label: 'Explore', icon: Compass },
    { to: '/create-post', label: 'Studio', icon: Wand2 },
    { to: '/inspiration', label: 'Inspiration Lab', icon: Dna },
    { to: '/my-gallery', label: 'My Vault', icon: FolderHeart }
  ];

  return (
    <header className="sticky top-0 z-40 w-full glass-panel border-b border-white/10 px-4 sm:px-8 py-3.5 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand Logo */}
        <Link to="/" className="flex items-center gap-2.5 group">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-pink-500 flex items-center justify-center text-white shadow-lg shadow-indigo-600/30 group-hover:scale-105 transition-transform">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <span className="font-heading font-extrabold text-lg tracking-tight text-white group-hover:text-indigo-400 transition-colors flex items-center gap-1.5">
              AetherArt <span className="text-xs px-1.5 py-0.5 rounded bg-indigo-500/20 border border-indigo-500/40 text-indigo-300 font-sans">2.0</span>
            </span>
          </div>
        </Link>

        {/* Center Nav Links */}
        <nav className="hidden md:flex items-center gap-1.5 bg-black/40 p-1 rounded-2xl border border-white/5">
          {navLinks.map((link) => {
            const Icon = link.icon;
            const isActive = location.pathname === link.to;
            return (
              <Link
                key={link.to}
                to={link.to}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 ${
                  isActive
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                    : 'text-slate-400 hover:text-white hover:bg-white/5'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {link.label}
              </Link>
            );
          })}
        </nav>

        {/* Right CTA Actions */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={onOpenSettings}
            title="AI Engine Settings"
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/10 border border-white/5 transition-colors"
          >
            <Settings className="w-4 h-4" />
          </button>

          <Link
            to="/create-post"
            className="glow-btn px-4 py-2 rounded-xl text-xs font-bold text-white flex items-center gap-1.5 shadow-lg"
          >
            <Wand2 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Create Art</span>
          </Link>
        </div>
      </div>

      {/* Mobile Sub-Navigation Bar */}
      <div className="flex md:hidden items-center justify-around pt-3 mt-2 border-t border-white/5">
        {navLinks.map((link) => {
          const Icon = link.icon;
          const isActive = location.pathname === link.to;
          return (
            <Link
              key={link.to}
              to={link.to}
              className={`px-2 py-1 text-xs font-medium flex flex-col items-center gap-1 ${
                isActive ? 'text-indigo-400 font-bold' : 'text-slate-400'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{link.label}</span>
            </Link>
          );
        })}
      </div>
    </header>
  );
};

const AppContent = () => {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  return (
    <div className="min-h-screen flex flex-col justify-between bg-[#07080d] text-slate-100 selection:bg-indigo-500 selection:text-white">
      <div>
        <NavigationHeader onOpenSettings={() => setIsSettingsOpen(true)} />
        <main className="px-4 sm:px-8 py-8 w-full max-w-7xl mx-auto">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/create-post" element={<CreatePost />} />
            <Route path="/inspiration" element={<InspirationLab />} />
            <Route path="/my-gallery" element={<MyGallery />} />
          </Routes>
        </main>
      </div>

      {/* Global Footer */}
      <footer className="w-full border-t border-white/10 bg-black/60 py-8 px-4 sm:px-8 mt-20">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <span className="font-bold text-white">AetherArt AI Creative Studio 2.0</span>
            <span>• Powered by DALL·E 3, Flux.1 & SDXL</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1 text-emerald-400">
              <ShieldCheck className="w-3.5 h-3.5" /> High-Performance AI Pipeline
            </span>
            <Link to="/create-post" className="hover:text-white transition-colors">Studio</Link>
            <Link to="/inspiration" className="hover:text-white transition-colors">Prompt Lab</Link>
            <Link to="/my-gallery" className="hover:text-white transition-colors">Vault</Link>
          </div>
        </div>
      </footer>

      {/* Engine Settings Modal */}
      <ApiSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </div>
  );
};

const App = () => {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AppContent />
      </ToastProvider>
    </BrowserRouter>
  );
};

export default App;