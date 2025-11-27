# synod/core/context.py
import os
from typing import List, Optional

def read_file_content(file_paths: List[str], base_dir: Optional[str] = None) -> str:
    """
    Reads the content of specified files and formats them into a single string
    suitable for providing context to an LLM.

    Args:
        file_paths (List[str]): A list of file paths to read.
        base_dir (Optional[str]): The base directory to resolve relative paths against.
                                  Defaults to the current working directory.

    Returns:
        str: A formatted string containing the file contents, or an empty string
             if no files could be read.
    """
    if not file_paths:
        return ""

    context_lines = []
    for rel_path in file_paths:
        file_path = os.path.join(base_dir or os.getcwd(), rel_path) if not os.path.isabs(rel_path) else rel_path
        
        if not os.path.exists(file_path):
            context_lines.append(f"--- File Not Found: {rel_path} ---")
            continue
        if not os.path.isfile(file_path):
            context_lines.append(f"--- Path is a Directory: {rel_path} ---")
            continue

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            context_lines.append(f"--- START FILE: {rel_path} ---")
            context_lines.append(content)
            context_lines.append(f"--- END FILE: {rel_path} ---")
        except Exception as e:
            context_lines.append(f"--- Error reading {rel_path}: {e} ---")

    return "\n".join(context_lines)

# Example usage (for testing purposes, not part of actual CLI execution)
if __name__ == "__main__":
    # Create some dummy files for testing
    with open("test_file_1.py", "w") as f:
        f.write("def hello_world():\n    print('Hello, World!')\n")
    with open("test_file_2.txt", "w") as f:
        f.write("This is a test file.\nIt has multiple lines.\n")
    
    # Test reading existing files
    context = read_file_content(["test_file_1.py", "test_file_2.txt", "non_existent_file.md"])
    print("--- Generated Context ---")
    print(context)
    print("--- End Generated Context ---")

    # Clean up dummy files
    os.remove("test_file_1.py")
    os.remove("test_file_2.txt")
