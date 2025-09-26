import { ApiError } from "../utils/ApiError.js";

export const erpSessionValidator = (req, res, next) => {
    const sessionId = process.env.ERP_SESSION_ID;
    if (!sessionId) {
        throw ApiError.internal("ERP session ID is not configured", 500);
    }
    next();
}