import { Router } from "express";
import { fetchAssignments, fetchAttendance, fetchCirculars, fetchTimeTable, fetchUserDetails } from "../controllers/erpController.js";
import { erpSessionValidator } from "../middlewares/erpSessionValidator.js";

const erpRouter = Router();

erpRouter.use(erpSessionValidator);
erpRouter.get("/getAttendance", fetchAttendance);
erpRouter.get("/getCirculars", fetchCirculars);
erpRouter.get("/getUserDetails", fetchUserDetails);
erpRouter.get("/getTimeTable", fetchTimeTable);
erpRouter.get("/getAssignments", fetchAssignments);


export default erpRouter;