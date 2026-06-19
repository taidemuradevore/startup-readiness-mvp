# look at the 1906output if you don't wanna scroll through the notebook
# This is all using gemini flash 2.5
# vibe coded btw, just to see what something could look like

## Combined App Layout

- Backend API: this repo root, with `api_endpoints.py` as the FastAPI entrypoint.
- Frontend app: `frontend/`, copied from the `startup-readiness` Next.js app.

Run the backend:

```bash
.venv/bin/uvicorn api_endpoints:app --reload --host 0.0.0.0 --port 8000
```

Run the frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend expects `NEXT_PUBLIC_API_URL=http://localhost:8000` and Supabase auth env values in `frontend/.env.local`. The backend reads Supabase and database env values from the root `.env`.
