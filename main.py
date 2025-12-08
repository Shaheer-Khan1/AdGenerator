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

# JSON cache file in root folder
JSON_CACHE_FILE = Path("drive_cache.json")

# Create directories
TEMP_DIR = Path("temp_videos")
OUTPUT_DIR = Path("output_videos")
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# === GLOBAL WHISPER MODEL (LOAD ONCE) ===
WHISPER_MODEL = None
FFMPEG_EXE = None

def load_whisper_model():
    """Load Whisper model once and keep it in memory"""
    global WHISPER_MODEL, FFMPEG_EXE
    
    if WHISPER_MODEL is None:
        try:
            import whisper
            import imageio_ffmpeg
            
            print("🔧 Loading Whisper base model for fast transcription...")
            
            # Get FFmpeg executable
            FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
            print(f"✅ FFmpeg executable: {FFMPEG_EXE}")
            
            # Use 'base' model for good balance of speed and accuracy
            # For even faster: use 'tiny' or 'small'
            WHISPER_MODEL = whisper.load_model("tiny")
            
            print("✅ Whisper base model loaded successfully!")
            
        except ImportError as e:
            print(f"❌ Error loading Whisper: {e}")
            print("Please install: pip install openai-whisper")
            raise
        except Exception as e:
            print(f"❌ Error loading Whisper model: {e}")
            raise
    
    return WHISPER_MODEL, FFMPEG_EXE

# Load model on startup
load_whisper_model()

# === FASTAPI APP ===
app = FastAPI(
    title="AI Video Generator API - Complete Drive Scraper",
    description="Generate videos from audio + ALL footage from Google Drive",
    version="5.2.0"
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

def log_info(message: str):
    """Log a message with timestamp to the terminal."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def log_task(task_id: str, message: str):
    """Log task progress with consistent formatting"""
    log_info(f"[{task_id}] {message}")
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
    """Get video duration using FFmpeg - returns default if fails"""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [exe, "-i", video_path]
        
        # Add timeout to prevent hanging
        result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, 
                              text=True, timeout=10.0)  # 10 second timeout
        
        match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
        if not match:
            return 10.0  # Default duration
        
        h, m, s = map(float, match.groups())
        return h * 3600 + m * 60 + s
    except subprocess.TimeoutExpired:
        log_error(f"Timeout getting duration for: {video_path}")
        return 10.0  # Default duration
    except Exception as e:
        log_error(f"Error getting video duration for {video_path}: {e}")
        return 10.0  # Default duration

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
                        items.update(self._parse_drive_json(data, folder_id))
                    except:
                        pass
            
            # Method 2: Direct HTML parsing for file links
            self._parse_html_links(html_content, items, folder_id)
            
            # Method 3: Look for data-id attributes
            data_id_matches = re.findall(r'data-id="([a-zA-Z0-9_-]{25,})"', html_content)
            for data_id in data_id_matches:
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
        aria_match = re.search(r'aria-label="([^"]+)"', context)
        if aria_match:
            return unquote(aria_match.group(1)).strip()
        
        title_match = re.search(r'title="([^"]+)"', context)
        if title_match:
            return unquote(title_match.group(1)).strip()
        
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
            
            items = self.extract_folder_data(html_content, folder_id)
            
            folder_name = "Root"
            if items.get('folders') or items.get('videos') or items.get('files'):
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
                
                if subfolder_id and subfolder_id != folder_id:
                    new_path = f"{current_path}/{subfolder_name}" if current_path else subfolder_name
                    
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
            videos.extend(node.get('videos', []))
            
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
            if depth not in summary['folders_by_depth']:
                summary['folders_by_depth'][depth] = 0
            summary['folders_by_depth'][depth] += 1
            
            video_count = len(node.get('videos', []))
            summary['total_videos'] += video_count
            summary['total_files'] += len(node.get('files', []))
            summary['total_folders'] += 1
            
            for video in node.get('videos', []):
                video_name = video.get('name', '').lower()
                for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.wmv', '.flv']:
                    if ext in video_name:
                        if ext not in summary['video_formats']:
                            summary['video_formats'][ext] = 0
                        summary['video_formats'][ext] += 1
                        break
            
            for subfolder in node.get('folders', {}).values():
                analyze_node(subfolder, depth + 1)
        
        analyze_node(structure)
        
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
    
    def get_folder_structure_with_video_counts(self, structure: Dict, current_path: str = "") -> List[Dict[str, Any]]:
        """Get flattened list of all folders with their video counts"""
        folders = []
        
        def extract_folders(node: Dict, path: str = ""):
            video_count = len(node.get('videos', []))
            if video_count > 0:
                folders.append({
                    'name': node.get('name', 'Unnamed'),
                    'path': path,
                    'video_count': video_count,
                    'full_path': f"{path}/{node.get('name', 'Unnamed')}" if path else node.get('name', 'Unnamed'),
                    'videos': node.get('videos', [])
                })
            
            for folder_name, subfolder in node.get('folders', {}).items():
                new_path = f"{path}/{folder_name}" if path else folder_name
                extract_folders(subfolder, new_path)
        
        extract_folders(structure)
        return folders

def load_cached_drive_data() -> Optional[Dict[str, Any]]:
    """Load cached drive data from JSON file"""
    try:
        if JSON_CACHE_FILE.exists():
            log_info(f"🔎 Attempting to load drive cache from {JSON_CACHE_FILE.resolve()}")
            with open(JSON_CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                log_info(f"✅ Loaded cached drive data from {JSON_CACHE_FILE}")
                log_info(f"   Cache keys: {list(data.keys())}")
                log_info(f"   Total videos in cache: {data.get('total_videos', 'unknown')}")
                return data
        else:
            log_info("⚠️ No drive cache file found on disk.")
            return None
    except Exception as e:
        log_info(f"⚠️ Error loading cache: {e}")
    
    return None

def save_drive_data_to_cache(drive_data: Dict[str, Any]) -> str:
    """Save drive data to cache JSON file in root folder"""
    try:
        log_info(f"💾 Saving drive data to cache at {JSON_CACHE_FILE.resolve()}")
        # Add cache timestamp
        drive_data_with_cache = {
            **drive_data,
            "cached_at": datetime.now().isoformat(),
            "cache_version": "1.0"
        }
        
        # Save to JSON file
        with open(JSON_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(drive_data_with_cache, f, indent=2, ensure_ascii=False, default=str)
        
        log_info(f"✅ Drive cache saved to: {JSON_CACHE_FILE}")
        log_info(f"   Cache size: {JSON_CACHE_FILE.stat().st_size / 1024:.2f} KB")
        return str(JSON_CACHE_FILE)
        
    except Exception as e:
        log_info(f"❌ Error saving cache: {e}")
        return ""

def get_drive_data(force_rescan: bool = False) -> Dict[str, Any]:
    """Get drive data - use cache if available, otherwise scrape"""
    log_info(f"📥 get_drive_data called (force_rescan={force_rescan})")
    # Try to load from cache first
    if not force_rescan:
        cached_data = load_cached_drive_data()
        if cached_data:
            # Check if this is the old format or new format
            if "folder_structure" in cached_data:
                # Already has the new format
                return cached_data
            elif "root_structure" in cached_data:
                # Old format, need to process it
                log_info("ℹ️ Cache in old format detected, rebuilding to new format for generation.")
                return get_drive_data_for_generation()  # This will process it correctly
            else:
                # Unknown format, need to rescan
                log_info("⚠️ Cache format unknown, falling back to fresh scrape.")
                pass
    
    # If no cache or forced rescan, scrape fresh
    log_task("drive", f"🚀 Starting fresh Drive scraping from folder: {GOOGLE_DRIVE_FOLDER_ID}")
    log_task("drive", "This may take a while for large folders...")
    
    scraper = GoogleDriveScraper(GOOGLE_DRIVE_FOLDER_ID)
    
    structure = scraper.scrape_folder(GOOGLE_DRIVE_FOLDER_ID, max_depth=100)
    
    if not structure:
        raise Exception("Failed to scrape Drive folder. Make sure it's public and accessible.")
    
    all_videos = scraper.get_all_videos(structure)
    summary = scraper.get_folder_summary(structure)
    folder_structure = scraper.get_folder_structure_with_video_counts(structure)
    
    log_task("drive", f"✅ Drive scraping complete!")
    log_task("drive", f"📊 Summary:")
    log_task("drive", f"  Total folders: {summary['total_folders']}")
    log_task("drive", f"  Total videos: {len(all_videos)}")
    log_task("drive", f"  Total files: {summary['total_files']}")
    log_task("drive", f"  Folders with videos: {len(folder_structure)}")
    log_info(f"📁 Folder structure entries: {len(folder_structure)}")
    log_info(f"🧭 Scrape completed at {datetime.now().isoformat()}")
    
    drive_data = {
        "root_structure": structure,
        "all_videos": all_videos,
        "folder_structure": folder_structure,
        "summary": summary,
        "total_videos": len(all_videos),
        "scraped_at": datetime.now().isoformat(),
        "source": "fresh_scrape"
    }
    
    # Save to cache
    save_drive_data_to_cache(drive_data)
    
    return drive_data
# === STEP 1: TRANSCRIBE AUDIO (USING PRE-LOADED WHISPER MODEL) ===
async def transcribe_audio_with_whisper(audio_path: str) -> Tuple[str, float]:
    """Transcribe audio using pre-loaded Whisper model (fast!)"""
    global WHISPER_MODEL, FFMPEG_EXE
    
    try:
        log_task("transcribe", "Transcribing with pre-loaded Whisper base model...")
        
        # Ensure model is loaded
        if WHISPER_MODEL is None:
            WHISPER_MODEL, FFMPEG_EXE = load_whisper_model()
        
        # Patch Whisper's audio module to use bundled FFmpeg
        import whisper
        import whisper.audio
        original_run = whisper.audio.run
        
        def patched_run(cmd, *args, **kwargs):
            """Replace 'ffmpeg' command with full path"""
            if isinstance(cmd, list) and len(cmd) > 0 and cmd[0] == 'ffmpeg':
                cmd = [FFMPEG_EXE] + cmd[1:]
            elif isinstance(cmd, str) and cmd == 'ffmpeg':
                cmd = FFMPEG_EXE
            return original_run(cmd, *args, **kwargs)
        
        # Apply patch
        whisper.audio.run = patched_run
        
        try:
            # Fast transcription with optimized settings
            start_time = time.time()
            result = WHISPER_MODEL.transcribe(
                str(audio_path),
                fp16=False,        # Use FP32 for stability
                language=None,     # Auto-detect language
                task="transcribe",
                verbose=False,
                # Optimize for speed
                best_of=1,         # Reduce search iterations
                beam_size=3,       # Smaller beam size for speed
                temperature=0.0,   # Deterministic output
                compression_ratio_threshold=2.4,
                logprob_threshold=-1.0,
                no_speech_threshold=0.6,
                condition_on_previous_text=False  # Don't condition on previous text
            )
            
            transcription_time = time.time() - start_time
            
            transcription = result["text"].strip()
            audio_duration = get_audio_duration(audio_path)
            
            log_task("transcribe", f"✅ Transcribed {len(transcription)} chars in {transcription_time:.1f}s")
            log_task("transcribe", f"   Transcription: {transcription[:200]}..." if len(transcription) > 200 else f"   Transcription: {transcription}")
            log_task("transcribe", f"   Audio duration: {audio_duration:.1f}s")
            log_task("transcribe", f"   Speed: {audio_duration/transcription_time:.1f}x real-time")
            
            return transcription, audio_duration
        finally:
            # Restore original run function
            whisper.audio.run = original_run
        
    except Exception as e:
        import traceback
        log_task("transcribe", f"❌ Transcription error: {str(e)}")
        log_task("transcribe", f"   Traceback: {traceback.format_exc()}")
        raise Exception(f"Transcription failed: {str(e)}")

# === STEP 2: USE CACHED DRIVE DATA ===
def get_drive_data_for_generation() -> Dict[str, Any]:
    """Get drive data for video generation - always use cache if available"""
    log_task("drive", "Checking for cached drive data...")
    log_info("🧠 Preparing drive data for generation (cache-first strategy)")
    
    # Always try to use cache first for video generation
    cached_data = load_cached_drive_data()
    
    if cached_data:
        log_task("drive", f"✅ Using cached drive data")
        log_info(f"   Cache source: {cached_data.get('source', 'unknown')}")
        log_info(f"   Cached at: {cached_data.get('cached_at', 'unknown')}")
        
        # Extract root_structure from cache
        root_structure = cached_data.get("root_structure")
        if not root_structure:
            raise Exception("No root_structure found in cache")
        
        # Create a scraper instance to use its methods
        scraper = GoogleDriveScraper(GOOGLE_DRIVE_FOLDER_ID)
        
        # Extract all videos
        all_videos = scraper.get_all_videos(root_structure)
        
        # Get folder structure with video counts
        folder_structure = scraper.get_folder_structure_with_video_counts(root_structure)
        
        # Get summary
        summary = scraper.get_folder_summary(root_structure)
        
        # Build the complete drive data structure
        drive_data = {
            "root_structure": root_structure,
            "all_videos": all_videos,
            "folder_structure": folder_structure,
            "summary": summary,
            "total_videos": len(all_videos),
            "scraped_at": cached_data.get("scraped_at", "Unknown"),
            "source": cached_data.get("source", "cache")
        }
        
        log_task("drive", f"📊 Cached Summary:")
        log_task("drive", f"  Total folders: {summary.get('total_folders', 0)}")
        log_task("drive", f"  Total videos: {len(all_videos)}")
        log_task("drive", f"  Folders with videos: {len(folder_structure)}")
        log_task("drive", f"  Scraped at: {drive_data['scraped_at']}")
        log_task("drive", f"  Source: {drive_data['source']}")
        log_info(f"✅ Drive data ready for generation. Videos available: {len(all_videos)}")
        
        return drive_data
    else:
        log_task("drive", "❌ No cache found. Please scan drive first!")
        raise Exception("No drive cache found. Please scan the drive first using /scan-drive endpoint.")

# === STEP 3: USE GEMINI TO SELECT FOLDERS AND DISTRIBUTION ===
# === STEP 3: USE GEMINI TO SELECT FOLDERS AND DISTRIBUTION ===
async def select_videos_with_gemini(
    transcription: str,
    audio_duration: float,
    drive_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Use Gemini to decide how many videos to take from each folder based on transcription"""
    try:
        log_info("🤖 Starting Gemini folder distribution step...")
        log_info(f"   Transcription length: {len(transcription)} chars")
        log_info(f"   Audio duration: {audio_duration:.2f}s")
        log_info(f"   Drive folders available: {len(drive_data.get('folder_structure', []))}")
        log_info(f"   Total videos available: {len(drive_data.get('all_videos', []))}")
        
        if not GEMINI_API_KEY:
            raise Exception("Gemini API key is required. Set GEMINI_API_KEY environment variable.")
        
        import google.generativeai as genai
        
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        folder_structure = drive_data.get("folder_structure", [])
        
        if not folder_structure:
            raise Exception("No folder structure found in drive cache.")
        
        # Calculate total clips needed (3 seconds per clip)
        total_clips_needed = int(math.ceil(audio_duration / 3))
        
        # Sort folders by video count (descending) and limit
        sorted_folders = sorted(folder_structure, key=lambda x: x['video_count'], reverse=True)[:30]  # Limit to 30 folders
        
        # Create a mapping for quick lookup
        folder_map = {}
        for i, folder in enumerate(sorted_folders):
            folder_map[i + 1] = {
                'folder_obj': folder,
                'name': folder['name'],
                'path': folder['path'],
                'video_count': folder['video_count'],
                'videos': folder.get('videos', []),
                'full_path': folder.get('full_path', '')
            }
        
        # Create Gemini prompt
        prompt = f"""You are a professional video editor planning a video montage.

AUDIO TRANSCRIPT:
"{transcription[:1000]}"  # Limit transcript length

AUDIO DURATION: {audio_duration:.1f} seconds
TOTAL CLIPS NEEDED: {total_clips_needed} (3 seconds each)

FOLDER LIST (sorted by video count):
{chr(10).join([f"{i}. {folder_map[i]['name']} | Videos: {folder_map[i]['video_count']} | Path: {folder_map[i]['full_path'][:50]}" for i in folder_map])}

YOUR TASK:
Distribute {total_clips_needed} clips across these folders based on relevance to the transcript.
Return JSON with exact format:

{{
  "folder_distribution": [
    {{"folder_index": 1, "clips_to_take": 5, "reason": "brief reason"}},
    {{"folder_index": 2, "clips_to_take": 3, "reason": "brief reason"}}
  ],
  "total_clips": {total_clips_needed}
}}

RULES:
- Sum of all clips_to_take MUST equal {total_clips_needed}
- Maximum clips_to_take per folder is its video_count
- Return ONLY the JSON, no other text"""

        log_task("gemini", f"Asking Gemini to distribute {total_clips_needed} clips across folders...")
        
        # Send request to Gemini with timeout
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(model.generate_content, prompt),
                timeout=60.0  # 60 second timeout
            )
            response_text = response.text.strip()
        except asyncio.TimeoutError:
            raise Exception("Gemini API timeout after 60 seconds")
        
        # Parse JSON response
        try:
            # Extract JSON
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx == -1 or end_idx <= start_idx:
                raise ValueError("No JSON found in Gemini response")
            
            json_str = response_text[start_idx:end_idx]
            result = json.loads(json_str)
            
            log_info(f"✅ Successfully parsed Gemini JSON response")
            
            # Process folder distribution
            folder_distribution = result.get("folder_distribution", [])
            
            # Validate and normalize distribution
            total_distributed = 0
            valid_distributions = []
            
            for dist in folder_distribution:
                folder_idx = dist.get("folder_index", 0)
                clips_to_take = dist.get("clips_to_take", 0)
                
                if folder_idx in folder_map and clips_to_take > 0:
                    max_possible = folder_map[folder_idx]['video_count']
                    actual_clips = min(clips_to_take, max_possible)
                    if actual_clips > 0:
                        valid_distributions.append({
                            'folder_idx': folder_idx,
                            'clips_to_take': actual_clips,
                            'reason': dist.get('reason', '')
                        })
                        total_distributed += actual_clips
            
            # Adjust if needed
            if total_distributed != total_clips_needed:
                adjustment = total_clips_needed - total_distributed
                if adjustment > 0 and valid_distributions:
                    # Add to the first folder
                    valid_distributions[0]['clips_to_take'] += adjustment
                    total_distributed += adjustment
            
            # Select videos efficiently
            selected_clips = []
            used_video_ids = set()
            
            for dist in valid_distributions:
                folder_idx = dist['folder_idx']
                clips_to_take = dist['clips_to_take']
                
                if folder_idx in folder_map:
                    folder_info = folder_map[folder_idx]
                    folder_videos = folder_info['videos']
                    
                    # Filter out already used videos
                    available_videos = [v for v in folder_videos if v.get('id') not in used_video_ids]
                    
                    if available_videos:
                        # Take random videos, but limit to available
                        take_count = min(clips_to_take, len(available_videos))
                        selected_videos = random.sample(available_videos, take_count)
                        
                        for video in selected_videos:
                            # Use a fixed small clip start (0-5 seconds) to avoid HTTP calls
                            clip_start = random.uniform(0, 5)
                            
                            selected_clips.append({
                                **video,
                                "clip_start": clip_start,
                                "clip_duration": 3.0,
                                "selection_reason": dist['reason'],
                                "source_folder": folder_info['full_path'],
                                "folder_clips_taken": take_count
                            })
                            
                            if video.get('id'):
                                used_video_ids.add(video['id'])
            
            # Fill any remaining slots with random videos
            if len(selected_clips) < total_clips_needed:
                missing = total_clips_needed - len(selected_clips)
                all_videos = drive_data.get("all_videos", [])
                
                # Get videos not already selected
                available_videos = [v for v in all_videos if v.get('id') not in used_video_ids]
                
                for i in range(missing):
                    if not available_videos:
                        break
                    
                    video = random.choice(available_videos)
                    clip_start = random.uniform(0, 5)
                    
                    selected_clips.append({
                        **video,
                        "clip_start": clip_start,
                        "clip_duration": 3.0,
                        "selection_reason": "Random selection to fill quota",
                        "source_folder": "Random selection",
                        "folder_clips_taken": 1
                    })
                    
                    if video.get('id'):
                        used_video_ids.add(video['id'])
            
            # Shuffle and limit to exact number needed
            random.shuffle(selected_clips)
            selected_clips = selected_clips[:total_clips_needed]
            
            # Create clip sequence
            clip_sequence = [
                {
                    "clip_index": i,
                    "start_time": i * 3.0,
                    "end_time": (i + 1) * 3.0
                }
                for i in range(len(selected_clips))
            ]
            
            # Count unique folders used
            unique_folders = set(clip.get('source_folder', 'Unknown') for clip in selected_clips)
            
            final_result = {
                "selected_videos": selected_clips,
                "clip_sequence": clip_sequence,
                "total_clips": len(selected_clips),
                "total_duration": len(selected_clips) * 3.0,
                "distribution_strategy": result.get("distribution_strategy", "Gemini AI distribution"),
                "gemini_used": True,
                "gemini_response_preview": response_text[:200] + "..." if len(response_text) > 200 else response_text,
                "folders_used": len(unique_folders),
                "total_folders_available": len(folder_structure)
            }
            
            log_task("gemini", f"✅ Gemini distributed {len(selected_clips)} clips across {len(unique_folders)} folders")
            
            return final_result
            
        except json.JSONDecodeError as e:
            log_error(f"❌ Failed to parse Gemini JSON response: {e}")
            log_error(f"Response text: {response_text[:500]}")
            raise Exception(f"Gemini response not valid JSON: {str(e)}")
        
    except ImportError:
        raise Exception("Google Generative AI not installed. Run: pip install google-generativeai")
    except Exception as e:
        log_error(f"❌ Gemini selection failed: {str(e)}")
        raise Exception(f"Gemini video distribution failed: {str(e)}")

# Add this helper function
def log_error(message: str):
    """Log error message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"❌ [{timestamp}] {message}", file=sys.stderr)

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
    log_info(f"⬇️ Download batch initiated (workers={max_workers})")
    
    downloaded_videos = []
    
    def download_single_video(video_info: Dict, index: int) -> Optional[Dict]:
        video_name = video_info.get("name", f"video_{index}")
        download_url = video_info.get("download_url")
        
        if not download_url:
            file_id = video_info.get("id")
            if file_id and not file_id.startswith("unknown_"):
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            else:
                return None
        
        output_path = task_dir / f"video_{index:03d}_{Path(video_name).stem}.mp4"
        
        try:
            log_info(f"   [dl-{index}] Preparing download for {video_name} from {download_url}")
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            for attempt in range(3):
                try:
                    log_info(f"   [dl-{index}] Attempt {attempt+1}/3")
                    response = session.get(download_url, stream=True, timeout=30)
                    
                    if 'confirm=' in response.url or 'download_warning' in response.url:
                        for key, value in response.cookies.items():
                            if 'download_warning' in key.lower():
                                download_url = f"{download_url}&confirm={value}"
                                response = session.get(download_url, stream=True, timeout=30)
                                break
                    
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    if output_path.exists() and output_path.stat().st_size > 1024:
                        log_info(f"   [dl-{index}] ✅ Downloaded {video_name} ({output_path.stat().st_size/1024:.1f} KB)")
                        return {
                            **video_info,
                            "local_path": str(output_path),
                            "download_success": True,
                            "file_size": output_path.stat().st_size
                        }
                    
                except Exception as e:
                    if attempt == 2:
                        raise
                    log_info(f"   [dl-{index}] Retry due to error: {str(e)[:80]}")
                    time.sleep(1)
            
        except Exception as e:
            log_info(f"   [dl-{index}] ❌ Download failed for {video_name}: {str(e)[:80]}")
            if output_path.exists():
                output_path.unlink()
            return None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for i, video_info in enumerate(video_selections):
            futures.append(executor.submit(download_single_video, video_info, i))
        
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            result = future.result()
            if result:
                downloaded_videos.append(result)
                if len(downloaded_videos) % 5 == 0:
                    log_task(task_id, f"  Downloaded {len(downloaded_videos)}/{len(video_selections)} videos")
    
    if not downloaded_videos:
        raise Exception(f"Failed to download any videos")
    
    log_task(task_id, f"✅ Downloaded {len(downloaded_videos)}/{len(video_selections)} videos")
    
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
        log_info(f"🎬 Clip creation started (workers={max_workers})")
        
        def create_single_clip(clip_info: Dict, index: int) -> Optional[str]:
            clip_index = clip_info.get("clip_index", index)
            
            if clip_index >= len(downloaded_videos):
                log_info(f"   [clip-{index}] Skipped - missing video at index {clip_index}")
                return None
            
            video_info = downloaded_videos[clip_index]
            video_path = video_info.get("local_path")
            
            if not video_path or not Path(video_path).exists():
                log_info(f"   [clip-{index}] Skipped - video path missing")
                return None
            
            clip_output = clips_dir / f"clip_{index:03d}.mp4"
            
            video_start_time = video_info.get("clip_start", random.uniform(0, 10))
            log_info(f"   [clip-{index}] Creating 3s clip from {video_path} starting at {video_start_time:.2f}s")
            
            cmd = [
                exe, "-y",
                "-ss", str(video_start_time),
                "-i", video_path,
                "-t", "3.0",  # Fixed 3-second clips
                "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "23",
                "-r", "30",
                "-an",
                str(clip_output)
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if clip_output.exists() and clip_output.stat().st_size > 10000:
                    log_info(f"   [clip-{index}] ✅ Clip created ({clip_output.stat().st_size/1024:.1f} KB)")
                    return str(clip_output)
                else:
                    log_info(f"   [clip-{index}] ❌ Clip output missing or too small")
                    return None
                    
            except subprocess.TimeoutExpired:
                log_info(f"   [clip-{index}] ❌ Timeout during ffmpeg")
                return None
            except Exception:
                log_info(f"   [clip-{index}] ❌ Unexpected error during clip creation")
                return None
        
        clip_paths = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for i, clip_info in enumerate(clip_sequence):
                futures.append(executor.submit(create_single_clip, clip_info, i))
            
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
        
        log_info(f"🔗 Merging {len(clip_paths)} clips with audio for task {task_id}")
        log_info(f"   Audio path: {audio_path}")
        log_info(f"   Output path: {output_path}")
        
        if not clip_paths:
            raise Exception("No clips to merge")
        
        concat_list = task_dir / "concat_list.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for clip_path in clip_paths:
                abs_path = Path(clip_path).resolve()
                f.write(f"file '{abs_path}'\n")
        
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
        log_info(f"   Running ffmpeg concat with list file at {concat_list}")
        subprocess.run(concat_cmd, check=True, capture_output=True, text=True, timeout=300)
        
        log_task(task_id, "Adding audio track...")
        log_info("   Combining concatenated video with audio track (aac 192k)")
        
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
        
        final_duration = get_video_duration(str(output_path))
        
        log_task(task_id, f"✅ Final video created: {output_path} ({final_duration:.1f}s)")
        log_info(f"🎉 Final video ready at {output_path} duration {final_duration:.1f}s")
        return str(output_path)
        
    except Exception as e:
        raise Exception(f"Merge failed: {str(e)}")

# === MAIN PROCESSING PIPELINE ===
async def process_video_generation_pipeline(
    audio_path: str,
    task_id: str
):
    """Main pipeline: Fast transcription → Use cached Drive data → Gemini distributes clips → Select random videos → Download → Create clips → Merge"""
    global active_tasks
    
    try:
        log_info(f"🚦 Starting pipeline for task {task_id}")
        start_pipeline = time.time()
        active_tasks += 1
        tasks[task_id]['status'] = 'processing'
        
        # STEP 1: Fast transcription with pre-loaded Whisper
        log_task(task_id, "Step 1/6: Fast transcription with pre-loaded Whisper...")
        step_start = time.time()
        transcription, audio_duration = await transcribe_audio_with_whisper(audio_path)
        tasks[task_id]['transcription'] = transcription
        tasks[task_id]['audio_duration'] = audio_duration
        log_info(f"📝 Step 1 done in {time.time() - step_start:.2f}s (duration={audio_duration:.2f}s)")
        
        # STEP 2: Get drive data from cache
        log_task(task_id, "Step 2/6: Loading drive data from cache...")
        step_start = time.time()
        drive_data = get_drive_data_for_generation()
        tasks[task_id]['drive_data'] = drive_data
        log_info(f"📂 Step 2 done in {time.time() - step_start:.2f}s (folders={len(drive_data.get('folder_structure', []))}, videos={len(drive_data.get('all_videos', []))})")
        
        # STEP 3: Use Gemini to distribute clips across folders
        log_task(task_id, "Step 3/6: Gemini distributing clips across folders...")
        step_start = time.time()
        selection_result = await select_videos_with_gemini(
            transcription, 
            audio_duration, 
            drive_data
        )
        tasks[task_id]['selection_result'] = selection_result
        log_info(f"🤖 Step 3 done in {time.time() - step_start:.2f}s (clips={selection_result.get('total_clips')})")
        
        # STEP 4: Download selected videos in parallel
        log_task(task_id, "Step 4/6: Downloading videos in parallel...")
        step_start = time.time()
        downloaded_videos = await download_drive_videos_batch(
            selection_result["selected_videos"],
            task_id,
            max_workers=5
        )
        tasks[task_id]['downloaded_videos'] = downloaded_videos
        log_info(f"⬇️ Step 4 done in {time.time() - step_start:.2f}s (downloaded={len(downloaded_videos)})")
        
        # STEP 5: Create video clips in parallel
        log_task(task_id, "Step 5/6: Creating 3-second clips in parallel...")
        step_start = time.time()
        clip_paths = create_video_clips_parallel(
            downloaded_videos,
            selection_result["clip_sequence"],
            task_id,
            max_workers=4
        )
        tasks[task_id]['clip_paths'] = clip_paths
        log_info(f"✂️ Step 5 done in {time.time() - step_start:.2f}s (clips={len(clip_paths)})")
        
        # STEP 6: Merge clips and add audio
        log_task(task_id, "Step 6/6: Merging clips with audio...")
        step_start = time.time()
        final_video_path = merge_clips_with_audio(
            clip_paths,
            audio_path,
            task_id
        )
        
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['output_file'] = final_video_path
        tasks[task_id]['completed_at'] = datetime.now()
        
        log_task(task_id, "✅ Video generation completed successfully!")
        log_info(f"🏁 Pipeline finished in {time.time() - start_pipeline:.2f}s for task {task_id}")
        
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
    
    log_info(f"🌐 /generate-video called with file {audio_file.filename}")
    if active_tasks >= MAX_CONCURRENT_TASKS:
        raise HTTPException(429, f"Server busy. Max {MAX_CONCURRENT_TASKS} concurrent tasks allowed.")
    
    if not audio_file.filename.lower().endswith(('.mp3', '.wav', '.m4a', '.aac', '.mp4', '.mov')):
        raise HTTPException(400, "Supported formats: MP3, WAV, M4A, AAC, MP4, MOV")
    
    task_id = str(uuid.uuid4())
    task_dir = TEMP_DIR / task_id
    task_dir.mkdir(exist_ok=True)
    
    audio_path = task_dir / "audio.mp3"
    try:
        log_info(f"📝 Saving uploaded audio to {audio_path}")
        with open(audio_path, "wb") as f:
            content = await audio_file.read()
            f.write(content)
        log_info(f"📦 Audio saved ({audio_path.stat().st_size/1024:.1f} KB)")
    except Exception as e:
        log_info(f"❌ Failed to save uploaded audio: {e}")
        raise HTTPException(500, f"Failed to save audio file: {str(e)}")
    
    tasks[task_id] = {
        'status': 'pending',
        'progress': 'Starting video generation...',
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
    
    background_tasks.add_task(process_video_generation_pipeline, str(audio_path), task_id)
    
    return JSONResponse({
        "task_id": task_id,
        "status": "pending",
        "message": "Video generation started",
        "created_at": tasks[task_id]['created_at'].isoformat(),
        "note": "Using pre-loaded Whisper model for fast transcription"
    })

@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """Get task status"""
    log_info(f"ℹ️ /task/{task_id} requested")
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
    
    if task['transcription']:
        response["transcription"] = task['transcription'][:200] + "..." if len(task['transcription']) > 200 else task['transcription']
    
    if task['audio_duration']:
        response["audio_duration"] = task['audio_duration']
        response["clips_needed"] = int(math.ceil(task['audio_duration'] / 3))
    
    if task['drive_data']:
        response["total_videos_found"] = task['drive_data'].get('total_videos', 0)
        response["total_folders"] = task['drive_data'].get('summary', {}).get('total_folders', 0)
        response["folders_with_videos"] = len(task['drive_data'].get('folder_structure', []))
    
    if task['selection_result']:
        response["clips_selected"] = task['selection_result'].get('total_clips', 0)
        response["distribution_strategy"] = task['selection_result'].get('distribution_strategy', '')
        response["folders_used"] = task['selection_result'].get('folders_used', 0)
        response["gemini_used"] = task['selection_result'].get('gemini_used', False)
    
    return JSONResponse(response)

@app.get("/download/{task_id}")
async def download_video(task_id: str):
    """Download generated video"""
    log_info(f"⬇️ /download/{task_id} requested")
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
    """Scan Drive and update cache"""
    try:
        log_task("scan", "Starting Drive scan...")
        log_info("🔍 /scan-drive called - forcing fresh scrape")
        drive_data = get_drive_data(force_rescan=True)
        
        summary = drive_data['summary']
        folder_structure = drive_data.get('folder_structure', [])
        
        return JSONResponse({
            "success": True,
            "message": "Drive scan completed and cache updated",
            "total_videos": drive_data['total_videos'],
            "total_folders": summary['total_folders'],
            "total_files": summary['total_files'],
            "folders_with_videos": len(folder_structure),
            "folders_by_depth": summary['folders_by_depth'],
            "video_formats": summary['video_formats'],
            "largest_folders": summary['largest_folders'][:10],
            "cache_file": str(JSON_CACHE_FILE),
            "cache_size": JSON_CACHE_FILE.stat().st_size if JSON_CACHE_FILE.exists() else 0,
            "scraped_at": drive_data['scraped_at']
        })
        
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e),
            "note": "Make sure your Google Drive folder is set to 'Anyone with the link can view'"
        })

@app.get("/cache-status")
async def cache_status():
    """Check cache status"""
    log_info("🗄️ /cache-status requested")
    if JSON_CACHE_FILE.exists():
        try:
            with open(JSON_CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            cache_time = data.get('cached_at', 'Unknown')
            total_videos = data.get('total_videos', 0)
            folder_structure = data.get('folder_structure', [])
            
            return JSONResponse({
                "success": True,
                "cache_exists": True,
                "cache_file": str(JSON_CACHE_FILE),
                "cache_size": JSON_CACHE_FILE.stat().st_size,
                "total_videos": total_videos,
                "folders_with_videos": len(folder_structure),
                "cached_at": cache_time,
                "can_generate_videos": total_videos > 0
            })
        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": f"Cache corrupted: {str(e)}"
            })
    else:
        return JSONResponse({
            "success": False,
            "cache_exists": False,
            "message": "No cache found. Please scan drive first."
        })

@app.get("/api/status")
async def api_status():
    """API status endpoint"""
    log_info("📡 /api/status requested")
    cache_exists = JSON_CACHE_FILE.exists()
    cache_size = JSON_CACHE_FILE.stat().st_size if cache_exists else 0
    
    return JSONResponse({
        "status": "running",
        "version": "5.2.0-fast-whisper",
        "active_tasks": active_tasks,
        "max_concurrent_tasks": MAX_CONCURRENT_TASKS,
        "total_tasks": len(tasks),
        "cache_exists": cache_exists,
        "cache_size": cache_size,
        "whisper_loaded": WHISPER_MODEL is not None,
        "drive_access": "public (complete scanning)",
        "features": [
            "Whisper base model pre-loaded (fast transcription)",
            "Cache-based folder structure (no expiration)",
            "Gemini AI for folder distribution only",
            "Random video selection from chosen folders",
            "3-second clips based on audio duration",
            "Manual cache update via /scan-drive"
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
        <title>🎬 AI Video Generator</title>
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
            .tabs {
                display: flex;
                justify-content: center;
                margin-bottom: 20px;
                border-bottom: 2px solid #eee;
            }
            .tab {
                padding: 12px 24px;
                cursor: pointer;
                border-bottom: 3px solid transparent;
                font-weight: 500;
                transition: all 0.3s;
            }
            .tab.active {
                border-bottom: 3px solid #667eea;
                color: #667eea;
            }
            .tab-content {
                display: none;
                text-align: left;
            }
            .tab-content.active {
                display: block;
            }
            .feature-list {
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
            .info-message {
                color: #856404;
                background: #fff3cd;
                padding: 15px;
                border-radius: 8px;
                margin: 15px 0;
                border: 1px solid #ffeaa7;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎬 AI Video Generator v5.2</h1>
            <p class="subtitle">Fast transcription + smart folder distribution</p>
            
            <div class="tabs">
                <div class="tab active" onclick="switchTab('generate')">Generate Video</div>
                <div class="tab" onclick="switchTab('cache')">Cache Status</div>
                <div class="tab" onclick="switchTab('scan')">Scan Drive</div>
            </div>
            
            <!-- Generate Video Tab -->
            <div id="generateTab" class="tab-content active">
                <div class="feature-list">
                    <h3>✨ How it works (Optimized):</h3>
                    <ul>
                        <li>Fast transcription using pre-loaded Whisper base model</li>
                        <li>Uses cached Google Drive folder structure</li>
                        <li>Gemini AI decides how many clips from each folder</li>
                        <li>Random video selection from chosen folders</li>
                        <li>Creates 3-second clips from selected videos</li>
                        <li>Generates final video with audio</li>
                    </ul>
                </div>
                
                <div id="cacheWarning" class="info-message" style="display: none;">
                    ⚠️ No drive cache found. Please scan drive first!
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
            
            <!-- Cache Status Tab -->
            <div id="cacheTab" class="tab-content">
                <div class="feature-list">
                    <h3>📁 Cache Information:</h3>
                    <p>Video generation uses cached Google Drive folder structure. You must scan your drive first before generating videos.</p>
                </div>
                
                <div id="cacheStatusArea">
                    <div class="step-info">Loading cache status...</div>
                </div>
                
                <div>
                    <button onclick="checkCacheStatus()">🔄 Check Cache Status</button>
                </div>
            </div>
            
            <!-- Scan Drive Tab -->
            <div id="scanTab" class="tab-content">
                <div class="feature-list">
                    <h3>🔍 Scan Google Drive:</h3>
                    <ul>
                        <li>Scans ALL folders and subfolders from your Google Drive</li>
                        <li>Builds folder structure with video counts</li>
                        <li>Saves data to cache for fast video generation</li>
                        <li>No authentication needed for public folders</li>
                        <li>Only needs to be done once (or when you add new videos)</li>
                    </ul>
                </div>
                
                <div>
                    <button id="scanBtn" onclick="scanDrive()">🔍 Scan Drive Now</button>
                </div>
                
                <div id="scanResultArea"></div>
            </div>
        </div>
        
        <script>
            // Tab switching
            function switchTab(tabName) {
                document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
                
                event.target.classList.add('active');
                document.getElementById(tabName + 'Tab').classList.add('active');
                
                if (tabName === 'cache') {
                    checkCacheStatus();
                }
            }
            
            // Check cache status on page load
            async function checkCacheStatus() {
                const cacheStatusArea = document.getElementById('cacheStatusArea');
                cacheStatusArea.innerHTML = '<div class="step-info">Checking cache...</div>';
                
                try {
                    const response = await fetch('/cache-status');
                    const data = await response.json();
                    
                    if (data.success) {
                        if (data.cache_exists) {
                            const sizeMB = (data.cache_size / 1024 / 1024).toFixed(2);
                            cacheStatusArea.innerHTML = `
                                <div class="success-message">
                                    <h3>✅ Cache Available</h3>
                                    <p>File: ${data.cache_file}</p>
                                    <p>Size: ${sizeMB} MB</p>
                                    <p>Total Videos: ${data.total_videos}</p>
                                    <p>Folders with videos: ${data.folders_with_videos}</p>
                                    <p>Cached at: ${new Date(data.cached_at).toLocaleString()}</p>
                                    <p>Status: Ready for video generation</p>
                                </div>
                            `;
                            
                            // Hide cache warning in generate tab
                            document.getElementById('cacheWarning').style.display = 'none';
                        } else {
                            cacheStatusArea.innerHTML = `
                                <div class="error-message">
                                    <h3>❌ No Cache Found</h3>
                                    <p>Please scan your Google Drive first.</p>
                                </div>
                            `;
                            
                            // Show cache warning in generate tab
                            document.getElementById('cacheWarning').style.display = 'block';
                        }
                    } else {
                        cacheStatusArea.innerHTML = `
                            <div class="error-message">
                                <h3>❌ Error</h3>
                                <p>${data.error || data.message}</p>
                            </div>
                        `;
                    }
                } catch (error) {
                    cacheStatusArea.innerHTML = `
                        <div class="error-message">
                            <h3>❌ Connection Error</h3>
                            <p>${error.message}</p>
                        </div>
                    `;
                }
            }
            
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
                
                // Check cache first
                const cacheCheck = await fetch('/cache-status');
                const cacheData = await cacheCheck.json();
                
                if (!cacheData.success || !cacheData.cache_exists) {
                    alert('No drive cache found. Please scan your Google Drive first!');
                    switchTab('scan');
                    return;
                }
                
                showStatus('Starting video generation...', 10);
                generateBtn.disabled = true;
                generateBtn.textContent = 'Processing...';
                
                const formData = new FormData();
                formData.append('audio_file', file);
                
                try {
                    const response = await fetch('/generate-video', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.detail || 'Failed to start');
                    }
                    
                    const data = await response.json();
                    taskId = data.task_id;
                    
                    startPolling();
                    
                } catch (error) {
                    showError(error.message);
                    resetUI();
                }
            }
            
            async function scanDrive() {
                const scanBtn = document.getElementById('scanBtn');
                const scanResultArea = document.getElementById('scanResultArea');
                
                scanResultArea.innerHTML = '<div class="step-info">Scanning Google Drive... This may take several minutes.</div>';
                scanBtn.disabled = true;
                scanBtn.textContent = 'Scanning...';
                
                try {
                    const response = await fetch('/scan-drive');
                    const data = await response.json();
                    
                    if (data.success) {
                        scanResultArea.innerHTML = `
                            <div class="success-message">
                                <h3>✅ Drive Scan Complete!</h3>
                                <p>Total Folders: ${data.total_folders}</p>
                                <p>Total Videos: ${data.total_videos}</p>
                                <p>Total Files: ${data.total_files}</p>
                                <p>Folders with videos: ${data.folders_with_videos}</p>
                                <p>Cache updated and ready for video generation</p>
                                <p>Scan completed at: ${new Date().toLocaleString()}</p>
                            </div>
                        `;
                        
                        // Update cache status
                        checkCacheStatus();
                    } else {
                        scanResultArea.innerHTML = `
                            <div class="error-message">
                                <h3>❌ Scan Failed</h3>
                                <p>${data.error || 'Unknown error'}</p>
                                <p>${data.note || ''}</p>
                            </div>
                        `;
                    }
                } catch (error) {
                    scanResultArea.innerHTML = `
                        <div class="error-message">
                            <h3>❌ Connection Error</h3>
                            <p>${error.message}</p>
                        </div>
                    `;
                }
                
                scanBtn.disabled = false;
                scanBtn.textContent = '🔍 Scan Drive Now';
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
                            stepInfo = `📁 Using ${status.total_videos_found} videos in ${status.folders_with_videos} folders`;
                        }
                        if (status.clips_selected) {
                            progress = 60;
                            stepInfo = `🤖 Gemini distributed ${status.clips_selected} clips across ${status.folders_used || 0} folders`;
                            if (status.distribution_strategy) {
                                stepInfo += `<br>Strategy: ${status.distribution_strategy}`;
                            }
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
                let html = `<div class="success-message">
                    <h3>✅ Video Generated Successfully!</h3>
                    <p>Audio Duration: ${status.audio_duration ? status.audio_duration.toFixed(1) + 's' : 'N/A'}</p>
                    <p>Clips Used: ${status.clips_selected || 'N/A'} (3 seconds each)</p>
                    <p>Folders Used: ${status.folders_used || 'N/A'} out of ${status.folders_with_videos || 'N/A'}</p>
                    <p>Drive Cache: ${status.total_videos_found || 'N/A'} videos available</p>`;
                
                html += `<a href="/download/${taskId}" class="download-link" style="
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
                    </a>`;
                
                html += `</div>`;
                resultArea.innerHTML = html;
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
            }
            
            // Check cache status on page load
            window.onload = function() {
                checkCacheStatus();
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting AI Video Generator API v5.2 on port {port}")
    print(f"🔗 Access at: http://localhost:{port}")
    print(f"📁 Using Google Drive folder ID: {GOOGLE_DRIVE_FOLDER_ID}")
    print(f"💾 Cache file: {JSON_CACHE_FILE}")
    print(f"🤖 Gemini API: {'Configured' if GEMINI_API_KEY else 'NOT CONFIGURED (required)'}")
    print(f"🗣️ Whisper model: {'base (pre-loaded and ready!)' if WHISPER_MODEL else 'NOT LOADED'}")
    print(f"⚡ Features:")
    print(f"  - Whisper base model pre-loaded (fast transcription)")
    print(f"  - Cache-based folder structure (no expiration)")
    print(f"  - Gemini AI for folder distribution only")
    print(f"  - Random video selection from chosen folders")
    print(f"  - 3-second clips based on audio duration")
    print(f"  - Manual cache update via /scan-drive")
    print(f"\n📋 IMPORTANT:")
    print(f"  1. First scan your drive: http://localhost:{port}/#scan")
    print(f"  2. Then generate videos using cached folder structure")
    print(f"  3. Gemini only sees folder names and video counts")
    print(f"  4. Videos are randomly selected from Gemini-chosen folders")
    print(f"  5. Whisper model is already loaded - no wait time!")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        workers=1
    )