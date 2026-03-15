import sys
import os
import logging
import json

sys.path.append(os.getcwd())

from app.services.catia_bridge import catia_bridge
from app.services.tree_extractor import tree_extractor

logging.basicConfig(level=logging.ERROR)

def prove_extraction():
    tree = tree_extractor.get_full_tree()
    if not tree:
        print("ERROR: Could not extract tree.")
        return

    results = []
    def collect(node):
        if node.get("properties") and node.get("type") in ["Part", "Component"]:
            results.append({
                "Name": node["name"],
                "Size": node["properties"].get("stock_size", "N/A"),
                "Mat": node["properties"].get("material", "N/A"),
                "Dimensions": node["properties"].get("dimensions", {})
            })
        for child in node.get("children", []):
            collect(child)
    
    collect(tree)
    
    output_data = {
        "Document": tree['name'],
        "TotalParts": len(results),
        "Parts": results
    }
    
    with open("bom_proof.json", "w") as f:
        json.dump(output_data, f, indent=2)
        
    print(f"Successfully wrote {len(results)} parts to bom_proof.json")

if __name__ == "__main__":
    prove_extraction()
