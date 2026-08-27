export const surpriseMePrompts = [
  'An ethereal cybernetic goddess surrounded by floating holographic lotus flowers in a neon rainstorm, unreal engine 5, 8k resolution',
  'A surrealist dream-like oil painting by Salvador Dalí of a golden cat playing chess on a melting clock in space',
  'An ancient mystical library inside a giant hollowed-out glowing crystal tree with spiral staircases, studio ghibli aesthetic',
  'Hyper-realistic cinematic close-up portrait of a cyberpunk samurai warrior with intricate glowing katana, volumetric smoke, 85mm lens',
  'A steampunk flying airship floating gracefully above Victorian London during golden hour, cinematic lighting, 4k concept art',
  'A cute glowing baby dragon curled up asleep on a pile of glowing amethyst gems, 3D Pixar animation style, octane render',
  'Futuristic solarpunk metropolis with cascading vertical hanging gardens, glass skyways, and clean energy waterfalls, bright sunny day',
  'A dramatic astronaut exploring an alien bioluminescent crystalline forest under twin purple moons, cinematic photorealism',
  'An ornate baroque robotic peacock with stained glass feathers reflecting vibrant neon lights, macro photography',
  'Isometric 3D diorama of a cozy miniature Japanese ramen shop in the rain, warm golden interior lighting, highly detailed',
  'A retro 80s synthwave sports car speeding along a neon highway toward an enormous purple retrowave sun, chromatic aberration',
  'A majestic stag made entirely of constellation stars and nebulae wandering through an enchanted midnight forest',
  'A delicious floating gourmet burger made of glowing futuristic culinary elements, commercial high-speed photography',
  'An ancient gothic cathedral transformed into a high-tech starship observatory, ray-tracing, dramatic rim lighting',
  'A playful red panda dressed as an astronaut drinking bubble tea on Mars, vibrant digital illustration'
];

export const stylePresets = [
  { id: 'photorealistic', name: 'Photorealistic', icon: '📸', promptSuffix: ', hyperrealistic 8k resolution, ultra-detailed photograph, Hasselblad 80mm lens, natural studio lighting, photorealistic masterpiece' },
  { id: 'cyberpunk', name: 'Cyberpunk Neon', icon: '🌆', promptSuffix: ', cyberpunk aesthetic, glowing neon lights, futuristic city vibes, high contrast, volumetric reflections, octan render' },
  { id: 'anime', name: 'Anime / Ghibli', icon: '🎨', promptSuffix: ', Studio Ghibli anime style, beautiful hand-drawn aesthetic, vibrant watercolor palette, Makoto Shinkai lighting, detailed anime scenery' },
  { id: '3d-render', name: '3D Pixar / Disney', icon: '✨', promptSuffix: ', 3D animation style, Pixar and Disney concept art, soft subsurface scattering, vibrant warm lighting, Octane render 3D character design' },
  { id: 'synthwave', name: 'Synthwave 80s', icon: '🌴', promptSuffix: ', 1980s retro synthwave, retrowave aesthetic, neon purple and cyan, chrome reflections, grid horizon, scanlines' },
  { id: 'dark-fantasy', name: 'Dark Fantasy', icon: '🗡️', promptSuffix: ', dark gothic fantasy, Elden Ring aesthetic, moody dramatic shadows, oil painting textures, volumetric mist, masterpiece' },
  { id: 'oil-painting', name: 'Classic Oil Painting', icon: '🖼️', promptSuffix: ', rich oil on canvas painting, visible textured brushstrokes, classical masterpiece, Rembrandt dramatic lighting' },
  { id: 'isometric', name: 'Isometric 3D', icon: '📦', promptSuffix: ', cute isometric 3D render, low poly diorama, miniature tilt-shift scene, clean minimalist vibrant lighting' },
  { id: 'vector-art', name: 'Vector Illustration', icon: '📐', promptSuffix: ', clean flat vector art, bold outlines, vibrant solid color palette, modern graphic design illustration' },
  { id: 'claymation', name: 'Claymation / Plasticine', icon: '🧸', promptSuffix: ', handcrafted stop-motion claymation, Aardman clay texture, soft studio lighting, macro depth of field' },
  { id: 'pixel-art', name: '16-Bit Pixel Art', icon: '👾', promptSuffix: ', 16-bit detailed pixel art, retro gaming aesthetic, vibrant pixel palette, nostalgic indie game art' },
  { id: 'watercolor', name: 'Ethereal Watercolor', icon: '🖌️', promptSuffix: ', expressive soft watercolor painting on cold-press paper, bleeding pastel pigments, artistic splatter, delicate' }
];

export const aspectRatios = [
  { id: '1:1', label: '1:1 Square', width: 1024, height: 1024, icon: 'Square', desc: 'Instagram, Avatars' },
  { id: '16:9', label: '16:9 Landscape', width: 1792, height: 1024, icon: 'Landscape', desc: 'Wallpapers, Banners' },
  { id: '9:16', label: '9:16 Portrait', width: 1024, height: 1792, icon: 'Portrait', desc: 'Stories, TikTok, Mobile' },
  { id: '4:3', label: '4:3 Classic', width: 1024, height: 768, icon: 'Classic', desc: 'Photography, Retro' },
  { id: '21:9', label: '21:9 Ultrawide', width: 1792, height: 768, icon: 'Ultrawide', desc: 'Cinematic Cinema' }
];

export const aiModels = [
  { id: 'flux-schnell', name: 'Flux.1 Schnell (Fast & Ultra HD)', badge: 'Free / Fast', provider: 'Pollinations Flux', speed: '2s - 4s' },
  { id: 'stable-diffusion-xl', name: 'Stable Diffusion XL Turbo', badge: 'High Detail', provider: 'Pollinations SDXL', speed: '3s - 5s' },
  { id: 'dalle-3', name: 'OpenAI DALL·E 3 (Photoreal)', badge: 'OpenAI Pro', provider: 'OpenAI API', speed: '8s - 12s' },
  { id: 'dalle-2', name: 'OpenAI DALL·E 2', badge: 'Legacy', provider: 'OpenAI API', speed: '5s - 8s' }
];

export const lightingModifiers = [
  'Volumetric God Rays',
  'Cyberpunk Neon Lighting',
  'Golden Hour Sunset',
  'Studio Softbox Lighting',
  'Bioluminescent Glow',
  'Dramatic Rim Light',
  'Moonlit Atmosphere',
  'Cinematic High Contrast'
];

export const cameraModifiers = [
  '85mm f/1.4 Portrait Lens',
  '35mm Vintage Film Grain',
  'Drone Aerial Top-Down View',
  'Macro Close-Up Detail',
  '16mm Ultra-Wide Angle',
  'Cinematic IMAX 70mm'
];

export const inspirationCategories = [
  {
    id: 'scifi',
    name: 'Sci-Fi & Cyberpunk',
    icon: '🚀',
    prompts: [
      { title: 'Neon Cyber City', prompt: 'A bustling multi-level cyberpunk metropolis in 2099 with flying sky-taxis, glowing neon kanji signs, and pouring rain reflecting on asphalt', style: 'cyberpunk' },
      { title: 'Deep Space Explorer', prompt: 'An astronaut standing on the precipice of a crystallized alien canyon staring into an enormous swirling cosmic wormhole', style: 'photorealistic' },
      { title: 'Bionic Android Portrait', prompt: 'A highly sophisticated female android with translucent ceramic skin revealing glowing optical fiber circuits underneath', style: '3d-render' }
    ]
  },
  {
    id: 'fantasy',
    name: 'Mythology & Fantasy',
    icon: '🐉',
    prompts: [
      { title: 'Floating Sky Islands', prompt: 'Majestic ancient castle ruins perched on floating lush green islands connected by glowing crystal rope bridges with waterfalls spilling into clouds', style: 'anime' },
      { title: 'Phoenix Rebirth', prompt: 'A mythical golden phoenix with wings of pure solar flames soaring through an erupting volcanic storm at twilight', style: 'dark-fantasy' },
      { title: 'Enchanted Forest Spirit', prompt: 'A giant mystical white wolf spirit with glowing blue markings walking gently through an ethereal autumn forest of golden leaves', style: 'anime' }
    ]
  },
  {
    id: 'portraits',
    name: 'Characters & Portraits',
    icon: '👤',
    prompts: [
      { title: 'Time Traveler', prompt: 'Close up portrait of a weathered Victorian gentleman holding an intricate glowing brass chronometer, dramatic side lighting', style: 'photorealistic' },
      { title: 'Cyber Samurai', prompt: 'A futuristic samurai warrior in matte black carbon-fiber armor with an illuminated neon red visor and dual plasma swords', style: 'cyberpunk' },
      { title: 'Cute Pixar Explorer', prompt: 'A charming little robotic cartographer wearing oversized goggles and a tiny leather backpack, adorable expressions', style: '3d-render' }
    ]
  },
  {
    id: 'architecture',
    name: 'Architecture & Worlds',
    icon: '🏛️',
    prompts: [
      { title: 'Solarpunk Sanctuary', prompt: 'A breathtaking glass solarpunk conservatory tower surrounded by crystal clear lagoon waters and futuristic hanging gardens', style: 'photorealistic' },
      { title: 'Cozy Rain Café', prompt: 'Warm and inviting coffee shop interior viewed from the rainy street window at night, steaming mugs and fairy lights', style: 'isometric' },
      { title: 'Futuristic Museum', prompt: 'Curved parametric architecture modern art museum with sweeping white marble corridors and natural sunlight skylights', style: 'photorealistic' }
    ]
  }
];

export const initialCommunityPosts = [
  {
    _id: 'post-demo-1',
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
      { id: 'c1', user: 'Kai', text: 'The color grading on this is incredible!', time: '2 hours ago' },
      { id: 'c2', user: 'Elena', text: 'Prompt remixed and got great results too!', time: '30 mins ago' }
    ],
    createdAt: '2026-08-25T14:32:00Z'
  },
  {
    _id: 'post-demo-2',
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
      { id: 'c3', user: 'Sarah', text: 'Epic sense of scale!', time: '5 hours ago' }
    ],
    createdAt: '2026-08-24T18:15:00Z'
  },
  {
    _id: 'post-demo-3',
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
      { id: 'c4', user: 'Kenji', text: 'Looks like a dream video game scene ❤️', time: '1 day ago' }
    ],
    createdAt: '2026-08-23T11:20:00Z'
  },
  {
    _id: 'post-demo-4',
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
    createdAt: '2026-08-22T09:45:00Z'
  },
  {
    _id: 'post-demo-5',
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
    createdAt: '2026-08-21T16:10:00Z'
  },
  {
    _id: 'post-demo-6',
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
    createdAt: '2026-08-20T21:00:00Z'
  }
];