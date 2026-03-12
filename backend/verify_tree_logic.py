import json
from app.services.tree_extractor import tree_extractor

def verify_tree_output():
    tree = tree_extractor.get_full_tree()
    if not tree:
        print("No tree extracted.")
        return
        
    print(f"Document: {tree.get('name')}")
    
    # Recursive print helper
    def print_node(node, depth=0):
        indent = "  " * depth
        print(f"{indent}- {node.get('name')} ({node.get('type')})")
        for child in node.get('children', []):
            print_node(child, depth + 1)

    print_node(tree)

if __name__ == "__main__":
    verify_tree_output()
