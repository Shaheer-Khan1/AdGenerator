# 📋 Comprehensive Logging Guide

## Overview

Your video generator now has **detailed, structured logging** at every step! This makes debugging and understanding the process much easier.

---

## 🔍 What Gets Logged

### 1. **TRANSCRIPTION - Starting**
When audio file is uploaded:
```
📋 TRANSCRIPTION - Starting
  Audio File: your_audio.mp3
  Content Type: audio/mpeg
  File Size: 1234567 bytes
```

### 2. **TRANSCRIPTION - Audio Saved**
After saving to temp directory:
```
📋 TRANSCRIPTION - Audio Saved
  Temp ID: abc123-def456-...
  Audio Path: temp_videos/transcribe_abc123/audio.mp3
  File Size: 1234567 bytes
```

### 3. **WHISPER - Initializing**
Before transcription:
```
📋 WHISPER - Initializing
  Model: tiny (~75MB)
  FFmpeg Path: C:\...\ffmpeg.exe
```

### 4. **WHISPER - Transcribing**
During transcription:
```
📋 WHISPER - Transcribing
  Audio File: your_audio.mp3
  Status: Processing...
```

### 5. **WHISPER - Transcription Complete**
After transcription:
```
📋 WHISPER - Transcription Complete
  Full Transcription: "Your complete transcribed text here..."
  Length: 245 characters
  Word Count: 42 words
  Detected Language: en
```

### 6. **GOOGLE DRIVE - Scanning Folder Structure**
When checking Drive folders:
```
📋 GOOGLE DRIVE - Scanning Folder Structure
  Folder ID: 1l_vWG07Q3tN1UChnlyR40_dZ3McO9NfB
  Folder URL: https://drive.google.com/drive/folders/...
  Method: Hardcoded structure (API requires auth)
```

### 7. **GOOGLE DRIVE - Found Folders**
Available folders:
```
📋 GOOGLE DRIVE - Found Folders
  Total Folders: 9
  Folder Names:
    [1] Cellulite
    [2] Glow Coffee
    [3] Hair
    ...
  Note: Video lists empty - using folder names for category matching
```

### 8. **GEMINI AI - Initializing**
Before sending to Gemini:
```
📋 GEMINI AI - Initializing
  Model: gemini-2.5-flash
  API Key: AIzaSyDYYbbXiakOEO...fdk
  Purpose: Analyze transcription and select best folder category
```

### 9. **GEMINI AI - Sending Request**
What we send to Gemini:
```
📋 GEMINI AI - Sending Request
  Transcription Length: 245 characters
  Transcription Preview: "Your transcription text here..."
  Available Folders:
    [1] Cellulite
    [2] Glow Coffee
    ...
  Prompt Length: 523 characters
  Full Prompt: [Complete prompt sent to Gemini]
```

### 10. **GEMINI AI - Received Response**
Gemini's raw response:
```
📋 GEMINI AI - Received Response
  Raw Response: "Glow Coffee"
  Response Length: 10 characters
```

### 11. **GEMINI AI - Final Selection**
After processing:
```
📋 GEMINI AI - Final Selection
  Selected Folder: Glow Coffee
  Is Valid: True
  Raw Response: "Glow Coffee"
```

### 12. **TRANSCRIPTION - Final Result**
Complete transcription result:
```
📋 TRANSCRIPTION - Final Result
  Success: True
  Transcription: "Your full transcription..."
  Language: en
  Suggested Folder: Glow Coffee
  Next Step: Will use Pexels with themed search based on folder
```

### 13. **VIDEO GENERATION - Starting with Upload**
When video generation starts:
```
📋 VIDEO GENERATION - Starting with Upload
  Task ID: xyz789-abc123-...
  Audio File: your_audio.mp3
  Audio Size: 1234567 bytes
  Suggested Folder: Glow Coffee
  Mapped Search Query: coffee beauty skin glow
  Folder Mapping: {Complete mapping dictionary}
  Script Text: "Your script text..."
```

### 14. **PEXELS - Searching Videos**
Before searching Pexels:
```
📋 PEXELS - Searching Videos
  Query: coffee beauty skin glow
  Requested Clips: 5
  API Endpoint: https://api.pexels.com/videos/search
  API Key: your_key_here...
```

### 15. **PEXELS - API Response**
Pexels API response:
```
📋 PEXELS - API Response
  Status Code: 200
  Total Results: 150
  Page: 1
  Per Page: 5
  Videos Found: 5
```

### 16. **PEXELS - Video [N]**
Each video found:
```
📋 PEXELS - Video 1
  Video ID: 1234567
  Duration: 15 seconds
  URL: https://videos.pexels.com/video-files/...
  Quality: hd
```

### 17. **PEXELS - Final Selection**
All videos selected:
```
📋 PEXELS - Final Selection
  Total Videos Selected: 5
  Video URLs: [List of all URLs]
```

---

## 📊 Log Format

All logs follow this format:

```
================================================================================
📋 [SECTION] - [Action]
================================================================================
  Key: Value
  Key: Value
  ...
================================================================================
```

**Features:**
- ✅ Clear section headers
- ✅ Structured key-value pairs
- ✅ Long strings truncated (200 chars)
- ✅ Nested data supported
- ✅ Easy to scan visually

---

## 🎯 Example Full Flow

Here's what you'll see for a complete video generation:

```
================================================================================
📋 TRANSCRIPTION - Starting
================================================================================
  Audio File: glow_coffee_script.mp3
  Content Type: audio/mpeg
  File Size: 2345678 bytes
================================================================================

================================================================================
📋 TRANSCRIPTION - Audio Saved
================================================================================
  Temp ID: abc-123-def-456
  Audio Path: temp_videos/transcribe_abc-123/audio.mp3
  File Size: 2345678 bytes
================================================================================

================================================================================
📋 WHISPER - Initializing
================================================================================
  Model: tiny (~75MB)
  FFmpeg Path: C:\...\ffmpeg.exe
================================================================================

================================================================================
📋 WHISPER - Transcription Complete
================================================================================
  Full Transcription: "Transform your skin with every sip! Our Glow Coffee..."
  Length: 156 characters
  Word Count: 24 words
  Detected Language: en
================================================================================

================================================================================
📋 GOOGLE DRIVE - Scanning Folder Structure
================================================================================
  Folder ID: 1l_vWG07Q3tN1UChnlyR40_dZ3McO9NfB
  Folder URL: https://drive.google.com/drive/folders/...
  Method: Hardcoded structure (API requires auth)
================================================================================

================================================================================
📋 GOOGLE DRIVE - Found Folders
================================================================================
  Total Folders: 9
  Folder Names:
    [1] Cellulite
    [2] Glow Coffee
    [3] Hair
    ...
================================================================================

================================================================================
📋 GEMINI AI - Sending Request
================================================================================
  Transcription Length: 156 characters
  Transcription Preview: "Transform your skin with every sip! Our Glow Coffee..."
  Available Folders:
    [1] Cellulite
    [2] Glow Coffee
    ...
  Full Prompt: [Complete prompt]
================================================================================

================================================================================
📋 GEMINI AI - Final Selection
================================================================================
  Selected Folder: Glow Coffee
  Is Valid: True
  Raw Response: "Glow Coffee"
================================================================================

================================================================================
📋 VIDEO GENERATION - Starting with Upload
================================================================================
  Task ID: xyz-789-abc-123
  Suggested Folder: Glow Coffee
  Mapped Search Query: coffee beauty skin glow
  Folder Mapping: {...}
================================================================================

================================================================================
📋 PEXELS - Searching Videos
================================================================================
  Query: coffee beauty skin glow
  Requested Clips: 5
  API Endpoint: https://api.pexels.com/videos/search
================================================================================

================================================================================
📋 PEXELS - Final Selection
================================================================================
  Total Videos Selected: 5
  Video URLs: [5 URLs]
================================================================================
```

---

## 🔧 How to Use Logs

### Debugging Issues

**Problem:** Wrong folder selected?
- Check `GEMINI AI - Sending Request` → See what transcription was sent
- Check `GEMINI AI - Received Response` → See Gemini's raw answer
- Check `GEMINI AI - Final Selection` → See if validation worked

**Problem:** No videos found?
- Check `PEXELS - API Response` → See if API returned results
- Check `PEXELS - Searching Videos` → Verify search query is correct

**Problem:** Transcription wrong?
- Check `WHISPER - Transcription Complete` → See full transcription
- Check `WHISPER - Initializing` → Verify FFmpeg path is correct

### Understanding Flow

Follow the logs in order to see:
1. Audio uploaded → Saved
2. Whisper transcribes → Result
3. Drive folders loaded → Structure
4. Gemini analyzes → Folder selected
5. Search query mapped → Pexels query
6. Videos found → URLs returned

---

## 📝 Log Locations

**Console Output:**
- All logs print to terminal/console
- Visible when running `uvicorn main:app --reload`

**Task Progress:**
- Key steps also logged to task progress
- Visible via `/task-status/{task_id}` endpoint

---

## 🎨 Log Sections

| Section | Purpose | When It Appears |
|---------|---------|-----------------|
| `TRANSCRIPTION` | Audio upload & processing | On `/transcribe-audio` |
| `WHISPER` | Speech-to-text | During transcription |
| `GOOGLE DRIVE` | Folder structure | When loading Drive |
| `GEMINI AI` | AI analysis | When selecting folder |
| `VIDEO GENERATION` | Video creation | On `/generate-video-upload` |
| `PEXELS` | Video search | When fetching clips |

---

## 💡 Tips

### Filter Logs

In terminal, you can filter:
```bash
# See only Gemini logs
uvicorn main:app --reload | grep "GEMINI"

# See only Drive logs
uvicorn main:app --reload | grep "DRIVE"

# See only errors
uvicorn main:app --reload | grep "Error"
```

### Save Logs to File

```bash
# Save all logs
uvicorn main:app --reload > logs.txt 2>&1

# Save and view at same time
uvicorn main:app --reload | tee logs.txt
```

---

## ✅ Summary

**What You Get:**
- ✅ Clear, structured logs at every step
- ✅ See exactly what's sent to Gemini
- ✅ See exactly what Drive finds
- ✅ See exactly what Pexels returns
- ✅ Easy debugging and troubleshooting
- ✅ Full transparency of the process

**Now you can:**
- 🔍 Debug issues easily
- 📊 Understand the flow
- 🐛 Find problems quickly
- ✅ Verify everything works correctly

**Your logs are now comprehensive and clear!** 🎉

