import { Router } from 'express';
import { getExplanation } from '../controllers/explanationController';

const router = Router();

// GET /api/steps/:stepId/explanation
router.get('/:stepId/explanation', getExplanation);

export default router;
