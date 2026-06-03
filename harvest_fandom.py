# archive_fandom.py
import requests
import json
import os
import time
import re

def sanitize_filename(name):
    """Sanitizes page titles to ensure they are legal filesystem names on macOS/Linux/Windows."""
    # Replace slashes, colons, and backslashes with dashes to avoid directory nesting issues
    return re.sub(r'[\\/*?:"<>|]', "-", name).strip()

def archive_fandom_to_individual_files():
    api_url = "https://dungeon-crawler-carl.fandom.com/api.php"
    headers = {
        "User-Agent": "DCCCrawlerArchiveBot/1.0 (Contact: veverkap@github; Split File Data Extraction Engine)"
    }
    
    # Target output folder name
    output_dir = "fandom_archive"
    os.makedirs(output_dir, exist_ok=True)
    
    params = {
        "action": "query",
        "format": "json",
        "generator": "allpages",
        "gapnamespace": 0,
        "gaplimit": 50,
        "prop": "revisions|categories",
        "rvprop": "content",
        "cllimit": "max"
    }
    
    batch_count = 1
    total_saved = 0
    
    print(f"Initiating full backup. Output folder targeted: ./{output_dir}/")
    print("---------------------------------------------------------------")
    
    while True:
        print(f"Ingesting API batch #{batch_count}...")
        response = requests.get(api_url, headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"Connection lost: HTTP {response.status_code}")
            return
            
        data = response.json()
        pages_dict = data.get("query", {}).get("pages", {})
        
        for page_id, page_info in pages_dict.items():
            title = page_info.get("title")
            
            # Skip common administrative or directory files
            if not title or any(skip in title.lower() for skip in ["mediaf", "list of", "special:"]):
                continue
                
            categories = [
                cat.get("title", "").replace("Category:", "") 
                for cat in page_info.get("categories", [])
            ]
            
            revisions = page_info.get("revisions", [])
            raw_content = ""
            if revisions:
                raw_content = revisions[0].get("slots", {}).get("main", {}).get("*", "")
                if not raw_content:
                    raw_content = revisions[0].get("*", "")
            
            # Prepare the singular entity record payload
            entity_data = {
                "title": title,
                "categories": categories,
                "content": raw_content.strip()
            }
            
            # Safely generate a unique filename
            safe_name = sanitize_filename(title)
            file_path = os.path.join(output_dir, f"{safe_name}.json")
            
            # Write the single record cleanly to disk
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(entity_data, f, indent=2, ensure_ascii=False)
                
            total_saved += 1
            
        if "continue" in data:
            params.update(data["continue"])
            batch_count += 1
            time.sleep(0.1)  # Respectful API pause
        else:
            break
            
    print("---------------------------------------------------------------")
    print("Backup sequence complete!")
    print(f"Successfully wrote {total_saved} individual JSON profiles into './{output_dir}/'.")

if __name__ == "__main__":
    archive_fandom_to_individual_files()