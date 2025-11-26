# 🎯 Multi-Folder Selection with Video Descriptions

## Overview

Gemini now suggests **2-3 folders** with **specific video descriptions** for each folder! This gives you much better control and more relevant video selection.

---

## ✨ What Changed

### Before:
- ❌ Gemini selected only **1 folder**
- ❌ No video descriptions
- ❌ Generic search queries

### After:
- ✅ Gemini selects **2-3 folders**
- ✅ Provides **video descriptions** for each folder
- ✅ Combines multiple themed searches
- ✅ Better relevance and variety

---

## 🔄 How It Works

### Step-by-Step Flow

```
1. Upload Audio File
   ↓
2. Whisper Transcribes
   ↓
3. Gemini Analyzes Transcription
   ↓
4. Gemini Selects 2-3 Folders:
   - Folder 1: "Glow Coffee"
     Videos: "Coffee being poured", "Person applying skincare"
   - Folder 2: "Product"
     Videos: "Product packaging", "Before/after comparison"
   - Folder 3: "Hair"
     Videos: "Shiny hair close-up"
   ↓
5. System Maps Folders to Pexels Queries
   ↓
6. Combines Queries for Video Search
   ↓
7. Generates Video with Mixed Footage
```

---

## 📋 Gemini Response Format

### What Gemini Returns:

```json
{
  "folders": [
    {
      "name": "Glow Coffee",
      "videos": [
        "Coffee being poured into cup",
        "Person applying coffee-based skincare product"
      ]
    },
    {
      "name": "Product",
      "videos": [
        "Product packaging close-up",
        "Before/after skin comparison"
      ]
    },
    {
      "name": "Hair",
      "videos": [
        "Shiny healthy hair close-up"
      ]
    }
  ],
  "raw_response": "FOLDER: Glow Coffee\nVIDEOS: ..."
}
```

---

## 🎬 Example Scenarios

### Scenario 1: Coffee Beauty Product

**Transcription:**
> "Transform your skin with every sip! Our Glow Coffee blend is packed with collagen and antioxidants for radiant, glowing skin."

**Gemini Selects:**
1. **Glow Coffee** - Coffee being poured, Coffee skincare application
2. **Product** - Product packaging, Before/after skin
3. **Hair** - (if mentions hair benefits)

**Pexels Searches:**
- Primary: "coffee beauty skin glow"
- Secondary: "beauty product cosmetics"
- Tertiary: "hair care beautiful"

---

### Scenario 2: Anti-Aging Product

**Transcription:**
> "Say goodbye to wrinkles! Our revolutionary serum reduces fine lines and restores youthful skin in just 30 days."

**Gemini Selects:**
1. **Wrinkles** - Wrinkle reduction, Smooth skin close-up
2. **Product** - Serum application, Product bottle
3. **Others** - General beauty/wellness

**Pexels Searches:**
- Primary: "anti aging wrinkles skincare"
- Secondary: "beauty product cosmetics"
- Tertiary: "beauty wellness"

---

### Scenario 3: Hair Care

**Transcription:**
> "Beautiful hair starts from within! Our new formula strengthens hair from root to tip, giving you silky smooth locks."

**Gemini Selects:**
1. **Hair** - Hair being brushed, Shiny hair close-up
2. **Product** - Hair product bottle, Application
3. **Others** - General beauty

**Pexels Searches:**
- Primary: "hair care beautiful"
- Secondary: "beauty product cosmetics"
- Tertiary: "beauty wellness"

---

## 📊 Logging Output

### What You'll See in Logs:

```
================================================================================
📋 GEMINI AI - Final Selection
================================================================================
  Selected Folders:
    [1] Glow Coffee
    [2] Product
    [3] Hair
  Total Folders: 3
  Video Descriptions:
    Glow Coffee:
      [1] Coffee being poured into cup
      [2] Person applying coffee-based skincare product
    Product:
      [1] Product packaging close-up
      [2] Before/after skin comparison
    Hair:
      [1] Shiny healthy hair close-up
  Raw Response: [Full Gemini response]
================================================================================

================================================================================
📋 VIDEO GENERATION - Starting with Upload
================================================================================
  Selected Folders:
    [1] Glow Coffee
    [2] Product
    [3] Hair
  Folder Count: 3
  Video Descriptions:
    Glow Coffee: [Coffee being poured, Person applying skincare]
    Product: [Product packaging, Before/after comparison]
    Hair: [Shiny hair close-up]
  Primary Search Query: coffee beauty skin glow
  All Search Queries:
    [1] coffee beauty skin glow
    [2] beauty product cosmetics
    [3] hair care beautiful
================================================================================
```

---

## 🎨 UI Display

### Folder Selection Box Shows:

```
📁 3 folders selected:
1. Glow Coffee (Coffee being poured, Person applying skincare)
2. Product (Product packaging, Before/after comparison)
3. Hair (Shiny hair close-up)
```

**Features:**
- ✅ Shows all selected folders
- ✅ Displays video descriptions for each
- ✅ Numbered list format
- ✅ Easy to read

---

## 🔧 Technical Details

### Backend Changes:

1. **New Function:** `get_folders_and_videos_from_gemini()`
   - Returns 2-3 folders with video descriptions
   - Parses Gemini's structured response
   - Validates folder names

2. **Updated Endpoint:** `/transcribe-audio`
   - Returns `suggested_folders` array
   - Includes `primary_folder` for backward compatibility
   - Provides video descriptions

3. **Updated Endpoint:** `/generate-video-upload`
   - Accepts `suggested_folders` as JSON string
   - Combines multiple search queries
   - Uses primary folder for main search

### Frontend Changes:

1. **Stores Multiple Folders:**
   ```javascript
   let selectedFolders = []; // Array of folder objects
   ```

2. **Displays All Folders:**
   - Shows folder names
   - Shows video descriptions
   - Formatted list

3. **Sends JSON:**
   ```javascript
   formData.append('suggested_folders', JSON.stringify(selectedFolders));
   ```

---

## 📈 Benefits

### 1. **Better Relevance**
- Multiple folders = more context
- Video descriptions guide selection
- More accurate matching

### 2. **More Variety**
- Videos from different categories
- Mix of product shots and lifestyle
- Richer visual content

### 3. **Smarter Selection**
- Gemini considers multiple angles
- Primary + secondary topics
- Better overall match

### 4. **Future-Ready**
- Video descriptions ready for Drive integration
- Can map to actual Drive videos later
- Easy to extend

---

## 🚀 Usage

### Step 1: Upload Audio
```
Upload your voiceover file
```

### Step 2: See Gemini's Selection
```
📁 3 folders selected:
1. Glow Coffee (Coffee being poured, Skincare application)
2. Product (Product packaging, Before/after)
3. Hair (Shiny hair close-up)
```

### Step 3: Generate Video
```
System combines all folders
Searches Pexels with multiple queries
Creates video with mixed footage
```

---

## 🔮 Future Enhancements

### When Drive Integration is Complete:

1. **Use Video Descriptions:**
   - Match descriptions to actual Drive videos
   - Select specific videos by name
   - Download exact matches

2. **Multi-Folder Downloads:**
   - Download from multiple Drive folders
   - Mix footage from different categories
   - Create richer videos

3. **Smart Mixing:**
   - Weight folders by relevance
   - More videos from primary folder
   - Fewer from secondary folders

---

## 📝 Example Logs

### Complete Flow:

```
[TRANSCRIPTION] Audio uploaded: glow_coffee.mp3
[WHISPER] Transcribing...
[WHISPER] Transcription: "Transform your skin with every sip..."
[GEMINI] Analyzing transcription...
[GEMINI] Selected 3 folders:
  - Glow Coffee (Coffee pour, Skincare)
  - Product (Packaging, Before/after)
  - Hair (Shiny hair)
[VIDEO GENERATION] Starting with 3 folders
[PEXELS] Searching: "coffee beauty skin glow"
[PEXELS] Found 5 videos
[VIDEO] Generating final video...
[COMPLETE] Video ready!
```

---

## ✅ Summary

**What You Get:**
- ✅ 2-3 folders selected by Gemini
- ✅ Video descriptions for each folder
- ✅ Combined Pexels searches
- ✅ Better relevance and variety
- ✅ Ready for Drive integration

**What's Logged:**
- ✅ All selected folders
- ✅ Video descriptions
- ✅ Search queries used
- ✅ Complete flow tracking

**Your system is now smarter and more flexible!** 🎉

