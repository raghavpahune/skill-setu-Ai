# SkillSetuAI

AI-Powered Labour-Market Intelligence & Curriculum-Alignment Platform

Government of Maharashtra — Department of Skills, Employment, Entrepreneurship & Innovation

---

## What is SkillSetuAI?

SkillSetuAI converts changing industry demand into actionable skill, curriculum, training, and career decisions. It connects **Government**, **Training Institutes**, **Employers**, and **Students** through continuously updated labour-market intelligence.

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.11+
- (Optional) Supabase project for database
- (Optional) Gemini API key for AI Copilot

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The app runs in **full demo mode** by default — no API keys or database required.

### Environment Variables

Copy `.env.example` to `.env` and fill in values as they become available:

```bash
cp .env.example .env
```

See `.env.example` for all configuration options.

## Architecture

```
frontend/ — React + Vite + Tailwind + Recharts + Leaflet
backend/  — Python FastAPI
ai/       — Modular LLM layer (Gemini primary, provider interface for extensibility)
data/     — Demo dataset + schema + real public data samples
```

## Demo Data

The MVP ships with realistic synthetic Maharashtra labour-market data covering 5 districts, 50+ skills, 500+ jobs, 25+ courses, and 15+ employers. Small real public data samples (NSDC qualification packs, NCO-2015 codes) are included to demonstrate real-source support.

All synthetic data is labelled `"source": "DEMO_SYNTHETIC"`.

## Deployment

| Component | Target |
|---|---|
| Frontend | Vercel |
| Backend | Render |
| Database | Supabase PostgreSQL |

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, Tailwind CSS, Recharts, Leaflet.js |
| Backend | Python, FastAPI |
| Database | Supabase PostgreSQL (+ pgvector reserved) |
| AI | Google Gemini (modular provider interface) |

## License

MIT License
