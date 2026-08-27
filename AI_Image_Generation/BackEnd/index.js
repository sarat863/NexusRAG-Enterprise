import express from 'express';
import * as dotenv from 'dotenv';
import cors from 'cors';

import connectDB from './mongodb/connect.js';
import postRoutes from './routes/postRoutes.js';
import dalleRoutes from './routes/dalleRoutes.js';

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));

app.use('/api/v1/post', postRoutes);
app.use('/api/v1/dalle', dalleRoutes);

app.get('/', async (req, res) => {
  res.json({
    status: 'online',
    app: 'AI Creative Studio 2.0 Backend',
    timestamp: new Date().toISOString()
  });
});

const PORT = process.env.PORT || 8080;

const startServer = async () => {
  try {
    if (process.env.MONGODB_URL) {
      try {
        await connectDB(process.env.MONGODB_URL);
        console.log('MongoDB connected successfully');
      } catch (dbErr) {
        console.warn('MongoDB connection warning (using in-memory fallback):', dbErr.message);
      }
    } else {
      console.log('No MONGODB_URL provided in env, running with in-memory resilient fallback store.');
    }

    app.listen(PORT, () => console.log(`AI Studio Server running at http://localhost:${PORT}`));
  } catch (error) {
    console.error('Server startup error:', error);
  }
};

startServer();