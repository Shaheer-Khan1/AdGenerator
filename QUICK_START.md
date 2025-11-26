# ⚡ Quick Start Guide

## 🎯 What This Does

Upload your audio → AI picks best category → Generates vertical video with captions!

---

## 🚀 Start the Server

### Windows:

```powershell
# 1. Navigate to project
cd C:\Users\shahe\OneDrive\Desktop\ShortsGenerator

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Start server
uvicorn main:app --reload
```

### Linux/Mac:

```bash
# 1. Navigate to project
cd /path/to/ShortsGenerator

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Start server
uvicorn main:app --reload
```

---

## 🌐 Open UI

Open browser: **http://localhost:8000/**

---

## 🎬 Create Your First Video

### Method 1: Upload Your Audio

1. **Click "Upload Audio" tab**

2. **Choose your audio file**
   - MP3, WAV, M4A, or AAC
   - Your voiceover/narration

3. **Click "Transcribe Audio"**
   - Wait 5-10 seconds
   - See transcription appear
   - See suggested folder (purple box)

4. **Click "Generate Video"**
   - Wait 30-60 seconds
   - Progress shows in real-time

5. **Click "Download Video"**
   - Get your finished video!

### Method 2: AI Voice

1. **Click "AI Voice" tab**

2. **Write your script**
   ```
   Transform your skin with every sip!
   Our Glow Coffee is packed with collagen...
   ```

3. **Add search query**
   ```
   coffee beauty glow
   ```

4. **Click "Generate Video"**

5. **Download when ready!**

---

## 🤖 How AI Selection Works

### Example 1: Coffee Product
**Your Audio:**
> "Discover radiant skin with Glow Coffee..."

**AI Thinks:**
- 🤖 Topic: Coffee beauty product
- 📁 Best folder: "Glow Coffee"
- 🔍 Pexels query: "coffee beauty skin glow"

**Result:** Videos of coffee, skin care, glowing faces

---

### Example 2: Hair Care
**Your Audio:**
> "Beautiful hair starts from within with our new formula..."

**AI Thinks:**
- 🤖 Topic: Hair care product
- 📁 Best folder: "Hair"
- 🔍 Pexels query: "hair care beautiful"

**Result:** Videos of hair brushing, shiny hair, hair care

---

### Example 3: Anti-Aging
**Your Audio:**
> "Say goodbye to wrinkles with our breakthrough serum..."

**AI Thinks:**
- 🤖 Topic: Anti-aging
- 📁 Best folder: "Wrinkles"
- 🔍 Pexels query: "anti aging wrinkles skincare"

**Result:** Videos of skincare, smooth skin, beauty routines

---

## 🎨 What You Get

✅ **720x1280 vertical video** (perfect for TikTok, Instagram, YouTube Shorts)
✅ **Your voiceover** (or AI-generated)
✅ **Synced captions** (word-by-word, subtle style)
✅ **Themed footage** (AI-matched to your content)
✅ **Professional look** (no watermarks)

---

## ⚙️ Settings

All optimized automatically:
- 5 video clips per video
- 24px caption font
- Bottom-centered captions
- Vertical format (9:16)
- High quality MP4

---

## 📁 Output Location

Videos saved to: `output_videos/`

Format: `{task-id}_final.mp4`

---

## 🐛 Troubleshooting

### Server won't start?

```bash
# Check if already running
# Kill old process and restart
```

### "Pexels API error"?

Check `.env` file:
```
PEXELS_API_KEY=your_key_here
```

### No audio in video?

- Ensure audio file is not corrupted
- Try converting to MP3 first

### Captions not showing?

- Currently disabled on Windows
- Works on Linux/cloud deployment

---

## 📊 Processing Times

| Step | Time | What's Happening |
|------|------|------------------|
| Transcription | 5-10s | Whisper AI analyzing audio |
| AI Analysis | 2-3s | Gemini picking category |
| Video Search | 3-5s | Finding Pexels videos |
| Download | 10-15s | Getting video clips |
| Processing | 20-30s | Converting, merging, captions |
| **Total** | **40-60s** | Complete video ready! |

---

## 🎯 Categories Available

1. **Cellulite** - Cellulite treatment content
2. **Glow Coffee** - Coffee beauty products
3. **Hair** - Hair care and styling
4. **Joints** - Joint health and wellness
5. **Menopause** - Menopause-related topics
6. **Nails** - Nail care and manicure
7. **Others** - General/miscellaneous
8. **Product** - General product videos
9. **Wrinkles** - Anti-aging and skincare

AI automatically picks the best match! 🤖

---

## 💡 Pro Tips

### Better Transcriptions
- Use clear audio (no background noise)
- Speak at normal pace
- Good microphone quality

### Better Video Selection
- Use specific topics in audio
- Mention product names clearly
- Keep focus on one topic per video

### Faster Processing
- Shorter audio = faster processing
- 30-60 seconds is ideal for shorts

---

## 🔄 Workflow

```
📤 Upload Audio
  ↓
🎤 Whisper Transcribes
  ↓
🤖 Gemini Analyzes Topic
  ↓
📁 Selects Best Category
  ↓
🔍 Searches Themed Videos
  ↓
📥 Downloads Clips
  ↓
✂️ Converts to Vertical
  ↓
🔊 Merges with Audio
  ↓
📝 Adds Synced Captions
  ↓
✅ Video Ready!
  ↓
📥 Download & Use
```

---

## 🎬 Example Use Cases

### TikTok/Instagram Reels
- Product promotions
- Tips and tricks
- Before/after stories
- Product reviews

### YouTube Shorts
- Quick tutorials
- Product highlights
- Educational content
- Testimonials

### Facebook Stories
- Brand awareness
- Product launches
- Flash sales
- Announcements

---

## 📈 System Requirements

**Minimum:**
- 2GB RAM
- Internet connection
- Modern browser

**Recommended:**
- 4GB RAM
- Fast internet
- Chrome/Firefox

---

## 🆘 Need Help?

Check these files:
- `DRIVE_STATUS.md` - Full system explanation
- `MODERN_CAPTIONS.md` - Caption system details
- `RENDER_DEPLOY.md` - Deployment guide

---

## ✅ You're Ready!

1. ✅ Server running: `uvicorn main:app --reload`
2. ✅ Browser open: http://localhost:8000/
3. ✅ Upload audio or write script
4. ✅ Generate amazing videos!

**That's it! Start creating! 🚀🎬**

