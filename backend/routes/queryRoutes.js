import express from "express";
import { enhance } from "../utils/promptEnhancer.js";

const queryRouter = express.Router();

queryRouter.post('/', async (req, res) => {
    const { query } = req.body;

    try {
        const response = await fetch('http://localhost:5000/chat', {
            method: 'POST',
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message:query })
        });

        const data = await response.json();

        if (!data) {
            throw new Error("Error in fetching query data...");
        }

        if(data?.intent){
            return res.json({ response: data.answer });
        } else if (data?.status == "scheduled"){
            const reminder = data?.reminder;
            console.log(JSON.stringify( reminder ))
            fetch("http://localhost:5678/webhook/set-calendar", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(reminder)
            }).then(response => {
                if (!response.ok) {
                    throw new Error("Failed to set calendar reminder.");
                }
            }).catch(err => {
                console.error(err);
                // return res.status(500).json({ response: "Failed to set calendar reminder." });
            });
            return res.json({ response: data.message });
        } else {
            return res.json({ response: "Improper response format." });
        }


        // Return database response if available

    } catch (error) {
        console.log(error)
        console.error(`Error in query route: ${error.message}`);
        return res.status(500).json({ error: "Internal Server Error" });
    }
});

export default queryRouter;
