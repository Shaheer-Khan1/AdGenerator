# 🎨 Simple UI Guide

## Overview

Your video generator now has a **beautiful, simple web UI** where you can:
1. Generate videos with AI voice (ElevenLabs)
2. Upload your own voiceover audio
3. Track progress in real-time
4. Download completed videos

---

## Access the UI

### Local Development
```
http://localhost:8000/
```

### After Deployment (Render)
```
https://your-app.onrender.com/
```

---

## Features

### ✨ Two Modes

**1. AI Voice Mode** (Default)
- Enter your script
- AI generates voiceover using ElevenLabs
- Automatic caption generation

**2. Upload Audio Mode**
- Upload your pre-recorded voiceover (MP3, WAV, M4A, AAC)
- Enter script text (for captions)
- Use your own voice!

### 🎯 Easy Switch
Click the link at the top to toggle between modes:
- "Want to use your own voice? Upload Audio"
- "Want to use AI voice? Use ElevenLabs"

---

## How to Use

### Option 1: AI Voice (ElevenLabs)

1. **Enter Script**
   ```
   Example: "Welcome to my channel. Today we're exploring AI technology."
   ```

2. **Enter Search Query**
   ```
   Example: technology, nature, business, sports
   ```

3. **Click "Generate Video with AI Voice"**

4. **Wait** (30-60 seconds)
   - See real-time progress updates
   - Status shows each step

5. **Download** when complete!

### Option 2: Upload Your Audio

1. **Click "Upload Audio"** link at top

2. **Upload Audio File**
   - Click the upload box
   - Select your MP3/WAV/M4A file
   - File name will show when uploaded

3. **Enter Script Text**
   ```
   Enter the exact text from your voiceover
   (Used to generate synced captions)
   ```

4. **Enter Search Query**
   ```
   Example: technology, nature, business
   ```

5. **Click "Generate Video with Your Audio"**

6. **Wait** (30-60 seconds)
   - Progress updates in real-time

7. **Download** your video!

---

## Progress Updates

The UI shows real-time progress:

```
⏳ Task created
⏳ Using uploaded audio...
⏳ Converting to vertical format...
⏳ Compiling videos...
⏳ Merging audio...
⏳ Adding modern captions...
✅ Video completed!
```

---

## Supported Audio Formats

When uploading your own voiceover:
- ✅ MP3
- ✅ WAV
- ✅ M4A
- ✅ AAC

**File size**: No strict limit, but keep under 10MB for best performance

---

## UI Features

### Beautiful Design
- Modern gradient background
- Clean white container
- Smooth animations
- Responsive (works on mobile!)

### Real-time Progress
- Live status updates every 2 seconds
- Animated progress bar
- Color-coded states:
  - 🔵 Blue = Processing
  - 🟢 Green = Success
  - 🔴 Red = Error

### Error Handling
- Clear error messages
- Automatic retry suggestions
- Server busy notification

---

## Technical Details

### API Endpoints Used

**AI Voice:**
```
POST /generate-video
Body: { script_text, search_query }
```

**Upload Audio:**
```
POST /generate-video-upload
Body: FormData { audio_file, script_text, search_query }
```

**Status Check:**
```
GET /task/{task_id}
Returns: { status, progress, error }
```

**Download:**
```
GET /download/{task_id}
Returns: video file
```

---

## Customization

### Change Colors

Edit `index.html`:

```css
/* Main gradient */
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

/* Button gradient */
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
```

### Change UI Text

Edit text in `index.html`:

```html
<h1>🎬 AI Video Generator</h1>
<p class="subtitle">Create stunning vertical videos with captions</p>
```

### Add Logo

Add to `index.html` before `<h1>`:

```html
<img src="your-logo.png" alt="Logo" style="width: 100px; margin: 0 auto 20px; display: block;">
```

---

## Troubleshooting

### UI Not Loading

**Check:**
1. Is the server running? (`uvicorn main:app`)
2. Is `index.html` in the same folder as `main.py`?
3. Try accessing `/api/status` to check if API works

### "Server Busy" Error

**Cause:** Too many concurrent tasks

**Solution:**
- Wait for current tasks to complete
- Or increase `MAX_CONCURRENT_TASKS` in `main.py`

### Upload Fails

**Check:**
1. File format (must be MP3, WAV, M4A, AAC)
2. File size (keep under 10MB)
3. File not corrupted

### Video Generation Fails

**Common causes:**
1. Invalid API keys (ElevenLabs/Pexels)
2. Network issues
3. Search query returns no videos

**Solution:**
- Check error message
- Try different search query
- Verify API keys in `.env`

---

## Mobile Support

The UI is fully responsive and works on:
- ✅ Desktop (Chrome, Firefox, Safari, Edge)
- ✅ Tablet (iPad, Android tablets)
- ✅ Mobile (iPhone, Android phones)

---

## Production Tips

### 1. Add Authentication

For production, add basic auth:

```python
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()

@app.get("/")
async def root(credentials: HTTPBasicCredentials = Depends(security)):
    # Verify credentials
    if credentials.username != "admin" or credentials.password != "password":
        raise HTTPException(401, "Invalid credentials")
    # ... serve UI
```

### 2. Add Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/generate-video")
@limiter.limit("5/minute")  # 5 requests per minute
async def generate_video(...):
    # ...
```

### 3. Add Custom Domain

On Render:
1. Go to Settings → Custom Domain
2. Add your domain
3. Update DNS records
4. SSL auto-provisioned!

---

## API Documentation

Access Swagger UI for API testing:
```
http://localhost:8000/docs
```

---

## Summary

✅ **Simple, beautiful UI**
✅ **Two modes**: AI voice or upload
✅ **Real-time progress** tracking
✅ **Mobile-friendly** responsive design
✅ **Easy to use** - no technical knowledge needed
✅ **Production-ready** with error handling

**Your video generator now has a professional web interface!** 🎉

---

## Quick Start

```bash
# 1. Make sure API keys are set in .env
PEXELS_API_KEY=your_key
ELEVENLABS_API_KEY=your_key

# 2. Run server
python main.py

# 3. Open browser
http://localhost:8000/

# 4. Generate videos!
```

Enjoy your new UI! 🚀


