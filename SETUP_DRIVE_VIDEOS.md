# 📝 Setup Guide: Drive Videos for Gemini Selection

## Goal

Send **actual video names** from your Drive folders to Gemini, so it can select **exact videos** based on the transcription.

---

## Step 1: List Your Videos

Go to your Google Drive folder and list all videos in each subfolder.

### For Each Folder:

1. Open the folder (e.g., "Glow Coffee")
2. List all video files
3. Get the file ID for each video:
   - Right-click video → "Get link"
   - Link format: `https://drive.google.com/file/d/FILE_ID_HERE/view`
   - Copy the FILE_ID

---

## Step 2: Create `drive_videos.json`

Create this file in your project root with ALL your videos:

```json
{
  "Glow Coffee": {
    "videos": [
      {"id": "1abc123xyz", "name": "coffee_pour.mp4"},
      {"id": "2def456uvw", "name": "woman_drinking_coffee.mp4"},
      {"id": "3ghi789rst", "name": "coffee_beans_closeup.mp4"},
      {"id": "4jkl012mno", "name": "glow_coffee_product.mp4"}
    ]
  },
  "Hair": {
    "videos": [
      {"id": "5pqr345stu", "name": "hair_brush_maria.mp4"},
      {"id": "6vwx678yza", "name": "shiny_hair_maria.mp4"},
      {"id": "7bcd901efg", "name": "hair_product_bottle.mp4"},
      {"id": "8hij234klm", "name": "woman_styling_hair.mp4"}
    ]
  },
  "Product": {
    "videos": [
      {"id": "9nop567qrs", "name": "product_packaging.mp4"},
      {"id": "0tuv890wxy", "name": "before_after_skin.mp4"},
      {"id": "1zab234cde", "name": "product_application.mp4"}
    ]
  },
  "Wrinkles": {
    "videos": [
      {"id": "2fgh567ijk", "name": "wrinkle_cream_application.mp4"},
      {"id": "3lmn890opq", "name": "smooth_skin_closeup.mp4"}
    ]
  },
  "Cellulite": {
    "videos": [
      {"id": "4rst123uvw", "name": "cellulite_treatment.mp4"}
    ]
  },
  "Joints": {
    "videos": []
  },
  "Menopause": {
    "videos": []
  },
  "Nails": {
    "videos": []
  },
  "Others": {
    "videos": []
  }
}
```

---

## Step 3: Make Videos Public

**CRITICAL:** Each video must be individually public!

1. In Google Drive, select a video
2. Right-click → Share
3. Change to: "Anyone with the link"
4. Permission: "Viewer"
5. Repeat for **EVERY video**

---

## How It Will Work

### Example:

**Your `drive_videos.json`:**
```json
{
  "Glow Coffee": {
    "videos": [
      {"id": "abc123", "name": "coffee_pour_sarah.mp4"},
      {"id": "def456", "name": "woman_drinking_sarah.mp4"},
      {"id": "ghi789", "name": "coffee_product.mp4"}
    ]
  },
  "Hair": {
    "videos": [
      {"id": "jkl012", "name": "hair_brush_sarah.mp4"},
      {"id": "mno345", "name": "shiny_hair_sarah.mp4"}
    ]
  }
}
```

**Whisper Transcribes:**
> "Transform your skin with Glow Coffee! Our revolutionary formula..."

**Gemini Receives:**
```
Transcription: "Transform your skin with Glow Coffee..."

Available videos:
📁 Glow Coffee:
  - coffee_pour_sarah.mp4 (ID: abc123)
  - woman_drinking_sarah.mp4 (ID: def456)
  - coffee_product.mp4 (ID: ghi789)

📁 Hair:
  - hair_brush_sarah.mp4 (ID: jkl012)
  - shiny_hair_sarah.mp4 (ID: mno345)
```

**Gemini Selects:**
```
FOLDER: Glow Coffee
VIDEO: coffee_pour_sarah.mp4|abc123
VIDEO: woman_drinking_sarah.mp4|def456

FOLDER: Hair
VIDEO: hair_brush_sarah.mp4|jkl012

ACTRESS: sarah
```

**System Downloads:**
- Exact videos from Drive
- All "sarah" videos for consistency
- Uses your branded footage!

---

## Logs You'll See

```
================================================================================
📋 GOOGLE DRIVE - Found Folders and Videos
================================================================================
  Total Folders: 9
  Folder Details:
    Glow Coffee:
      Video Count: 4
      Video Names: [coffee_pour_sarah.mp4, woman_drinking_sarah.mp4, ...]
    Hair:
      Video Count: 2
      Video Names: [hair_brush_sarah.mp4, shiny_hair_sarah.mp4]
================================================================================

================================================================================
📋 GEMINI AI - Sending Request with Video List
================================================================================
  Transcription: "Transform your skin with Glow Coffee..."
  Total Folders with Videos: 2
  Total Videos Available: 6
  Prompt Length: 1234
================================================================================

================================================================================
📋 GEMINI AI - Final Selection
================================================================================
  Selected Folders: [Glow Coffee, Hair]
  Selected Videos:
    Glow Coffee: [coffee_pour_sarah.mp4, woman_drinking_sarah.mp4]
    Hair: [hair_brush_sarah.mp4]
  Detected Actress: sarah
  Total Videos Selected: 3
================================================================================

================================================================================
📋 VIDEO GENERATION - Starting with Upload
================================================================================
  Selected Folders: [Glow Coffee, Hair]
  Video Descriptions:
    Glow Coffee: [{name: coffee_pour_sarah.mp4, id: abc123}, ...]
    Hair: [{name: hair_brush_sarah.mp4, id: jkl012}]
================================================================================
```

---

## Quick Template

Copy and edit this:

```bash
# Copy template
cp drive_videos_template.json drive_videos.json

# Edit it with your video IDs and names
# Use any text editor
```

**Fill in:**
- Replace `YOUR_FILE_ID_X` with actual Drive file IDs
- Replace filenames with your actual filenames
- Add ALL videos from ALL folders

---

## Example: Getting File IDs

### Method 1: From Drive UI

1. **Open video in Drive**
2. **Right-click** → "Get link"
3. **Copy:** `https://drive.google.com/file/d/1abc123xyz/view`
4. **Extract:** `1abc123xyz` (the part between `/d/` and `/view`)

### Method 2: From Shareable Link

1. Click "Share" on video
2. Copy link
3. Extract ID from URL

---

## Benefits

Once you create `drive_videos.json`:

✅ **Gemini sees actual video names**
✅ **Selects exact videos by name**
✅ **Detects actress names from filenames**
✅ **Prioritizes matching actress videos**
✅ **Downloads exact videos from Drive**
✅ **Uses YOUR footage, not Pexels**

---

## What Happens Without `drive_videos.json`?

- System falls back to Pexels
- Uses themed searches based on folder names
- Still works, but not your exact videos

---

## Summary

**To Use Your Drive Videos:**
1. ✅ Create `drive_videos.json` with all video IDs and names
2. ✅ Make videos public in Drive
3. ✅ Restart server
4. ✅ Upload audio
5. ✅ Gemini selects your exact videos!

**File needed:**
`drive_videos.json` in project root with format:
```json
{
  "FolderName": {
    "videos": [
      {"id": "FILE_ID", "name": "filename.mp4"}
    ]
  }
}
```

Once you create this file, the system will use your exact Drive videos! 🎬

