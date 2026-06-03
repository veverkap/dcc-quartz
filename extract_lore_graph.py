# /// script
# dependencies = [
#   "openai",
# ]
# ///
import os
import glob
import re
import json
from openai import OpenAI

# --- 1. SET UP QUARTZ WORKSPACE ---
def setup_quartz_dirs(base_quartz_dir):
    content_dir = os.path.join(base_quartz_dir, "content")
    subdirs = ["characters", "items", "factions", "locations", "mechanics"]
    for subdir in subdirs:
        os.makedirs(os.path.join(content_dir, subdir), exist_ok=True)
    return content_dir

# --- 2. SAVE INDIVIDUAL GRAPH ENTITIES ---
def save_entity_file(content_dir, entity_block):
    title_match = re.search(r'title:\s*(.+)$', entity_block, re.MULTILINE)
    if not title_match:
        title_match = re.search(r'^#\s+(.+)$', entity_block, re.MULTILINE)
    if not title_match:
        return
        
    entity_name = title_match.group(1).strip().replace('[', '').replace(']', '').replace('"', '')
    # Clean up filename (remove special chars, swap spaces for underscores)
    cleaned_name = re.sub(r'[^a-zA-Z0-9_\- ]', '', entity_name).strip().replace(' ', '_').lower()
    
    # --- ENFORCE OPERATING SYSTEM FILENAME LIMITS ---
    if len(cleaned_name) > 100:
        print(f"   [!] Warning: Extremely long title detected ('{entity_name[:30]}...'). Truncating filename.")
        cleaned_name = cleaned_name[:100].rstrip('_')
        
    safe_filename = cleaned_name + ".md"
    
    type_match = re.search(r'type:\s*(.+)$', entity_block, re.MULTILINE)
    type_str = "mechanics"
    if type_match:
        type_str = type_match.group(1).strip().lower().replace('[', '').replace(']', '').replace('"', '')

    folder_map = {
        "crawler": "characters", "main character": "characters", "npc": "characters", "deity": "characters", "god": "characters",
        "item": "items", "spell": "items", "equipment": "items", "weapon": "items",
        "faction": "factions", "corporation": "factions",
        "floor": "locations", "room": "locations", "zone": "locations"
    }
    
    target_folder = "mechanics"
    for key, folder in folder_map.items():
        if key in type_str:
            target_folder = folder
            break
            
    final_path = os.path.join(content_dir, target_folder, safe_filename)
    
    # --- DEFENSIVE FRONTMATTER ESCAPING ---
    # Escape any existing double quotes in the title text, then wrap the entire frontmatter string 
    # to safeguard against unquoted colons (e.g., "title: Dungeon Crawler World: Earth")
    safe_title_yaml = entity_name.replace('"', '\\"')
    
    # Strip whatever loose frontmatter the LLM returned, and rebuild a pristine, sanitized frontmatter block
    clean_body_only = re.sub(r'---.*?---', '', entity_block, flags=re.DOTALL).strip()
    
    sanitized_entity_block = (
        f"---\n"
        f"title: \"{safe_title_yaml}\"\n"
        f"type: {target_folder.capitalize().rstrip('s')}\n"
        f"tags: [dcc-lore-graph]\n"
        f"---\n"
        f"# {entity_name}\n\n"
        f"{clean_body_only}"
    )
    
    if os.path.exists(final_path):
        with open(final_path, 'a', encoding='utf-8') as f:
            f.write(f"\n\n## Additional Observations\n{clean_body_only}")
    else:
        with open(final_path, 'w', encoding='utf-8') as f:
            f.write(sanitized_entity_block.strip())
            
    print(f"   [+] Synced: {target_folder}/{safe_filename}")

# --- 3. PROCESS CHAPTER TEXT ---
def process_chapter_text(client, model_id, chapter_text, content_dir):
    system_prompt = """
    You are an expert graph lore analyst specialized in processing the LitRPG book series 'Dungeon Crawler Carl'.
    Analyze the provided chapter text and extract ONLY notable entities that match the following structural taxonomy.
    
    CRITICAL: You are strictly restricted to assigning one of these five exact strings to the 'type' field. Do not invent sub-types or variations:
    1. Character (Use for Crawlers, NPCs, Deities, Gods, Hunters, Mobs, and named beasts)
    2. Item (Use for Weapons, Equipment, Spells, Potions, Scrolls, and Artifacts)
    3. Faction (Use for Guilds, Syndicates, Corporations, Alliances, and Sponsor groups)
    4. Location (Use for Floors, Rooms, Zones, Castles, and specific geometric settings)
    5. Mechanic (Use ONLY for active System Announcements, Achievements, and explicit Dungeon Rules)
    
    For EVERY entity found, output a completely standalone Markdown documentation block wrapped inside a '---ENTITY_START---' and '---ENTITY_END---' delimiter.
    Matches must strictly use standard internal markdown wiki-links `[[Entity Name]]` for graph connectivity.
    
    Example Schema output:
    ---ENTITY_START---
    title: "Entity Name"
    type: Character
    tags: [dcc-lore-graph]
    ---
    # Entity Name
    Contextual description...
    ---ENTITY_END---
    """
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Analyze this chapter text:\n\n{chapter_text}"}
        ],
        temperature=0.2
    )
    raw_output = response.choices[0].message.content
    entity_blocks = re.findall(r'---ENTITY_START---(.*?)---ENTITY_END---', raw_output, re.DOTALL)
    for block in entity_blocks:
        save_entity_file(content_dir, block)

# --- 4. INLINE INTER-BOOK RECONCILIATION ---
def reconcile_book_boundary(client, model_id, base_quartz_dir, folder_name="characters"):
    """Deduplicates loose character files and heals wiki-links mid-run."""
    target_dir = os.path.join(base_quartz_dir, "content", folder_name)
    files = glob.glob(os.path.join(target_dir, "*.md"))
    entity_names = [os.path.splitext(os.path.basename(f))[0] for f in files]
    
    if len(entity_names) < 2:
        return

    print(f"\n[🔄] Triggering Automatic Reconciliation Layer for {folder_name}...")
    
    system_prompt = """
    You are a data deduplication utility. You will be given a list of filenames representing lore entities from 'Dungeon Crawler Carl'.
    Identify which names represent the EXACT same entity. Select the most accurate name as the 'canonical' name.
    Output strictly a JSON object mapping duplicate aliases to their single canonical name. Include ONLY items with duplicates.
    """
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(entity_names)}
        ],
        response_format={"type": "json_object"},
        temperature=0.0
    )
    alias_map = json.loads(response.choices[0].message.content)
    
    if not alias_map:
        print("[+] No mid-run duplicates found. Vault is structurally optimized.")
        return

    print(f"   [!] Found duplicates to resolve: {json.dumps(alias_map)}")
    
    # Merge file contents
    for alias, canonical in alias_map.items():
        alias_path = os.path.join(target_dir, f"{alias}.md")
        canonical_path = os.path.join(target_dir, f"{canonical}.md")
        
        if os.path.exists(alias_path):
            with open(alias_path, 'r', encoding='utf-8') as f:
                alias_content = f.read()
            clean_alias_text = re.sub(r'---.*?---', '', alias_content, flags=re.DOTALL).strip()
            with open(canonical_path, 'a', encoding='utf-8') as f:
                f.write(f"\n\n## Automated Merge Entry ({alias})\n{clean_alias_text}")
            os.remove(alias_path)

    # Heal all cross-links everywhere
    all_vault_files = glob.glob(os.path.join(base_quartz_dir, "content", "**", "*.md"), recursive=True)
    for file_path in all_vault_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        updated = False
        for alias, canonical in alias_map.items():
            alias_link = alias.replace('_', ' ')
            canonical_link = canonical.replace('_', ' ')
            pattern = re.compile(r'\[\[\s*' + re.escape(alias_link) + r'\s*\]\]', re.IGNORECASE)
            if pattern.search(content):
                content = pattern.sub(f"[[{canonical_link}]]", content)
                updated = True
        if updated:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
    print("[+] Mid-run graph connections updated and synchronized successfully.\n")

# --- 5. STATE LEDGER MANAGEMENT ---
def load_state_ledger(ledger_path):
    if os.path.exists(ledger_path):
        with open(ledger_path, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()

def save_state_ledger(ledger_path, processed_set):
    with open(ledger_path, 'w', encoding='utf-8') as f:
        json.dump(list(processed_set), f, indent=2)

# --- 6. CORE PIPELINE CONTROL ---
def main():
    client = OpenAI(
        base_url=os.environ.get("COPILOT_API_BASE"),
        api_key=os.environ.get("COPILOT_API_KEY")
    )
    TARGET_MODEL = "gpt-5-mini"
    CHAPTERS_SRC_DIR = "./extracted_series_chapters"
    QUARTZ_WORKSPACE_DIR = "/Users/veverkap/Code/personal/dcc-lore"
    LEDGER_FILE_PATH = os.path.join(CHAPTERS_SRC_DIR, ".processed_chapters.json")
    
    content_dir = setup_quartz_dirs(QUARTZ_WORKSPACE_DIR)
    processed_files = load_state_ledger(LEDGER_FILE_PATH)
    chapter_files = sorted(glob.glob(os.path.join(CHAPTERS_SRC_DIR, "**", "*.txt"), recursive=True))
    
    if not chapter_files:
        print("[-] Error: No raw text chapters found.")
        return
        
    print(f"[=] Launching Integrated Graph Pipeline via model: {TARGET_MODEL}")
    
    current_book_folder = None
    
    try:
        for file_path in chapter_files:
            file_id = os.path.relpath(file_path, CHAPTERS_SRC_DIR)
            filename_lower = os.path.basename(file_path).lower()
            
            # Detect what book folder we are currently traversing
            # e.g., '1_Dungeon_Crawler_Carl_-_Matt_Dinniman_2020'
            path_parts = file_id.split(os.sep)
            book_folder = path_parts[0] if len(path_parts) > 1 else None
            
            # --- BOOK BOUNDARY DETECTOR ---
            # If we switch to a new book folder, run reconciliation on the previous book's data
            if current_book_folder and book_folder != current_book_folder:
                print(f"\n[🏁] Reached edge boundary for: {current_book_folder}")
                reconcile_book_boundary(client, TARGET_MODEL, QUARTZ_WORKSPACE_DIR, "characters")
                reconcile_book_boundary(client, TARGET_MODEL, QUARTZ_WORKSPACE_DIR, "items")
            
            current_book_folder = book_folder
            
            if file_id in processed_files:
                print(f"[-] Skipping (already processed in history): {filename_lower}")
                continue
                
            if any(skip_word in filename_lower for skip_word in ["title", "copyright", "toc", "intro", "preface"]):
                print(f"[-] Skipping metadata file: {os.path.basename(file_path)}")
                processed_files.add(file_id)
                continue
                
            
            with open(file_path, 'r', encoding='utf-8') as f:
                chapter_content = f.read()
                
            content_peek = chapter_content[:600].lower()
            meta_indicators = ["all rights reserved", "edited by", "cover illustration", "copyright ©", "published by", "patreon", "thanks to all of my readers"]
            if any(indicator in content_peek for indicator in meta_indicators):
                processed_files.add(file_id)
                continue
                
            print(f"[*] Processing: {current_book_folder} -> {filename_lower}")
            process_chapter_text(client, TARGET_MODEL, chapter_content, content_dir)
            processed_files.add(file_id)
            
        # --- FINAL CLOSING BOUNDARY ---
        # Run reconciliation one last time when the final file loop finishes
        if current_book_folder:
            print(f"\n[🏁] Reached end of series execution line on: {current_book_folder}")
            reconcile_book_boundary(client, TARGET_MODEL, QUARTZ_WORKSPACE_DIR, "characters")
            reconcile_book_boundary(client, TARGET_MODEL, QUARTZ_WORKSPACE_DIR, "items")
            exit(0)

    except KeyboardInterrupt:
        print("\n[!] Processing paused. State synchronized safely to disk.")
    finally:
        save_state_ledger(LEDGER_FILE_PATH, processed_files)
        print("[=] Execution layer complete.")

if __name__ == "__main__":
    main()