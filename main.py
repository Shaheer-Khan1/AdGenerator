"""
AI Video Generator API (Memory-Optimized Edition)
==================================================
Optimized for 2-4GB instances:
- No Whisper (removed - uses ~1-2GB RAM)
- No MoviePy (replaced with FFmpeg subprocess)
- No PIL/ImageDraw (replaced with FFmpeg drawtext)
- Aggressive memory cleanup
- 720p resolution (not 1080p)
- Max 5 clips
- Stream processing only
"""

import os
import requests
import json
import subprocess
import uuid
import shutil
import gc
import re
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn
import imageio_ffmpeg as ffmpeg

from dotenv import load_dotenv
load_dotenv()

# === CONFIGURATION ===
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("VOICE_ID", "KUJ0dDUYhYz8c1Is7Ct6")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_DRIVE_FOLDER_ID = "1l_vWG07Q3tN1UChnlyR40_dZ3McO9NfB"

# Validate required environment variables (make optional for Drive-only mode)
if not ELEVENLABS_API_KEY:
    print("Warning: ELEVENLABS_API_KEY not set - AI voice will not work")

if not GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY not set - AI search query generation will use fallback")

if not PEXELS_API_KEY:
    print("Warning: PEXELS_API_KEY not set - Video search will not work")

# Memory-optimized settings
MIN_CLIPS = 2
MAX_CLIPS = 5  # Reduced from 10
VIDEO_WIDTH = 720  # Reduced from 1080
VIDEO_HEIGHT = 1280  # Reduced from 1920
MAX_CONCURRENT_TASKS = 2  # Limit concurrent processing

# Create directories
TEMP_DIR = Path("temp_videos")
OUTPUT_DIR = Path("output_videos")
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# === PYDANTIC MODELS ===
class VideoGenerationRequest(BaseModel):
    script_text: str = Field(..., description="The script text for voiceover", min_length=10)
    search_query: str = Field(default="technology", description="Search query for relevant video clips")
    voice_id: Optional[str] = Field(default=None, description="ElevenLabs voice ID (optional)")
    callback_url: Optional[str] = Field(default=None, description="If provided, the server will POST the generated video to this URL when done.")

# === CAPTION SETTINGS (Hardcoded) ===
# Subtle, natural captions with word-by-word sync
# Memory impact: ~0MB (just text processing, no ML models)
ADD_CAPTIONS = False  # Disabled - user doesn't want captions
WORDS_PER_CAPTION = 1  # Show 1 word at a time for best sync
CAPTION_FONT_SIZE = 24  # Smaller, more subtle

class VideoGenerationResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str  # "pending", "processing", "completed", "failed"
    progress: str
    error: Optional[str] = None
    output_file: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

# === GLOBAL TASK STORAGE ===
tasks: Dict[str, Dict[str, Any]] = {}
active_tasks = 0  # Track concurrent tasks

# === MEMORY MANAGEMENT ===
def free_memory() -> None:
    """Aggressive garbage collection"""
    gc.collect()
    gc.collect()  # Call twice for thorough cleanup
    gc.collect()

def log_task(task_id: str, message: str) -> None:
    """Log task progress"""
    print(f"[{task_id}] {message}")
    if task_id in tasks:
        tasks[task_id]['progress'] = message

def log_info(title: str, data: Any, indent: int = 0) -> None:
    """Pretty print logging for debugging"""
    prefix = "  " * indent
    print(f"\n{'='*80}")
    if title:
        print(f"{prefix}📋 {title}")
        print(f"{'='*80}")
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                print(f"{prefix}  {key}:")
                log_info("", value, indent + 2)
            else:
                # Truncate long strings
                if isinstance(value, str) and len(value) > 200:
                    display_value = value[:200] + "..."
                else:
                    display_value = value
                print(f"{prefix}  {key}: {display_value}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, str) and len(item) > 200:
                display_item = item[:200] + "..."
            else:
                display_item = item
            print(f"{prefix}  [{i+1}] {display_item}")
    else:
        display_data = str(data)
        if len(display_data) > 200:
            display_data = display_data[:200] + "..."
        print(f"{prefix}{display_data}")
    print(f"{'='*80}\n")

# === FASTAPI APP ===
app = FastAPI(
    title="AI Video Generator API (Memory-Optimized)",
    description="Generate short-form videos optimized for 2-4GB instances",
    version="2.0.0-optimized"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === GOOGLE DRIVE FUNCTIONS (Public Folder Scraping) ===

def scrape_public_drive_folder(folder_id: str):
    """
    Scrape public Google Drive folder to get all subfolders and video files.
    Works without authentication by parsing the public folder HTML.
    """
    try:
        import re
        
        # Get public folder page
        folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(folder_url, headers=headers, timeout=30)
        response.raise_for_status()
        html = response.text
        
        # Extract folder and file data from the page
        # Drive embeds data in a JavaScript object
        # Pattern: ["FILE_ID","FILE_NAME","MIME_TYPE",...]
        
        # Find all file IDs and names in the HTML
        file_pattern = r'\["([a-zA-Z0-9_-]{20,})",\s*"([^"]+)",\s*"([^"]*video[^"]*|[^"]*folder[^"]*)"'
        matches = re.findall(file_pattern, html)
        
        drive_structure = {}
        
        # Since we can't easily distinguish folders from the HTML,
        # let's use a simpler approach: hardcode known folders and scrape each
        known_folders = {
            "Cellulite": None,
            "Glow Coffee": None,
            "Hair": None,
            "Joints": None,
            "Menopause": None,
            "Nails": None,
            "Others": None,
            "Product": None,
            "Wrinkles": None
        }
        
        # For now, let's create a mock structure based on known folders
        # In production, you'd scrape each subfolder or use a service account
        # For quick solution: use direct file IDs if we can extract them
        
        # Fallback: Return structure to let Gemini work with folder names
        for folder_name in known_folders:
            drive_structure[folder_name] = {
                'videos': []  # Will be populated by scraping or manual mapping
            }
        
        print(f"Scraped Drive folder structure: {len(drive_structure)} folders found")
        return drive_structure
        
    except Exception as e:
        print(f"Error scraping Drive folder: {e}")
        return {}

def get_drive_videos_from_mapping():
    """
    Load video mapping from file or return empty structure.
    User should create drive_videos.json with actual video IDs and names.
    """
    mapping_file = Path("drive_videos.json")
    
    if mapping_file.exists():
        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                drive_structure = json.load(f)
            # Count total videos including subfolders
            total_videos = 0
            for folder in drive_structure.values():
                total_videos += len(folder.get('videos', []))
                subfolders = folder.get('subfolders', {})
                for subfolder in subfolders.values():
                    total_videos += len(subfolder.get('videos', []))
            
            log_info("GOOGLE DRIVE - Loaded Video Mapping", {
                "Source": "drive_videos.json",
                "Folders": list(drive_structure.keys()),
                "Total Videos (including subfolders)": total_videos
            })
            return drive_structure
        except Exception as e:
            print(f"Error loading drive_videos.json: {e}")
    
    # Return empty structure if no mapping file
    drive_structure = {
        "Cellulite": {"videos": [], "subfolders": {}},
        "Glow Coffee": {"videos": [], "subfolders": {}},
        "Hair": {"videos": [], "subfolders": {}},
        "Joints": {"videos": [], "subfolders": {}},
        "Menopause": {"videos": [], "subfolders": {}},
        "Nails": {"videos": [], "subfolders": {}},
        "Others": {"videos": [], "subfolders": {}},
        "Product": {"videos": [], "subfolders": {}},
        "Wrinkles": {"videos": [], "subfolders": {}}
    }
    
    log_info("GOOGLE DRIVE - No Mapping File", {
        "Note": "Create drive_videos.json with video IDs and names",
        "Folders": list(drive_structure.keys()),
        "Example Format": {
            "Glow Coffee": {
                "videos": [
                    {"id": "abc123xyz", "name": "coffee_pour_sarah.mp4"}
                ],
                "subfolders": {
                    "Coffee Pouring": {
                        "videos": [
                            {"id": "def456uvw", "name": "pour_closeup.mp4"}
                        ]
                    }
                }
            }
        }
    })
    
    return drive_structure

def list_drive_folders_and_files(folder_id: str):
    """
    List folders and files from public Google Drive.
    Loads actual video files from mapping file if available.
    """
    log_info("GOOGLE DRIVE - Scanning Folder Structure", {
        "Folder ID": folder_id,
        "Folder URL": f"https://drive.google.com/drive/folders/{folder_id}",
        "Method": "Loading from drive_videos.json mapping file"
    })
    
    drive_structure = get_drive_videos_from_mapping()
    
    # Add folder URLs
    for folder_name in drive_structure:
        drive_structure[folder_name]["folder_url"] = f"https://drive.google.com/drive/folders/{folder_id}"
    
    # Calculate total videos including subfolders
    folder_details = {}
    for name, folder in drive_structure.items():
        main_videos = folder.get('videos', [])
        subfolders = folder.get('subfolders', {})
        
        subfolder_info = {}
        total_subfolder_videos = 0
        for subfolder_name, subfolder_data in subfolders.items():
            subfolder_videos = subfolder_data.get('videos', [])
            total_subfolder_videos += len(subfolder_videos)
            if subfolder_videos:
                subfolder_info[subfolder_name] = {
                    "Video Count": len(subfolder_videos),
                    "Video Names": [v.get('name', 'unknown') for v in subfolder_videos[:3]]
                }
        
        folder_details[name] = {
            "Main Folder Videos": len(main_videos),
            "Subfolders": len(subfolders),
            "Subfolder Videos": total_subfolder_videos,
            "Total Videos": len(main_videos) + total_subfolder_videos,
            "Main Video Names": [v.get('name', 'unknown') for v in main_videos[:3]],
            "Subfolder Details": subfolder_info if subfolder_info else "None"
        }
    
    log_info("GOOGLE DRIVE - Found Folders and Videos", {
        "Total Folders": len(drive_structure),
        "Folder Details": folder_details
    })
    
    return drive_structure

async def download_and_cache_drive_folder(folder_id: str = None) -> List[dict]:
    """Download entire Google Drive folder and cache videos locally"""
    try:
        import zipfile
        import shutil
        from pathlib import Path
        
        folder_id = folder_id or GOOGLE_DRIVE_FOLDER_ID
        cache_dir = Path("drive_cache") / folder_id
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if already cached (recursively check all subfolders)
        cached_videos = list(cache_dir.glob("**/*.mp4")) + list(cache_dir.glob("**/*.mov")) + list(cache_dir.glob("**/*.avi")) + list(cache_dir.glob("**/*.mkv")) + list(cache_dir.glob("**/*.webm"))
        if cached_videos:
            log_info("GOOGLE DRIVE - Using Cached Videos", {
                "Folder ID": folder_id,
                "Cached Videos": len(cached_videos),
                "Cache Dir": str(cache_dir)
            })
            
            videos = []
            for video_path in cached_videos:
                # Determine folder_name based on path relative to cache_dir
                relative_path = video_path.relative_to(cache_dir)
                folder_name_from_path = str(relative_path.parent) if str(relative_path.parent) != '.' else ""
                
                videos.append({
                    'id': video_path.stem,  # Use filename as ID
                    'name': video_path.name,
                    'local_path': str(video_path),
                    'cached': True,
                    'folder_name': folder_name_from_path  # Store the folder name for filtering
                })
            return videos
        
        # For folders, we need to use a different approach
        # Try to download individual files or use gdown library
        log_info("GOOGLE DRIVE - Downloading Folder", {
            "Folder ID": folder_id,
            "Note": "Attempting to download folder contents..."
        })
        
        # Use gdown if available, otherwise try direct download
        try:
            import gdown
            # Download folder - gdown has a 50 file limit
            folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
            try:
                # Try with remaining_ok parameter if available (allows partial downloads)
                try:
                    gdown.download_folder(folder_url, output=str(cache_dir), quiet=False, use_cookies=False, remaining_ok=True)
                except TypeError:
                    # remaining_ok not available, try without it
                    gdown.download_folder(folder_url, output=str(cache_dir), quiet=False, use_cookies=False)
            except Exception as e:
                error_msg = str(e)
                # If error is about 50 file limit, try downloading subfolders individually
                if "50 files" in error_msg or "more than 50" in error_msg.lower():
                    log_info("GOOGLE DRIVE - Folder too large", {
                        "Note": "Folder has more than 50 files. Attempting to download subfolders individually...",
                        "Error": error_msg
                    })
                    
                    # Try to extract subfolder IDs from Drive page and download each individually
                    try:
                        try:
                            import requests
                            from bs4 import BeautifulSoup
                        except ImportError:
                            log_info("GOOGLE DRIVE - Missing libraries", {
                                "Note": "Install requests and beautifulsoup4 for subfolder extraction: pip install requests beautifulsoup4"
                            })
                            raise
                        import re
                        
                        # Get the Drive folder page
                        page_url = f"https://drive.google.com/drive/folders/{folder_id}"
                        response = requests.get(page_url, timeout=10)
                        
                        if response.status_code == 200:
                            # Try to extract folder IDs from the page
                            # Google Drive uses data-id attributes or encoded folder IDs in the HTML
                            soup = BeautifulSoup(response.text, 'html.parser')
                            
                            # Look for folder links - they contain the folder ID in the URL
                            folder_links = soup.find_all('a', href=re.compile(r'/drive/folders/([a-zA-Z0-9_-]+)'))
                            
                            subfolder_ids = []
                            seen_names = set()
                            
                            for link in folder_links:
                                href = link.get('href', '')
                                match = re.search(r'/drive/folders/([a-zA-Z0-9_-]+)', href)
                                if match:
                                    sub_id = match.group(1)
                                    # Get folder name from link text or aria-label
                                    folder_name = link.get_text(strip=True) or link.get('aria-label', '') or f"folder_{sub_id}"
                                    
                                    # Avoid duplicates and the main folder
                                    if sub_id != folder_id and sub_id not in [s['id'] for s in subfolder_ids]:
                                        subfolder_ids.append({'id': sub_id, 'name': folder_name})
                            
                            # Download each subfolder
                            if subfolder_ids:
                                log_info("GOOGLE DRIVE - Found Subfolders", {
                                    "Count": len(subfolder_ids),
                                    "Subfolders": [s['name'] for s in subfolder_ids[:5]]  # Show first 5
                                })
                                
                                for subfolder in subfolder_ids:
                                    subfolder_cache = cache_dir / subfolder['name']
                                    subfolder_cache.mkdir(parents=True, exist_ok=True)
                                    
                                    try:
                                        subfolder_url = f"https://drive.google.com/drive/folders/{subfolder['id']}"
                                        gdown.download_folder(subfolder_url, output=str(subfolder_cache), quiet=True, use_cookies=False)
                                        log_info("GOOGLE DRIVE - Subfolder Downloaded", {
                                            "Folder": subfolder['name']
                                        })
                                    except Exception as sub_e:
                                        log_info("GOOGLE DRIVE - Subfolder Download Failed", {
                                            "Folder": subfolder['name'],
                                            "Error": str(sub_e)[:100]  # Truncate long errors
                                        })
                                        continue
                            else:
                                log_info("GOOGLE DRIVE - No Subfolders Found", {
                                    "Note": "Could not extract subfolder IDs from Drive page"
                                })
                        else:
                            log_info("GOOGLE DRIVE - Could not access Drive page", {
                                "Status": response.status_code
                            })
                    except Exception as scrape_e:
                        log_info("GOOGLE DRIVE - Subfolder extraction failed", {
                            "Error": str(scrape_e)[:100],
                            "Note": "Falling back to error message"
                        })
                    
                    # Check if any files were downloaded
                    downloaded = list(cache_dir.glob("**/*.mp4")) + list(cache_dir.glob("**/*.mov")) + list(cache_dir.glob("**/*.avi")) + list(cache_dir.glob("**/*.mkv")) + list(cache_dir.glob("**/*.webm"))
                    if not downloaded:
                        log_info("GOOGLE DRIVE - No files downloaded", {
                            "Note": "gdown cannot download folders with more than 50 files. Please organize videos into smaller subfolders (max 50 files each)."
                        })
                        return []
                else:
                    log_info("GOOGLE DRIVE - Download failed", {
                        "Error": error_msg,
                        "Note": "Make sure folder is shared/public"
                    })
                    return []
        except ImportError:
            # Fallback: try to get file list and download individually
            log_info("GOOGLE DRIVE - gdown not available", {
                "Note": "Install gdown: pip install gdown"
            })
            return []
        except Exception as e:
            log_info("GOOGLE DRIVE - Download failed", {
                "Error": str(e),
                "Note": "Make sure folder is shared/public"
            })
            return []
        
        # Get downloaded videos (recursively)
        cached_videos = list(cache_dir.glob("**/*.mp4")) + list(cache_dir.glob("**/*.mov")) + list(cache_dir.glob("**/*.avi")) + list(cache_dir.glob("**/*.mkv")) + list(cache_dir.glob("**/*.webm"))
        
        videos = []
        for video_path in cached_videos:
            # Determine folder_name based on path relative to cache_dir
            relative_path = video_path.relative_to(cache_dir)
            folder_name_from_path = str(relative_path.parent) if str(relative_path.parent) != '.' else ""
            
            videos.append({
                'id': video_path.stem,
                'name': video_path.name,
                'local_path': str(video_path),
                'cached': True,
                'folder_name': folder_name_from_path  # Store the folder name for filtering
            })
        
        log_info("GOOGLE DRIVE - Folder Cached", {
            "Folder ID": folder_id,
            "Videos Downloaded": len(videos),
            "Cache Dir": str(cache_dir)
        })
        
        return videos
        
    except Exception as e:
        log_info("GOOGLE DRIVE - Cache Error", {
            "Error": str(e),
            "Note": "Cannot download folder. Make sure folder is shared/public."
        })
        return []

async def fetch_videos_from_drive_folder(folder_name: str, folder_id: str = None) -> List[dict]:
    """Fetch video IDs directly from Google Drive folder by scraping the folder page (no API needed)"""
    try:
        import re
        import asyncio
        
        # Get folder ID by searching in main folder
        if not folder_id:
            # First, get the main folder page
            main_folder_url = f"https://drive.google.com/drive/folders/{GOOGLE_DRIVE_FOLDER_ID}"
            
            # Fetch the main folder page
            response = requests.get(main_folder_url, timeout=30)
            if response.status_code != 200:
                log_info(f"GOOGLE DRIVE - Cannot access folder", {
                    "Folder Name": folder_name,
                    "Main Folder ID": GOOGLE_DRIVE_FOLDER_ID,
                    "Error": f"HTTP {response.status_code}"
                })
                return []
            
            # Parse HTML to find folder by name
            html = response.text
            
            # Google Drive stores folder data in window['_DRIVE_ivd'] or similar JSON structures
            # Look for folder name in the page
            folder_pattern = rf'"{re.escape(folder_name)}"[^}}]*"id":"([a-zA-Z0-9_-]+)"'
            matches = re.findall(folder_pattern, html)
            
            if not matches:
                # Try alternative pattern - Google Drive uses different formats
                # Look for folder links
                folder_link_pattern = rf'/drive/folders/([a-zA-Z0-9_-]+)[^"]*"[^>]*>{re.escape(folder_name)}'
                matches = re.findall(folder_link_pattern, html)
            
            if not matches:
                log_info(f"GOOGLE DRIVE - Folder not found in main folder", {
                    "Folder Name": folder_name,
                    "Main Folder ID": GOOGLE_DRIVE_FOLDER_ID,
                    "HTML Preview": html[:500] if len(html) > 500 else html,
                    "Note": "Cannot find folder in Drive. Make sure folder name matches exactly and folder is accessible."
                })
                return []
            
            folder_id = matches[0]
            log_info(f"GOOGLE DRIVE - Found Folder", {
                "Folder Name": folder_name,
                "Folder ID": folder_id
            })
        
        # Now fetch videos from the found folder
        folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
        response = requests.get(folder_url, timeout=30)
        
        if response.status_code != 200:
            log_info(f"GOOGLE DRIVE - Cannot access folder", {
                "Folder": folder_name,
                "Folder ID": folder_id,
                "Error": f"HTTP {response.status_code}"
            })
            return []
        
        html = response.text
        all_videos = []
        
        # Extract video file IDs and names from the page
        # Google Drive stores file data in various formats - try multiple patterns
        
        # Pattern 1: Look for video file links with IDs (most common)
        video_pattern = r'/file/d/([a-zA-Z0-9_-]{20,})'
        video_id_matches = re.findall(video_pattern, html)
        
        # Pattern 2: Look for file names near IDs
        # Try to find video file extensions
        video_extensions = r'\.(mp4|mov|avi|mkv|webm|wmv|flv|m4v)'
        video_name_pattern = rf'([^"<>]*{video_extensions})'
        video_name_matches = re.findall(video_name_pattern, html, re.IGNORECASE)
        
        # Pattern 3: Look in script tags for JSON data (Google Drive embeds data here)
        script_pattern = r'<script[^>]*>(.*?)</script>'
        scripts = re.findall(script_pattern, html, re.DOTALL)
        
        for script in scripts:
            # Look for file IDs in script content
            script_ids = re.findall(r'["\']([a-zA-Z0-9_-]{20,})["\']', script)
            for file_id in script_ids:
                # Check if there's a video extension nearby
                context = script[max(0, script.find(file_id)-50):script.find(file_id)+100]
                if re.search(video_extensions, context, re.IGNORECASE):
                    # Try to find name
                    name_match = re.search(rf'["\']([^"\']*{video_extensions})["\']', context, re.IGNORECASE)
                    video_name = name_match.group(1) if name_match else f"video_{file_id[:8]}.mp4"
                    all_videos.append({
                        'id': file_id,
                        'name': video_name.strip(),
                        'folder_name': folder_name
                    })
        
        # Add IDs found from pattern 1
        for video_id in video_id_matches:
            if video_id not in [v['id'] for v in all_videos]:
                # Try to find a name for this ID
                name_context = html[max(0, html.find(video_id)-100):html.find(video_id)+200]
                name_match = re.search(rf'["\']([^"\']*{video_extensions})["\']', name_context, re.IGNORECASE)
                video_name = name_match.group(1) if name_match else f"video_{video_id[:8]}.mp4"
                all_videos.append({
                    'id': video_id,
                    'name': video_name.strip(),
                    'folder_name': folder_name
                })
        
        # Remove duplicates
        seen_ids = set()
        unique_videos = []
        for video in all_videos:
            if video['id'] not in seen_ids:
                seen_ids.add(video['id'])
                unique_videos.append(video)
        
        log_info(f"GOOGLE DRIVE - Fetched Videos (No API)", {
            "Folder": folder_name,
            "Folder ID": folder_id,
            "Total Videos Found": len(unique_videos),
            "HTML Length": len(html),
            "Source": "Web scraping (no API credentials needed)"
        })
        
        if len(unique_videos) == 0:
            log_info(f"GOOGLE DRIVE - No Videos Found", {
                "Folder": folder_name,
                "Note": "Web scraping may not work if folder requires authentication. Consider making folder public or using Google Drive API."
            })
        
        return unique_videos
        
    except Exception as e:
        log_info(f"GOOGLE DRIVE - Error", {
            "Folder": folder_name,
            "Error": str(e),
            "Note": "Cannot fetch from Drive. Make sure folder is accessible."
        })
        return []

def detect_actress_name(video_name: str) -> Optional[str]:
    """Detect actress name from video filename"""
    import re
    # Common patterns: name_video.mp4, video_name.mp4, name-surname_video.mp4
    # Look for capitalized words that might be names
    patterns = [
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',  # First Last or FirstLast
        r'([A-Z][a-z]+_[A-Z][a-z]+)',  # First_Last
        r'([A-Z][a-z]+-[A-Z][a-z]+)',  # First-Last
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, video_name)
        if matches:
            # Filter out common non-name words
            exclude_words = {'Video', 'Clip', 'Footage', 'Scene', 'Shot', 'Product', 'Coffee', 'Glow'}
            potential_names = [m for m in matches if m not in exclude_words]
            if potential_names:
                return potential_names[0].replace('_', ' ').replace('-', ' ')
    return None

async def fetch_drive_video_ids(folder_id: str, folder_name: str = "") -> List[dict]:
    """
    Fetch video IDs from a Google Drive folder by scraping the folder page.
    Returns list of dicts with 'id' and 'name' keys.
    """
    try:
        import requests
        import re
        
        folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
        
        log_info(f"GOOGLE DRIVE - Fetching video IDs from folder", {
            "Folder": folder_name or folder_id,
            "URL": folder_url
        })
        
        response = requests.get(folder_url, timeout=30)
        response.raise_for_status()
        html = response.text
        
        all_videos = []
        
        # Pattern 1: Look for video file IDs
        video_pattern = r'/file/d/([a-zA-Z0-9_-]{25,})'
        video_id_matches = re.findall(video_pattern, html)
        
        # Pattern 2: Look for file names with video extensions
        video_extensions = r'\.(mp4|mov|avi|mkv|webm|wmv|flv|m4v)'
        video_name_pattern = rf'([^"<>]*{video_extensions})'
        video_name_matches = re.findall(video_name_pattern, html, re.IGNORECASE)
        
        # Pattern 3: Look in script tags for JSON data
        script_pattern = r'<script[^>]*>(.*?)</script>'
        scripts = re.findall(script_pattern, html, re.DOTALL)
        
        for script in scripts:
            # Look for file IDs with video extensions nearby
            script_ids = re.findall(r'["\']([a-zA-Z0-9_-]{25,})["\']', script)
            for file_id in script_ids:
                # Check if there's a video extension nearby
                context = script[max(0, script.find(file_id)-100):script.find(file_id)+200]
                if re.search(video_extensions, context, re.IGNORECASE):
                    # Try to find name
                    name_match = re.search(rf'["\']([^"\']*{video_extensions})["\']', context, re.IGNORECASE)
                    video_name = name_match.group(1) if name_match else f"video_{file_id[:8]}.mp4"
                    
                    # Avoid duplicates
                    if file_id not in [v['id'] for v in all_videos]:
                        all_videos.append({
                            'id': file_id,
                            'name': video_name.strip(),
                            'folder_name': folder_name
                        })
        
        # Add IDs from pattern 1
        for video_id in video_id_matches:
            if video_id not in [v['id'] for v in all_videos]:
                # Try to find a name for this ID
                name_context = html[max(0, html.find(video_id)-200):html.find(video_id)+300]
                name_match = re.search(rf'["\']([^"\']*{video_extensions})["\']', name_context, re.IGNORECASE)
                video_name = name_match.group(1) if name_match else f"video_{video_id[:8]}.mp4"
                all_videos.append({
                    'id': video_id,
                    'name': video_name.strip(),
                    'folder_name': folder_name
                })
        
        log_info(f"GOOGLE DRIVE - Found videos", {
            "Folder": folder_name or folder_id,
            "Count": len(all_videos),
            "Source": "Web scraping"
        })
        
        return all_videos
        
    except Exception as e:
        log_info(f"GOOGLE DRIVE - Error fetching video IDs", {
            "Folder": folder_name or folder_id,
            "Error": str(e)
        })
        return []

def get_video_duration(video_path: str) -> float:
    """Get video duration using FFmpeg"""
    try:
        exe = ffmpeg.get_ffmpeg_exe()
        cmd = [exe, "-i", video_path]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        
        match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
        if not match:
            return 5.0  # Default fallback duration
        
        h, m, s = map(float, match.groups())
        return h * 3600 + m * 60 + s
    except Exception as e:
        return 5.0  # Default fallback

async def download_specific_videos_from_folder(folder_name: str, num_videos: int = 5, target_duration: float = None) -> List[dict]:
    """
    Select videos from already downloaded Drive cache.
    - Flexible folder matching (handles renamed folders)
    - Selects videos based on audio duration if provided
    - Avoids repeating scenes (checks video names/paths for uniqueness)
    """
    try:
        import random
        from pathlib import Path
        
        main_folder_id = GOOGLE_DRIVE_FOLDER_ID
        cache_base = Path("drive_cache") / main_folder_id
        
        # Also check root drive_cache in case structure changed
        if not cache_base.exists():
            cache_base = Path("drive_cache")
        
        print(f"   🔍 Searching for videos in cache matching '{folder_name}'...")
        
        # Find all videos in the cache (recursively)
        all_videos = (
            list(cache_base.glob("**/*.mp4")) + 
            list(cache_base.glob("**/*.mov")) + 
            list(cache_base.glob("**/*.avi")) + 
            list(cache_base.glob("**/*.mkv")) + 
            list(cache_base.glob("**/*.webm"))
        )
        
        print(f"   📊 Found {len(all_videos)} total videos in cache")
        
        # Flexible folder matching - check multiple strategies
        matching_videos = []
        folder_lower = folder_name.lower()
        
        # Strategy 1: Exact match in path
        for video_path in all_videos:
            path_str = str(video_path).lower()
            if folder_lower in path_str:
                matching_videos.append(video_path)
        
        # Strategy 2: Match in parent folder names (if Strategy 1 found nothing)
        if not matching_videos:
            for video_path in all_videos:
                for parent in video_path.parents:
                    if parent.name and folder_lower in parent.name.lower():
                        matching_videos.append(video_path)
                        break
        
        # Strategy 3: Partial word matching (e.g., "wrinkle" matches "Wrinkles")
        if not matching_videos:
            # Split folder name into words
            folder_words = folder_lower.split()
            for video_path in all_videos:
                path_str = str(video_path).lower()
                # Check if any word from folder name appears in path
                if any(word in path_str for word in folder_words if len(word) > 3):
                    matching_videos.append(video_path)
        
        # Remove duplicates
        matching_videos = list(set(matching_videos))
        
        if not matching_videos:
            log_info(f"GOOGLE DRIVE - No videos found matching {folder_name}", {
                "Total Videos": len(all_videos),
                "Cache Path": str(cache_base),
                "Note": "Folder name might not match cache folder structure"
            })
            print(f"   ❌ No videos found for folder '{folder_name}'")
            
            # Show available folder names for debugging
            available_folders = set()
            for v in all_videos[:50]:  # Check more videos
                for parent in v.parents:
                    if parent.name and parent.name != main_folder_id and len(parent.name) > 2:
                        available_folders.add(parent.name)
            if available_folders:
                print(f"   💡 Available folders in cache: {', '.join(sorted(list(available_folders))[:15])}")
            
            return []
        
        print(f"   ✅ Found {len(matching_videos)} videos matching '{folder_name}'")
        
        # Get video durations and filter out duplicates/repeating scenes
        video_info = []
        seen_scenes = set()  # Track unique scenes to avoid repeats
        
        for video_path in matching_videos:
            # Extract scene identifier (filename without extension, or base name)
            scene_id = video_path.stem.lower()
            
            # Check for repeating scenes - skip if we've seen similar scene
            is_duplicate = False
            for seen in seen_scenes:
                # Check if scenes are too similar (same base name or very similar)
                if scene_id == seen or (len(scene_id) > 10 and scene_id[:10] == seen[:10]):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                try:
                    duration = get_video_duration(str(video_path))
                    video_info.append({
                        'path': video_path,
                        'duration': duration,
                        'scene_id': scene_id
                    })
                    seen_scenes.add(scene_id)
                except Exception as e:
                    # If duration check fails, use default
                    video_info.append({
                        'path': video_path,
                        'duration': 5.0,
                        'scene_id': scene_id
                    })
                    seen_scenes.add(scene_id)
        
        if not video_info:
            print(f"   ⚠️  No unique videos found after filtering duplicates")
            return []
        
        # Select videos based on duration if target_duration is provided
        if target_duration and target_duration > 0:
            # Optimized: Select minimum videos needed to cover duration
            # Each clip will be 2-3 seconds (varied), so we need fewer videos
            # Average clip duration: 2.5 seconds
            avg_clip_duration = 2.5
            clips_needed = int(target_duration / avg_clip_duration) + 1
            
            # We'll cycle through videos, so we need fewer videos
            # Minimum 3 videos for variety, but optimize based on duration
            videos_needed = max(3, min(clips_needed // 2, len(video_info)))
            # For longer videos, we can use fewer videos (cycle through them)
            if target_duration > 15:
                videos_needed = max(3, min(5, len(video_info)))  # Max 5 videos for longer content
            
            num_to_select = min(videos_needed, len(video_info))
            
            print(f"   ⏱️  Target duration: {target_duration:.1f}s")
            print(f"   🎯 Optimized selection: {num_to_select} videos (will cycle with 2-3s clips)")
            
            # Select diverse videos (shuffle for randomness)
            random.shuffle(video_info)
            selected_info = video_info[:num_to_select]
            
            total_duration = sum(v['duration'] for v in selected_info)
            print(f"   📏 Selected videos total duration: {total_duration:.1f}s")
        else:
            # No duration target - just select random videos
            num_to_select = min(num_videos, len(video_info))
            selected_info = random.sample(video_info, num_to_select)
            print(f"   🎲 Randomly selected {num_to_select} videos")
        
        # Create video objects
        videos = []
        for vid_info in selected_info:
            video_path = vid_info['path']
            videos.append({
                'id': video_path.stem,
                'name': video_path.name,
                'local_path': str(video_path),
                'duration': vid_info['duration'],
                'cached': True,
                'folder_name': folder_name
            })
            print(f"      📹 {video_path.name} ({vid_info['duration']:.1f}s)")
        
        log_info(f"GOOGLE DRIVE - Selected videos from cache", {
            "Folder": folder_name,
            "Available": len(matching_videos),
            "Selected": len(videos),
            "Total Duration": sum(v.get('duration', 0) for v in videos),
            "Source": "Existing cache (no download needed)"
        })
        
        return videos
        
    except Exception as e:
        log_info(f"GOOGLE DRIVE - Error selecting videos from cache", {
            "Folder": folder_name,
            "Error": str(e)
        })
        print(f"   ❌ Error: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return []

async def get_exact_videos_from_gemini(transcription: str, drive_structure: dict, audio_duration: float = None) -> dict:
    """Use Gemini to select relevant FOLDERS, then randomly pick videos from those folders"""
    
    def are_semantically_similar(folder_name: str, gemini_response: str) -> bool:
        """Check if folder name and Gemini response are semantically similar (e.g., Kollagen=Collagen)"""
        # Common semantic mappings (English/German/variations)
        semantic_pairs = {
            'collagen': ['kollagen', 'colágeno'],
            'hair': ['haar', 'cabello', 'pelo'],
            'skin': ['haut', 'piel'],
            'nails': ['nägel', 'nagel', 'uñas'],
            'joints': ['gelenke', 'articulaciones'],
            'wrinkles': ['falten', 'arrugas'],
            'cellulite': ['zellulitis', 'celulitis'],
            'menopause': ['menopause', 'menopausia', 'wechseljahre'],
            'glow': ['glanz', 'brillo'],
            'coffee': ['kaffee', 'café']
        }
        
        folder_lower = folder_name.lower()
        response_lower = gemini_response.lower()
        
        # Check direct match
        if folder_lower in response_lower or response_lower in folder_lower:
            return True
        
        # Check semantic pairs
        for english_term, variations in semantic_pairs.items():
            # If folder contains English term
            if english_term in folder_lower:
                # Check if response contains any variation
                if any(var in response_lower for var in variations):
                    return True
            # If folder contains a variation
            if any(var in folder_lower for var in variations):
                # Check if response contains English term
                if english_term in response_lower:
                    return True
        
        return False
    
    try:
        import google.generativeai as genai
        import random
        
        log_info("GEMINI AI - Initializing for Folder Selection", {
            "Model": "gemini-2.5-flash",
            "Purpose": "Select relevant folders based on transcription"
        })
        
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Build folder list - just folder names (videos will be fetched from Drive API)
        folder_list_text = ""
        
        for folder_name in drive_structure.keys():
            folder_list_text += f"\n📁 {folder_name}"
        
        if not drive_structure:
            log_info("GEMINI AI - No Folders Found", {
                "Note": "No folders found in drive_videos.json"
            })
            return {
                'folders': [{'name': 'Others', 'videos': []}],
                'product_mentioned': None,
                'actress_name': None,
                'raw_response': 'No folders found'
            }
        
        # Calculate approximate timing for transcription
        words = transcription.split()
        words_per_second = 2.5  # Average speaking rate
        estimated_duration = len(words) / words_per_second if audio_duration is None else audio_duration
        
        prompt = f"""You are analyzing a voiceover transcription to create a TIMELINE that maps specific topics to video folders.

Transcription: "{transcription}"
Estimated Audio Duration: {estimated_duration:.1f} seconds

Available folders in Google Drive:
{folder_list_text}

CRITICAL INSTRUCTIONS:
1. **Timeline Analysis**: Analyze the transcription and identify WHEN different topics are mentioned:
   - Break down the transcription into segments (e.g., 0-4s, 4-8s, etc.)
   - Identify which folder is most relevant for EACH segment
   - Example: If transcription says "I have wrinkles" (0-2s) then "try this product" (2-5s), map:
     * 0-2s → Wrinkles folder
     * 2-5s → Product folder

2. **Topic-to-Folder Mapping**: Match topics to folders:
   - "skin", "wrinkles", "face", "haut" → Wrinkles folder
   - "product", "supplement", "cream", "bottle" → Product folder
   - "hair", "haar", "cheveux" → Hair folder
   - "joints", "gelenke", "articulations" → Joints folder
   - Product names (e.g., "Glow Coffee") → Glow Coffee folder
   - Match by MEANING, not just exact spelling

3. **Select 2 Primary Folders**: Based on the timeline, select the 2 MOST USED folders:
   - These are the folders that appear most frequently in the timeline
   - Quality over quantity - ONLY the top 2 folders

4. **Video Distribution**: Indicate how videos should be distributed:
   - First folder: How many videos (3-5)
   - Second folder: How many videos (3-5)

Respond in this EXACT format:

PRODUCT_MENTIONED: [Product/Brand name if mentioned, otherwise "None"]

TIMELINE:
0-Xs: [FolderName] - [Brief description of what's mentioned]
Xs-Ys: [FolderName] - [Brief description]
Ys-Zs: [FolderName] - [Brief description]
(Continue for all segments)

FOLDER: FolderName1
RELEVANCE: High
VIDEOS_TO_USE: 5
TIMELINE_SEGMENTS: [List of time ranges where this folder should be used, e.g., "0-3s, 6-9s"]

FOLDER: FolderName2
RELEVANCE: Medium
VIDEOS_TO_USE: 4
TIMELINE_SEGMENTS: [List of time ranges where this folder should be used, e.g., "3-6s, 9-12s"]

Example 1 (Product mentioned):
Transcription: "Entdecken Sie Glow Coffee, das revolutionäre Kollagen für strahlende Haut"
PRODUCT_MENTIONED: Glow Coffee

FOLDER: Glow Coffee
RELEVANCE: High
VIDEOS_TO_USE: 5

FOLDER: Wrinkles (matches "Haut" = "Skin")
RELEVANCE: Medium
VIDEOS_TO_USE: 4

Example 2 (Generic topic):
Transcription: "Bekommen Sie schöne glänzende Haare mit unserem Produkt"
PRODUCT_MENTIONED: None

FOLDER: Hair (matches "Haare")
RELEVANCE: High
VIDEOS_TO_USE: 5

FOLDER: Product
RELEVANCE: Medium
VIDEOS_TO_USE: 3

Now analyze and select folders:"""
        
        log_info("GEMINI AI - Sending Folder Selection Request", {
            "Transcription": transcription[:200],
            "Total Folders Available": len(drive_structure),
            "Folder List": folder_list_text
        })
        
        response = model.generate_content(prompt)
        raw_response = response.text.strip()
        
        log_info("GEMINI AI - Received Response", {
            "Raw Response": raw_response
        })
        
        # Parse response - extract product name, folder names, timeline, and video counts
        selected_folder_names = []
        product_mentioned = None
        folder_video_counts = {}  # Map folder name to requested video count
        folder_timeline_segments = {}  # Map folder name to time segments when it should be used
        
        current_folder = None
        timeline_mode = False
        
        for line in raw_response.split('\n'):
            line = line.strip()
            
            if line.startswith('PRODUCT_MENTIONED:'):
                product = line.replace('PRODUCT_MENTIONED:', '').strip()
                if product.lower() not in ['none', 'n/a', '']:
                    product_mentioned = product
                    
            elif line.startswith('TIMELINE:'):
                timeline_mode = True
                continue
                
            elif line.startswith('FOLDER:'):
                timeline_mode = False
                folder_name = line.replace('FOLDER:', '').strip()
                # Validate folder name with semantic matching
                for valid_folder in drive_structure.keys():
                    if (valid_folder.lower() in folder_name.lower() or 
                        folder_name.lower() in valid_folder.lower() or
                        are_semantically_similar(valid_folder, folder_name)):
                        if valid_folder not in selected_folder_names:
                            selected_folder_names.append(valid_folder)
                        current_folder = valid_folder
                        break
                        
            elif line.startswith('VIDEOS_TO_USE:') and current_folder:
                try:
                    count = int(line.replace('VIDEOS_TO_USE:', '').strip())
                    folder_video_counts[current_folder] = count
                except:
                    folder_video_counts[current_folder] = 5  # Default
                    
            elif line.startswith('TIMELINE_SEGMENTS:') and current_folder:
                # Parse timeline segments like "0-3s, 6-9s"
                segments_str = line.replace('TIMELINE_SEGMENTS:', '').strip()
                segments = []
                for seg in segments_str.split(','):
                    seg = seg.strip()
                    # Parse "0-3s" or "0-3" format
                    if '-' in seg and 's' in seg:
                        try:
                            start, end = seg.replace('s', '').split('-')
                            segments.append((float(start.strip()), float(end.strip())))
                        except:
                            pass
                if segments:
                    folder_timeline_segments[current_folder] = segments
                    
            elif timeline_mode and current_folder and ('-' in line or 's' in line.lower()):
                # Parse timeline entries like "0-4s: Wrinkles - description"
                if ':' in line:
                    time_part = line.split(':')[0].strip()
                    if '-' in time_part and 's' in time_part:
                        try:
                            time_part = time_part.replace('s', '').strip()
                            start, end = time_part.split('-')
                            start_time = float(start.strip())
                            end_time = float(end.strip())
                            # Store this segment for the folder mentioned in the description
                            desc_part = line.split(':', 1)[1] if ':' in line else ''
                            for valid_folder in drive_structure.keys():
                                if valid_folder.lower() in desc_part.lower():
                                    if valid_folder not in folder_timeline_segments:
                                        folder_timeline_segments[valid_folder] = []
                                    folder_timeline_segments[valid_folder].append((start_time, end_time))
                                    break
                        except:
                            pass
        
        # Limit to 2 folders maximum
        selected_folder_names = selected_folder_names[:2]
        
        # If no folders found, fallback to Others
        if not selected_folder_names:
            selected_folder_names = ['Others']
            folder_video_counts['Others'] = random.randint(3, 5)
        
        log_info("GEMINI AI - Folders Selected", {
            "Product Mentioned": product_mentioned or "None",
            "Selected Folders": selected_folder_names,
            "Video Counts Per Folder": folder_video_counts
        })
        
        # Download specific videos from each selected folder (not entire folders)
        selected_folders = []
        
        for folder_name in selected_folder_names:
            # Get video count for this folder (3-5 videos)
            num_videos = folder_video_counts.get(folder_name, random.randint(3, 5))
            num_videos = min(max(3, num_videos), 5)  # Clamp between 3-5
            
            print(f"\n📁 FOLDER SELECTED: {folder_name}")
            if audio_duration:
                print(f"   Selecting videos based on audio duration ({audio_duration:.1f}s)...\n")
            else:
                print(f"   Selecting {num_videos} random videos from this folder...\n")
            
            # Download specific videos from this folder
            # Pass audio duration for duration-based selection
            folder_videos = await download_specific_videos_from_folder(folder_name, num_videos, audio_duration)
            
            if folder_videos:
                # Get timeline segments for this folder
                timeline_segments = folder_timeline_segments.get(folder_name, [])
                
                selected_folders.append({
                    'name': folder_name,
                    'videos': folder_videos,
                    'timeline_segments': timeline_segments  # Store when to use this folder
                })
                
                print(f"✅ FOLDER: {folder_name}")
                if timeline_segments:
                    print(f"   Timeline: {timeline_segments}")
                print(f"   Selected {len(folder_videos)} videos:")
                for v in folder_videos:
                    print(f"   📹 {v.get('name', 'unknown')}")
                print()
                
                log_info(f"FOLDER: {folder_name} - Selected Videos", {
                    "Selected Count": len(folder_videos),
                    "Timeline Segments": timeline_segments,
                    "Selected Videos": [v.get('name', 'unknown') for v in folder_videos],
                    "Source": "Downloaded from Drive folder"
                })
            else:
                selected_folders.append({
                    'name': folder_name,
                    'videos': [],
                    'timeline_segments': folder_timeline_segments.get(folder_name, [])
                })
                print(f"⚠️  FOLDER: {folder_name} - No videos found\n")
                log_info(f"FOLDER: {folder_name} - No Videos", {
                    "Note": "Could not download videos from this folder"
                })
        
        result = {
            'folders': selected_folders,
            'product_mentioned': product_mentioned,
            'actress_name': None,
            'raw_response': raw_response
        }
        
        log_info("GEMINI AI - Final Selection", {
            "Product Mentioned": product_mentioned or "None",
            "Selected Folders": [f['name'] for f in result['folders']],
            "Total Videos Selected": sum(len(f['videos']) for f in result['folders']),
            "Videos Per Folder": {f['name']: len(f['videos']) for f in result['folders']}
        })
        
        return result
        
    except Exception as e:
        log_info("GEMINI AI - Error", {
            "Error": str(e),
            "Fallback": "Others"
        })
        return {
            'folders': [{'name': 'Others', 'videos': []}],
            'actress_name': None,
            'raw_response': f'Error: {str(e)}'
        }
# === VIDEO PROCESSING FUNCTIONS ===
async def search_pexels_videos(query: str, num_clips: int):
    """Fetch video clips from Pexels API"""
    log_info("PEXELS - Searching Videos", {
        "Query": query,
        "Requested Clips": num_clips,
        "API Endpoint": "https://api.pexels.com/videos/search",
        "API Key": f"{PEXELS_API_KEY[:10]}...{PEXELS_API_KEY[-5:]}" if PEXELS_API_KEY else "NOT SET"
    })
    
    url = f"https://api.pexels.com/videos/search?query={query}&per_page={min(num_clips, 15)}"
    headers = {"Authorization": PEXELS_API_KEY}
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
        
        log_info("PEXELS - API Response", {
            "Status Code": response.status_code,
            "Total Results": data.get('total_results', 0),
            "Page": data.get('page', 1),
            "Per Page": data.get('per_page', 0),
            "Videos Found": len(data.get('videos', []))
        })
        
        videos = []
        for i, v in enumerate(data.get('videos', [])[:num_clips]):
            video_files = v.get('video_files', [])
            if video_files:
                video_url = video_files[0]['link']
                videos.append(video_url)
                log_info(f"PEXELS - Video {i+1}", {
                    "Video ID": v.get('id'),
                    "Duration": v.get('duration'),
                    "URL": video_url,
                    "Quality": video_files[0].get('quality', 'unknown')
                })
        
        if not videos:
            raise Exception(f"No videos found for: {query}")
        
        log_info("PEXELS - Final Selection", {
            "Total Videos Selected": len(videos),
            "Video URLs": videos
        })
        
        return videos
    except Exception as e:
        raise Exception(f"Pexels API error: {e}")

async def download_drive_videos(video_ids: List[dict], task_id: str):
    """Download specific videos from Google Drive using video IDs"""
    task_dir = TEMP_DIR / task_id
    task_dir.mkdir(exist_ok=True)
    paths = []
    
    for i, video_info in enumerate(video_ids):
        video_id = video_info.get('id')
        video_name = video_info.get('name', f'drive_video_{i+1}')
        
        if not video_id:
            continue
        
        try:
            # Google Drive direct download URL
            download_url = f"https://drive.google.com/uc?export=download&id={video_id}"
            
            out_path = task_dir / f"drive_{i+1}_{video_name}"
            log_task(task_id, f"Downloading from Drive: {video_name} ({i+1}/{len(video_ids)})")
            
            # First request to get confirmation page (for large files)
            session = requests.Session()
            response = session.get(download_url, stream=True, timeout=60)
            
            # Handle Google Drive virus scan warning
            if 'virus scan warning' in response.text.lower():
                # Extract confirm token
                import re
                confirm_match = re.search(r'confirm=([^&]+)', response.text)
                if confirm_match:
                    confirm_token = confirm_match.group(1)
                    download_url = f"https://drive.google.com/uc?export=download&id={video_id}&confirm={confirm_token}"
                    response = session.get(download_url, stream=True, timeout=60)
            
            response.raise_for_status()
            
            with open(out_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            paths.append(str(out_path))
            log_task(task_id, f"Downloaded: {video_name}")
        except Exception as e:
            print(f"Failed to download video {video_name} (ID: {video_id}): {e}")
            continue
    
    if not paths:
        raise Exception("Failed to download any videos from Drive")
    
    free_memory()
    return paths

async def download_videos(video_urls: List[str], task_id: str):
    """Download videos with streaming to minimize memory"""
    task_dir = TEMP_DIR / task_id
    task_dir.mkdir(exist_ok=True)
    paths = []
    
    for i, url in enumerate(video_urls):
        out_path = task_dir / f"clip_{i+1}.mp4"
        log_task(task_id, f"Downloading clip {i+1}/{len(video_urls)}")
        
        try:
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(out_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                paths.append(str(out_path))
        except Exception as e:
            print(f"Download failed for clip {i+1}: {e}")
            continue
    
    if not paths:
        raise Exception("Failed to download any videos")
    
    free_memory()
    return paths

def convert_to_vertical(input_path: str, output_path: str):
    """Convert video to vertical format using FFmpeg - memory efficient"""
    exe = ffmpeg.get_ffmpeg_exe()
    cmd = [
        exe, "-y", "-i", input_path,
        "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k",
        output_path
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg convert failed: {e.stderr}"
        print(error_msg)
        raise Exception(error_msg)

async def convert_videos_to_vertical(paths: List[str], task_id: str):
    """Convert all videos to vertical format"""
    task_dir = TEMP_DIR / task_id
    converted = []
    
    for i, path in enumerate(paths):
        out_path = task_dir / f"vertical_{i+1}.mp4"
        log_task(task_id, f"Converting {i+1}/{len(paths)} to vertical")
        
        try:
            convert_to_vertical(path, str(out_path))
            converted.append(str(out_path))
            # Delete original to save space
            Path(path).unlink(missing_ok=True)
            free_memory()
        except Exception as e:
            print(f"Conversion failed for clip {i+1}: {e}")
            continue
    
    if not converted:
        raise Exception("Failed to convert any videos")
    
    return converted

async def generate_voiceover(script_text: str, task_id: str, voice_id: Optional[str]):
    """Generate voiceover using ElevenLabs API"""
    task_dir = TEMP_DIR / task_id
    task_dir.mkdir(exist_ok=True)
    output_file = task_dir / "voice.mp3"
    
    voice = voice_id or VOICE_ID
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/stream"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg"
    }
    payload = {
        "text": script_text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {"stability": 0.7, "similarity_boost": 0.7}
    }
    
    try:
        log_task(task_id, "Generating voiceover...")
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        response.raise_for_status()
        
        with open(output_file, "wb") as f:
            f.write(response.content)
        
        if not output_file.exists() or output_file.stat().st_size == 0:
            raise Exception("Voiceover file creation failed")
        
        log_task(task_id, "Voiceover generated")
        return str(output_file)
    except Exception as e:
        raise Exception(f"Voiceover generation failed: {e}")

def get_audio_duration(audio_path: str) -> float:
    """Get audio duration using FFmpeg"""
    exe = ffmpeg.get_ffmpeg_exe()
    cmd = [exe, "-i", audio_path]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
    if not match:
        return 10.0  # Default fallback
    
    h, m, s = map(float, match.groups())
    return h * 3600 + m * 60 + s

async def compile_videos(paths: List[str], target_duration: float, task_id: str, 
                        folder_timelines: dict = None, video_to_folder_map: dict = None):
    """
    Timeline-aware compilation: Uses videos from appropriate folders based on transcription timeline.
    If timeline is provided, switches videos when topics change. Otherwise, cycles through videos.
    """
    import random
    
    task_dir = TEMP_DIR / task_id
    output_path = task_dir / "compiled.mp4"
    exe = ffmpeg.get_ffmpeg_exe()
    
    # Group videos by folder
    videos_by_folder = {}
    if video_to_folder_map:
        for video_path in paths:
            folder_name = video_to_folder_map.get(video_path, 'unknown')
            if folder_name not in videos_by_folder:
                videos_by_folder[folder_name] = []
            videos_by_folder[folder_name].append(video_path)
    else:
        # Fallback: treat all videos as one group
        videos_by_folder['unknown'] = paths
    
    use_timeline = folder_timelines and len(folder_timelines) > 0
    
    if use_timeline:
        log_task(task_id, f"Creating timeline-aware compilation ({len(paths)} videos, {target_duration:.1f}s target)...")
    else:
        log_task(task_id, f"Creating optimized video compilation ({len(paths)} videos, {target_duration:.1f}s target)...")
    
    # Get video durations
    video_durations = {}
    video_positions = {}
    for video_path in paths:
        try:
            duration = get_video_duration(video_path)
            video_durations[video_path] = duration
            video_positions[video_path] = 0.0
        except:
            video_durations[video_path] = 10.0
            video_positions[video_path] = 0.0
    
    list_file = task_dir / "list.txt"
    current_time = 0.0
    segment_idx = 0
    
    # Clip durations will vary between 2-3 seconds
    min_clip_duration = 2.0
    max_clip_duration = 3.0
    
    # Helper function to get which folder should be used at current time
    def get_folder_for_time(current_t: float) -> str:
        if not use_timeline:
            return None
        
        for folder_name, segments in folder_timelines.items():
            for start, end in segments:
                if start <= current_t < end:
                    return folder_name
        # If no timeline match, return first available folder
        return list(videos_by_folder.keys())[0] if videos_by_folder else None
    
    # Track which video index to use for each folder (for cycling)
    folder_video_indices = {folder: 0 for folder in videos_by_folder.keys()}
    
    with open(list_file, "w", encoding="utf-8") as f:
        while current_time < target_duration:
            # Determine which folder to use based on timeline
            if use_timeline:
                target_folder = get_folder_for_time(current_time)
                if target_folder and target_folder in videos_by_folder:
                    available_videos = videos_by_folder[target_folder]
                    if available_videos:
                        # Cycle through videos in this folder
                        video_idx = folder_video_indices[target_folder] % len(available_videos)
                        video_path = available_videos[video_idx]
                        folder_video_indices[target_folder] += 1
                    else:
                        # Fallback to any available video
                        video_path = paths[segment_idx % len(paths)]
                else:
                    # Fallback: cycle through all videos
                    video_path = paths[segment_idx % len(paths)]
            else:
                # No timeline: cycle through all videos
                video_idx = segment_idx % len(paths)
                video_path = paths[video_idx]
            
            video_duration = video_durations.get(video_path, 10.0)
            current_pos = video_positions.get(video_path, 0.0)
            
            # Random clip duration between 2-3 seconds
            clip_duration = round(random.uniform(min_clip_duration, max_clip_duration), 1)
            
            # Check if we have enough video left
            if current_pos + clip_duration > video_duration:
                video_positions[video_path] = 0.0
                current_pos = 0.0
            
            # Create segment
            segment_output = task_dir / f"segment_{segment_idx}.mp4"
            
            cut_cmd = [
                exe, "-y",
                "-ss", str(current_pos),
                "-i", video_path,
                "-t", str(clip_duration),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                "-r", "30",
                "-an",
                str(segment_output)
            ]
            
            try:
                result = subprocess.run(cut_cmd, check=True, capture_output=True, text=True, timeout=60)
                
                if Path(segment_output).exists() and Path(segment_output).stat().st_size > 10000:
                    abs_path = Path(segment_output).resolve()
                    path_str = str(abs_path).replace('\\', '/')
                    f.write(f"file '{path_str}'\n")
                    
                    video_positions[video_path] += clip_duration
                    current_time += clip_duration
                    segment_idx += 1
                    
                    if segment_idx % 5 == 0:
                        folder_info = f" ({video_to_folder_map.get(video_path, 'unknown')})" if video_to_folder_map else ""
                        log_task(task_id, f"Created {segment_idx} segments ({current_time:.1f}s / {target_duration:.1f}s){folder_info}")
                else:
                    Path(segment_output).unlink(missing_ok=True)
                    video_positions[video_path] = 0.0
                    continue
                    
            except subprocess.CalledProcessError as e:
                print(f"Failed to create segment {segment_idx}: {e.stderr[:200]}")
                Path(segment_output).unlink(missing_ok=True)
                video_positions[video_path] = 0.0
                segment_idx += 1
                if segment_idx >= len(paths) * 10:
                    break
                continue
            
            if segment_idx > 1000:
                break
    
    if segment_idx == 0:
        raise Exception("Failed to create any video segments")
    
    log_task(task_id, f"Created {segment_idx} segments, concatenating to {target_duration:.1f}s...")
    
    # Concatenate without trimming - we'll trim during audio merge
    concat_cmd = [
        exe, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-r", "30",  # Consistent framerate
        str(output_path)
    ]
    
    try:
        subprocess.run(concat_cmd, check=True, capture_output=True, text=True, timeout=300)
        log_task(task_id, f"Videos compiled successfully")
    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg concat failed: {e.stderr}"
        print(error_msg)
        raise Exception(error_msg)
    
    free_memory()
    return str(output_path)

def merge_audio_video(video_path: str, audio_path: str, output_path: str):
    """Merge audio with video using FFmpeg - video length will match audio length exactly"""
    exe = ffmpeg.get_ffmpeg_exe()
    
    # Get audio duration to ensure video matches it exactly
    audio_duration = get_audio_duration(audio_path)
    
    cmd = [
        exe, "-y",
        "-stream_loop", "-1",  # Loop video if needed
        "-i", video_path,      # Input 0: video (will loop if audio is longer)
        "-i", audio_path,      # Input 1: audio
        "-map", "0:v",         # Map video from input 0
        "-map", "1:a",         # Map audio from input 1
        "-c:v", "libx264",     # Encode video
        "-preset", "ultrafast",
        "-crf", "28",
        "-c:a", "aac",         # Encode audio to AAC
        "-b:a", "192k",        # Higher audio bitrate for better quality
        "-t", str(audio_duration),  # EXACT duration to match audio
        "-shortest",           # Safety: end when audio ends
        output_path
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=180)
    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg merge failed: {e.stderr}"
        print(error_msg)
        raise Exception(error_msg)

# === MODERN CAPTIONING SYSTEM (No Whisper!) ===

def estimate_word_timing(text: str, duration: float) -> list:
    """
    Estimate word-by-word timing based on word length and pauses.
    More accurate than simple division - accounts for natural speech patterns.
    """
    words = text.split()
    
    # Estimate syllables per word (rough but effective)
    def count_syllables(word):
        word = word.lower().strip('.,!?;:')
        vowels = 'aeiouy'
        syllables = 0
        previous_was_vowel = False
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not previous_was_vowel:
                syllables += 1
            previous_was_vowel = is_vowel
        return max(1, syllables)
    
    # Calculate relative timing based on syllables
    word_data = []
    total_syllables = sum(count_syllables(w) for w in words)
    
    # Average speaking rate: ~2.5 syllables per second
    # Add pauses for punctuation
    current_time = 0.0
    for word in words:
        syllables = count_syllables(word)
        # Base duration from syllables
        word_duration = (syllables / total_syllables) * duration
        
        # Add pause for punctuation
        if word.endswith(('.', '!', '?')):
            word_duration += 0.3
        elif word.endswith((',', ';', ':')):
            word_duration += 0.15
        
        word_data.append({
            'word': word.strip('.,!?;:'),
            'start': current_time,
            'end': current_time + word_duration
        })
        current_time += word_duration
    
    # Normalize to fit exact duration
    if word_data:
        scale = duration / current_time
        for w in word_data:
            w['start'] *= scale
            w['end'] *= scale
    
    return word_data

def create_modern_srt(text: str, duration: float, task_id: str) -> str:
    """Create word-by-word SRT with natural timing for better sync"""
    task_dir = TEMP_DIR / task_id
    srt_path = task_dir / "captions.srt"
    
    # Get word-by-word timing
    word_timings = estimate_word_timing(text, duration)
    
    if not word_timings:
        return None
    
    # Create word-by-word captions for better sync
    caption_index = 1
    with open(srt_path, "w", encoding="utf-8") as f:
        i = 0
        while i < len(word_timings):
            # Take WORDS_PER_CAPTION words at a time
            group = word_timings[i:i+WORDS_PER_CAPTION]
            
            if not group:
                break
            
            # Caption timing
            start_time = group[0]['start']
            end_time = group[-1]['end']
            
            # Format times
            start_str = format_srt_time(start_time)
            end_str = format_srt_time(end_time)
            
            # Join words (keep natural case, not uppercase)
            caption_text = ' '.join(w['word'] for w in group)
            
            f.write(f"{caption_index}\n")
            f.write(f"{start_str} --> {end_str}\n")
            f.write(f"{caption_text}\n\n")
            
            caption_index += 1
            i += WORDS_PER_CAPTION
    
    return str(srt_path)

def format_srt_time(seconds: float) -> str:
    """Format seconds to SRT time format: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def add_modern_captions_with_ffmpeg(video_path: str, srt_path: str, output_path: str):
    """Add subtle, natural captions with word-by-word sync"""
    import platform
    exe = ffmpeg.get_ffmpeg_exe()
    
    # Properly escape path for FFmpeg on Windows vs Linux/Mac
    abs_srt_path = str(Path(srt_path).resolve())
    
    if platform.system() == 'Windows':
        # Windows: Use forward slashes and escape special chars properly
        # Replace backslashes with forward slashes
        srt_path_ffmpeg = abs_srt_path.replace('\\', '/')
        # Escape colons (but not the drive letter colon)
        # e.g., C:/path/file.srt -> C\\:/path/file.srt
        if len(srt_path_ffmpeg) > 1 and srt_path_ffmpeg[1] == ':':
            srt_path_ffmpeg = srt_path_ffmpeg[0] + '\\:' + srt_path_ffmpeg[2:]
        # Escape special characters for FFmpeg filter
        srt_path_ffmpeg = srt_path_ffmpeg.replace("'", "'\\\\\\''")
    else:
        # Linux/Mac: Standard escaping
        srt_path_ffmpeg = abs_srt_path.replace('\\', '/').replace(':', '\\:')
    
    # Subtle caption style: Small white text, thin black outline, no background
    cmd = [
        exe, "-y", "-i", video_path,
        "-vf", (
            f"subtitles='{srt_path_ffmpeg}':force_style='"
            f"FontName=Arial,FontSize={CAPTION_FONT_SIZE},Bold=0,"
            f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"  # White text, black outline
            f"BorderStyle=1,Outline=2,Shadow=0,"  # Thin outline, no shadow
            f"BackColour=&H00000000,Alignment=2,MarginV=30'"  # No background, bottom center, 30px margin
        ),
        "-c:a", "copy",
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=180)
    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg caption failed: {e.stderr}"
        print(error_msg)
        raise Exception(error_msg)

async def process_video_generation(request: VideoGenerationRequest, task_id: str):
    """Main video processing pipeline - memory optimized"""
    global active_tasks
    
    try:
        active_tasks += 1
        tasks[task_id]['status'] = 'processing'
        log_task(task_id, "Starting video generation...")
        
        # Step 1: Get or generate voiceover
        if tasks[task_id].get('use_uploaded_audio'):
            # Use uploaded audio
            audio_path = tasks[task_id]['audio_path']
            log_task(task_id, "Using uploaded audio...")
        else:
            # Generate voiceover with ElevenLabs
            audio_path = await generate_voiceover(request.script_text, task_id, request.voice_id)
        
        duration = get_audio_duration(audio_path)
        log_task(task_id, f"Target duration: {duration:.1f}s")
        
        # Step 2: Fetch and download videos from Google Drive ONLY
        task_data = tasks[task_id]
        selected_folders = task_data.get('selected_folders', [])
        drive_videos = []
        
        # Collect all selected Drive videos
        for folder_info in selected_folders:
            if isinstance(folder_info, dict) and 'videos' in folder_info:
                drive_videos.extend(folder_info['videos'])
        
        # Validate Drive videos
        if not drive_videos:
            error_msg = "No Drive videos selected. Please ensure folders contain videos in drive_videos.json"
            log_task(task_id, f"ERROR: {error_msg}")
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = error_msg
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Use cached videos (already downloaded from Drive folder)
        log_task(task_id, f"Using {len(drive_videos)} cached videos from Drive folder...")
        folder_names = set()
        downloaded = []
        video_to_folder_map = {}  # Map video path to folder name
        folder_timelines = {}  # Map folder name to timeline segments
        
        # Extract timeline info from folder_info
        for folder_info in selected_folders:
            if isinstance(folder_info, dict):
                folder_name = folder_info.get('name', 'unknown')
                timeline_segments = folder_info.get('timeline_segments', [])
                if timeline_segments:
                    folder_timelines[folder_name] = timeline_segments
                    log_task(task_id, f"Timeline for {folder_name}: {timeline_segments}")
        
        for v in drive_videos:
            folder_name = v.get('folder_name', 'unknown')
            folder_names.add(folder_name)
            
            # Check if video is cached (has local_path)
            if v.get('cached') and v.get('local_path'):
                local_path = v.get('local_path')
                if os.path.exists(local_path):
                    downloaded.append(local_path)
                    video_to_folder_map[local_path] = folder_name
                    log_task(task_id, f"Using cached video: {v.get('name', 'unknown')} ({folder_name})")
                else:
                    log_task(task_id, f"Warning: Cached video not found: {local_path}")
            else:
                # Fallback: try to download from Drive ID if no cache
                log_task(task_id, f"Video not cached, attempting download: {v.get('name', 'unknown')}")
        
        if not downloaded:
            error_msg = "No cached videos found. Make sure Drive folder was downloaded successfully."
            log_task(task_id, f"ERROR: {error_msg}")
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = error_msg
            raise HTTPException(status_code=400, detail=error_msg)
        
        log_task(task_id, f"Selected folders: {', '.join(folder_names)}")
        log_task(task_id, f"Using {len(downloaded)} cached videos from Drive folder")
        
        # Step 3: Convert to vertical format
        log_task(task_id, "Optimizing video format...")
        converted = await convert_videos_to_vertical(downloaded, task_id)
        
        # Update mapping for converted videos
        converted_to_folder_map = {}
        for orig_path, converted_path in zip(downloaded, converted):
            folder_name = video_to_folder_map.get(orig_path, 'unknown')
            converted_to_folder_map[converted_path] = folder_name
        
        # Step 4: Compile videos with timeline support
        log_task(task_id, "Compiling videos with timeline-aware switching...")
        compiled = await compile_videos(converted, duration, task_id, folder_timelines, converted_to_folder_map)

        # Step 5: Merge audio with video
        log_task(task_id, "Merging audio...")
        task_dir = TEMP_DIR / task_id
        merged_video = task_dir / "merged.mp4"
        merge_audio_video(compiled, audio_path, str(merged_video))
        
        # Step 6: Add modern captions (hardcoded - always enabled, lightweight!)
        if ADD_CAPTIONS:
            log_task(task_id, "Adding modern captions...")
            srt_path = create_modern_srt(request.script_text, duration, task_id)
            final_output = OUTPUT_DIR / f"{task_id}_final.mp4"
            add_modern_captions_with_ffmpeg(str(merged_video), srt_path, str(final_output))
            log_task(task_id, "Modern captions added")
        else:
            # No captions - use merged video as final
            final_output = OUTPUT_DIR / f"{task_id}_final.mp4"
            shutil.move(str(merged_video), str(final_output))
        
        # Update task
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['output_file'] = str(final_output)
        tasks[task_id]['completed_at'] = datetime.now()
        log_task(task_id, "✅ Completed!")
        
        # Callback if provided
        if request.callback_url:
            try:
                with open(final_output, 'rb') as f:
                    requests.post(
                        request.callback_url,
                        files={'video': (f"{task_id}.mp4", f, "video/mp4")},
                        data={'task_id': task_id, 'status': 'completed'},
                        timeout=30
                    )
            except Exception as e:
                print(f"Callback failed: {e}")

        # Cleanup
        shutil.rmtree(TEMP_DIR / task_id, ignore_errors=True)
        free_memory()
        
    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)
        tasks[task_id]['completed_at'] = datetime.now()
        log_task(task_id, f"❌ Failed: {e}")
        shutil.rmtree(TEMP_DIR / task_id, ignore_errors=True)
        free_memory()
    finally:
        active_tasks -= 1

# === API ENDPOINTS ===

# ElevenLabs endpoint removed - only audio upload is supported

@app.post("/generate-video-upload", response_model=VideoGenerationResponse)
async def generate_video_with_upload(
    audio_file: UploadFile = File(...),
    suggested_folders: str = Form(default=""),  # JSON string of folders
    script_text: str = Form(default=""),
    background_tasks: BackgroundTasks = None
):
    """Start video generation with uploaded voiceover (using Pexels for now)"""
    global active_tasks
    
    # Limit concurrent tasks
    if active_tasks >= MAX_CONCURRENT_TASKS:
        raise HTTPException(503, f"Server busy. Max {MAX_CONCURRENT_TASKS} concurrent tasks allowed.")
    
    # Validate audio file (case-insensitive)
    if not audio_file.filename.lower().endswith(('.mp3', '.wav', '.m4a', '.aac')):
        raise HTTPException(400, "Audio file must be MP3, WAV, M4A, or AAC format")
    
    task_id = str(uuid.uuid4())
    task_dir = TEMP_DIR / task_id
    task_dir.mkdir(exist_ok=True)
    
    # Save uploaded audio
    audio_path = task_dir / "voice.mp3"
    with open(audio_path, "wb") as f:
        content = await audio_file.read()
        f.write(content)
    
    # Parse folders from JSON string (contains selected videos with IDs)
    try:
        if suggested_folders:
            folders_data = json.loads(suggested_folders)
            if isinstance(folders_data, list):
                selected_folders = folders_data
            elif isinstance(folders_data, dict) and 'folders' in folders_data:
                selected_folders = folders_data['folders']
            else:
                selected_folders = []
        else:
            selected_folders = []
    except Exception as e:
        print(f"Error parsing folders JSON: {e}")
        selected_folders = []
    
    # Use transcription-based search query for unique video selection
    if script_text and len(script_text) > 20:
        # Extract key terms from transcription for unique search
        import google.generativeai as genai
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            # Detect key topics from transcription (works for any language)
            topics_detected = []
            french_to_english = {
                'collagène': 'collagen supplement skin',
                'peau': 'skin care face',
                'rides': 'wrinkles anti aging',
                'cheveux': 'hair care beauty',
                'ongles': 'nails manicure',
                'café': 'coffee drink',
                'cellulite': 'cellulite treatment',
                'articulations': 'joints health',
                'ménopause': 'menopause health',
                'visage': 'face beauty',
                'crème': 'cream skincare',
                'vitamine': 'vitamin supplement',
                'supplément': 'supplement health'
            }
            
            # Check for French keywords and add English equivalents
            script_lower = script_text.lower()
            for french, english in french_to_english.items():
                if french in script_lower:
                    topics_detected.append(english)
            
            # Add folder context to help Gemini understand the theme
            folder_context = ""
            if selected_folders:
                folder_names = [f.get('name', f) if isinstance(f, dict) else f for f in selected_folders[:5]]
                folder_context = f"\n\nSelected folders (use these themes): {', '.join(folder_names)}"
                
                # Add folder-specific visual hints
                folder_hints = {
                    'Product': 'product bottles packaging supplements',
                    'Wrinkles': 'anti aging wrinkles smooth skin face',
                    'Hair': 'long shiny hair brushing styling',
                    'Joints': 'joints flexibility movement wellness',
                    'Nails': 'nails manicure hands beauty',
                    'Glow Coffee': 'coffee drink morning glowing skin',
                    'Cellulite': 'cellulite treatment legs smooth',
                    'Menopause': 'mature woman health wellness'
                }
                
                folder_visual_hints = []
                for fname in folder_names:
                    if fname in folder_hints:
                        folder_visual_hints.append(folder_hints[fname])
                
                if folder_visual_hints:
                    folder_context += f"\nVisual elements to include: {', '.join(folder_visual_hints)}"
            
            # Add detected topics to help Gemini understand
            detected_context = ""
            if topics_detected:
                detected_context = f"\n\nDetected topics (use these for context): {', '.join(set(topics_detected[:3]))}"
            
            prompt = f"""You are a video search specialist. Analyze this transcription (which may be in any language) and create a HIGHLY SPECIFIC search query IN ENGLISH for finding relevant stock videos on Pexels.

Transcription: "{script_text[:500]}"{detected_context}{folder_context}

IMPORTANT: 
- The transcription may be in French, English, or other languages
- You MUST respond with the search query in ENGLISH only
- Analyze the FULL transcription content, not just keywords
- The detected topics and folders are HINTS to help you, but analyze the full story/message
- Extract visual elements, emotions, results, and specific details from the entire transcription
- Think about what would make compelling stock footage for THIS SPECIFIC content

Your task:
1. Read and understand the FULL transcription (not just keywords)
2. Identify ALL visual elements being described (people, products, actions, settings, emotions, results)
3. Translate key concepts to ENGLISH visual terms
4. Think about what would look good on camera (close-ups, activities, emotions, results)
5. Use CONCRETE, VISUAL terms (not abstract concepts)
6. Be DETAILED and SPECIFIC - include multiple visual elements from the full story
7. Include WHO is in the video (woman, person, hands, face, body parts, etc.)
8. Include WHAT action is happening (applying, taking, drinking, showing, comparing)
9. Include visual RESULTS or emotions (glowing, smooth, shiny, happy, confident, surprised)
10. Focus on MULTIPLE aspects from the entire narrative to get the most relevant results

Good examples (all in English, detailed):
- "beautiful woman applying collagen cream on face smooth glowing skin closeup"
- "woman taking supplement pills vitamin bottle health wellness routine"
- "close up mature woman face before after wrinkles anti aging treatment"
- "hands massaging face skincare routine cream application beauty"
- "woman brushing long shiny healthy hair beauty care routine"
- "before after skin comparison wrinkles aging smooth radiant results"
- "woman drinking coffee morning routine glowing skin beauty lifestyle"

Bad examples:
- "beauty wellness" (too vague, too short)
- "good product" (not visual, not specific)
- "woman face" (too generic, needs more detail)
- "santé beauté" (not in English - must translate to English)

Context clues for translation:
- If about "collagène" → analyze the full story about collagen testing, results, transformation
- If about "café" → analyze coffee routine, preparation, benefits story
- If about "cheveux" → analyze hair care journey, styling, transformation process
- If about "peau" → analyze skin care routine, application, visible results
- If about "rides" → analyze anti-aging treatment, before/after, transformation journey
- If about "supplément/vitamine" → analyze supplement taking routine, health improvements

Now create a DETAILED search query (10-15 words) IN ENGLISH that captures the FULL STORY and focuses on WHAT THE CAMERA WOULD SEE.
Include WHO, WHAT action, JOURNEY/PROCESS, and VISUAL results from the full transcription:

Search query:"""
            
            response = model.generate_content(prompt)
            primary_query = response.text.strip().strip('"\'')
            
            log_info("GEMINI - Generated Search Query", {
                "Transcription Preview": script_text[:200],
                "Generated Query": primary_query
            })
        except Exception as e:
            print(f"Error generating search query: {e}")
            # Improved fallback to simple extraction
            words = script_text.lower().split()
            
            # Remove common words (expanded list)
            stop_words = {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 
                'by', 'from', 'is', 'are', 'was', 'were', 'been', 'be', 'have', 'has', 'had', 
                'do', 'does', 'did', 'will', 'would', 'could', 'should', 'can', 'may', 'might',
                'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
                'your', 'our', 'their', 'my', 'his', 'her', 'its', 'what', 'which', 'who',
                'when', 'where', 'why', 'how', 'all', 'each', 'every', 'some', 'many', 'much',
                'more', 'most', 'other', 'such', 'only', 'just', 'very', 'too', 'also'
            }
            
            # Look for visual/concrete nouns and action verbs
            visual_keywords = []
            for word in words:
                clean_word = word.strip('.,!?;:')
                if len(clean_word) > 4 and clean_word not in stop_words:
                    visual_keywords.append(clean_word)
            
            # Take first 8-10 meaningful words for more detail
            if visual_keywords:
                primary_query = ' '.join(visual_keywords[:10])
            else:
                primary_query = "woman applying beauty skincare cream face closeup routine"
            
            log_info("GEMINI - Fallback Query Generated", {
                "Transcription Preview": script_text[:200],
                "Fallback Query": primary_query
            })
    else:
        # Fallback if no transcription
        primary_query = "woman applying beauty skincare product face closeup routine"
    
    # Get folder names for logging
    if selected_folders:
        folder_names = [f.get('name', f) if isinstance(f, dict) else f for f in selected_folders[:3]]
    else:
        folder_names = ["Others"]
    
    log_info("VIDEO GENERATION - Starting with Upload", {
        "Task ID": task_id,
        "Audio File": audio_file.filename,
        "Audio Size": f"{len(content)} bytes",
        "Selected Folders": folder_names,
        "Folder Count": len(folder_names),
        "Video Descriptions": {f.get('name', f): f.get('videos', []) for f in selected_folders if isinstance(f, dict)} if selected_folders else {},
        "Content-Based Search Query": primary_query,
        "Script Text": script_text[:100] + "..." if len(script_text) > 100 else script_text
    })
    
    tasks[task_id] = {
        'status': 'pending',
        'progress': 'Preparing video generation...',
        'error': None,
        'output_file': None,
        'created_at': datetime.now(),
        'completed_at': None,
        'use_uploaded_audio': True,
        'audio_path': str(audio_path),
        'script_text': script_text,
        'selected_folders': selected_folders,  # Keep the full objects with video IDs
        'video_descriptions': {f.get('name', f): f.get('videos', []) for f in selected_folders if isinstance(f, dict)} if selected_folders else {}
    }
    
    # Create a request object for processing
    request = VideoGenerationRequest(
        script_text=script_text or "uploaded audio",
        search_query=primary_query
    )
    
    background_tasks.add_task(process_video_generation, request, task_id)
    
    return VideoGenerationResponse(
        task_id=task_id,
        status="pending",
        message="Video generation started with your audio"
    )

@app.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get task status"""
    if task_id not in tasks:
        raise HTTPException(404, "Task not found")
    
    task = tasks[task_id]
    return TaskStatusResponse(
        task_id=task_id,
        status=task['status'],
        progress=task['progress'],
        error=task.get('error'),
        output_file=task.get('output_file'),
        created_at=task['created_at'],
        completed_at=task.get('completed_at')
    )

@app.get("/download/{task_id}")
async def download_video(task_id: str):
    """Download generated video"""
    if task_id not in tasks:
        raise HTTPException(404, "Task not found")
    
    task = tasks[task_id]
    if task['status'] != 'completed':
        raise HTTPException(400, "Video not ready")
    
    file_path = task.get('output_file')
    if not file_path or not Path(file_path).exists():
        raise HTTPException(404, "File not found")
    
    return FileResponse(file_path, media_type="video/mp4", filename=f"{task_id}.mp4")

@app.post("/transcribe-audio")
async def transcribe_audio(audio_file: UploadFile = File(...)):
    """Transcribe uploaded audio using Whisper and analyze with Gemini"""
    try:
        log_info("TRANSCRIPTION - Starting", {
            "Audio File": audio_file.filename,
            "Content Type": audio_file.content_type,
            "File Size": f"{audio_file.size} bytes" if hasattr(audio_file, 'size') else "unknown"
        })
        
        # Save uploaded audio temporarily
        temp_id = str(uuid.uuid4())
        temp_dir = TEMP_DIR / f"transcribe_{temp_id}"
        temp_dir.mkdir(exist_ok=True)
        
        audio_path = temp_dir / "audio.mp3"
        with open(audio_path, "wb") as f:
            content = await audio_file.read()
            f.write(content)
        
        log_info("TRANSCRIPTION - Audio Saved", {
            "Temp ID": temp_id,
            "Audio Path": str(audio_path),
            "File Size": f"{len(content)} bytes"
        })
        
        # Get bundled FFmpeg path
        ffmpeg_exe = ffmpeg.get_ffmpeg_exe()
        
        log_info("WHISPER - Initializing", {
            "Model": "tiny (~75MB)",
            "FFmpeg Path": ffmpeg_exe
        })
        
        # Patch Whisper's audio module to use bundled FFmpeg
        import whisper
        import whisper.audio
        
        # Store original run function
        original_run = whisper.audio.run
        
        def patched_run(cmd, *args, **kwargs):
            """Replace 'ffmpeg' command with full path"""
            if isinstance(cmd, list) and len(cmd) > 0 and cmd[0] == 'ffmpeg':
                cmd = [ffmpeg_exe] + cmd[1:]
            return original_run(cmd, *args, **kwargs)
        
        # Apply patch
        whisper.audio.run = patched_run
        
        try:
            print("Loading Whisper model (tiny)...")
            model = whisper.load_model("tiny")  # Smallest model, ~75MB
            
            log_info("WHISPER - Transcribing", {
                "Audio File": audio_file.filename,
                "Status": "Processing..."
            })
            
            result = model.transcribe(str(audio_path))
            transcription = result["text"].strip()
            
            log_info("WHISPER - Transcription Complete", {
                "Full Transcription": transcription,
                "Length": len(transcription),
                "Word Count": len(transcription.split()),
                "Detected Language": result.get("language", "unknown")
            })
            
            # Get audio duration for video selection
            audio_duration = get_audio_duration(str(audio_path))
            
            # Get Drive structure (folder names only)
            drive_structure = list_drive_folders_and_files(GOOGLE_DRIVE_FOLDER_ID)
            
            # Analyze with Gemini to select EXACT videos from Drive folders
            # Pass audio duration so videos can be selected based on length
            gemini_result = await get_exact_videos_from_gemini(transcription, drive_structure, audio_duration)
            
            log_info("TRANSCRIPTION - Final Result", {
                "Success": True,
                "Transcription": transcription,
                "Language": result.get("language", "unknown"),
                "Selected Folders": [f['name'] for f in gemini_result['folders']],
                "Video Descriptions": {f['name']: f['videos'] for f in gemini_result['folders']},
                "Next Step": "Will use Pexels with themed searches based on folders"
            })
            
            return {
                "success": True,
                "transcription": transcription,
                "language": result.get("language", "unknown"),
                "suggested_folders": gemini_result['folders'],
                "primary_folder": gemini_result['folders'][0]['name'] if gemini_result['folders'] else "Others",
                "actress_name": gemini_result.get('actress_name'),
                "message": f"Selected {len(gemini_result['folders'])} folders with {sum(len(f['videos']) for f in gemini_result['folders'])} videos."
            }
        finally:
            # Restore original run function
            whisper.audio.run = original_run
            
            # Cleanup
            if 'model' in locals():
                del model
            shutil.rmtree(temp_dir, ignore_errors=True)
            free_memory()
        
    except Exception as e:
        # Cleanup on error
        if 'temp_dir' in locals():
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        print(f"Transcription error: {e}")
        import traceback
        print(traceback.format_exc())
        
        return {
            "success": False,
            "transcription": f"Could not transcribe: {str(e)}"
        }

async def analyze_transcription_with_gemini(transcription: str) -> str:
    """Use Gemini to analyze transcription and suggest relevant footage folder"""
    try:
        import google.generativeai as genai
        
        # Configure Gemini
        genai.configure(api_key="AIzaSyDYYbbXiakOEOpEH-4hTHZvpZMaoEX3fdk")
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Available folders based on the image
        available_folders = [
            "Cellulite",
            "Glow Coffee", 
            "Hair",
            "Joints",
            "Menopause",
            "Nails",
            "Others",
            "Product",
            "Wrinkles"
        ]
        
        # Create prompt
        prompt = f"""Analyze this transcription and choose the MOST relevant folder for video footage.

Transcription: "{transcription}"

Available folders:
{chr(10).join(f'- {folder}' for folder in available_folders)}

Rules:
1. Choose ONLY ONE folder that best matches the topic
2. If it's about a product, choose "Product"
3. If none match well, choose "Others"
4. Respond with ONLY the folder name, nothing else

Folder:"""
        
        # Get response
        response = model.generate_content(prompt)
        suggested_folder = response.text.strip()
        
        # Validate response
        if suggested_folder not in available_folders:
            # Try to find closest match
            suggested_lower = suggested_folder.lower()
            for folder in available_folders:
                if folder.lower() in suggested_lower or suggested_lower in folder.lower():
                    suggested_folder = folder
                    break
            else:
                suggested_folder = "Others"  # Fallback
        
        print(f"Gemini suggested folder: {suggested_folder}")
        return suggested_folder
        
    except Exception as e:
        print(f"Gemini analysis error: {e}")
        return "Others"  # Fallback on error

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the UI"""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse(content="<h1>UI not found. API is running at /docs</h1>", status_code=200)

@app.get("/api/status")
def api_status():
    """API status endpoint"""
    return {
        "status": "ok",
        "version": "2.0-optimized",
        "message": "AI Video Generator (Memory Optimized for 2-4GB)",
        "active_tasks": active_tasks,
        "max_concurrent": MAX_CONCURRENT_TASKS
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, workers=1)