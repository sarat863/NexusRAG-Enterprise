import express from 'express';
import * as dotenv from 'dotenv';
import OpenAI from 'openai';

dotenv.config();

const router = express.Router();

// Helper to initialize OpenAI client on-demand (server env key or client-provided key)
const getOpenAIClient = (customKey) => {
  const key = customKey || process.env.OPENAI_API_KEY;
  if (!key) return null;
  return new OpenAI({ apiKey: key });
};

// Free fallback generator using Pollinations AI (Flux / SDXL)
const generateWithFallback = async ({ prompt, width = 1024, height = 1024, model = 'flux', seed }) => {
  const actualSeed = seed || Math.floor(Math.random() * 1000000);
  const pollinationsModel = model === 'stable-diffusion-xl' ? 'turbo' : 'flux';
  const encodedPrompt = encodeURIComponent(prompt);
  const imageUrl = `https://image.pollinations.ai/prompt/${encodedPrompt}?width=${width}&height=${height}&seed=${actualSeed}&model=${pollinationsModel}&nologo=true`;

  const response = await fetch(imageUrl);
  if (!response.ok) {
    throw new Error(`Fallback generator failed with status: ${response.status}`);
  }
  const arrayBuffer = await response.arrayBuffer();
  const buffer = Buffer.from(arrayBuffer);
  const base64 = buffer.toString('base64');
  return { base64, url: imageUrl, engine: `Pollinations (${pollinationsModel})` };
};

router.route('/').get((req, res) => {
  res.json({
    status: 'online',
    message: 'AI Generation Engine 2.0 Ready',
    supportedModels: ['flux-schnell', 'stable-diffusion-xl', 'dalle-3', 'dalle-2']
  });
});

// Image Generation Endpoint
router.route('/').post(async (req, res) => {
  try {
    const {
      prompt,
      model = 'flux-schnell',
      size = '1024x1024',
      quality = 'standard',
      style = 'vivid',
      customApiKey,
      width = 1024,
      height = 1024,
      seed
    } = req.body;

    if (!prompt) {
      return res.status(400).json({ error: 'Prompt is required' });
    }

    // If requested DALL-E model and API key is available
    const openai = getOpenAIClient(customApiKey);
    if ((model === 'dalle-3' || model === 'dalle-2') && openai) {
      try {
        const dalleSize = model === 'dalle-3'
          ? (size === '1792x1024' || size === '1024x1792' ? size : '1024x1024')
          : '1024x1024';

        const aiResponse = await openai.images.generate({
          model: model === 'dalle-3' ? 'dall-e-3' : 'dall-e-2',
          prompt,
          n: 1,
          size: dalleSize,
          quality: model === 'dalle-3' ? quality : undefined,
          style: model === 'dalle-3' ? style : undefined,
          response_format: 'b64_json'
        });

        const imageBase64 = aiResponse.data[0].b64_json;
        return res.status(200).json({
          photo: imageBase64,
          engine: model === 'dalle-3' ? 'OpenAI DALL·E 3' : 'OpenAI DALL·E 2',
          revisedPrompt: aiResponse.data[0].revised_prompt || prompt
        });
      } catch (openaiErr) {
        console.warn('OpenAI error, falling back to Flux/SDXL engine:', openaiErr?.message || openaiErr);
        // Seamlessly fallback to Flux
      }
    }

    // Fast Flux / SDXL generation
    const fallbackResult = await generateWithFallback({
      prompt,
      width,
      height,
      model,
      seed
    });

    return res.status(200).json({
      photo: fallbackResult.base64,
      imageUrl: fallbackResult.url,
      engine: fallbackResult.engine
    });
  } catch (error) {
    console.error('Generation route error:', error);
    res.status(500).json({
      error: error?.message || 'Failed to generate image',
      details: String(error)
    });
  }
});

// Prompt Enhancer Endpoint
router.route('/enhance-prompt').post(async (req, res) => {
  try {
    const { prompt, styleName = '', lighting = '', camera = '' } = req.body;
    if (!prompt) {
      return res.status(400).json({ error: 'Prompt is required' });
    }

    let enhanced = prompt.trim();
    if (lighting) enhanced += `, dramatic ${lighting.toLowerCase()}`;
    if (camera) enhanced += `, shot on ${camera}`;
    if (styleName) enhanced += `, in ${styleName} style`;
    enhanced += ', highly detailed, 8k resolution, photorealistic masterpiece, cinematic lighting, volumetric atmosphere, sharp focus';

    res.status(200).json({ enhancedPrompt: enhanced });
  } catch (error) {
    res.status(500).json({ error: 'Failed to enhance prompt' });
  }
});

export default router;