import express from 'express';
import * as dotenv from 'dotenv';
import { v2 as cloudinary } from 'cloudinary';
import Post from '../mongodb/models/post.js';

dotenv.config();

const router = express.Router();

const isCloudinaryConfigured = () => {
  return (
    process.env.CLOUDINARY_CLOUD_NAME &&
    process.env.CLOUDINARY_API_KEY &&
    process.env.CLOUDINARY_API_SECRET
  );
};

if (isCloudinaryConfigured()) {
  cloudinary.config({
    cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
    api_key: process.env.CLOUDINARY_API_KEY,
    api_secret: process.env.CLOUDINARY_API_SECRET
  });
}

// In-memory fallback post store with initial community posts if MongoDB is not connected
let memoryPosts = [
  {
    _id: 'post-1',
    name: 'Aria Vance',
    prompt: 'A cybernetic geisha with delicate porcelain faceplates and glowing gold circuitry under a neon cherry blossom canopy',
    photo: 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1200&q=80',
    model: 'Flux.1 Schnell',
    style: 'cyberpunk',
    aspectRatio: '1:1',
    tags: ['Cyberpunk', 'Futuristic', 'Portrait', 'Neon'],
    likes: 142,
    reactions: { fire: 45, heart: 67, rocket: 22, mindblown: 18 },
    comments: [
      { user: 'Kai', text: 'The color grading on this is incredible!', time: '2 hours ago' },
      { user: 'Elena', text: 'Prompt remixed and got great results too!', time: '30 mins ago' }
    ],
    createdAt: new Date(Date.now() - 3600000 * 24).toISOString()
  },
  {
    _id: 'post-2',
    name: 'Devon Miles',
    prompt: 'An astronaut discovering an ancient mystical glowing temple buried beneath the red sands of Mars, dramatic dust storm',
    photo: 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=1200&q=80',
    model: 'DALL·E 3',
    style: 'photorealistic',
    aspectRatio: '16:9',
    tags: ['Sci-Fi', 'Space', 'Mars', 'Cinematic'],
    likes: 98,
    reactions: { fire: 31, heart: 40, rocket: 52, mindblown: 29 },
    comments: [
      { user: 'Sarah', text: 'Epic sense of scale!', time: '5 hours ago' }
    ],
    createdAt: new Date(Date.now() - 3600000 * 48).toISOString()
  },
  {
    _id: 'post-3',
    name: 'Sora Tanaka',
    prompt: 'Cozy miniature ramen shop on a quiet rainy evening in Neo-Tokyo, warm lanterns, detailed diorama aesthetic',
    photo: 'https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=1200&q=80',
    model: 'Stable Diffusion XL',
    style: 'isometric',
    aspectRatio: '1:1',
    tags: ['Isometric', 'Tokyo', 'Cozy', '3D'],
    likes: 215,
    reactions: { fire: 60, heart: 120, rocket: 15, mindblown: 42 },
    comments: [
      { user: 'Kenji', text: 'Looks like a dream video game scene ❤️', time: '1 day ago' }
    ],
    createdAt: new Date(Date.now() - 3600000 * 72).toISOString()
  },
  {
    _id: 'post-4',
    name: 'Maya Lin',
    prompt: 'Surreal floating crystal botanical sanctuary over an emerald ocean at golden hour, Studio Ghibli clouds',
    photo: 'https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=1200&q=80',
    model: 'Flux.1 Schnell',
    style: 'anime',
    aspectRatio: '16:9',
    tags: ['Ghibli', 'Fantasy', 'Nature', 'Dreamy'],
    likes: 184,
    reactions: { fire: 28, heart: 95, rocket: 33, mindblown: 56 },
    comments: [],
    createdAt: new Date(Date.now() - 3600000 * 96).toISOString()
  },
  {
    _id: 'post-5',
    name: 'Leo Vance',
    prompt: 'Hyper-detailed 3D render of a baby robotic chameleon with gemstone scales and mechanical clockwork eyes',
    photo: 'https://images.unsplash.com/photo-1563089145-599997674d42?auto=format&fit=crop&w=1200&q=80',
    model: 'DALL·E 3',
    style: '3d-render',
    aspectRatio: '1:1',
    tags: ['3D', 'Pixar', 'Creature', 'Cute'],
    likes: 167,
    reactions: { fire: 44, heart: 78, rocket: 19, mindblown: 37 },
    comments: [],
    createdAt: new Date(Date.now() - 3600000 * 120).toISOString()
  },
  {
    _id: 'post-6',
    name: 'Astrid Olsen',
    prompt: 'Vintage 1980s synthwave sports car racing on an endless grid highway under an oversized purple neon sun',
    photo: 'https://images.unsplash.com/photo-1508739773434-c26b3d09e071?auto=format&fit=crop&w=1200&q=80',
    model: 'Flux.1 Schnell',
    style: 'synthwave',
    aspectRatio: '16:9',
    tags: ['Synthwave', '80s', 'Retro', 'Car'],
    likes: 129,
    reactions: { fire: 62, heart: 45, rocket: 38, mindblown: 14 },
    comments: [],
    createdAt: new Date(Date.now() - 3600000 * 144).toISOString()
  }
];

// GET ALL POSTS WITH FILTERING & SORTING
router.route('/').get(async (req, res) => {
  try {
    const { search, style, sortBy = 'latest' } = req.query;

    let posts = [];
    try {
      posts = await Post.find().lean();
    } catch {
      posts = [...memoryPosts];
    }

    if (!posts || posts.length === 0) {
      posts = [...memoryPosts];
    }

    // Apply Search Filter
    if (search) {
      const q = search.toLowerCase();
      posts = posts.filter(
        (p) =>
          p.prompt?.toLowerCase().includes(q) ||
          p.name?.toLowerCase().includes(q) ||
          p.tags?.some((t) => t.toLowerCase().includes(q))
      );
    }

    // Apply Style Filter
    if (style && style !== 'all') {
      posts = posts.filter((p) => p.style === style);
    }

    // Apply Sorting
    if (sortBy === 'popular') {
      posts.sort((a, b) => (b.likes || 0) - (a.likes || 0));
    } else if (sortBy === 'oldest') {
      posts.sort((a, b) => new Date(a.createdAt) - new Date(b.createdAt));
    } else {
      // Latest default
      posts.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
    }

    res.status(200).json({ success: true, data: posts });
  } catch (error) {
    console.error('Error fetching posts:', error);
    res.status(200).json({ success: true, data: memoryPosts });
  }
});

// CREATE A POST
router.route('/').post(async (req, res) => {
  try {
    const {
      name,
      prompt,
      photo,
      model = 'Flux.1 Schnell',
      style = 'photorealistic',
      aspectRatio = '1:1',
      tags = []
    } = req.body;

    if (!name || !prompt || !photo) {
      return res.status(400).json({ success: false, message: 'Missing required fields' });
    }

    let photoUrl = photo;

    // Upload to Cloudinary if photo is base64 and Cloudinary is configured
    if (isCloudinaryConfigured() && photo.startsWith('data:')) {
      try {
        const uploadResponse = await cloudinary.uploader.upload(photo, {
          folder: 'ai-image-generator'
        });
        photoUrl = uploadResponse.secure_url || uploadResponse.url;
      } catch (cloudErr) {
        console.warn('Cloudinary upload skipped, using direct data url:', cloudErr?.message);
      }
    }

    const postPayload = {
      _id: `post-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
      name,
      prompt,
      photo: photoUrl,
      model,
      style,
      aspectRatio,
      tags,
      likes: 0,
      reactions: { fire: 0, heart: 0, rocket: 0, mindblown: 0 },
      comments: [],
      createdAt: new Date().toISOString()
    };

    try {
      const created = await Post.create(postPayload);
      res.status(201).json({ success: true, data: created });
    } catch {
      // In-memory fallback
      memoryPosts.unshift(postPayload);
      res.status(201).json({ success: true, data: postPayload });
    }
  } catch (error) {
    console.error('Error creating post:', error);
    res.status(500).json({ success: false, message: error?.message || 'Server error' });
  }
});

// LIKE TOGGLE ROUTE
router.route('/:id/like').patch(async (req, res) => {
  try {
    const { id } = req.params;
    const { action = 'like' } = req.body; // 'like' or 'unlike'
    const delta = action === 'unlike' ? -1 : 1;

    try {
      const post = await Post.findById(id);
      if (post) {
        post.likes = Math.max(0, (post.likes || 0) + delta);
        await post.save();
        return res.status(200).json({ success: true, likes: post.likes });
      }
    } catch {}

    // In-memory fallback
    const memPost = memoryPosts.find((p) => p._id === id);
    if (memPost) {
      memPost.likes = Math.max(0, (memPost.likes || 0) + delta);
      return res.status(200).json({ success: true, likes: memPost.likes });
    }

    res.status(200).json({ success: true, likes: 1 });
  } catch (error) {
    res.status(500).json({ success: false, message: error.message });
  }
});

// ADD COMMENT ROUTE
router.route('/:id/comment').post(async (req, res) => {
  try {
    const { id } = req.params;
    const { user = 'Anonymous', text } = req.body;

    if (!text) {
      return res.status(400).json({ success: false, message: 'Comment text is required' });
    }

    const newComment = {
      id: `comm-${Date.now()}`,
      user,
      text,
      time: 'Just now',
      createdAt: new Date().toISOString()
    };

    try {
      const post = await Post.findById(id);
      if (post) {
        post.comments.push(newComment);
        await post.save();
        return res.status(201).json({ success: true, comment: newComment });
      }
    } catch {}

    const memPost = memoryPosts.find((p) => p._id === id);
    if (memPost) {
      if (!memPost.comments) memPost.comments = [];
      memPost.comments.push(newComment);
      return res.status(201).json({ success: true, comment: newComment });
    }

    res.status(201).json({ success: true, comment: newComment });
  } catch (error) {
    res.status(500).json({ success: false, message: error.message });
  }
});

export default router;