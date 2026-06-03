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

def get_all_filenames(target_dir):
    """Gathers all markdown filenames within a specific subdirectory folder."""
    files = glob.glob(os.path.join(target_dir, "*.md"))
    return [os.path.splitext(os.path.basename(f))[0] for f in files]

def generate_alias_map(client, model_id, entity_names):
    """Asks the LLM to group semantic duplicates into a canonical map."""
    system_prompt = """
    You are a data deduplication utility. You will be given a list of filenames representing lore entities from 'Dungeon Crawler Carl'.
    Identify which names represent the EXACT same entity (e.g., 'donut', 'princess_donut', and 'princess_donut_the_queen_anne_chonk' are all the same cat).
    Select the most accurate, recognizable name as the 'canonical' name.
    
    Output strictly a JSON object mapping duplicate aliases to their single canonical name. 
    Only include items that actually have duplicates. Keep keys and values exactly as they appear in the input list.
    
    Example Output:
    {
      "donut": "princess_donut",
      "bea": "beatrice_bea",
      "princess_donut_the_queen_anne_chonk": "princess_donut"
    }
    """
    
    # FIX #1: Fixed missing "content" key mapping structure to prevent API payload rejection crashes
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Analyze this list of entities:\n{json.dumps(entity_names)}"}
        ],
        response_format={"type": "json_object"},
        temperature=0.0
    )
    
    return json.loads(response.choices[0].message.content)

def merge_and_rewrite_vault(base_vault_dir, alias_map, folder_name):
    """Merges duplicate markdown files and updates all cross-links across the vault."""
    target_dir = os.path.join(base_vault_dir, "content", folder_name)
    all_vault_files = glob.glob(os.path.join(base_vault_dir, "content", "**", "*.md"), recursive=True)
    
    # 1. Merge the file content together
    for alias, canonical in alias_map.items():
        alias_path = os.path.join(target_dir, f"{alias}.md")
        canonical_path = os.path.join(target_dir, f"{canonical}.md")
        
        if os.path.exists(alias_path):
            print(f"   [>] Merging content: {folder_name}/{alias}.md ──> {canonical}.md")
            with open(alias_path, 'r', encoding='utf-8') as f:
                alias_content = f.read()
                
            clean_alias_text = re.sub(r'---.*?---', '', alias_content, flags=re.DOTALL).strip()
            
            with open(canonical_path, 'a', encoding='utf-8') as f:
                f.write(f"\n\n## Reconciled Observations ({alias})\n{clean_alias_text}")
                
            os.remove(alias_path)

    # 2. Rewrite cross-links everywhere so Quartz connects edges cleanly
    print(f"[*] Healing cross-linked wiki-graph edges for {folder_name}...")
    for file_path in all_vault_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        updated = False
        for alias, canonical in alias_map.items():
            alias_link_term = alias.replace('_', ' ')
            canonical_link_term = canonical.replace('_', ' ')
            
            pattern = re.compile(r'\[\[\s*' + re.escape(alias_link_term) + r'\s*\]\]', re.IGNORECASE)
            
            if pattern.search(content):
                content = pattern.sub(f"[[{canonical_link_term}]]", content)
                updated = True
                
        if updated:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

# --- 4. NEW WORKFLOW AUTOMATION: WIKI DIFF SUGGESTIONS ENGINE ---
def generate_wiki_suggestions(extracted_dir="extracted_lore", fandom_dir="fandom_archive"):
    """Compares locally extracted records against the fandom archive to locate missing wiki pages."""
    print("\n🤖 Generating Actionable Fandom Wiki Suggestion Ledger...")
    print("====================================================================")
    
    if not os.path.exists(extracted_dir) or not os.path.exists(fandom_dir):
        print("[-] Skipping suggestions: Either 'extracted_lore' or 'fandom_archive' directory is missing.")
        return

    new_entities = []
    missing_metadata = []

    for filename in os.listdir(extracted_dir):
        if not filename.endswith(".json"):
            continue
            
        with open(os.path.join(extracted_dir, filename), "r", encoding="utf-8") as f:
            ai_data = json.load(f)
            
        entity_title = ai_data["title"]
        fandom_file_path = os.path.join(fandom_dir, filename)
        
        # Scenario A: Page is missing entirely from the central fan wiki
        if not os.path.exists(fandom_file_path):
            new_entities.append(entity_title)
            continue
            
        # Scenario B: Page exists, but it's an empty template stub
        with open(fandom_file_path, "r", encoding="utf-8") as f:
            fandom_data = json.load(f)
            
        if len(ai_data["content"]) > 200 and len(fandom_data["content"]) == 0:
            missing_metadata.append(entity_title)

    if new_entities:
        print("\n✨ [NEW PAGES TO CREATE] Missing completely from the Fandom Wiki:")
        for entity in sorted(new_entities):
            print(f"  + {entity}")
            
    if missing_metadata:
        print("\n📝 [EDITS TO SUGGEST] Fandom stub needs text info injected from your local logs:")
        for item in sorted(missing_metadata):
            print(f"  • {item}")
            
    if not new_entities and not missing_metadata:
        print("\n✅ Perfect synchronization achieved across all local models and Fandom branches!")

def main():
    client = OpenAI(
        base_url=os.environ.get("COPILOT_API_BASE"),
        api_key=os.environ.get("COPILOT_API_KEY")
    )
    TARGET_MODEL = "gpt-5-mini" 
    
    # FIX #2: Synchronized with your absolute active development workspace location
    QUARTZ_WORKSPACE_DIR = "/Users/veverkap/Code/personal/dcc-lore"
    
    # Loop over all 5 subcategories to keep the entire vault topology clean
    taxonomies = ["characters", "items", "factions", "locations", "mechanics"]
    
    print(f"[=] Initializing Global Optimization Sequence via {TARGET_MODEL}...")
    
    for folder in taxonomies:
        target_path = os.path.join(QUARTZ_WORKSPACE_DIR, "content", folder)
        if not os.path.exists(target_path):
            continue
            
        entity_names = get_all_filenames(target_path)
        if len(entity_names) < 2:
            continue
            
        print(f"\n[*] Scanning '{folder}' folder for layout duplicates...")
        alias_map = generate_alias_map(client, TARGET_MODEL, entity_names)
        
        if alias_map:
            print(f"[+] Identified Duplicate Map: {json.dumps(alias_map, indent=2)}")
            merge_and_rewrite_vault(QUARTZ_WORKSPACE_DIR, alias_map, folder)
        else:
            print(f"[+] No duplicates detected inside '{folder}'.")

    print("\n[=] Graph Optimization Complete!")
    
    # Run the auditing suggestions comparison cycle
    generate_wiki_suggestions()

if __name__ == "__main__":
    main()