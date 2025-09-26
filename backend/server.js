import 'dotenv/config'
import cors from 'cors'
import express from "express"
import connectDB from "./configs/db.js";
import authRouter from "./routes/authRoutes.js";
import { errorHandler, notFound } from './middlewares/errorMiddleware.js';
import userRouter from './routes/userRoutes.js';
import queryRouter from './routes/queryRoutes.js';
import roomRouter from './routes/roomRoutes.js';
import erpRouter from './routes/erpRoutes.js';
import mapRouter from './routes/mapRoutes.js';


// Initializations
const PORT = process.env.PORT || 6969;
const app = express();

// Middlewares
app.use(cors({
    origin: "*"
}));
app.use(express.json());
app.use(express.urlencoded({ extended: true }))

// ------------Routes------------
app.use("/api/v0/auth", authRouter); // Authentication routes
app.use("/api/v0/users", userRouter); // User management routes
app.use("/api/query", queryRouter); // Queryt routes
app.use("/api/chat/room/create/:roomName/:userID", roomRouter); // Queryt routes

// --------ERP Integration--------
app.use("/api/v0/erp", erpRouter);

// --------Maps Integration--------
app.use("/api/v0/maps", mapRouter);


// Error handling middleware
app.use(notFound);
app.use(errorHandler);


// Connect MongoDB
await connectDB();

// Server Listening
app.listen(PORT, (error) => {
    if (error) console.log(error.message);
    console.log(`🚀 Server is running on http://localhost:${PORT}`);
})