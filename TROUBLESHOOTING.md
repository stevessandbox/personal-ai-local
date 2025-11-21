# Troubleshooting: Blank Screen

If you're seeing a blank screen, try these steps:

## 1. Check if React app is running

**For Development:**
```bash
# Terminal 1: Start FastAPI backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Start React dev server
npm run dev
```

Then open: http://localhost:5173 (Vite default port)

**For Production:**
```bash
# Build the React app first
npm run build

# Then start FastAPI (it will serve the built app)
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then open: http://localhost:8000

## 2. Check browser console

Open browser DevTools (F12) and check:
- Console tab for JavaScript errors
- Network tab to see if requests are failing

## 3. Verify dependencies are installed

```bash
# Install Node.js dependencies
npm install

# Install Python dependencies
pip install -r requirements.txt
```

## 4. Check if backend is running

The React app needs the FastAPI backend running on port 8000. Verify:
- Backend is running: http://localhost:8000
- No port conflicts

## 5. Clear browser cache

Try hard refresh: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)

## Common Issues

- **Blank screen with no errors**: Usually means React app isn't built/running
- **CORS errors**: Make sure backend is running and Vite proxy is configured
- **404 errors**: Check that `app/static/index.html` exists (after building)

