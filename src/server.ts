import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import stepsRouter from './routes/steps';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 4000;

app.use(express.json());

// CORS: allow your Next.js frontend to call this
app.use(
  cors({
    origin: (process.env.CORS_ORIGIN || 'http://localhost:3000').split(','),
    credentials: true
  })
);

// Simple health check
app.get('/health', (_req, res) => {
  res.json({ status: 'ok' });
});

// API routes
app.use('/api/steps', stepsRouter);

app.listen(PORT, () => {
  console.log(`Backend listening on port ${PORT}`);
});
