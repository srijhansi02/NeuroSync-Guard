# Combined Audio Analysis: Acoustic + Semantic

## Overview

The updated NeuroSync Guard combines two analysis approaches:

1. **Acoustic Analysis** (Always Available)
   - Detects voice cloning, voice changers, synthetic audio
   - Uses trained ML model on audio characteristics
   - Returns: prediction (SAFE/AI VOICE CLONE/VOICE CHANGER/FRAUD), confidence, anomaly score

2. **Semantic Analysis** (Optional, requires Gemini API)
   - Detects 18+ types of scams and fraud patterns
   - Performs speech-to-text transcription (optional)
   - Uses Gemini 1.5 Flash for intelligent scam analysis
   - Returns: fraud category, risk level, scam indicators, explanation

## Supported Scam Types

- **Financial Scams** - Banking, wire transfers, cryptocurrency, investments, loans
- **Tech Support Scams** - Fake Microsoft/Apple/antivirus support
- **Impersonation Scams** - Police, IRS, government, utilities
- **Romance/Dating Scams** - Emotional manipulation, fake relationships
- **Prize/Lottery Scams** - Won money they didn't enter
- **Charity Scams** - Fake donations and relief funds
- **Job/Employment Scams** - Fake job offers, advance payments
- **Rental/Real Estate Scams** - Fake listings, advance payment
- **Delivery Scams** - Package delivery issues, suspicious tracking
- **Healthcare/Pharmacy Scams** - Fake prescriptions, fake insurance
- **Social Media Scams** - Fake profiles, verification
- **Account Takeover** - Password resets, 2FA bypasses
- **Tax Scams** - Fake IRS, tax refunds
- **Insurance Scams** - Fake claims, inflated costs
- **Extortion/Blackmail** - Threats, sextortion, leaked data
- **Grandparent Scams** - Family emergency, money needed
- **Vehicle Scams** - Accidents, roadside assistance
- **Utility Scams** - Power/water company threats

## Setup

### Enable Gemini Semantic Analysis (Optional)

1. **Get a Gemini API Key:**
   ```
   Visit: https://aistudio.google.com/app/apikeys
   Click "Create API Key"
   ```

2. **Set Environment Variable:**
   ```bash
   # Windows PowerShell
   $env:GEMINI_API_KEY = "your_api_key_here"
   
   # Windows Command Prompt
   set GEMINI_API_KEY=your_api_key_here
   
   # Or create .env file in project root
   GEMINI_API_KEY=your_api_key_here
   GEMINI_MODEL=gemini-1.5-flash
   ```

3. **Restart Backend:**
   ```bash
   python app.py
   ```

## Response Format

### Successful Upload Response (with Semantic Analysis)

```json
{
  "id": "uuid-here",
  "filename": "call_recording.wav",
  "prediction": "AI VOICE CLONE",
  "confidence": 92.5,
  "anomaly_score": 0.8234,
  "verdict": "CRITICAL SECURITY MISMATCH",
  "category": "AI Voice Clone / Deepfake Replica",
  "explanation": "ALERT: Synthetic voice clone footprint identified by trained network weights! | Semantic: Urgency, Financial Data Request, Identity Claim. Category: Financial Scam.",
  "processing_ms": 2450,
  "duration_s": 15.5,
  "created_at": "2026-07-05T12:34:56.789Z",
  "semantic_analysis": {
    "semantic_available": true,
    "risk_level": "Critical",
    "scam_indicators": ["Urgency", "Financial Data Request", "Identity Claim"],
    "fraud_category": "Financial Scam",
    "explanation": "Detected 3 fraud indicators",
    "combined_risk_score": 0.92
  },
  "transcript": "[actual transcript or placeholder]"
}
```

### Without Gemini API (Fallback to Heuristic)

When Gemini API key is not configured, semantic analysis uses pattern matching:
- Detects keywords: urgency, financial data, impersonation, tech support claims
- Provides risk level and fraud indicators locally
- No external API calls required

## Workflow

```
User uploads audio
    ↓
Node proxy (server.js) sends to Flask backend
    ↓
Flask: Load audio and perform acoustic analysis (ML model)
    ↓
Flask: Extract acoustic prediction + anomaly score
    ↓
Flask: [OPTIONAL] Transcribe audio to text
    ↓
Flask: [OPTIONAL] Send transcript + acoustic context to Gemini API
    ↓
Flask: [OPTIONAL] Receive structured fraud analysis from Gemini
    ↓
Flask: Merge acoustic + semantic results
    ↓
React Frontend: Display combined analysis
    - Acoustic results (voice clone detection)
    - Semantic results (fraud indicators, scam type)
    - Risk scores from both models
    - Red flags and recommendations
```

## Result Screen Display

The result screen now shows:

1. **Title & Message** - Based on acoustic prediction
2. **Risk Level** - From case rules (Low/High/Critical)
3. **Confidence** - ML model confidence (%)
4. **Source** - Filename and processing time
5. **Acoustic Analysis** - Voice cloning verdict + anomaly score
6. **Semantic Analysis** (if available)
   - Risk level from Gemini
   - Fraud category (Financial Scam, Tech Support, Impersonation, etc.)
   - Red flag badges (Urgency, OTP request, etc.)

## Testing Without Gemini

The system works perfectly without Gemini configured:
- Acoustic analysis runs on every upload
- Semantic analysis uses local heuristic pattern matching
- Same UI display with slightly different analysis source

## Error Handling

- **No Gemini API**: Falls back to heuristic analysis silently
- **Transcription fails**: Uses placeholder text
- **Gemini API timeout**: Falls back to heuristic
- **Network error**: Returns acoustic analysis only

## Example Fraud Scenarios Detected

### Financial Scam
```
Keywords: bank, password, OTP, card, transfer, money, wire, crypto
Red Flags: Urgent payment, financial data request, secrecy
Risk: Critical if requesting OTP/CVV/password
```

### Tech Support Scam
```
Keywords: tech support, Microsoft, Apple, virus, malware
Red Flags: Remote access request, software issue
Type: Tech Support Scam
```

### Romance Scam
```
Keywords: love, sweetheart, dating, relationship, overseas
Red Flags: Emotional connection, money request, travel story
Type: Romance Scam
```

### Grandparent Scam
```
Keywords: grandpa, emergency, accident, hospital, jail, bail
Red Flags: Family emergency, urgent money, secrecy
Type: Grandparent Scam
Risk: Critical
```

### Prize/Lottery Scam
```
Keywords: congratulations, won, lottery, jackpot, claimed
Red Flags: Unexpected prize, money required to claim
Type: Prize/Lottery Scam
```

### Job/Employment Scam
```
Keywords: job, hiring, salary, advance payment, processing fee
Red Flags: Upfront payment, too good to be true salary
Type: Job/Employment Scam
```

### Extortion/Blackmail
```
Keywords: blackmail, leak, photo, sextortion, threat, expose
Red Flags: Threats, demands, personal information
Type: Extortion/Blackmail
Risk: Critical
```

## Configuration Details

| Setting | Default | Description |
|---------|---------|-------------|
| GEMINI_API_KEY | (none) | Required for semantic analysis |
| GEMINI_MODEL | gemini-1.5-flash | Model to use for analysis (fast & efficient) |
| Speech-to-Text | Auto-detect | Falls back to placeholder if unavailable |

## API Endpoints

All endpoints now include optional semantic analysis:

- `POST /api/upload` - Full analysis with transcript + semantic
- `POST /api/proxy-intercept` - Stream analysis with semantic
- `GET /api/history` - Returns historical analyses including semantic data

## Privacy Notes

- Audio transcripts are sent to Gemini API (if enabled)
- Audio recordings themselves are NOT stored/shared
- Only anonymized analysis results are kept in history
- Review privacy policy before enabling Gemini integration

## Troubleshooting

**Semantic analysis not appearing:**
- Check GEMINI_API_KEY environment variable is set
- Verify API key is valid at aistudio.google.com
- Check browser console for errors

**Transcription shows placeholder:**
- google-cloud-speech not installed
- Audio format not supported
- Works fine - heuristic analysis still runs

**Slow processing:**
- Semantic analysis adds ~1-3 seconds
- API latency varies with Gemini service
- Acoustic analysis is fast (~500ms)

---

**Version:** 1.0 (Acoustic + Semantic Combined)  
**Last Updated:** 2026-07-05
