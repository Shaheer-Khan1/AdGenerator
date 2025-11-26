# 🚀 Quick Setup Guide - Use Your Drive Videos

## Goal

Make Gemini select **exact videos by name** from your Google Drive.

---

## ⚡ Quick Start (Choose One Method)

### Method 1: Edit JSON Directly

1. **Open `drive_videos.json`**
2. **Replace sample IDs with your actual video IDs:**

```json
{
  "Glow Coffee": {
    "videos": [
      {"id": "YOUR_REAL_FILE_ID", "name": "your_actual_video.mp4"}
    ]
  }
}
```

3. **Save and restart server**

### Method 2: Use Helper Script

1. **Open `create_drive_mapping.py`**
2. **Add your videos:**

```python
videos = {
    "Glow Coffee": [
        ("1abc123xyz", "coffee_pour_v1.mp4"),
        ("2def456uvw", "coffee_pour_v2.mp4"),
    ],
    "Hair": [
        ("3ghi789rst", "hair_smooth.mp4"),
    ]
}
```

3. **Run script:**

```powershell
python create_drive_mapping.py
```

4. **It creates `drive_videos.json` automatically!**

---

## 📋 How to Get File IDs from Google Drive

### Step-by-Step:

1. **Go to your Drive folder:**
   https://drive.google.com/drive/folders/1l_vWG07Q3tN1UChnlyR40_dZ3McO9NfB

2. **Open a subfolder** (e.g., "Glow Coffee")

3. **For each video:**
   - Right-click → "Get link" or "Share"
   - You'll see: `https://drive.google.com/file/d/1abc123xyz456/view`
   - **Copy the ID:** `1abc123xyz456` (between `/d/` and `/view`)

4. **Note the filename:** `coffee_pour.mp4`

5. **Make video public:**
   - Click "Share"
   - Change to "Anyone with the link"
   - Permission: "Viewer"

6. **Add to your list:**
   ```json
   {"id": "1abc123xyz456", "name": "coffee_pour.mp4"}
   ```

---

## 🎯 Example: Complete Entry

Let's say you have 3 videos in "Glow Coffee":

### Videos in Drive:
1. `coffee_pour_sarah.mp4` - Link: `https://drive.google.com/file/d/1aB2cD3eF4gH/view`
2. `coffee_product.mp4` - Link: `https://drive.google.com/file/d/5iJ6kL7mN8oP/view`
3. `woman_drinking.mp4` - Link: `https://drive.google.com/file/d/9qR0sT1uV2wX/view`

### Your JSON:

```json
{
  "Glow Coffee": {
    "videos": [
      {"id": "1aB2cD3eF4gH", "name": "coffee_pour_sarah.mp4"},
      {"id": "5iJ6kL7mN8oP", "name": "coffee_product.mp4"},
      {"id": "9qR0sT1uV2wX", "name": "woman_drinking.mp4"}
    ]
  }
}
```

---

## ✅ What Happens After Setup

### 1. Upload Audio

Audio says: *"Transform your skin with Glow Coffee..."*

### 2. System Logs

```
================================================================================
📋 GOOGLE DRIVE - Found Folders and Videos
================================================================================
  Total Folders: 9
  Folder Details:
    Glow Coffee:
      Video Count: 3
      Video Names: [coffee_pour_sarah.mp4, coffee_product.mp4, woman_drinking.mp4]
================================================================================
```

### 3. Gemini Receives

```
Transcription: "Transform your skin with Glow Coffee..."

Available videos:
📁 Glow Coffee:
  - coffee_pour_sarah.mp4 (ID: 1aB2cD3eF4gH)
  - coffee_product.mp4 (ID: 5iJ6kL7mN8oP)
  - woman_drinking.mp4 (ID: 9qR0sT1uV2wX)
```

### 4. Gemini Selects

```
FOLDER: Glow Coffee
VIDEO: coffee_pour_sarah.mp4|1aB2cD3eF4gH
VIDEO: coffee_product.mp4|5iJ6kL7mN8oP

ACTRESS: sarah
```

### 5. System Downloads

```
Downloading from Drive: coffee_pour_sarah.mp4 (1/2)
Downloading from Drive: coffee_product.mp4 (2/2)
```

### 6. Video Created

✅ Your exact Drive videos + your audio + captions = Final video!

---

## 🎭 Pro Tip: Actress Names

Name your videos with actress names for consistency!

**Good filenames:**
- `coffee_pour_sarah.mp4`
- `hair_smooth_sarah.mp4`
- `product_showcase_sarah.mp4`

**Result:**
- Gemini detects "sarah"
- Finds all "sarah" videos
- Uses same actress across entire video
- Professional, consistent look!

---

## 🔍 Testing Your Setup

1. **Check your JSON is valid:**
   ```powershell
   python -c "import json; print(json.load(open('drive_videos.json')))"
   ```

2. **Start server:**
   ```powershell
   uvicorn main:app --reload
   ```

3. **Upload test audio**

4. **Watch the logs:**
   - See your video names sent to Gemini
   - See Gemini's exact selections
   - See downloads from Drive

---

## 🚨 Troubleshooting

### "No videos found"
- ✅ Check `drive_videos.json` exists
- ✅ Check JSON syntax is valid
- ✅ Restart server

### "Download failed"
- ✅ Make videos public in Drive
- ✅ Check file IDs are correct
- ✅ Try downloading manually: `https://drive.google.com/uc?export=download&id=YOUR_ID`

### "Fallback to Pexels"
- ✅ `drive_videos.json` is empty or missing
- ✅ Add video entries
- ✅ Restart server

---

## 📊 Current Status

**Right Now:**

✅ Code is ready
✅ Sample `drive_videos.json` exists
✅ Comprehensive logging
✅ Actress detection
✅ Exact video selection

**You Need:**

⏳ Add your actual video IDs to `drive_videos.json`
⏳ Make videos public in Drive
⏳ Restart server

**Then:**

🎉 Gemini will select your exact videos!
🎉 Your branded footage in every video!
🎉 Consistent actress across clips!

---

## 📝 Minimal Example to Test

Start small! Add just 2 videos:

```json
{
  "Glow Coffee": {
    "videos": [
      {"id": "YOUR_FILE_ID_1", "name": "video1.mp4"},
      {"id": "YOUR_FILE_ID_2", "name": "video2.mp4"}
    ]
  },
  "Hair": {"videos": []},
  "Product": {"videos": []},
  "Wrinkles": {"videos": []},
  "Cellulite": {"videos": []},
  "Joints": {"videos": []},
  "Menopause": {"videos": []},
  "Nails": {"videos": []},
  "Others": {"videos": []}
}
```

Test it! If it works, add more videos.

---

## 🎬 Ready to Go!

Your system now:

1. ✅ Loads video list from `drive_videos.json`
2. ✅ Sends actual video names to Gemini
3. ✅ Gemini selects exact videos
4. ✅ Downloads from Drive
5. ✅ Uses your footage!

**Just add your video data and test!** 🚀

---

## Need Help?

Check these files:
- `HOW_IT_WORKS.md` - Detailed flow explanation
- `SETUP_DRIVE_VIDEOS.md` - Complete setup guide
- `create_drive_mapping.py` - Helper script

**The code is ready - it's just waiting for your video data!**

