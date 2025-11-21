# Backend Setup (Python)
python -m venv .venv

# Activate the venv in PowerShell:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
.\.venv\Scripts\Activate.ps1

# Install Python dependencies
pip install -r requirements.txt

# Frontend Setup (Node.js/React)
npm install

# Development
# Terminal 1: Run FastAPI backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Run React dev server
npm run dev

# Production Build
npm run build
# Then run the FastAPI server (it will serve the built React app)
