# /// script
# dependencies = [
#   "ebooklib",
#   "beautifulsoup4",
# ]
# ///
import os
import re
import glob
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

def clean_html_to_text(html_content):
    """Strips HTML tags and formatting, returning clean plaintext blocks."""
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text(separator="\n")

def extract_single_epub(epub_path, base_output_dir):
    """Reads a single EPUB file and extracts individual chapters into text files."""
    # Create a safe directory name based on the book filename (e.g., "Dungeon_Crawler_Carl_1")
    book_filename = os.path.splitext(os.path.basename(epub_path))[0]
    safe_book_dir = re.sub(r'[^a-zA-Z0-9_\- ]', '', book_filename).strip().replace(' ', '_')
    book_output_dir = os.path.join(base_output_dir, safe_book_dir)
    
    print(f"\n[*] Processing Book: {book_filename}")
    print(f"[*] Target directory: {book_output_dir}")
    
    os.makedirs(book_output_dir, exist_ok=True)
    
    try:
        # ebooklib requires ignore_extra_images to safely load text-heavy files without crashing
        book = epub.read_epub(epub_path, options={"ignore_extra_images": True})
    except Exception as e:
        print(f"[-] Error reading archival data for {book_filename}: {e}")
        return

    chapter_counter = 1
    
    # Iterate through all structural documents inside the EPUB binary
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            raw_html = item.get_content()
            clean_text = clean_html_to_text(raw_html).strip()
            
            # Filter out empty files, copyright pages, or table of contents lists
            if len(clean_text) < 400:
                continue
                
            # Try to extract a clean chapter title from the first few lines
            first_lines = [line.strip() for line in clean_text.split('\n') if line.strip()][:3]
            title_guess = " ".join(first_lines)
            
            # Simple regex clean to ensure a safe, standard filename string
            safe_title = re.sub(r'[^a-zA-Z0-9_\- ]', '', title_guess).strip().replace(' ', '_')
            if not safe_title or len(safe_title) > 50:
                safe_title = f"Chapter_{chapter_counter:02d}"
            
            filename = f"ch_{chapter_counter:02d}_{safe_title}.txt"
            file_path = os.path.join(book_output_dir, filename)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(clean_text)
                
            print(f"   [+] Extracted: {filename} ({len(clean_text)} chars)")
            chapter_counter += 1

    print(f"[+] Finished extracting: {book_filename}")

def main():
    BOOKS_SRC_DIR = "./private_books"
    OUTPUT_WORKSPACE_DIR = "./extracted_series_chapters"
    
    # Setup source directory if it doesn't exist
    if not os.path.exists(BOOKS_SRC_DIR):
        print(f"[!] Target folder '{BOOKS_SRC_DIR}' not found. Creating it now...")
        os.makedirs(BOOKS_SRC_DIR, exist_ok=True)
        print(f"[i] Please drop your .epub files into the '{BOOKS_SRC_DIR}/' folder and re-run the script.")
        return

    # Gather and sort all epubs in the source directory alphabetical/numerical order
    epub_files = sorted(glob.glob(os.path.join(BOOKS_SRC_DIR, "*.epub")))
    
    if not epub_files:
        print(f"[-] No .epub files found inside '{BOOKS_SRC_DIR}/'. Zero items processed.")
        return
        
    print(f"[=] Found {len(epub_files)} book files inside '{BOOKS_SRC_DIR}/'. Starting pipeline...")
    
    for epub_path in epub_files:
        extract_single_epub(epub_path, OUTPUT_WORKSPACE_DIR)
        
    print(f"\n[=] Batch Processing Execution Finished! Check results in: {OUTPUT_WORKSPACE_DIR}")

if __name__ == "__main__":
    main()