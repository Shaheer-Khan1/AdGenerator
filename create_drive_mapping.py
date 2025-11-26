"""
Helper script to create drive_videos.json from your Google Drive folder.

Usage:
1. List your videos manually in this script
2. Run: python create_drive_mapping.py
3. It will generate drive_videos.json
"""

import json

# === EDIT THIS SECTION WITH YOUR VIDEOS ===

videos = {
    "Glow Coffee": [
        # Format: ("FILE_ID", "filename.mp4")
        # Get FILE_ID from: https://drive.google.com/file/d/FILE_ID/view
        
        # Example entries - REPLACE WITH YOUR ACTUAL DATA:
        ("SAMPLE_ID_1", "coffee_pour_v1.mp4"),
        ("SAMPLE_ID_2", "coffee_product_showcase.mp4"),
        ("SAMPLE_ID_3", "woman_drinking_coffee.mp4"),
        # Add more videos here...
    ],
    
    "Hair": [
        ("SAMPLE_ID_4", "hair_brush_smooth.mp4"),
        ("SAMPLE_ID_5", "shiny_hair_closeup.mp4"),
        # Add more videos here...
    ],
    
    "Product": [
        ("SAMPLE_ID_6", "product_packaging.mp4"),
        ("SAMPLE_ID_7", "before_after_comparison.mp4"),
        # Add more videos here...
    ],
    
    "Wrinkles": [
        ("SAMPLE_ID_8", "wrinkle_cream_application.mp4"),
        # Add more videos here...
    ],
    
    "Cellulite": [
        # Add your cellulite videos here...
    ],
    
    "Joints": [
        # Add your joint videos here...
    ],
    
    "Menopause": [
        # Add your menopause videos here...
    ],
    
    "Nails": [
        # Add your nail videos here...
    ],
    
    "Others": [
        # Add other videos here...
    ]
}

# === END OF EDIT SECTION ===

def create_json():
    """Convert the videos dict to proper JSON format"""
    output = {}
    
    for folder_name, video_list in videos.items():
        output[folder_name] = {
            "videos": [
                {"id": video_id, "name": video_name}
                for video_id, video_name in video_list
            ]
        }
    
    # Save to file
    with open("drive_videos.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print("✅ Created drive_videos.json!")
    print(f"\nTotal folders: {len(output)}")
    print(f"Total videos: {sum(len(folder['videos']) for folder in output.values())}")
    print("\nFolder breakdown:")
    for folder_name, data in output.items():
        video_count = len(data['videos'])
        if video_count > 0:
            print(f"  📁 {folder_name}: {video_count} videos")
            for video in data['videos'][:3]:
                print(f"     - {video['name']}")
            if video_count > 3:
                print(f"     ... and {video_count - 3} more")

if __name__ == "__main__":
    create_json()

