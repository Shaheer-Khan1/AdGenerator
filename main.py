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

async def get_exact_videos_from_gemini(transcription: str, drive_structure: dict) -> dict:
    """Use Gemini to select EXACT videos from Drive folders, detecting actress names and prioritizing matching videos"""
    try:
        import google.generativeai as genai
        
        log_info("GEMINI AI - Initializing for Exact Video Selection", {
            "Model": "gemini-2.5-flash",
            "Purpose": "Select specific videos from Drive folders, detect actress names"
        })
        
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Build video list for each folder (including subfolders)
        folders_with_videos = {}
        all_videos_count = 0
        
        for folder_name, folder_data in drive_structure.items():
            # Get videos directly in folder
            videos = folder_data.get('videos', [])
            all_folder_videos = list(videos)  # Copy main folder videos
            
            # Get videos from subfolders
            subfolders = folder_data.get('subfolders', {})
            for subfolder_name, subfolder_data in subfolders.items():
                subfolder_videos = subfolder_data.get('videos', [])
                # Add subfolder videos with path info
                for v in subfolder_videos:
                    video_copy = v.copy()
                    video_copy['subfolder'] = subfolder_name
                    all_folder_videos.append(video_copy)
            
            if all_folder_videos:
                folders_with_videos[folder_name] = {
                    'videos': all_folder_videos,
                    'subfolders': subfolders
                }
                all_videos_count += len(all_folder_videos)
        
        if not folders_with_videos:
            log_info("GEMINI AI - No Videos Found", {
                "Note": "No videos in drive_videos.json. Please add video IDs and names.",
                "Fallback": "Will use Pexels"
            })
            return {
                'folders': [{'name': 'Others', 'videos': []}],
                'actress_name': None,
                'raw_response': 'No videos in Drive mapping'
            }
        
        # Create prompt with actual video names (including nested structure)
        # Show ALL videos with clear folder hierarchy
        video_list_text = ""
        for folder_name, folder_info in folders_with_videos.items():
            video_list_text += f"\n📁 FOLDER: {folder_name}\n"
            videos = folder_info['videos']
            
            # Show main folder videos first
            main_videos = [v for v in videos if 'subfolder' not in v]
            if main_videos:
                video_list_text += f"  Main folder videos:\n"
                for video in main_videos:
                    video_name = video.get('name', 'unknown')
                    video_id = video.get('id', '')
                    video_list_text += f"    • {video_name} (ID: {video_id})\n"
            
            # Show subfolder videos with clear hierarchy
            subfolders = folder_info.get('subfolders', {})
            for subfolder_name, subfolder_data in subfolders.items():
                subfolder_videos = subfolder_data.get('videos', [])
                if subfolder_videos:
                    video_list_text += f"  📂 SUBFOLDER: {subfolder_name} (inside {folder_name}):\n"
                    for video in subfolder_videos:
                        video_name = video.get('name', 'unknown')
                        video_id = video.get('id', '')
                        video_list_text += f"    • {video_name} (ID: {video_id})\n"
        
        prompt = f"""You are analyzing a voiceover transcription to select EXACT videos from Google Drive.

Transcription: "{transcription}"

Available videos in Google Drive folders (📁 = main folder, 📂 = subfolder):
{video_list_text}

Task:
1. Analyze the transcription content and topic thoroughly
2. Select ALL RELEVANT folders (not just 2-3, but as many as match the content)
3. From each folder, choose 2-4 SPECIFIC videos by their EXACT names (can be from main folder or subfolders)
4. If a video name contains an actress name (e.g., "sarah", "maria"), note it
5. If an actress is detected, prioritize videos with the SAME actress name across ALL folders
6. Respond with EXACT video names and IDs
7. More folders = better variety, so don't limit yourself to just a few

Respond in this EXACT format:

FOLDER: FolderName1
VIDEO: exact_video_name.mp4|video_id_1
VIDEO: another_video_name.mp4|video_id_2

FOLDER: FolderName2
VIDEO: video_name.mp4|video_id_3

ACTRESS: actress_name (if detected, otherwise "None")

Examples:
If transcription is about coffee and you see videos with "sarah":
FOLDER: Glow Coffee
VIDEO: coffee_pour_sarah.mp4|abc123
VIDEO: pour_closeup.mp4|def456

FOLDER: Product
VIDEO: product_sarah.mp4|ghi789

ACTRESS: sarah

Now analyze and select EXACT videos:"""
        
        log_info("GEMINI AI - Sending Request with Video List", {
            "Transcription": transcription[:200],
            "Total Folders with Videos": len(folders_with_videos),
            "Total Videos Available": all_videos_count,
            "Prompt Length": len(prompt),
            "Video List Preview": video_list_text[:500] + "..." if len(video_list_text) > 500 else video_list_text
        })
        
        response = model.generate_content(prompt)
        raw_response = response.text.strip()
        
        log_info("GEMINI AI - Received Response", {
            "Raw Response": raw_response[:500]
        })
        
        # Parse response
        selected_folders = []
        current_folder = None
        detected_actress = None
        
        for line in raw_response.split('\n'):
            line = line.strip()
            if line.startswith('FOLDER:'):
                folder_name = line.replace('FOLDER:', '').strip()
                # Validate folder name
                for valid_folder in drive_structure.keys():
                    if valid_folder.lower() in folder_name.lower() or folder_name.lower() in valid_folder.lower():
                        current_folder = valid_folder
                        break
                if current_folder and current_folder not in [f['name'] for f in selected_folders]:
                    selected_folders.append({
                        'name': current_folder,
                        'videos': []
                    })
            elif line.startswith('VIDEO:') and current_folder:
                video_info = line.replace('VIDEO:', '').strip()
                # Parse "video_name.mp4|video_id" format
                if '|' in video_info:
                    video_name, video_id = video_info.split('|', 1)
                    video_name = video_name.strip()
                    video_id = video_id.strip()
                else:
                    video_name = video_info.strip()
                    video_id = None
                
                if selected_folders:
                    selected_folders[-1]['videos'].append({
                        'name': video_name,
                        'id': video_id
                    })
            elif line.startswith('ACTRESS:'):
                actress_name = line.replace('ACTRESS:', '').strip()
                if actress_name.lower() != 'none':
                    detected_actress = actress_name
        
        # If actress detected, prioritize matching videos
        if detected_actress:
            log_info("GEMINI AI - Actress Detected", {
                "Actress Name": detected_actress,
                "Action": "Prioritizing videos with same actress"
            })
            
            # Find all videos with this actress name (including subfolders)
            for folder_name, folder_data in drive_structure.items():
                videos = folder_data.get('videos', [])
                matching_videos = [v for v in videos if detected_actress.lower() in v.get('name', '').lower()]
                
                # Also check subfolders
                subfolders = folder_data.get('subfolders', {})
                for subfolder_data in subfolders.values():
                    subfolder_videos = subfolder_data.get('videos', [])
                    matching_videos.extend([v for v in subfolder_videos if detected_actress.lower() in v.get('name', '').lower()])
                
                if matching_videos:
                    # Add matching videos to selected folders if not already there
                    folder_found = False
                    for selected_folder in selected_folders:
                        if selected_folder['name'] == folder_name:
                            # Add matching videos that aren't already selected
                            existing_names = [v['name'] for v in selected_folder['videos']]
                            for match_video in matching_videos:
                                if match_video.get('name') not in existing_names:
                                    selected_folders.append({
                                        'name': folder_name,
                                        'videos': [{
                                            'name': match_video.get('name'),
                                            'id': match_video.get('id')
                                        }]
                                    })
                            folder_found = True
                            break
                    
                    if not folder_found and matching_videos:
                        selected_folders.append({
                            'name': folder_name,
                            'videos': [{
                                'name': v.get('name'),
                                'id': v.get('id')
                            } for v in matching_videos[:3]]
                        })
        
        # Ensure we have at least one folder
        if not selected_folders:
            selected_folders.append({
                'name': 'Others',
                'videos': []
            })
        
        result = {
            'folders': selected_folders,  # No limit - return all relevant folders
            'actress_name': detected_actress,
            'raw_response': raw_response
        }
        
        log_info("GEMINI AI - Final Selection", {
            "Selected Folders": [f['name'] for f in result['folders']],
            "Selected Videos": {f['name']: [v['name'] for v in f['videos']] for f in result['folders']},
            "Detected Actress": detected_actress,
            "Total Videos Selected": sum(len(f['videos']) for f in result['folders'])
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

async def compile_videos(paths: List[str], target_duration: float, task_id: str):
    """Compile videos by switching between different videos every 3 seconds"""
    task_dir = TEMP_DIR / task_id
    output_path = task_dir / "compiled.mp4"
    exe = ffmpeg.get_ffmpeg_exe()
    
    log_task(task_id, "Creating dynamic video cuts...")
    
    # Simple approach: Just loop the entire sequence of videos until we have enough
    video_segments = []
    clip_duration = 3.0
    current_time = 0.0
    segment_idx = 0
    
    # Create concat list that repeats the video sequence
    list_file = task_dir / "list.txt"
    
    # Calculate how many times we need to repeat the full sequence
    # Each full sequence = len(paths) * 3 seconds
    sequence_duration = len(paths) * clip_duration
    full_repeats = int(target_duration / sequence_duration) + 2  # +2 to ensure we have enough
    
    with open(list_file, "w", encoding="utf-8") as f:
        for repeat in range(full_repeats):
            for video_idx, video_path in enumerate(paths):
                # Use different 3-second segments from each video on each repeat
                start_time = repeat * clip_duration
                
                # Create segment
                segment_output = task_dir / f"segment_{segment_idx}.mp4"
                
                cut_cmd = [
                    exe, "-y",
                    "-ss", str(start_time),
                    "-i", video_path,
                    "-t", str(clip_duration),
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                    "-r", "30",  # Set framerate to 30fps for consistency
                    "-an",  # Remove audio
                    str(segment_output)
                ]
                
                try:
                    subprocess.run(cut_cmd, check=True, capture_output=True, text=True, timeout=60)
                    
                    # Verify segment exists and has reasonable size
                    if Path(segment_output).exists() and Path(segment_output).stat().st_size > 10000:
                        abs_path = Path(segment_output).resolve()
                        path_str = str(abs_path).replace('\\', '/')
                        f.write(f"file '{path_str}'\n")
                        segment_idx += 1
                        current_time += clip_duration
                        
                        if segment_idx % len(paths) == 0:  # After each full sequence
                            log_task(task_id, f"Completed sequence {segment_idx // len(paths)} ({current_time:.1f}s)")
                    else:
                        # If segment is too small or doesn't exist, use from beginning
                        Path(segment_output).unlink(missing_ok=True)
                        
                        # Retry from beginning of video
                        cut_cmd[3] = "0"  # Start from 0
                        subprocess.run(cut_cmd, check=True, capture_output=True, text=True, timeout=60)
                        
                        if Path(segment_output).exists():
                            abs_path = Path(segment_output).resolve()
                            path_str = str(abs_path).replace('\\', '/')
                            f.write(f"file '{path_str}'\n")
                            segment_idx += 1
                            current_time += clip_duration
                        
                except subprocess.CalledProcessError as e:
                    print(f"Failed to create segment {segment_idx}: {e.stderr}")
                    Path(segment_output).unlink(missing_ok=True)
                    continue
                
                # Stop if we have enough
                if current_time >= target_duration + 3.0:  # Extra buffer
                    break
            
            if current_time >= target_duration + 3.0:
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
        
        # Step 2: Fetch and download videos (Drive or Pexels)
        task_data = tasks[task_id]
        selected_folders = task_data.get('selected_folders', [])
        drive_videos = []
        
        # Collect all selected Drive videos
        for folder_info in selected_folders:
            if isinstance(folder_info, dict) and 'videos' in folder_info:
                drive_videos.extend(folder_info['videos'])
        
        # Check if drive videos have REAL IDs (not SAMPLE IDs)
        has_real_drive_ids = drive_videos and all(
            v.get('id') and 
            not v.get('id', '').startswith('SAMPLE_ID') 
            for v in drive_videos
        )
        
        if has_real_drive_ids:
            # Use Drive videos
            log_task(task_id, "Using Google Drive videos...")
            try:
            downloaded = await download_drive_videos(drive_videos, task_id)
            except Exception as e:
                log_task(task_id, f"Drive download failed: {e}, falling back to Pexels...")
                # Fallback to Pexels
                num_clips = max(MIN_CLIPS, min(MAX_CLIPS, int(duration / 10) + 1))
                video_urls = await search_pexels_videos(request.search_query, num_clips)
                downloaded = await download_videos(video_urls, task_id)
        else:
            # Use Pexels videos (no Drive videos or sample IDs detected)
            if drive_videos:
                log_task(task_id, "Sample Drive IDs detected, using Pexels instead...")
            else:
                log_task(task_id, "No Drive videos found, using Pexels...")
            
            num_clips = max(MIN_CLIPS, min(MAX_CLIPS, int(duration / 10) + 1))
            video_urls = await search_pexels_videos(request.search_query, num_clips)
            downloaded = await download_videos(video_urls, task_id)
        
        # Step 3: Convert to vertical format
        log_task(task_id, "Optimizing video format...")
        converted = await convert_videos_to_vertical(downloaded, task_id)
        
        # Step 4: Compile videos
        log_task(task_id, "Compiling videos...")
        compiled = await compile_videos(converted, duration, task_id)

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
            
            # Get Drive structure (folder names only)
            drive_structure = list_drive_folders_and_files(GOOGLE_DRIVE_FOLDER_ID)
            
            # Analyze with Gemini to select EXACT videos from Drive folders
            gemini_result = await get_exact_videos_from_gemini(transcription, drive_structure)
            
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