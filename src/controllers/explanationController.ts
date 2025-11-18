import { Request, Response } from 'express';
import { ExplanationData } from '../types/explanation';

export const getExplanation = (req: Request, res: Response) => {
  const stepId = Number(req.params.stepId || 1);

  const payload: ExplanationData = {
    step: stepId,
    magicNumber: 42, // 👈 your magic number from backend
    explanation: `This is example server data for step ${stepId}. The magic number is 42.`
  };

  res.json(payload);
};
