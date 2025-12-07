"""
Test script to download Google Drive folder
"""

import os
from pathlib import Path

# Your Drive folder ID
FOLDER_ID = "1l_vWG07Q3tN1UChnlyR40_dZ3McO9NfB"
FOLDER_URL = f"https://drive.google.com/drive/folders/{FOLDER_ID}"

# Cache directory
cache_dir = Path("drive_cache") / FOLDER_ID
cache_dir.mkdir(parents=True, exist_ok=True)

print("=" * 80)
print("🧪 Testing Google Drive Folder Download")
print("=" * 80)
print(f"Folder ID: {FOLDER_ID}")
print(f"Folder URL: {FOLDER_URL}")
print(f"Cache Directory: {cache_dir}")
print("=" * 80)
print()

try:
    import gdown
    print("✅ gdown is installed")
    print()
    
    print("📥 Starting download...")
    print("This may take a while depending on folder size...")
    print()
    
    # Download folder
    gdown.download_folder(
        FOLDER_URL,
        output=str(cache_dir),
        quiet=False,
        use_cookies=False
    )
    
    print()
    print("=" * 80)
    print("✅ Download Complete!")
    print("=" * 80)
    
    # Check what was downloaded
    downloaded_files = list(cache_dir.glob("**/*"))
    video_files = [f for f in downloaded_files if f.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv', '.webm']]
    
    print(f"\n📊 Results:")
    print(f"   Total files downloaded: {len(downloaded_files)}")
    print(f"   Video files found: {len(video_files)}")
    print()
    
    if video_files:
        print("📹 Video files:")
        for i, video in enumerate(video_files[:10], 1):  # Show first 10
            print(f"   {i}. {video.name}")
        if len(video_files) > 10:
            print(f"   ... and {len(video_files) - 10} more")
    else:
        print("⚠️  No video files found in downloaded folder")
    
    print()
    print(f"📁 Cache location: {cache_dir.absolute()}")
    print("=" * 80)
    
except ImportError:
    print("❌ ERROR: gdown is not installed!")
    print()
    print("Install it with:")
    print("   pip install gdown")
    print()
    
except Exception as e:
    error_msg = str(e)
    print()
    print("=" * 80)
    print(f"❌ ERROR: {error_msg}")
    print("=" * 80)
    print()
    
    # If it's a 50-file limit error, try downloading subfolders
    if "50 files" in error_msg or "more than 50" in error_msg.lower():
        print("⚠️  Folder has more than 50 files. Trying to download subfolders individually...")
        print()
        
        try:
            import requests
            from bs4 import BeautifulSoup
            import re
            
            # Get subfolder IDs from Drive page
            page_url = f"https://drive.google.com/drive/folders/{FOLDER_ID}"
            response = requests.get(page_url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                folder_links = soup.find_all('a', href=re.compile(r'/drive/folders/([a-zA-Z0-9_-]+)'))
                
                subfolder_ids = []
                for link in folder_links:
                    href = link.get('href', '')
                    match = re.search(r'/drive/folders/([a-zA-Z0-9_-]+)', href)
                    if match:
                        sub_id = match.group(1)
                        folder_name = link.get_text(strip=True) or link.get('aria-label', '') or f"folder_{sub_id}"
                        if sub_id != FOLDER_ID and sub_id not in [s['id'] for s in subfolder_ids]:
                            subfolder_ids.append({'id': sub_id, 'name': folder_name})
                
                if subfolder_ids:
                    print(f"📁 Found {len(subfolder_ids)} subfolders. Downloading...")
                    print()
                    
                    for subfolder in subfolder_ids:
                        subfolder_cache = cache_dir / subfolder['name']
                        subfolder_cache.mkdir(parents=True, exist_ok=True)
                        
                        print(f"📥 Downloading: {subfolder['name']}...")
                        try:
                            subfolder_url = f"https://drive.google.com/drive/folders/{subfolder['id']}"
                            gdown.download_folder(subfolder_url, output=str(subfolder_cache), quiet=True, use_cookies=False)
                            print(f"   ✅ Downloaded: {subfolder['name']}")
                        except Exception as sub_e:
                            print(f"   ❌ Failed: {subfolder['name']} - {str(sub_e)[:50]}")
                    
                    print()
                    # Check results
                    downloaded_files = list(cache_dir.glob("**/*"))
                    video_files = [f for f in downloaded_files if f.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv', '.webm']]
                    
                    print("=" * 80)
                    print(f"✅ Download Complete!")
                    print(f"   Total files: {len(downloaded_files)}")
                    print(f"   Video files: {len(video_files)}")
                    print("=" * 80)
                else:
                    print("⚠️  No subfolders found in Drive page")
            else:
                print(f"⚠️  Could not access Drive page (Status: {response.status_code})")
        except ImportError:
            print("⚠️  Missing libraries. Install: pip install requests beautifulsoup4")
        except Exception as scrape_e:
            print(f"⚠️  Subfolder extraction failed: {str(scrape_e)[:100]}")
    else:
        print("Possible issues:")
        print("1. Folder is not shared/public")
        print("2. Folder is too large")
        print("3. Network connection issue")
        print("4. Folder ID is incorrect")
        print()
        print("Make sure:")
        print("- Folder is shared with 'Anyone with the link'")
        print("- Folder URL is correct")
        print()

