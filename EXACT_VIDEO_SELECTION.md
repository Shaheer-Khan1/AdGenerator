# 🎯 Exact Video Selection from Drive

## Overview

The system now selects **EXACT videos** from your Google Drive folders, not just descriptions! It also detects actress names and prioritizes videos with the same actress for consistency.

---

## ✨ Features

1. ✅ **Selects Exact Videos** - Chooses specific videos by name and ID
2. ✅ **Actress Detection** - Automatically detects actress names from filenames
3. ✅ **Actress Matching** - Prioritizes videos with the same actress across folders
4. ✅ **Multiple Folders** - Selects videos from 2-3 relevant folders
5. ✅ **Direct Download** - Downloads videos directly from Drive

---

## 📋 Setup: Create `drive_videos.json`

### Step 1: Get Video IDs from Google Drive

For each video in your Drive folders:

1. **Open the video** in Google Drive
2. **Right-click** → **Get link**
3. **Copy the link** - Format: `https://drive.google.com/file/d/FILE_ID_HERE/view`
4. **Extract the FILE_ID** (the part between `/d/` and `/view`)

### Step 2: Create `drive_videos.json`

Create a file named `drive_videos.json` in your project root:

```json
{
  "Glow Coffee": {
    "videos": [
      {"id": "1abc123xyz", "name": "coffee_pour_sarah.mp4"},
      {"id": "2def456uvw", "name": "skincare_sarah.mp4"},
      {"id": "3ghi789rst", "name": "product_closeup.mp4"}
    ]
  },
  "Hair": {
    "videos": [
      {"id": "4jkl012mno", "name": "hair_brush_maria.mp4"},
      {"id": "5pqr345stu", "name": "shiny_hair_maria.mp4"},
      {"id": "6vwx678yza", "name": "hair_product.mp4"}
    ]
  },
  "Product": {
    "videos": [
      {"id": "7bcd901efg", "name": "product_packaging.mp4"},
      {"id": "8hij234klm", "name": "before_after.mp4"}
    ]
  },
  "Cellulite": {
    "videos": []
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
  },
  "Wrinkles": {
    "videos": []
  }
}
```

### Step 3: Make Videos Public

**Important:** Each video file must be individually public:

1. **Select all video files** in each folder
2. **Right-click** → **Share**
3. **Change to:** "Anyone with the link"
4. **Set permission:** "Viewer"
5. **Do this for EVERY video** in EVERY folder

---

## 🎬 How It Works

### Example Flow:

```
1. Upload Audio: "Transform your skin with Glow Coffee..."

2. Whisper Transcribes:
   "Transform your skin with Glow Coffee..."

3. Gemini Analyzes:
   - Topic: Coffee beauty product
   - Looks at actual video names in Drive
   - Sees: "coffee_pour_sarah.mp4", "skincare_sarah.mp4"
   - Detects actress: "sarah"

4. Gemini Selects:
   FOLDER: Glow Coffee
   VIDEO: coffee_pour_sarah.mp4|1abc123xyz
   VIDEO: skincare_sarah.mp4|2def456uvw
   
   FOLDER: Product
   VIDEO: product_sarah.mp4|7bcd901efg
   
   ACTRESS: sarah

5. System Prioritizes:
   - Finds all videos with "sarah" in name
   - Adds matching videos from other folders
   - Ensures consistent actress across clips

6. Downloads:
   - Downloads exact videos by ID
   - Uses Drive direct download URLs

7. Generates Video:
   - Uses your exact Drive footage
   - Consistent actress throughout
```

---

## 🎭 Actress Name Detection

### How It Works:

The system detects actress names from video filenames using patterns:

**Supported Patterns:**
- `name_video.mp4` → Detects "name"
- `video_name.mp4` → Detects "name"
- `firstname_lastname_video.mp4` → Detects "firstname lastname"
- `firstname-lastname_video.mp4` → Detects "firstname lastname"

**Examples:**
- `coffee_pour_sarah.mp4` → Actress: "sarah"
- `hair_maria_jones.mp4` → Actress: "maria jones"
- `skincare_anna-smith.mp4` → Actress: "anna smith"

**Filtered Words:**
These are NOT detected as names:
- Video, Clip, Footage, Scene, Shot
- Product, Coffee, Glow, Hair, etc.

---

## 📊 Logging Output

### What You'll See:

```
================================================================================
📋 GEMINI AI - Initializing for Exact Video Selection
================================================================================
  Model: gemini-2.5-flash
  Purpose: Select specific videos from Drive folders, detect actress names
================================================================================

================================================================================
📋 GEMINI AI - Sending Request with Video List
================================================================================
  Transcription: "Transform your skin with Glow Coffee..."
  Total Folders with Videos: 3
  Total Videos Available: 8
  Prompt Length: 1234
================================================================================

================================================================================
📋 GEMINI AI - Received Response
================================================================================
  Raw Response: FOLDER: Glow Coffee
VIDEO: coffee_pour_sarah.mp4|1abc123xyz
VIDEO: skincare_sarah.mp4|2def456uvw
FOLDER: Product
VIDEO: product_sarah.mp4|7bcd901efg
ACTRESS: sarah
================================================================================

================================================================================
📋 GEMINI AI - Actress Detected
================================================================================
  Actress Name: sarah
  Action: Prioritizing videos with same actress
================================================================================

================================================================================
📋 GEMINI AI - Final Selection
================================================================================
  Selected Folders: [Glow Coffee, Product]
  Selected Videos:
    Glow Coffee: [coffee_pour_sarah.mp4, skincare_sarah.mp4]
    Product: [product_sarah.mp4]
  Detected Actress: sarah
  Total Videos Selected: 3
================================================================================
```

---

## 🔧 Technical Details

### File Structure:

**`drive_videos.json`:**
```json
{
  "FolderName": {
    "videos": [
      {"id": "FILE_ID", "name": "filename.mp4"}
    ]
  }
}
```

### Gemini Prompt Format:

```
Available videos in Google Drive folders:
📁 Glow Coffee:
  - coffee_pour_sarah.mp4 (ID: 1abc123xyz)
  - skincare_sarah.mp4 (ID: 2def456uvw)
...

Task:
1. Select 2-3 folders
2. Choose EXACT videos by name
3. Detect actress names
4. Prioritize matching actress videos

Respond format:
FOLDER: FolderName
VIDEO: video_name.mp4|video_id
ACTRESS: actress_name
```

### Download Process:

1. **Parse Gemini Response** - Extract video IDs and names
2. **Detect Actress** - Find actress name in selected videos
3. **Prioritize Matching** - Add videos with same actress
4. **Download from Drive** - Use direct download URLs:
   ```
   https://drive.google.com/uc?export=download&id=VIDEO_ID
   ```
5. **Handle Virus Scan** - Automatically handles Drive's confirmation page

---

## 🚀 Usage

### Step 1: Create `drive_videos.json`

Copy `drive_videos_template.json` and fill in your video IDs:

```bash
cp drive_videos_template.json drive_videos.json
# Edit drive_videos.json with your video IDs
```

### Step 2: Make Videos Public

Make sure all videos are publicly accessible.

### Step 3: Restart Server

```bash
uvicorn main:app --reload
```

### Step 4: Upload Audio

1. Upload audio file
2. System transcribes
3. Gemini selects exact videos
4. Detects actress if present
5. Downloads from Drive
6. Generates video!

---

## ✅ Benefits

### Before (Descriptions):
- ❌ Generic video descriptions
- ❌ No actress consistency
- ❌ Uses Pexels stock footage

### After (Exact Videos):
- ✅ Selects your exact videos
- ✅ Detects and matches actress names
- ✅ Consistent actress across clips
- ✅ Uses your branded footage
- ✅ Full control over content

---

## 🐛 Troubleshooting

### "No videos found in Drive"

**Check:**
1. Is `drive_videos.json` in project root?
2. Are video IDs correct?
3. Are videos public?

**Fix:**
- Verify file exists: `ls drive_videos.json`
- Check JSON syntax: `python -m json.tool drive_videos.json`
- Verify video IDs match Drive links

### "Download failed"

**Causes:**
- Video not public
- Wrong video ID
- Network timeout

**Solution:**
- Make video public (individual file, not just folder)
- Verify video ID from Drive link
- Check internet connection

### "Actress not detected"

**Why:**
- Filename doesn't match patterns
- Name not capitalized properly
- Filtered as non-name word

**Fix:**
- Use format: `video_name_actress.mp4`
- Capitalize first letter: `Sarah` not `sarah`
- Avoid common words in name position

---

## 📝 Example `drive_videos.json`

```json
{
  "Glow Coffee": {
    "videos": [
      {"id": "1abc123xyz", "name": "coffee_pour_sarah.mp4"},
      {"id": "2def456uvw", "name": "skincare_sarah.mp4"},
      {"id": "3ghi789rst", "name": "product_closeup.mp4"}
    ]
  },
  "Hair": {
    "videos": [
      {"id": "4jkl012mno", "name": "hair_brush_maria.mp4"},
      {"id": "5pqr345stu", "name": "shiny_hair_maria.mp4"}
    ]
  },
  "Product": {
    "videos": [
      {"id": "6vwx678yza", "name": "product_packaging.mp4"},
      {"id": "7bcd901efg", "name": "before_after.mp4"}
    ]
  },
  "Cellulite": {"videos": []},
  "Joints": {"videos": []},
  "Menopause": {"videos": []},
  "Nails": {"videos": []},
  "Others": {"videos": []},
  "Wrinkles": {"videos": []}
}
```

---

## 🎉 Summary

**What You Get:**
- ✅ Exact video selection from Drive
- ✅ Actress name detection
- ✅ Consistent actress matching
- ✅ Your branded footage
- ✅ Full control

**Setup Required:**
1. Create `drive_videos.json` with video IDs
2. Make videos public
3. Restart server

**Your system now selects exact videos and matches actresses automatically!** 🎬✨

