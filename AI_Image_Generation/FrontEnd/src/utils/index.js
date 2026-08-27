import FileSaver from 'file-saver';
import confetti from 'canvas-confetti';
import { surpriseMePrompts, stylePresets } from '../constants';

export const API_BASE_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8080/api/v1';

export function getRandomPrompt(currentPrompt) {
  const available = surpriseMePrompts.filter((p) => p !== currentPrompt);
  const randomIndex = Math.floor(Math.random() * available.length);
  return available[randomIndex] || surpriseMePrompts[0];
}

export function enhancePrompt(prompt, styleId = '', lighting = '', camera = '') {
  if (!prompt || !prompt.trim()) return '';

  let enhanced = prompt.trim();
  
  // Add lighting if selected
  if (lighting && !enhanced.toLowerCase().includes(lighting.toLowerCase())) {
    enhanced += `, illuminated with ${lighting.toLowerCase()}`;
  }

  // Add camera/lens if selected
  if (camera && !enhanced.toLowerCase().includes(camera.toLowerCase())) {
    enhanced += `, captured on ${camera}`;
  }

  // Add style preset suffix
  if (styleId) {
    const styleObj = stylePresets.find((s) => s.id === styleId);
    if (styleObj && styleObj.promptSuffix) {
      enhanced += styleObj.promptSuffix;
    }
  }

  // Add aesthetic polish details if not already heavily stylized
  if (!enhanced.includes('8k') && !enhanced.includes('masterpiece') && !enhanced.includes('detailed')) {
    enhanced += ', highly detailed, intricate textures, award-winning composition, sharp focus, 8k resolution';
  }

  return enhanced;
}

export async function downloadImage(id, photoUrl, format = 'png', baseName = 'ai-creation') {
  try {
    // If it's a data URL or same-origin
    if (photoUrl.startsWith('data:') || photoUrl.startsWith('blob:')) {
      const link = document.createElement('a');
      link.href = photoUrl;
      link.download = `${baseName}-${id || Date.now()}.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      return;
    }

    // Convert external image to Blob via Canvas to support PNG/JPG/WebP conversion & bypass cross-origin download issues
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = photoUrl;
    await new Promise((resolve, reject) => {
      img.onload = resolve;
      img.onerror = () => {
        // Fallback: save original link directly
        FileSaver.saveAs(photoUrl, `${baseName}-${id || Date.now()}.${format}`);
        resolve(null);
      };
    });

    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth || img.width;
    canvas.height = img.naturalHeight || img.height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);

    let mimeType = 'image/png';
    if (format === 'jpg' || format === 'jpeg') mimeType = 'image/jpeg';
    if (format === 'webp') mimeType = 'image/webp';

    canvas.toBlob((blob) => {
      if (blob) {
        FileSaver.saveAs(blob, `${baseName}-${id || Date.now()}.${format}`);
      } else {
        FileSaver.saveAs(photoUrl, `${baseName}-${id || Date.now()}.${format}`);
      }
    }, mimeType, 0.95);
  } catch (error) {
    console.error('Download error:', error);
    FileSaver.saveAs(photoUrl, `${baseName}-${id || Date.now()}.${format}`);
  }
}

export function triggerConfetti() {
  try {
    confetti({
      particleCount: 80,
      spread: 70,
      origin: { y: 0.6 },
      colors: ['#6366f1', '#ec4899', '#06b6d4', '#10b981', '#f59e0b']
    });
  } catch (e) {
    // Ignore if not supported
  }
}

// Local Storage for Favorites
const FAVORITES_KEY = 'ai_image_favorites';
export function getFavorites() {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function toggleFavorite(post) {
  try {
    const favs = getFavorites();
    const existsIndex = favs.findIndex((f) => (f._id && f._id === post._id) || f.photo === post.photo);
    let updated;
    let isNowFav = false;
    if (existsIndex >= 0) {
      updated = favs.filter((_, idx) => idx !== existsIndex);
      isNowFav = false;
    } else {
      updated = [post, ...favs];
      isNowFav = true;
    }
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(updated));
    return { favorites: updated, isFavorite: isNowFav };
  } catch {
    return { favorites: [], isFavorite: false };
  }
}

export function isFavorite(postId, photoUrl) {
  const favs = getFavorites();
  return favs.some((f) => (postId && f._id === postId) || (photoUrl && f.photo === photoUrl));
}

// Local Storage for Creation History
const HISTORY_KEY = 'ai_image_history';
export function getHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveToHistory(item) {
  try {
    const history = getHistory();
    const newItem = {
      ...item,
      id: item.id || `hist-${Date.now()}`,
      createdAt: new Date().toISOString()
    };
    const updated = [newItem, ...history].slice(0, 50); // Keep latest 50
    localStorage.setItem(HISTORY_KEY, JSON.stringify(updated));
    return updated;
  } catch {
    return [];
  }
}

export function clearHistory() {
  localStorage.removeItem(HISTORY_KEY);
}

// API Settings Storage
const SETTINGS_KEY = 'ai_image_settings';
export function getApiSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    return raw ? JSON.parse(raw) : { openaiApiKey: '', preferredModel: 'flux-schnell', defaultAspectRatio: '1:1' };
  } catch {
    return { openaiApiKey: '', preferredModel: 'flux-schnell', defaultAspectRatio: '1:1' };
  }
}

export function saveApiSettings(settings) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch (e) {
    console.error('Error saving settings:', e);
  }
}