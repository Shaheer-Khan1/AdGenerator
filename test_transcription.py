"""
Test script to test folder and video selection with a transcription
"""

import asyncio
import json
import sys
import os

# Add the current directory to path to import from main.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import necessary functions from main.py
from main import get_exact_videos_from_gemini, list_drive_folders_and_files, GOOGLE_DRIVE_FOLDER_ID

async def test_transcription():
    """Test the transcription processing"""
    
    transcription = "have so many wrinkles, I love to try new products to reduce my wrinkles every day. And I also enjoy taking my dog to the park."
    
    print("=" * 80)
    print("🧪 Testing Folder and Video Selection")
    print("=" * 80)
    print(f"\n📝 Transcription:")
    print(f"   {transcription}\n")
    print("=" * 80)
    print()
    
    # Get drive structure
    print("📁 Loading Drive folder structure...")
    drive_structure = list_drive_folders_and_files(GOOGLE_DRIVE_FOLDER_ID)
    
    if not drive_structure:
        print("❌ ERROR: Could not load Drive folder structure")
        print("   Make sure GOOGLE_DRIVE_FOLDER_ID is set correctly")
        return
    
    print(f"✅ Found {len(drive_structure)} folders:")
    for folder_name in drive_structure.keys():
        print(f"   - {folder_name}")
    print()
    
    # Test Gemini selection
    print("🤖 Calling Gemini AI to select folders...")
    print()
    
    try:
        result = await get_exact_videos_from_gemini(transcription, drive_structure)
        
        print("=" * 80)
        print("✅ RESULTS")
        print("=" * 80)
        print()
        
        print(f"📦 Product Mentioned: {result.get('product_mentioned', 'None')}")
        print()
        
        folders = result.get('folders', [])
        print(f"📁 Selected Folders: {len(folders)}")
        print()
        
        total_videos = 0
        for folder_info in folders:
            folder_name = folder_info.get('name', 'Unknown')
            videos = folder_info.get('videos', [])
            total_videos += len(videos)
            
            print(f"   📁 {folder_name}")
            print(f"      Videos: {len(videos)}")
            if videos:
                for i, video in enumerate(videos[:5], 1):  # Show first 5
                    video_name = video.get('name', 'unknown')
                    local_path = video.get('local_path', 'N/A')
                    cached = video.get('cached', False)
                    print(f"      {i}. {video_name}")
                    print(f"         Path: {local_path}")
                    print(f"         Cached: {cached}")
                if len(videos) > 5:
                    print(f"      ... and {len(videos) - 5} more")
            print()
        
        print(f"📊 Total Videos Selected: {total_videos}")
        print()
        print("=" * 80)
        
        if total_videos == 0:
            print("⚠️  WARNING: No videos were selected!")
            print("   This might mean:")
            print("   - Folders couldn't be downloaded")
            print("   - No videos found in selected folders")
            print("   - Drive folder is not accessible")
        elif total_videos > 10:
            print(f"⚠️  WARNING: {total_videos} videos selected (expected max 10)")
        else:
            print(f"✅ Success! Selected {total_videos} videos (within limit of 10)")
        
    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ ERROR: {str(e)}")
        print("=" * 80)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_transcription())
