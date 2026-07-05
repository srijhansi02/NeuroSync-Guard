# NeuroSync Guard

NeuroSync Guard is a lightweight voice-analysis demo that combines a React/Vite frontend with a Flask backend and a trained audio classifier.

## Prerequisites

- Python 3.10+ and pip
- Node.js 18+ and npm
- A working audio checkpoint at [training_checkpoints/model_checkpoint.pt](training_checkpoints/model_checkpoint.pt)

## Quick start

### Windows

1. Open PowerShell or Command Prompt in the project root.
2. Run:
   ```powershell
   .\run_project.bat
   ```
3. Open http://localhost:3000

### macOS / Linux

1. Open a terminal in the project root.
2. Run:
   ```bash
   chmod +x ./run_project.sh
   ./run_project.sh
   ```
3. Open http://localhost:3000

## Manual setup

### Python environment

```bash
python -m venv .venv
source .venv/bin/activate   # macOS / Linux
.venv\Scripts\activate      # Windows PowerShell
pip install -r requirements.txt
```

### Frontend dependencies

```bash
npm install
npm run build
```

### Run services

Start the backend:

```bash
python app.py
```

Start the frontend proxy:

```bash
node server.js
```

The backend listens on port 5001 and the frontend proxy listens on port 3000.

## Notes

- The app expects the trained checkpoint file to be present in [training_checkpoints/model_checkpoint.pt](training_checkpoints/model_checkpoint.pt).
- The frontend build output is served by [server.js](server.js).
- If you want to develop the React UI interactively, use:

```bash
npm run dev
```
