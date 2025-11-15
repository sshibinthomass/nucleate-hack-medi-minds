## React Frontend (Vite) - Simple Chat

Scripts:

- `npm run dev` - start dev server on 5173
- `npm run build` - production build
- `npm run preview` - preview production build

Environment:

- Create `.env` and set `VITE_BACKEND_URL=http://localhost:8000` if your backend is different.

Backend dependency:

- Expects FastAPI backend running on `http://localhost:8000` with `POST /chat` as implemented in `backend/main.py`.
