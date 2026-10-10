# Agent HQ

A chat app where each conversation is an AI agent with an assigned role.

## Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # Git Bash on Windows
pip install -r requirements.txt
cp .env.example .env               # fill in your keys
uvicorn main:app --reload --port 8000
```

Health check: http://localhost:8000/health

## Frontend (Vite + React)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173
