console.log("🚀 Node.js script has successfully started executing...");
const express = require('express');
const multer = require('multer');
const axios = require('axios');
const cors = require('cors');
const path = require('path');

const app = express();
const DIST_DIR = path.join(__dirname, 'dist');

app.use(cors());
app.use(express.json());
app.use(express.static(DIST_DIR));

app.get('*', (req, res) => {
    res.sendFile(path.join(DIST_DIR, 'index.html'));
});

const storage = multer.memoryStorage();
const upload = multer({ storage: storage });

// Single Stream Proxy Intercept Route
app.post('/api/proxy-intercept', upload.single('audio'), async (req, res) => {
    try {
        if (!req.file) {
            return res.status(400).json({ success: false, error: "No call audio stream detected." });
        }

        const buffer = req.file.buffer;
        const encodedAudio = buffer.toString('base64');
        const name = req.file.originalname || 'upload.wav';
        console.log(`📡 Stream Intercepted: processing wave stream for ${name}`);

        const maxRetries = 4;
        const retryDelayMs = 1000;
        let pythonResponse = null;
        for (let attempt = 1; attempt <= maxRetries; attempt += 1) {
            try {
                pythonResponse = await axios.post('http://localhost:5001/analyze', {
                    audio_b64: encodedAudio,
                    filename: name
                }, {
                    headers: { 'Content-Type': 'application/json' },
                    timeout: 10000,
                });
                break;
            } catch (innerError) {
                const isRefused = innerError.code === 'ECONNREFUSED';
                console.warn(`⚠️ Python microservice request attempt ${attempt} failed: ${innerError.message}`);
                if (isRefused) {
                    console.error(`❌ Connection refused to Python service at http://localhost:5001/analyze (code=${innerError.code}). Ensure app.py is running and listening on port 5001.`);
                }
                if (attempt === maxRetries) {
                    throw innerError;
                }
                await new Promise(resolve => setTimeout(resolve, retryDelayMs));
            }
        }

        return res.status(200).json({
            success: true,
            logs: pythonResponse.data
        });

    } catch (error) {
        console.error("❌ Pipeline Bridge Exception:", error.message);
        console.error("Please ensure the Python Flask service is running on http://localhost:5001 and has finished booting.");
        return res.status(502).json({ success: false, error: "Validation Pipeline Intercept Failure.", details: error.message });
    }
});

const PORT = 3000;
app.listen(PORT, () => {
    console.log(`🚀 NeuroSync-Guard Node.js Proxy Service listening on http://localhost:${PORT}`);
});