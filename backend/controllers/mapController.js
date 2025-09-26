import axios from "axios";
import expressAsyncHandler from "express-async-handler";
import { formatMatrixData } from "../utils/formatData.js";

export const getMetrices = expressAsyncHandler(async (req, res) => {
    const url = "https://api.openrouteservice.org/v2/matrix/driving-car";

    const { locations } = req.body || {}


    if (!locations || !Array.isArray(locations) || locations.length === 0) {
        return res.status(400).json({
            success: false,
            message: "Locations must be a non-empty array"
        });
    }

    for (let i = 0; i < locations.length; i++) {
        const loc = locations[i];

        if (!loc.name || typeof loc.name !== "string") {
            return res.status(400).json({
                success: false,
                message: `Location at index ${i} must have a valid 'name'`
            });
        }

        if (
            !loc.coords ||
            !Array.isArray(loc.coords) ||
            loc.coords.length !== 2 ||
            typeof loc.coords[0] !== "number" ||
            typeof loc.coords[1] !== "number"
        ) {
            return res.status(400).json({
                success: false,
                message: `Location at index ${i} must have valid 'coords' as [longitude, latitude]`
            });
        }
    }

    const coordsList = locations.map(loc => loc.coords);


    try {
        const result = await axios.post(
            url,
            {
                "locations": coordsList,
                "metrics": ["distance", "duration"]
            },
            {
                headers: {
                    "Authorization": process.env.OPEN_ROUTES_API_KEY,
                    "Content-Type": "application/json"
                }
            }
        );

        const data = formatMatrixData(result?.data, locations)

        return res
            .status(200)
            .json({
                success: true,
                message: "distance and duration fetched successfully",
                data
            });

    } catch (error) {
        return res
            .status(500)
            .json({
                success: false,
                message: error?.response?.data || error?.message || "Error while getting metrics"
            });
    }
});
