import sys
import os

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from pycatia import catia
from pycatia.space_analyses_interfaces.spa_workbench import SPAWorkbench
from pycatia.mec_mod_interfaces.part_document import PartDocument

def test_bbox():
    try:
        caa = catia()
        documents = caa.documents
        
        target_doc = None
        for i in range(1, documents.count + 1):
            doc = documents.item(i)
            if ".CATPart" in doc.name:
                target_doc = doc
                break
        
        if not target_doc:
            print("No CATPart found open.")
            return

        print(f"Target Document: {target_doc.name}")
        
        part_doc = PartDocument(target_doc.com_object)
        part = part_doc.part
        
        # In pycatia, SPAWorkbench(com_object) expects the object that HAS GetWorkbench method
        spa = SPAWorkbench(target_doc.com_object)
        
        body = part.main_body
        print(f"MainBody: {body.name}")
        
        ref = part.create_reference_from_object(body)
        meas = spa.get_measurable(ref)
        
        print("Attempting get_boundary_box...")
        bbox = meas.get_boundary_box()
        print(f"Bounding Box: {bbox}")
        
        if bbox:
            l = abs(bbox[3] - bbox[0])
            w = abs(bbox[4] - bbox[1])
            h = abs(bbox[5] - bbox[2])
            print(f"L={l}, W={w}, H={h}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")

if __name__ == "__main__":
    test_bbox()
