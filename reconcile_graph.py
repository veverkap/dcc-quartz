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
    
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "system_prompt"},
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
            print(f"   [>] Merging content: {alias}.md ──> {canonical}.md")
            with open(alias_path, 'r', encoding='utf-8') as f:
                alias_content = f.read()
                
            # Strip front-matter boilerplate from the alias file before merging
            clean_alias_text = re.sub(r'---.*?---', '', alias_content, flags=re.DOTALL).strip()
            
            # Append observations directly to the canonical note file
            with open(canonical_path, 'a', encoding='utf-8') as f:
                f.write(f"\n\n## Reconciled Observations ({alias})\n{clean_alias_text}")
                
            # Safe delete the old duplicated alias note file
            os.remove(alias_path)

    # 2. Rewrite cross-links everywhere so Quartz connects edges cleanly
    print("[*] Rewriting wiki-links across all files to heal graph edges...")
    for file_path in all_vault_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        updated = False
        for alias, canonical in alias_map.items():
            # Turn safe filenames back into readable wiki-link terms for the regex check
            # e.g., 'princess_donut' -> 'Princess Donut'
            alias_link_term = alias.replace('_', ' ')
            canonical_link_term = canonical.replace('_', ' ')
            
            # Case-insensitive pattern matching for [[alias link]] style formats
            pattern = re.compile(r'\[\[\s*' + re.escape(alias_link_term) + r'\s*\]\]', re.IGNORECASE)
            
            if pattern.search(content):
                content = pattern.sub(f"[[{canonical_link_term}]]", content)
                updated = True
                
        if updated:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

def main():
    client = OpenAI(
        base_url=os.environ.get("COPILOT_API_BASE"),
        api_key=os.environ.get("COPILOT_API_KEY")
    )
    TARGET_MODEL = "gpt-5-mini" 
    QUARTZ_WORKSPACE_DIR = "./quartz-lore-vault"
    
    # Run reconciliation on the characters directory first
    char_dir = os.path.join(QUARTZ_WORKSPACE_DIR, "content", "characters")
    if not os.path.exists(char_dir):
        print("[-] Target content folder does not exist yet.")
        return
        
    print("[*] Scanning characters folder for layout duplicates...")
    entity_names = get_all_filenames(char_dir)
    
    if len(entity_names) < 2:
        print("[-] Not enough entities to evaluate duplicates.")
        return
        
    print(f"[*] Mapping aliases using {TARGET_MODEL}...")
    alias_map = generate_alias_map(client, TARGET_MODEL, entity_names)
    
    if not alias_map:
        print("[+] No duplicates detected by the model. Graph is clean.")
        return
        
    print(f"[+] Identified Duplicate Map: {json.dumps(alias_map, indent=2)}")
    merge_and_rewrite_vault(QUARTZ_WORKSPACE_DIR, alias_map, "characters")
    print("[=] Graph Optimization Complete!")

if __name__ == "__main__":
    main()