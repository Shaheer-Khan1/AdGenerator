"""
AI Video Generator API - Complete Google Drive Scraper
Scrapes ALL folders and subfolders from public Google Drive
No authentication needed for public folders
"""

import os
import requests
import json
import subprocess
import uuid
import shutil
import gc
import re
import math
import random
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Set
from pathlib import Path
import asyncio
import time
import html
from urllib.parse import unquote, urlparse, parse_qs
import concurrent.futures

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from dotenv import load_dotenv
load_dotenv()

# === CONFIGURATION ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "1l_vWG07Q3tN1UChnlyR40_dZ3McO9NfB")

# Memory-optimized settings
VIDEO_WIDTH = 720
VIDEO_HEIGHT = 1280
MAX_CONCURRENT_TASKS = 2
CLIP_DURATION = 3.0  # Video changes every 3 seconds

# Create directories
TEMP_DIR = Path("temp_videos")
OUTPUT_DIR = Path("output_videos")
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# === FASTAPI APP ===
app = FastAPI(
    title="AI Video Generator API - Complete Drive Scraper",
    description="Generate videos from audio + ALL footage from Google Drive",
    version="4.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === GLOBAL STATE ===
tasks: Dict[str, Dict[str, Any]] = {}
active_tasks = 0

# === UTILITY FUNCTIONS ===
def free_memory():
    """Aggressive garbage collection"""
    gc.collect()
    gc.collect()

def log_task(task_id: str, message: str):
    """Log task progress"""
    print(f"[{task_id}] {message}")
    if task_id in tasks:
        tasks[task_id]['progress'] = message

def get_audio_duration(audio_path: str) -> float:
    """Get audio duration using FFmpeg"""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [exe, "-i", audio_path]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        
        match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
        if not match:
            return 30.0
        
        h, m, s = map(float, match.groups())
        return h * 3600 + m * 60 + s
    except Exception as e:
        print(f"Error getting audio duration: {e}")
        return 30.0

def get_video_duration(video_path: str) -> float:
    """Get video duration using FFmpeg"""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [exe, "-i", video_path]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        
        match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
        if not match:
            return 10.0
        
        h, m, s = map(float, match.groups())
        return h * 3600 + m * 60 + s
    except Exception as e:
        print(f"Error getting video duration: {e}")
        return 10.0

# === ADVANCED DRIVE SCRAPER ===
class GoogleDriveScraper:
    """Advanced scraper for public Google Drive folders with unlimited depth"""
    
    def __init__(self, folder_id: str):
        self.folder_id = folder_id
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Cache to avoid re-scraping
        self.scraped_folders: Set[str] = set()
        self.all_items: Dict[str, List[Dict]] = {}
        
    def extract_folder_data(self, html_content: str, folder_id: str) -> Dict[str, Any]:
        """Extract folder data from Google Drive HTML"""
        items = {
            'folders': [],
            'videos': [],
            'files': []
        }
        
        try:
            # Method 1: Look for Google Drive's JSON data
            # Google Drive embeds data in window['_DRIVE_ivd'] or similar
            json_patterns = [
                r'window\["_DRIVE_ivd"\]\s*=\s*(\{.*?\});',
                r'var _DRIVE_ivd\s*=\s*(\{.*?\});',
                r'window\._DRIVE_ivd\s*=\s*(\{.*?\});',
                r'\["docs-dialog-host"\]\s*,\s*"(\{.*?\})"',
                r'\["docs-dialog-host"\]\s*,\s*(\{.*?\})',
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, html_content, re.DOTALL)
                for match in matches:
                    try:
                        data = json.loads(match)
                        # Try to extract items from different JSON structures
                        items.update(self._parse_drive_json(data, folder_id))
                    except:
                        pass
            
            # Method 2: Direct HTML parsing for file links
            self._parse_html_links(html_content, items, folder_id)
            
            # Method 3: Look for data-id attributes
            data_id_matches = re.findall(r'data-id="([a-zA-Z0-9_-]{25,})"', html_content)
            for data_id in data_id_matches:
                # Check if it's likely a file or folder
                context = html_content[max(0, html_content.find(data_id)-200):html_content.find(data_id)+200]
                if '/folders/' in context:
                    items['folders'].append({
                        'id': data_id,
                        'name': self._extract_name_from_context(context, data_id) or f"Folder_{data_id[:8]}",
                        'type': 'folder'
                    })
                elif 'video' in context.lower() or any(ext in context.lower() for ext in ['.mp4', '.mov', '.avi']):
                    items['videos'].append({
                        'id': data_id,
                        'name': self._extract_name_from_context(context, data_id) or f"Video_{data_id[:8]}",
                        'type': 'video'
                    })
            
            # Method 4: Look for Google Drive's grid items
            grid_items = re.findall(r'<div[^>]*data-id="([^"]+)"[^>]*>.*?<div[^>]*aria-label="([^"]+)"', 
                                   html_content, re.DOTALL)
            for item_id, item_name in grid_items:
                item_name = unquote(item_name).strip()
                if not item_id or not item_name:
                    continue
                
                if 'folder' in item_name.lower() or '/folders/' in html_content[html_content.find(item_id)-100:html_content.find(item_id)+100]:
                    items['folders'].append({
                        'id': item_id,
                        'name': item_name,
                        'type': 'folder'
                    })
                elif any(ext in item_name.lower() for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']):
                    items['videos'].append({
                        'id': item_id,
                        'name': item_name,
                        'type': 'video'
                    })
                else:
                    items['files'].append({
                        'id': item_id,
                        'name': item_name,
                        'type': 'file'
                    })
            
        except Exception as e:
            print(f"Error extracting folder data: {e}")
        
        return items
    
    def _parse_drive_json(self, data: Dict, folder_id: str) -> Dict[str, Any]:
        """Parse Google Drive JSON structure"""
        items = {
            'folders': [],
            'videos': [],
            'files': []
        }
        
        def extract_from_nested(obj, path=""):
            if isinstance(obj, dict):
                # Look for folder/file data
                if 'id' in obj and 'name' in obj:
                    item_id = obj.get('id', '')
                    item_name = obj.get('name', '')
                    mime_type = obj.get('mimeType', '')
                    
                    if mime_type == 'application/vnd.google-apps.folder':
                        items['folders'].append({
                            'id': item_id,
                            'name': item_name,
                            'type': 'folder',
                            'mimeType': mime_type
                        })
                    elif 'video' in mime_type:
                        items['videos'].append({
                            'id': item_id,
                            'name': item_name,
                            'type': 'video',
                            'mimeType': mime_type
                        })
                    else:
                        items['files'].append({
                            'id': item_id,
                            'name': item_name,
                            'type': 'file',
                            'mimeType': mime_type
                        })
                
                # Recurse through all values
                for key, value in obj.items():
                    extract_from_nested(value, f"{path}.{key}")
            
            elif isinstance(obj, list):
                for item in obj:
                    extract_from_nested(item, path)
        
        extract_from_nested(data)
        return items
    
    def _parse_html_links(self, html_content: str, items: Dict[str, Any], folder_id: str):
        """Parse direct HTML links for files and folders"""
        # Folder links
        folder_links = re.findall(r'href="[^"]*/folders/([a-zA-Z0-9_-]{25,})[^"]*"[^>]*>([^<]+)</a>', html_content)
        for folder_id, folder_name in folder_links:
            folder_name = unquote(folder_name).strip()
            if folder_name and folder_id:
                items['folders'].append({
                    'id': folder_id,
                    'name': folder_name,
                    'type': 'folder'
                })
        
        # File links (including videos)
        file_links = re.findall(r'href="[^"]*/file/d/([a-zA-Z0-9_-]{25,})[^"]*"[^>]*>([^<]+)</a>', html_content)
        for file_id, file_name in file_links:
            file_name = unquote(file_name).strip()
            if file_name and file_id:
                if any(ext in file_name.lower() for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.wmv', '.flv']):
                    items['videos'].append({
                        'id': file_id,
                        'name': file_name,
                        'type': 'video'
                    })
                else:
                    items['files'].append({
                        'id': file_id,
                        'name': file_name,
                        'type': 'file'
                    })
    
    def _extract_name_from_context(self, context: str, item_id: str) -> str:
        """Extract item name from surrounding HTML context"""
        # Look for aria-label
        aria_match = re.search(r'aria-label="([^"]+)"', context)
        if aria_match:
            return unquote(aria_match.group(1)).strip()
        
        # Look for title attribute
        title_match = re.search(r'title="([^"]+)"', context)
        if title_match:
            return unquote(title_match.group(1)).strip()
        
        # Look for text content
        text_match = re.search(r'>([^<>]{5,100})<', context)
        if text_match:
            return unquote(text_match.group(1)).strip()
        
        return ""
    
    def scrape_folder(self, folder_id: str, current_path: str = "", max_depth: int = 10, 
                     current_depth: int = 0) -> Dict[str, Any]:
        """Recursively scrape a folder and all subfolders"""
        if folder_id in self.scraped_folders or current_depth > max_depth:
            return {}
        
        self.scraped_folders.add(folder_id)
        
        folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
        print(f"Scraping folder (depth {current_depth}): {folder_id}")
        
        try:
            response = self.session.get(folder_url, timeout=30)
            response.raise_for_status()
            html_content = response.text
            
            # Extract items from this folder
            items = self.extract_folder_data(html_content, folder_id)
            
            # Get folder name
            folder_name = "Root"
            if items.get('folders') or items.get('videos') or items.get('files'):
                # Try to get folder name from title
                title_match = re.search(r'<title>([^<]+)</title>', html_content)
                if title_match:
                    folder_name = unquote(title_match.group(1)).replace(' - Google Drive', '').strip()
            
            folder_structure = {
                'id': folder_id,
                'name': folder_name,
                'path': current_path,
                'url': folder_url,
                'folders': {},
                'videos': [],
                'files': [],
                'total_items': 0
            }
            
            # Process videos
            for video in items.get('videos', []):
                video_id = video.get('id', '')
                video_name = video.get('name', f"Video_{video_id[:8]}")
                
                # Get download URL
                download_url = f"https://drive.google.com/uc?export=download&id={video_id}"
                
                folder_structure['videos'].append({
                    'id': video_id,
                    'name': video_name,
                    'download_url': download_url,
                    'view_url': f"https://drive.google.com/file/d/{video_id}/view",
                    'folder_path': current_path,
                    'folder_name': folder_name,
                    'type': 'video'
                })
            
            # Process files
            for file in items.get('files', []):
                file_id = file.get('id', '')
                file_name = file.get('name', f"File_{file_id[:8]}")
                
                folder_structure['files'].append({
                    'id': file_id,
                    'name': file_name,
                    'download_url': f"https://drive.google.com/uc?export=download&id={file_id}",
                    'folder_path': current_path,
                    'folder_name': folder_name,
                    'type': 'file'
                })
            
            # Recursively scrape subfolders
            subfolders = items.get('folders', [])
            print(f"Found {len(subfolders)} subfolders in {folder_name}")
            
            for folder in subfolders:
                subfolder_id = folder.get('id', '')
                subfolder_name = folder.get('name', f"Folder_{subfolder_id[:8]}")
                
                if subfolder_id and subfolder_id != folder_id:  # Avoid infinite recursion
                    new_path = f"{current_path}/{subfolder_name}" if current_path else subfolder_name
                    
                    # Scrape subfolder
                    subfolder_structure = self.scrape_folder(
                        subfolder_id, 
                        new_path, 
                        max_depth, 
                        current_depth + 1
                    )
                    
                    if subfolder_structure:
                        folder_structure['folders'][subfolder_name] = subfolder_structure
            
            # Calculate totals
            folder_structure['total_items'] = (
                len(folder_structure['videos']) + 
                len(folder_structure['files']) +
                sum(f['total_items'] for f in folder_structure['folders'].values())
            )
            
            return folder_structure
            
        except Exception as e:
            print(f"Error scraping folder {folder_id}: {e}")
            return {}
    
    def get_all_videos(self, structure: Dict) -> List[Dict]:
        """Extract ALL videos from the folder structure"""
        videos = []
        
        def extract_videos(node: Dict, current_path: str = ""):
            # Add videos from this folder
            videos.extend(node.get('videos', []))
            
            # Process subfolders
            for folder_name, subfolder in node.get('folders', {}).items():
                new_path = f"{current_path}/{folder_name}" if current_path else folder_name
                extract_videos(subfolder, new_path)
        
        extract_videos(structure)
        return videos
    
    def get_folder_summary(self, structure: Dict) -> Dict[str, Any]:
        """Get summary of all folders and videos"""
        summary = {
            'total_folders': 0,
            'total_videos': 0,
            'total_files': 0,
            'folders_by_depth': {},
            'video_formats': {},
            'largest_folders': []
        }
        
        def analyze_node(node: Dict, depth: int = 0):
            # Update depth count
            if depth not in summary['folders_by_depth']:
                summary['folders_by_depth'][depth] = 0
            summary['folders_by_depth'][depth] += 1
            
            # Count videos in this folder
            video_count = len(node.get('videos', []))
            summary['total_videos'] += video_count
            summary['total_files'] += len(node.get('files', []))
            summary['total_folders'] += 1
            
            # Track video formats
            for video in node.get('videos', []):
                video_name = video.get('name', '').lower()
                for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.wmv', '.flv']:
                    if ext in video_name:
                        if ext not in summary['video_formats']:
                            summary['video_formats'][ext] = 0
                        summary['video_formats'][ext] += 1
                        break
            
            # Track subfolders
            for subfolder in node.get('folders', {}).values():
                analyze_node(subfolder, depth + 1)
        
        analyze_node(structure)
        
        # Find folders with most videos
        def find_largest_folders(node: Dict, path: str = ""):
            video_count = len(node.get('videos', []))
            if video_count > 0:
                summary['largest_folders'].append({
                    'name': node.get('name', 'Unnamed'),
                    'path': path,
                    'video_count': video_count,
                    'total_items': node.get('total_items', 0)
                })
            
            for folder_name, subfolder in node.get('folders', {}).items():
                new_path = f"{path}/{folder_name}" if path else folder_name
                find_largest_folders(subfolder, new_path)
        
        find_largest_folders(structure)
        summary['largest_folders'].sort(key=lambda x: x['video_count'], reverse=True)
        
        return summary

# === STEP 1: TRANSCRIBE AUDIO ===
async def transcribe_audio_with_whisper(audio_path: str) -> Tuple[str, float]:
    """Transcribe audio using Whisper and return transcription + duration"""
    try:
        import whisper
        import imageio_ffmpeg
        
        log_task("transcribe", "Loading Whisper model...")
        
        # Patch Whisper to use bundled FFmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        original_run = whisper.audio.run
        
        def patched_run(cmd, *args, **kwargs):
            if isinstance(cmd, list) and len(cmd) > 0 and cmd[0] == 'ffmpeg':
                cmd = [ffmpeg_exe] + cmd[1:]
            return original_run(cmd, *args, **kwargs)
        
        whisper.audio.run = patched_run
        
        # Load model (tiny for speed, base for better accuracy)
        model = whisper.load_model("base")
        
        # Transcribe
        log_task("transcribe", "Transcribing audio...")
        result = model.transcribe(
            str(audio_path),
            fp16=False,
            language=None
        )
        
        transcription = result["text"].strip()
        audio_duration = get_audio_duration(audio_path)
        
        # Clean up
        del model
        whisper.audio.run = original_run
        free_memory()
        
        log_task("transcribe", f"Transcribed {len(transcription)} chars, duration: {audio_duration:.1f}s")
        return transcription, audio_duration
        
    except ImportError:
        raise Exception("Whisper not installed. Run: pip install openai-whisper")
    except Exception as e:
        raise Exception(f"Transcription failed: {str(e)}")

# === STEP 2: COMPLETE DRIVE SCRAPING ===
def scrape_complete_drive_structure(folder_id: str = None) -> Dict[str, Any]:
    """Scrape ALL folders and subfolders from Google Drive with unlimited depth"""
    folder_id = folder_id or GOOGLE_DRIVE_FOLDER_ID
    
    log_task("drive", f"🚀 Starting complete Drive scraping from folder: {folder_id}")
    log_task("drive", "This may take a while for large folders...")
    
    scraper = GoogleDriveScraper(folder_id)
    
    # Scrape with unlimited depth
    structure = scraper.scrape_folder(folder_id, max_depth=100)
    
    if not structure:
        raise Exception("Failed to scrape Drive folder. Make sure it's public and accessible.")
    
    # Get all videos
    all_videos = scraper.get_all_videos(structure)
    
    # Get summary
    summary = scraper.get_folder_summary(structure)
    
    log_task("drive", f"✅ Drive scraping complete!")
    log_task("drive", f"📊 Summary:")
    log_task("drive", f"  Total folders: {summary['total_folders']}")
    log_task("drive", f"  Total videos: {summary['total_videos']}")
    log_task("drive", f"  Total files: {summary['total_files']}")
    
    for depth, count in summary['folders_by_depth'].items():
        log_task("drive", f"  Depth {depth}: {count} folders")
    
    log_task("drive", f"  Video formats: {summary['video_formats']}")
    
    if summary['largest_folders']:
        log_task("drive", f"  Top 5 folders by video count:")
        for i, folder in enumerate(summary['largest_folders'][:5], 1):
            log_task("drive", f"    {i}. {folder['name']}: {folder['video_count']} videos")
    
    return {
        "root_structure": structure,
        "all_videos": all_videos,
        "summary": summary,
        "total_videos": len(all_videos),
        "scraped_at": datetime.now().isoformat()
    }

# === STEP 3: USE GEMINI TO SELECT VIDEOS ===
async def select_videos_with_gemini(
    transcription: str,
    audio_duration: float,
    drive_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Use Gemini to select exact videos based on script timing"""
    try:
        import google.generativeai as genai
        
        if not GEMINI_API_KEY:
            return select_videos_randomly(audio_duration, drive_data)
        
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Prepare video information
        all_videos = drive_data["all_videos"]
        
        if not all_videos:
            raise Exception("No videos found in Drive")
        
        # Group videos by folder path for better organization
        videos_by_folder = {}
        for video in all_videos:
            folder_path = video.get('folder_path', 'Root')
            if folder_path not in videos_by_folder:
                videos_by_folder[folder_path] = []
            videos_by_folder[folder_path].append(video)
        
        # Create a sample of videos for Gemini to consider
        video_samples = []
        for folder_path, videos in list(videos_by_folder.items())[:10]:  # Limit to 10 folders
            sample_videos = videos[:3]  # 3 videos per folder
            for video in sample_videos:
                video_samples.append({
                    'id': video['id'],
                    'name': video['name'],
                    'folder': folder_path,
                    'index': len(video_samples)  # Keep track of index
                })
        
        # Calculate clips needed
        num_clips_needed = int(math.ceil(audio_duration / CLIP_DURATION))
        
        prompt = f"""You are a professional video editor selecting footage from a massive video library.

AUDIO TRANSCRIPT:
"{transcription}"

AUDIO DURATION: {audio_duration:.1f} seconds
VIDEO REQUIREMENT: Show a different clip every {CLIP_DURATION} seconds
TOTAL CLIPS NEEDED: {num_clips_needed}

VIDEO LIBRARY INFORMATION:
Total videos available: {len(all_videos)}
Videos organized in folders by content type.

SAMPLE VIDEOS (representative of entire library):
{chr(10).join([f"{i+1}. {v['folder']}/: {v['name'][:50]}..." for i, v in enumerate(video_samples[:20])])}

INSTRUCTIONS:
1. Analyze the audio transcript carefully
2. Select videos that visually match the content
3. Provide variety - different angles, shots, scenes
4. Consider the folder paths as hints about content type
5. Each clip will be {CLIP_DURATION} seconds long
6. You need exactly {num_clips_needed} clips

RESPONSE FORMAT (must be valid JSON):
{{
  "selected_videos": [
    {{
      "video_index": 0,  // Index in the sample videos list (0-{len(video_samples)-1})
      "clip_start": 0.0,  // Start time in seconds (0-30)
      "reason": "Why this video fits the audio"
    }},
    // More clips...
  ],
  "total_clips": {num_clips_needed},
  "selection_strategy": "Brief description of your selection approach"
}}

IMPORTANT: 
- video_index must be between 0 and {len(video_samples)-1}
- Return ONLY the JSON, no other text"""

        log_task("gemini", f"Selecting {num_clips_needed} clips from {len(all_videos)} videos...")
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Parse JSON response
        try:
            # Extract JSON
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx == -1 or end_idx <= start_idx:
                raise ValueError("No JSON found")
            
            json_str = response_text[start_idx:end_idx]
            result = json.loads(json_str)
            
            # Map selected videos to actual video data
            selected_clips = []
            clip_sequence = []
            
            for i, selection in enumerate(result.get("selected_videos", [])):
                video_index = selection.get("video_index", i % len(video_samples))
                
                if 0 <= video_index < len(video_samples):
                    sample_video = video_samples[video_index]
                    
                    # Find the actual video in the full list
                    actual_video = None
                    for video in all_videos:
                        if video['id'] == sample_video['id']:
                            actual_video = video
                            break
                    
                    if actual_video:
                        selected_clips.append({
                            **actual_video,
                            "clip_start": selection.get("clip_start", random.uniform(0, 10)),
                            "clip_duration": CLIP_DURATION,
                            "selection_reason": selection.get("reason", "")
                        })
                        
                        clip_sequence.append({
                            "clip_index": i,
                            "start_time": i * CLIP_DURATION,
                            "end_time": (i + 1) * CLIP_DURATION
                        })
            
            # Fill remaining slots if needed
            while len(selected_clips) < num_clips_needed:
                random_video = random.choice(all_videos)
                selected_clips.append({
                    **random_video,
                    "clip_start": random.uniform(0, 10),
                    "clip_duration": CLIP_DURATION,
                    "selection_reason": "Random selection to fill quota"
                })
                
                clip_sequence.append({
                    "clip_index": len(selected_clips) - 1,
                    "start_time": (len(selected_clips) - 1) * CLIP_DURATION,
                    "end_time": len(selected_clips) * CLIP_DURATION
                })
            
            # Limit to exactly what we need
            selected_clips = selected_clips[:num_clips_needed]
            clip_sequence = clip_sequence[:num_clips_needed]
            
            final_result = {
                "selected_videos": selected_clips,
                "clip_sequence": clip_sequence,
                "total_clips": len(selected_clips),
                "total_duration": len(selected_clips) * CLIP_DURATION,
                "selection_strategy": result.get("selection_strategy", ""),
                "gemini_used": True
            }
            
            log_task("gemini", f"✅ Selected {len(selected_clips)} videos")
            return final_result
            
        except json.JSONDecodeError as e:
            log_task("gemini", "Gemini response not valid JSON, using random selection")
            return select_videos_randomly(audio_duration, drive_data)
        
    except Exception as e:
        log_task("gemini", f"Gemini failed: {str(e)}, using random selection")
        return select_videos_randomly(audio_duration, drive_data)

def select_videos_randomly(audio_duration: float, drive_data: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback random selection"""
    all_videos = drive_data["all_videos"]
    
    if not all_videos:
        raise Exception("No videos found in Drive")
    
    num_clips_needed = int(math.ceil(audio_duration / CLIP_DURATION))
    
    # Select random videos
    selected_videos = random.sample(
        all_videos, 
        min(num_clips_needed, len(all_videos))
    )
    
    # Fill remaining slots if needed
    while len(selected_videos) < num_clips_needed:
        selected_videos.append(random.choice(all_videos))
    
    selected_videos = selected_videos[:num_clips_needed]
    
    # Prepare clips
    selected_clips = []
    clip_sequence = []
    
    for i, video in enumerate(selected_videos):
        selected_clips.append({
            **video,
            "clip_start": random.uniform(0, 10),
            "clip_duration": CLIP_DURATION,
            "selection_reason": "Random selection"
        })
        
        clip_sequence.append({
            "clip_index": i,
            "start_time": i * CLIP_DURATION,
            "end_time": (i + 1) * CLIP_DURATION
        })
    
    return {
        "selected_videos": selected_clips,
        "clip_sequence": clip_sequence,
        "total_clips": len(selected_clips),
        "total_duration": len(selected_clips) * CLIP_DURATION,
        "selection_strategy": "Random selection (Gemini unavailable)",
        "gemini_used": False
    }

# === STEP 4: DOWNLOAD VIDEOS ===
async def download_drive_videos_batch(
    video_selections: List[Dict[str, Any]],
    task_id: str,
    max_workers: int = 5
) -> List[Dict[str, Any]]:
    """Download videos in parallel for faster processing"""
    task_dir = TEMP_DIR / task_id
    task_dir.mkdir(exist_ok=True)
    
    log_task(task_id, f"Starting parallel download of {len(video_selections)} videos...")
    
    downloaded_videos = []
    failed_downloads = []
    
    def download_single_video(video_info: Dict, index: int) -> Optional[Dict]:
        """Download a single video"""
        video_name = video_info.get("name", f"video_{index}")
        download_url = video_info.get("download_url")
        
        if not download_url:
            # Try to construct from ID
            file_id = video_info.get("id")
            if file_id and not file_id.startswith("unknown_"):
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            else:
                return None
        
        output_path = task_dir / f"video_{index:03d}_{Path(video_name).stem}.mp4"
        
        try:
            # Use session for better performance
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            # Download with retries
            for attempt in range(3):
                try:
                    response = session.get(download_url, stream=True, timeout=30)
                    
                    # Handle Google Drive confirmation
                    if 'confirm=' in response.url or 'download_warning' in response.url:
                        # Try to get confirm token
                        for key, value in response.cookies.items():
                            if 'download_warning' in key.lower():
                                download_url = f"{download_url}&confirm={value}"
                                response = session.get(download_url, stream=True, timeout=30)
                                break
                    
                    # Save file
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    # Verify
                    if output_path.exists() and output_path.stat().st_size > 1024:
                        return {
                            **video_info,
                            "local_path": str(output_path),
                            "download_success": True,
                            "file_size": output_path.stat().st_size
                        }
                    
                except Exception as e:
                    if attempt == 2:  # Last attempt
                        raise
                    time.sleep(1)
            
        except Exception as e:
            print(f"Download failed for {video_name}: {str(e)[:50]}")
            if output_path.exists():
                output_path.unlink()
            return None
    
    # Download in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for i, video_info in enumerate(video_selections):
            futures.append(executor.submit(download_single_video, video_info, i))
        
        # Collect results
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            result = future.result()
            if result:
                downloaded_videos.append(result)
                if len(downloaded_videos) % 5 == 0:
                    log_task(task_id, f"  Downloaded {len(downloaded_videos)}/{len(video_selections)} videos")
            else:
                failed_downloads.append(i)
    
    if not downloaded_videos:
        raise Exception(f"Failed to download any videos. {len(failed_downloads)} failed")
    
    log_task(task_id, f"✅ Downloaded {len(downloaded_videos)}/{len(video_selections)} videos")
    if failed_downloads:
        log_task(task_id, f"  Failed downloads: {len(failed_downloads)} videos")
    
    return downloaded_videos

# === STEP 5: CREATE VIDEO CLIPS ===
def create_video_clips_parallel(
    downloaded_videos: List[Dict[str, Any]],
    clip_sequence: List[Dict[str, Any]],
    task_id: str,
    max_workers: int = 4
) -> List[str]:
    """Create clips in parallel for faster processing"""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        
        task_dir = TEMP_DIR / task_id
        clips_dir = task_dir / "clips"
        clips_dir.mkdir(exist_ok=True)
        
        log_task(task_id, f"Creating {len(clip_sequence)} clips in parallel...")
        
        def create_single_clip(clip_info: Dict, index: int) -> Optional[str]:
            """Create a single 3-second clip"""
            clip_index = clip_info.get("clip_index", index)
            
            if clip_index >= len(downloaded_videos):
                return None
            
            video_info = downloaded_videos[clip_index]
            video_path = video_info.get("local_path")
            
            if not video_path or not Path(video_path).exists():
                return None
            
            clip_output = clips_dir / f"clip_{index:03d}.mp4"
            
            # Use clip_start from selection or random point
            video_start_time = video_info.get("clip_start", random.uniform(0, 10))
            
            # Create clip command
            cmd = [
                exe, "-y",
                "-ss", str(video_start_time),
                "-i", video_path,
                "-t", str(CLIP_DURATION),
                "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "23",
                "-r", "30",
                "-an",
                str(clip_output)
            ]
            
            try:
                # Run FFmpeg
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if clip_output.exists() and clip_output.stat().st_size > 10000:
                    return str(clip_output)
                else:
                    return None
                    
            except subprocess.TimeoutExpired:
                return None
            except Exception:
                return None
        
        # Create clips in parallel
        clip_paths = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for i, clip_info in enumerate(clip_sequence):
                futures.append(executor.submit(create_single_clip, clip_info, i))
            
            # Collect results
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                result = future.result()
                if result:
                    clip_paths.append(result)
                    if len(clip_paths) % 10 == 0:
                        log_task(task_id, f"  Created {len(clip_paths)}/{len(clip_sequence)} clips")
        
        if not clip_paths:
            raise Exception("Failed to create any clips")
        
        log_task(task_id, f"✅ Created {len(clip_paths)} clips")
        return clip_paths
        
    except Exception as e:
        raise Exception(f"Clip creation failed: {str(e)}")

# === STEP 6: MERGE CLIPS AND ADD AUDIO ===
def merge_clips_with_audio(
    clip_paths: List[str],
    audio_path: str,
    task_id: str
) -> str:
    """Merge all clips and add audio track"""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        
        task_dir = TEMP_DIR / task_id
        output_path = OUTPUT_DIR / f"{task_id}_final.mp4"
        
        # Create concatenation list
        concat_list = task_dir / "concat_list.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for clip_path in clip_paths:
                abs_path = Path(clip_path).resolve()
                f.write(f"file '{abs_path}'\n")
        
        # Concatenate clips
        temp_video = task_dir / "concatenated.mp4"
        
        concat_cmd = [
            exe, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-r", "30",
            "-an",
            str(temp_video)
        ]
        
        log_task(task_id, "Concatenating clips...")
        subprocess.run(concat_cmd, check=True, capture_output=True, text=True, timeout=300)
        
        # Add audio
        log_task(task_id, "Adding audio track...")
        
        merge_cmd = [
            exe, "-y",
            "-i", str(temp_video),
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_path)
        ]
        
        subprocess.run(merge_cmd, check=True, capture_output=True, text=True, timeout=180)
        
        if not output_path.exists():
            raise Exception("Final video not created")
        
        # Get final duration
        final_duration = get_video_duration(str(output_path))
        
        log_task(task_id, f"✅ Final video created: {output_path} ({final_duration:.1f}s)")
        return str(output_path)
        
    except Exception as e:
        raise Exception(f"Merge failed: {str(e)}")

# === MAIN PROCESSING PIPELINE ===
async def process_video_generation_pipeline(
    audio_path: str,
    task_id: str
):
    """Main pipeline: Transcribe → Scrape ALL Drive → Select videos → Download → Create clips → Merge"""
    global active_tasks
    
    try:
        active_tasks += 1
        tasks[task_id]['status'] = 'processing'
        
        # STEP 1: Transcribe audio
        log_task(task_id, "Step 1/6: Transcribing audio with Whisper...")
        transcription, audio_duration = await transcribe_audio_with_whisper(audio_path)
        tasks[task_id]['transcription'] = transcription
        tasks[task_id]['audio_duration'] = audio_duration
        
        # STEP 2: Scrape COMPLETE Google Drive structure
        log_task(task_id, "Step 2/6: Scraping ALL folders and subfolders from Drive...")
        drive_data = scrape_complete_drive_structure(GOOGLE_DRIVE_FOLDER_ID)
        tasks[task_id]['drive_data'] = drive_data
        
        # STEP 3: Use Gemini to select videos
        log_task(task_id, "Step 3/6: Selecting videos with Gemini...")
        selection_result = await select_videos_with_gemini(
            transcription, 
            audio_duration, 
            drive_data
        )
        tasks[task_id]['selection_result'] = selection_result
        
        # STEP 4: Download selected videos in parallel
        log_task(task_id, "Step 4/6: Downloading videos in parallel...")
        downloaded_videos = await download_drive_videos_batch(
            selection_result["selected_videos"],
            task_id,
            max_workers=5
        )
        tasks[task_id]['downloaded_videos'] = downloaded_videos
        
        # STEP 5: Create video clips in parallel
        log_task(task_id, "Step 5/6: Creating 3-second clips in parallel...")
        clip_paths = create_video_clips_parallel(
            downloaded_videos,
            selection_result["clip_sequence"],
            task_id,
            max_workers=4
        )
        tasks[task_id]['clip_paths'] = clip_paths
        
        # STEP 6: Merge clips and add audio
        log_task(task_id, "Step 6/6: Merging clips with audio...")
        final_video_path = merge_clips_with_audio(
            clip_paths,
            audio_path,
            task_id
        )
        
        # Update task status
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['output_file'] = final_video_path
        tasks[task_id]['completed_at'] = datetime.now()
        
        log_task(task_id, "✅ Video generation completed successfully!")
        
        # Cleanup temp files (keep final video)
        try:
            task_dir = TEMP_DIR / task_id
            shutil.rmtree(task_dir, ignore_errors=True)
        except:
            pass
        
        free_memory()
        
    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)
        tasks[task_id]['completed_at'] = datetime.now()
        log_task(task_id, f"❌ Failed: {e}")
        
        # Cleanup on error
        try:
            task_dir = TEMP_DIR / task_id
            shutil.rmtree(task_dir, ignore_errors=True)
        except:
            pass
        
        free_memory()
        
    finally:
        active_tasks -= 1

# === API ENDPOINTS ===
@app.post("/generate-video")
async def generate_video(
    audio_file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """Main endpoint to generate video from audio"""
    global active_tasks
    
    if active_tasks >= MAX_CONCURRENT_TASKS:
        raise HTTPException(429, f"Server busy. Max {MAX_CONCURRENT_TASKS} concurrent tasks allowed.")
    
    # Validate file
    if not audio_file.filename.lower().endswith(('.mp3', '.wav', '.m4a', '.aac', '.mp4', '.mov')):
        raise HTTPException(400, "Supported formats: MP3, WAV, M4A, AAC, MP4, MOV")
    
    # Create task
    task_id = str(uuid.uuid4())
    task_dir = TEMP_DIR / task_id
    task_dir.mkdir(exist_ok=True)
    
    # Save uploaded file
    audio_path = task_dir / "audio.mp3"
    try:
        with open(audio_path, "wb") as f:
            content = await audio_file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(500, f"Failed to save audio file: {str(e)}")
    
    # Initialize task
    tasks[task_id] = {
        'status': 'pending',
        'progress': 'Starting complete video generation...',
        'error': None,
        'output_file': None,
        'created_at': datetime.now(),
        'completed_at': None,
        'transcription': None,
        'audio_duration': None,
        'drive_data': None,
        'selection_result': None,
        'downloaded_videos': None,
        'clip_paths': None
    }
    
    # Start background processing
    background_tasks.add_task(process_video_generation_pipeline, str(audio_path), task_id)
    
    return JSONResponse({
        "task_id": task_id,
        "status": "pending",
        "message": "Video generation started with complete Drive scanning",
        "created_at": tasks[task_id]['created_at'].isoformat(),
        "note": "This may take a while as we scan ALL folders and subfolders"
    })

@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """Get task status"""
    if task_id not in tasks:
        raise HTTPException(404, "Task not found")
    
    task = tasks[task_id]
    
    response = {
        "task_id": task_id,
        "status": task['status'],
        "progress": task['progress'],
        "created_at": task['created_at'].isoformat(),
    }
    
    if task['completed_at']:
        response["completed_at"] = task['completed_at'].isoformat()
    
    if task['error']:
        response["error"] = task['error']
    
    if task['output_file']:
        response["output_file"] = task['output_file']
        response["download_url"] = f"/download/{task_id}"
    
    # Include processing info
    if task['transcription']:
        response["transcription"] = task['transcription'][:200] + "..." if len(task['transcription']) > 200 else task['transcription']
    
    if task['audio_duration']:
        response["audio_duration"] = task['audio_duration']
    
    if task['drive_data']:
        response["total_videos_found"] = task['drive_data'].get('total_videos', 0)
        response["total_folders"] = task['drive_data'].get('summary', {}).get('total_folders', 0)
    
    if task['selection_result']:
        response["clips_selected"] = task['selection_result'].get('total_clips', 0)
        response["selection_strategy"] = task['selection_result'].get('selection_strategy', '')
    
    return JSONResponse(response)

@app.get("/download/{task_id}")
async def download_video(task_id: str):
    """Download generated video"""
    if task_id not in tasks:
        raise HTTPException(404, "Task not found")
    
    task = tasks[task_id]
    if task['status'] != 'completed':
        raise HTTPException(400, "Video not ready yet")
    
    file_path = task.get('output_file')
    if not file_path or not Path(file_path).exists():
        raise HTTPException(404, "Video file not found")
    
    return FileResponse(
        file_path,
        media_type="video/mp4",
        filename=f"{task_id}.mp4"
    )

@app.get("/scan-drive")
async def scan_drive_endpoint():
    """Scan Drive without generating video"""
    try:
        log_task("scan", "Starting Drive scan...")
        drive_data = scrape_complete_drive_structure(GOOGLE_DRIVE_FOLDER_ID)
        
        # Format response
        summary = drive_data['summary']
        
        return JSONResponse({
            "success": True,
            "total_videos": drive_data['total_videos'],
            "total_folders": summary['total_folders'],
            "total_files": summary['total_files'],
            "folders_by_depth": summary['folders_by_depth'],
            "video_formats": summary['video_formats'],
            "largest_folders": summary['largest_folders'][:10],
            "sample_videos": [
                {
                    "name": v['name'],
                    "folder": v.get('folder_path', 'Root'),
                    "download_url": v.get('download_url', '')
                }
                for v in drive_data['all_videos'][:5]
            ],
            "scraped_at": drive_data['scraped_at']
        })
        
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e),
            "note": "Make sure your Google Drive folder is set to 'Anyone with the link can view'"
        })

@app.get("/api/status")
async def api_status():
    """API status endpoint"""
    return JSONResponse({
        "status": "running",
        "version": "4.0.0-complete-scraper",
        "active_tasks": active_tasks,
        "max_concurrent_tasks": MAX_CONCURRENT_TASKS,
        "total_tasks": len(tasks),
        "drive_access": "public (complete scanning)",
        "features": [
            "Complete Google Drive scanning (ALL folders)",
            "Unlimited depth scraping",
            "Parallel downloading",
            "Parallel clip creation",
            "Gemini AI video selection",
            "3-second clip switching"
        ]
    })

# === SIMPLE UI ===
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve simple UI"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎬 Complete AI Video Generator</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            .container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                width: 100%;
                max-width: 800px;
                padding: 40px;
                text-align: center;
            }
            h1 {
                color: #333;
                margin-bottom: 10px;
                font-size: 2.5em;
            }
            .subtitle {
                color: #666;
                margin-bottom: 20px;
                font-size: 1.1em;
            }
            .feature-list {
                text-align: left;
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
            }
            .feature-list li {
                margin: 10px 0;
                padding-left: 20px;
                position: relative;
            }
            .feature-list li:before {
                content: "✓";
                position: absolute;
                left: 0;
                color: #28a745;
                font-weight: bold;
            }
            .upload-area {
                border: 3px dashed #ddd;
                border-radius: 15px;
                padding: 40px 20px;
                margin: 20px 0;
                cursor: pointer;
                transition: all 0.3s;
                background: #f8f9fa;
            }
            .upload-area:hover {
                border-color: #667eea;
                background: #f0f2ff;
            }
            #fileInput {
                display: none;
            }
            .file-label {
                display: block;
                cursor: pointer;
            }
            .upload-icon {
                font-size: 3em;
                margin-bottom: 15px;
                color: #667eea;
            }
            .upload-text {
                font-size: 1.2em;
                color: #555;
                margin-bottom: 10px;
            }
            .file-name {
                color: #888;
                font-size: 0.9em;
                margin-top: 10px;
                word-break: break-all;
            }
            button {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 15px 40px;
                border-radius: 50px;
                font-size: 1.1em;
                font-weight: bold;
                cursor: pointer;
                margin: 10px 5px;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            button:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
            }
            button:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
                box-shadow: none;
            }
            .status-area {
                margin-top: 30px;
                padding: 20px;
                border-radius: 10px;
                background: #f8f9fa;
                display: none;
            }
            .progress-bar {
                height: 8px;
                background: #e9ecef;
                border-radius: 4px;
                margin: 20px 0;
                overflow: hidden;
            }
            .progress-fill {
                height: 100%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                width: 0%;
                transition: width 0.3s;
                border-radius: 4px;
            }
            .step-info {
                text-align: left;
                margin: 15px 0;
                padding: 15px;
                background: white;
                border-radius: 8px;
                border-left: 4px solid #667eea;
            }
            .success-message {
                color: #28a745;
                background: #d4edda;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
            }
            .error-message {
                color: #dc3545;
                background: #f8d7da;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎬 Complete AI Video Generator</h1>
            <p class="subtitle">Scans ALL folders in your Google Drive + AI-powered video selection</p>
            
            <div class="feature-list">
                <h3>✨ Features:</h3>
                <ul>
                    <li>Scans ALL folders and subfolders from Google Drive (no limits)</li>
                    <li>Transcribes audio with Whisper AI</li>
                    <li>Selects relevant videos with Gemini AI</li>
                    <li>Changes video every 3 seconds for dynamic content</li>
                    <li>Parallel downloading and processing</li>
                    <li>No authentication needed (public folders only)</li>
                </ul>
            </div>
            
            <div class="upload-area" id="uploadArea">
                <label class="file-label" for="fileInput">
                    <div class="upload-icon">📁</div>
                    <div class="upload-text">Click to upload audio file</div>
                    <div>or drag and drop here</div>
                    <div class="file-name" id="fileName">No file selected</div>
                </label>
                <input type="file" id="fileInput" accept=".mp3,.wav,.m4a,.aac,.mp4,.mov">
            </div>
            
            <div>
                <button id="generateBtn" onclick="startGeneration()" disabled>🎬 Generate Video</button>
                <button id="scanBtn" onclick="scanDrive()">🔍 Scan Drive Only</button>
            </div>
            
            <div class="status-area" id="statusArea">
                <h3>Processing Status</h3>
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                <div id="stepDetails"></div>
                <div id="resultArea"></div>
            </div>
        </div>
        
        <script>
            // File upload
            const fileInput = document.getElementById('fileInput');
            const uploadArea = document.getElementById('uploadArea');
            const fileName = document.getElementById('fileName');
            const generateBtn = document.getElementById('generateBtn');
            
            fileInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (file) {
                    fileName.textContent = file.name;
                    generateBtn.disabled = false;
                }
            });
            
            // Drag and drop
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                uploadArea.addEventListener(eventName, preventDefaults, false);
            });
            
            function preventDefaults(e) {
                e.preventDefault();
                e.stopPropagation();
            }
            
            ['dragenter', 'dragover'].forEach(eventName => {
                uploadArea.addEventListener(eventName, highlight, false);
            });
            
            ['dragleave', 'drop'].forEach(eventName => {
                uploadArea.addEventListener(eventName, unhighlight, false);
            });
            
            function highlight() {
                uploadArea.classList.add('dragover');
            }
            
            function unhighlight() {
                uploadArea.classList.remove('dragover');
            }
            
            uploadArea.addEventListener('drop', handleDrop, false);
            
            function handleDrop(e) {
                const dt = e.dataTransfer;
                const file = dt.files[0];
                
                if (file && file.type.startsWith('audio/')) {
                    fileInput.files = dt.files;
                    fileName.textContent = file.name;
                    generateBtn.disabled = false;
                }
            }
            
            // Video generation
            let taskId = null;
            let pollingInterval = null;
            
            async function startGeneration() {
                const file = fileInput.files[0];
                if (!file) return;
                
                showStatus('Starting complete video generation...', 10);
                generateBtn.disabled = true;
                generateBtn.textContent = 'Processing...';
                
                const formData = new FormData();
                formData.append('audio_file', file);
                
                try {
                    const response = await fetch('/generate-video', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (!response.ok) throw new Error('Failed to start');
                    
                    const data = await response.json();
                    taskId = data.task_id;
                    
                    startPolling();
                    
                } catch (error) {
                    showError(error.message);
                    resetUI();
                }
            }
            
            async function scanDrive() {
                showStatus('Scanning Google Drive (this may take a while)...', 20);
                document.getElementById('scanBtn').disabled = true;
                
                try {
                    const response = await fetch('/scan-drive');
                    const data = await response.json();
                    
                    if (data.success) {
                        let html = `<div class="success-message">
                            <h3>✅ Drive Scan Complete!</h3>
                            <p>Total Folders: ${data.total_folders}</p>
                            <p>Total Videos: ${data.total_videos}</p>
                            <p>Total Files: ${data.total_files}</p>
                            <p>Largest Folders:</p>
                            <ul>`;
                        
                        data.largest_folders.forEach(folder => {
                            html += `<li>${folder.name}: ${folder.video_count} videos</li>`;
                        });
                        
                        html += `</ul></div>`;
                        
                        document.getElementById('resultArea').innerHTML = html;
                    } else {
                        showError(data.error);
                    }
                } catch (error) {
                    showError(error.message);
                }
                
                document.getElementById('scanBtn').disabled = false;
            }
            
            function startPolling() {
                if (pollingInterval) clearInterval(pollingInterval);
                
                pollingInterval = setInterval(async () => {
                    try {
                        const response = await fetch(`/task/${taskId}`);
                        const status = await response.json();
                        
                        updateStatus(status);
                        
                        if (status.status === 'completed' || status.status === 'failed') {
                            clearInterval(pollingInterval);
                            
                            if (status.status === 'completed') {
                                showSuccess(status);
                            } else {
                                showError(status.error || 'Generation failed');
                            }
                            
                            resetUI();
                        }
                    } catch (error) {
                        console.error('Polling error:', error);
                    }
                }, 3000);
            }
            
            function updateStatus(status) {
                let progress = 0;
                let stepInfo = '';
                
                switch (status.status) {
                    case 'processing':
                        if (status.transcription) {
                            progress = 20;
                            stepInfo = `📝 Transcribed: ${status.transcription}`;
                        }
                        if (status.total_videos_found) {
                            progress = 40;
                            stepInfo = `📁 Found ${status.total_videos_found} videos in ${status.total_folders || 0} folders`;
                        }
                        if (status.clips_selected) {
                            progress = 60;
                            stepInfo = `🤖 Selected ${status.clips_selected} clips: ${status.selection_strategy}`;
                        }
                        if (status.progress && status.progress.includes('Downloading')) {
                            progress = 70;
                        }
                        if (status.progress && status.progress.includes('Creating')) {
                            progress = 85;
                        }
                        if (status.progress && status.progress.includes('Merging')) {
                            progress = 95;
                        }
                        break;
                    case 'completed':
                        progress = 100;
                        break;
                }
                
                document.getElementById('progressFill').style.width = progress + '%';
                document.getElementById('stepDetails').innerHTML = stepInfo ? 
                    `<div class="step-info">${stepInfo}</div>` : '';
            }
            
            function showStatus(message, progress) {
                document.getElementById('statusArea').style.display = 'block';
                document.getElementById('progressFill').style.width = progress + '%';
                document.getElementById('stepDetails').innerHTML = 
                    `<div class="step-info">${message}</div>`;
            }
            
            function showSuccess(status) {
                const resultArea = document.getElementById('resultArea');
                resultArea.innerHTML = `
                    <div class="success-message">
                        <h3>✅ Video Generated Successfully!</h3>
                        <p>Duration: ${status.audio_duration ? status.audio_duration.toFixed(1) + 's' : 'N/A'}</p>
                        <p>Clips used: ${status.clips_selected || 'N/A'}</p>
                        <p>Drive scanned: ${status.total_videos_found || 'N/A'} videos found</p>
                        <a href="/download/${taskId}" class="download-link" style="
                            display: inline-block;
                            background: #28a745;
                            color: white;
                            padding: 12px 30px;
                            border-radius: 50px;
                            text-decoration: none;
                            font-weight: bold;
                            margin-top: 15px;
                        " download>
                            📥 Download Video
                        </a>
                    </div>
                `;
            }
            
            function showError(message) {
                const resultArea = document.getElementById('resultArea');
                resultArea.innerHTML = `
                    <div class="error-message">
                        <strong>❌ Error:</strong> ${message}
                    </div>
                `;
            }
            
            function resetUI() {
                generateBtn.disabled = false;
                generateBtn.textContent = '🎬 Generate Video';
                document.getElementById('scanBtn').disabled = false;
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting Complete AI Video Generator API on port {port}")
    print(f"🔗 Access at: http://localhost:{port}")
    print(f"📁 Using Google Drive folder ID: {GOOGLE_DRIVE_FOLDER_ID}")
    print(f"⚡ Features: Unlimited folder scanning, parallel processing, AI selection")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        workers=1
    )