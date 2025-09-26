import express from 'express'
import { getMetrices } from '../controllers/mapController.js';


const router = express.Router();

router.get('/getMetrices',getMetrices)


export default router;