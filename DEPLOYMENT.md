# Deployment Guide

This project is deployed as two services:

- Backend API on Render from `backend/main.py`
- Frontend Vite app on Vercel from the `frontend` folder

## 1. Deploy Backend To Render

1. Push this repository to GitHub.
2. In Render, choose **New > Web Service** and connect the GitHub repo.
3. If Render detects `render.yaml`, use the Blueprint flow. Otherwise use:
   - Root Directory: `backend`
   - Runtime: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Health Check Path: `/health`
4. Add environment variables:
   - `GEMINI_API_KEY`: your Gemini API key
   - `JOOBLE_API_KEY`: optional, for live job results
   - `DEBUG`: `False`
   - `USE_TF`: `0`
   - `USE_TORCH`: `1`
   - `TF_ENABLE_ONEDNN_OPTS`: `0`
5. Deploy and wait until Render shows the service is live.
6. Open `https://your-render-service.onrender.com/health`; it should return:

```json
{"status":"ok"}
```

## 2. Deploy Frontend To Vercel

1. In Vercel, choose **Add New > Project** and import the same GitHub repo.
2. Set:
   - Framework Preset: `Vite`
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `dist`
   - Install Command: `npm install`
3. Add environment variable:
   - `VITE_API_BASE_URL`: your Render backend URL, for example `https://your-render-service.onrender.com`
4. Deploy.

## 3. Connect Both Services

After both deployments finish:

1. Visit your Vercel URL.
2. Upload or paste a resume.
3. If requests fail, confirm `VITE_API_BASE_URL` has no trailing slash and points to the Render service, not the Vercel URL.

## Notes

- Legacy `.doc` parsing uses Microsoft Word automation and only works on Windows. Render runs Linux, so deploy-friendly formats are PDF, DOCX, TXT, and images.
- The backend can run without `JOOBLE_API_KEY`; it falls back to the local demo job database.
- The backend needs `GEMINI_API_KEY` for the best profile parsing and reasoning results.
