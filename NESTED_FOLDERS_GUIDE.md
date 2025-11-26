# 📂 Nested Folders Guide - Subfolders Support

## ✅ NEW: Subfolder Support!

The system now supports **nested folders** (subfolders within main folders)!

---

## 📁 New JSON Structure

```json
{
  "Glow Coffee": {
    "videos": [
      {"id": "main_video_id_1", "name": "coffee_main.mp4"}
    ],
    "subfolders": {
      "Coffee Pouring": {
        "videos": [
          {"id": "sub_video_id_1", "name": "pour_closeup_1.mp4"},
          {"id": "sub_video_id_2", "name": "pour_closeup_2.mp4"}
        ]
      },
      "Coffee Drinking": {
        "videos": [
          {"id": "sub_video_id_3", "name": "woman_drinking_sarah.mp4"},
          {"id": "sub_video_id_4", "name": "man_drinking_coffee.mp4"}
        ]
      }
    }
  },
  "Hair": {
    "videos": [
      {"id": "hair_main_1", "name": "hair_showcase.mp4"}
    ],
    "subfolders": {
      "Hair Brushing": {
        "videos": [
          {"id": "brush_1", "name": "brush_smooth_sarah.mp4"},
          {"id": "brush_2", "name": "brush_slow_motion.mp4"}
        ]
      }
    }
  }
}
```

---

## 🎯 How It Works

### Structure

```
Your Google Drive
│
├── Glow Coffee/
│   ├── coffee_main.mp4                 ← Main folder video
│   ├── Coffee Pouring/                  ← Subfolder
│   │   ├── pour_closeup_1.mp4
│   │   └── pour_closeup_2.mp4
│   └── Coffee Drinking/                 ← Subfolder
│       ├── woman_drinking_sarah.mp4
│       └── man_drinking_coffee.mp4
│
├── Hair/
│   ├── hair_showcase.mp4               ← Main folder video
│   └── Hair Brushing/                   ← Subfolder
│       ├── brush_smooth_sarah.mp4
│       └── brush_slow_motion.mp4
```

### Your `drive_videos.json`

```json
{
  "Glow Coffee": {
    "videos": [
      {"id": "FILE_ID_1", "name": "coffee_main.mp4"}
    ],
    "subfolders": {
      "Coffee Pouring": {
        "videos": [
          {"id": "FILE_ID_2", "name": "pour_closeup_1.mp4"},
          {"id": "FILE_ID_3", "name": "pour_closeup_2.mp4"}
        ]
      },
      "Coffee Drinking": {
        "videos": [
          {"id": "FILE_ID_4", "name": "woman_drinking_sarah.mp4"},
          {"id": "FILE_ID_5", "name": "man_drinking_coffee.mp4"}
        ]
      }
    }
  }
}
```

---

## 📊 What Gemini Sees

When you upload audio, Gemini receives:

```
Available videos in Google Drive folders (📁 = main folder, 📂 = subfolder):

📁 Glow Coffee:
  - coffee_main.mp4 (ID: FILE_ID_1)
  📂 Coffee Pouring:
    - pour_closeup_1.mp4 (ID: FILE_ID_2)
    - pour_closeup_2.mp4 (ID: FILE_ID_3)
  📂 Coffee Drinking:
    - woman_drinking_sarah.mp4 (ID: FILE_ID_4)
    - man_drinking_coffee.mp4 (ID: FILE_ID_5)

📁 Hair:
  - hair_showcase.mp4 (ID: HAIR_MAIN_1)
  📂 Hair Brushing:
    - brush_smooth_sarah.mp4 (ID: BRUSH_1)
    - brush_slow_motion.mp4 (ID: BRUSH_2)
```

---

## 🎬 Example Workflow

### 1. Upload Audio

Audio: *"Discover the secret of glowing skin with our coffee blend. Sarah demonstrates the perfect pour..."*

### 2. Whisper Transcribes

Transcription: *"Discover the secret of glowing skin with our coffee blend. Sarah demonstrates the perfect pour..."*

### 3. Gemini Selects EXACT Videos

```
FOLDER: Glow Coffee
VIDEO: pour_closeup_1.mp4|FILE_ID_2
VIDEO: woman_drinking_sarah.mp4|FILE_ID_4
VIDEO: pour_closeup_2.mp4|FILE_ID_3

FOLDER: Product
VIDEO: product_showcase_sarah.mp4|PRODUCT_ID_1

ACTRESS: sarah
```

**Notice:** Gemini selected:
- ✅ Videos from main folder
- ✅ Videos from subfolders
- ✅ Prioritized "sarah" videos across all folders

### 4. System Downloads

```
Downloading from Drive: pour_closeup_1.mp4 (1/4)
Downloading from Drive: woman_drinking_sarah.mp4 (2/4)
Downloading from Drive: pour_closeup_2.mp4 (3/4)
Downloading from Drive: product_showcase_sarah.mp4 (4/4)
```

---

## 📋 Logs You'll See

```
================================================================================
📋 GOOGLE DRIVE - Loaded Video Mapping
================================================================================
  Source: drive_videos.json
  Folders: [Glow Coffee, Hair, Product, ...]
  Total Videos (including subfolders): 25

================================================================================
📋 GOOGLE DRIVE - Found Folders and Videos
================================================================================
  Glow Coffee:
    Main Folder Videos: 1
    Subfolders: 2
    Subfolder Videos: 4
    Total Videos: 5
    Subfolder Details:
      Coffee Pouring:
        Video Count: 2
        Video Names: [pour_closeup_1.mp4, pour_closeup_2.mp4]
      Coffee Drinking:
        Video Count: 2
        Video Names: [woman_drinking_sarah.mp4, man_drinking_coffee.mp4]

================================================================================
📋 GEMINI AI - Sending Request with Video List
================================================================================
  Total Folders with Videos: 9
  Total Videos Available: 25
  Prompt shows nested structure with 📁 and 📂 icons

================================================================================
📋 GEMINI AI - Final Selection
================================================================================
  Selected Folders: [Glow Coffee, Product]
  Selected Videos:
    Glow Coffee: [pour_closeup_1.mp4, woman_drinking_sarah.mp4, ...]
    Product: [product_showcase_sarah.mp4]
  Detected Actress: sarah
```

---

## 🔧 How to Set Up

### Option 1: Manually Edit JSON

```json
{
  "Glow Coffee": {
    "videos": [],                    ← Main folder videos
    "subfolders": {                   ← Subfolders
      "Subfolder Name": {
        "videos": [
          {"id": "ID", "name": "name.mp4"}
        ]
      }
    }
  }
}
```

### Option 2: Use Helper Script

```python
# Edit create_drive_mapping.py

videos = {
    "Glow Coffee": {
        "main": [
            ("FILE_ID_1", "coffee_main.mp4")
        ],
        "subfolders": {
            "Coffee Pouring": [
                ("FILE_ID_2", "pour_closeup_1.mp4"),
                ("FILE_ID_3", "pour_closeup_2.mp4")
            ]
        }
    }
}
```

---

## ✨ Benefits

### Before (Flat Structure)

```
Glow Coffee: 10 videos (all mixed together)
```

**Problem:** Hard to organize, cluttered

### After (Nested Structure)

```
Glow Coffee:
├── 2 main videos
├── Coffee Pouring/
│   └── 3 specific videos
└── Coffee Drinking/
    └── 5 specific videos
```

**Benefits:**
- ✅ Better organization
- ✅ Gemini sees context (subfolder names help)
- ✅ More specific video selection
- ✅ Clearer logs
- ✅ Same actress detection across nested videos

---

## 🎭 Actress Detection

Works across ALL levels:

**Main folder video:** `hair_showcase_sarah.mp4`
**Subfolder video:** `brush_smooth_sarah.mp4`

**Result:**
- ✅ Gemini detects "sarah"
- ✅ Finds ALL "sarah" videos (main + subfolders)
- ✅ Prioritizes consistency

---

## 🚀 Quick Start

1. **Update `drive_videos.json`:**

```json
{
  "Glow Coffee": {
    "videos": [
      {"id": "YOUR_ID", "name": "video.mp4"}
    ],
    "subfolders": {
      "Coffee Pouring": {
        "videos": [
          {"id": "YOUR_ID_2", "name": "pour.mp4"}
        ]
      }
    }
  }
}
```

2. **Restart server:**

```powershell
uvicorn main:app --reload
```

3. **Upload audio**

4. **Check logs** - you'll see:
   - Videos from main folders
   - Videos from subfolders
   - Nested structure in Gemini's prompt

---

## 📝 Notes

- ✅ Subfolders are **optional** - you can use flat structure
- ✅ Mix flat + nested as needed
- ✅ No limit on subfolder count
- ✅ Subfolder names help Gemini understand context
- ✅ All videos (main + subfolders) go to Gemini

---

## 🔍 Example: Complete Structure

```json
{
  "Glow Coffee": {
    "videos": [
      {"id": "main_1", "name": "coffee_product.mp4"}
    ],
    "subfolders": {
      "Pouring": {
        "videos": [
          {"id": "pour_1", "name": "pour_slow.mp4"},
          {"id": "pour_2", "name": "pour_fast.mp4"}
        ]
      },
      "Drinking": {
        "videos": [
          {"id": "drink_1", "name": "woman_sarah.mp4"}
        ]
      },
      "Product Shots": {
        "videos": [
          {"id": "prod_1", "name": "package_closeup.mp4"}
        ]
      }
    }
  },
  "Hair": {
    "videos": [],
    "subfolders": {
      "Before After": {
        "videos": [
          {"id": "ba_1", "name": "transformation_sarah.mp4"}
        ]
      }
    }
  }
}
```

**Gemini sees:**

```
📁 Glow Coffee:
  - coffee_product.mp4
  📂 Pouring:
    - pour_slow.mp4
    - pour_fast.mp4
  📂 Drinking:
    - woman_sarah.mp4
  📂 Product Shots:
    - package_closeup.mp4

📁 Hair:
  📂 Before After:
    - transformation_sarah.mp4
```

**Gemini selects:**

```
FOLDER: Glow Coffee
VIDEO: pour_slow.mp4|pour_1
VIDEO: woman_sarah.mp4|drink_1

FOLDER: Hair
VIDEO: transformation_sarah.mp4|ba_1

ACTRESS: sarah
```

---

## ✅ Summary

**New Feature:** Nested folders (subfolders)!

**How to use:**
1. Add `"subfolders": {}` to your JSON
2. Put videos in subfolders
3. System automatically includes them in Gemini's selection

**Benefits:**
- Better organization
- Context-aware selection
- Same actress detection
- Clearer logs

**Your system now supports complex Drive structures!** 🎉

