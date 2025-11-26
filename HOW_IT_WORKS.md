# 🎯 How Exact Video Selection Works

## Overview

The system now sends **actual video names** from your Drive folders to Gemini, which selects the **exact best-matching videos**.

---

## 📂 Current Setup

I've created `drive_videos.json` with **sample data**. You need to replace it with your actual video IDs and names.

---

## 🔄 Complete Flow

### 1. You Upload Audio

```
Upload: "Transform your skin with Glow Coffee..."
```

### 2. Whisper Transcribes

```
Transcription: "Transform your skin with Glow Coffee. Our revolutionary formula..."
```

### 3. System Loads Drive Videos

From `drive_videos.json`:

```json
{
  "Glow Coffee": {
    "videos": [
      {"id": "abc123", "name": "coffee_pour_closeup.mp4"},
      {"id": "def456", "name": "woman_drinking_coffee.mp4"},
      {"id": "ghi789", "name": "coffee_beans.mp4"},
      {"id": "jkl012", "name": "glow_coffee_product.mp4"}
    ]
  },
  "Hair": {
    "videos": [
      {"id": "mno345", "name": "hair_brush_smooth.mp4"},
      {"id": "pqr678", "name": "shiny_hair_closeup.mp4"}
    ]
  }
}
```

### 4. System Sends to Gemini

```
Transcription: "Transform your skin with Glow Coffee..."

Available videos in Google Drive:
📁 Glow Coffee:
  - coffee_pour_closeup.mp4 (ID: abc123)
  - woman_drinking_coffee.mp4 (ID: def456)
  - coffee_beans.mp4 (ID: ghi789)
  - glow_coffee_product.mp4 (ID: jkl012)

📁 Hair:
  - hair_brush_smooth.mp4 (ID: mno345)
  - shiny_hair_closeup.mp4 (ID: pqr678)

Task:
Select 2-3 folders and choose 2-3 SPECIFIC videos from each.
Respond with EXACT video names and IDs.
```

### 5. Gemini Selects Exact Videos

```
FOLDER: Glow Coffee
VIDEO: coffee_pour_closeup.mp4|abc123
VIDEO: glow_coffee_product.mp4|jkl012

FOLDER: Product
VIDEO: product_packaging.mp4|xyz789

ACTRESS: None
```

### 6. System Downloads Videos

```
Downloading from Drive:
- coffee_pour_closeup.mp4 (ID: abc123)
- glow_coffee_product.mp4 (ID: jkl012)
- product_packaging.mp4 (ID: xyz789)
```

### 7. Video Generated

Your exact Drive videos + your audio + captions = Final video! 🎬

---

## 📋 What You Need to Do

### Replace Sample Data

Edit `drive_videos.json` and replace:

**Before (current sample):**
```json
{"id": "SAMPLE_ID_1", "name": "coffee_pour_closeup.mp4"}
```

**After (your actual data):**
```json
{"id": "1abc123xyz", "name": "your_actual_video.mp4"}
```

### How to Get Your Data

1. **Open Google Drive folder:**
   https://drive.google.com/drive/folders/1l_vWG07Q3tN1UChnlyR40_dZ3McO9NfB

2. **For each subfolder** (Glow Coffee, Hair, etc.):
   - Open the folder
   - For each video file:
     - Right-click → "Get link"
     - Extract file ID from link
     - Note the filename
     - Add to JSON

3. **Example:**
   ```
   Video: "coffee_sarah_v1.mp4"
   Link: https://drive.google.com/file/d/1abc123xyz456/view
   
   JSON Entry:
   {"id": "1abc123xyz456", "name": "coffee_sarah_v1.mp4"}
   ```

---

## 🎭 Actress Name Detection

If your filenames contain actress names, Gemini will detect and prioritize them!

**Examples:**

**Filename:** `coffee_pour_sarah.mp4`
- ✅ Detects: "sarah"
- ✅ Finds other "sarah" videos
- ✅ Prioritizes consistency

**Filename:** `hair_maria_jones.mp4`
- ✅ Detects: "maria jones"
- ✅ Finds other "maria" videos
- ✅ Uses same actress across clips

---

## 📊 Logs You'll See

### When It Works:

```
================================================================================
📋 GOOGLE DRIVE - Found Folders and Videos
================================================================================
  Total Folders: 9
  Folder Details:
    Glow Coffee:
      Video Count: 4
      Video Names: [coffee_pour_closeup.mp4, woman_drinking_coffee.mp4, ...]
    Hair:
      Video Count: 2
      Video Names: [hair_brush_smooth.mp4, shiny_hair_closeup.mp4]
================================================================================

================================================================================
📋 GEMINI AI - Sending Request with Video List
================================================================================
  Transcription: "Transform your skin with Glow Coffee..."
  Total Folders with Videos: 2
  Total Videos Available: 6
  Prompt: [Shows complete list sent to Gemini]
================================================================================

================================================================================
📋 GEMINI AI - Final Selection
================================================================================
  Selected Folders: [Glow Coffee, Product]
  Selected Videos:
    Glow Coffee: [coffee_pour_closeup.mp4, glow_coffee_product.mp4]
    Product: [product_packaging.mp4]
  Detected Actress: None
  Total Videos Selected: 3
================================================================================
```

---

## 🚨 If Videos Not Found

If `drive_videos.json` is empty or missing:

```
================================================================================
📋 GEMINI AI - No Videos Found
================================================================================
  Note: No videos in drive_videos.json. Please add video IDs and names.
  Fallback: Will use Pexels
================================================================================
```

System will fall back to Pexels with themed searches.

---

## ✅ Checklist

Before testing:

- [ ] Created `drive_videos.json` with actual video IDs
- [ ] All videos are public in Drive ("Anyone with link")
- [ ] Filenames match exactly (including `.mp4`)
- [ ] File IDs are correct (copied from Drive links)
- [ ] Server restarted after creating file

---

## 🧪 Test It

1. **Edit `drive_videos.json`** with your real video IDs
2. **Make videos public** in Drive
3. **Restart server:**
   ```powershell
   uvicorn main:app --reload
   ```
4. **Upload audio file**
5. **Check logs** - you'll see:
   - Actual video names sent to Gemini
   - Gemini's exact video selections
   - Download from Drive
   - Your footage in final video!

---

## 📝 Summary

**Current State:**
- ✅ Code is ready
- ✅ Sample `drive_videos.json` created
- ✅ Logging is comprehensive
- ⏳ **You need to add your actual video IDs**

**Next Step:**
1. Go to Drive
2. Get video IDs for all videos
3. Update `drive_videos.json`
4. Restart server
5. Test!

**Your system will then:**
- ✅ Send actual video names to Gemini
- ✅ Gemini selects exact videos
- ✅ Downloads from Drive
- ✅ Uses your branded footage!

---

## Example Entry

```json
{
  "Glow Coffee": {
    "videos": [
      {"id": "1a2b3c4d5e6f7g8h9i0j", "name": "coffee_pour_sarah_v1.mp4"},
      {"id": "2b3c4d5e6f7g8h9i0j1k", "name": "coffee_pour_sarah_v2.mp4"},
      {"id": "3c4d5e6f7g8h9i0j1k2l", "name": "woman_drinking_sarah.mp4"},
      {"id": "4d5e6f7g8h9i0j1k2l3m", "name": "glow_coffee_product.mp4"}
    ]
  }
}
```

**The system is ready - just add your video data!** 🚀

