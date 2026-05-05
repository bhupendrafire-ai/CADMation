
import os
import sys
import unittest
import json
import shutil

# Setup paths
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.services.bom_cache_service import BOMCacheService

class TestBOMCacheService(unittest.TestCase):
    def setUp(self):
        self.service = BOMCacheService()
        # Override cache dir for testing
        self.test_dir = os.path.join(os.getcwd(), "test_bom_brain")
        self.service.cache_dir = self.test_dir
        os.makedirs(self.test_dir, exist_ok=True)
        self.project = "TestProject"

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_save_and_load(self):
        instance = "Part.1"
        data = {"stock_size": "100x50x20", "method": "STL"}
        
        # Save
        self.service.save_item(self.project, instance, data)
        
        # Load
        loaded = self.service.load_all(self.project)
        self.assertIn(instance, loaded)
        self.assertEqual(loaded[instance]["stock_size"], "100x50x20")

    def test_merge_updates(self):
        instance = "Part.1"
        
        # Initial save
        self.service.save_item(self.project, instance, {"stock_size": "100x50x20"})
        
        # Update with body name
        self.service.save_item(self.project, instance, {"measurementBodyName": "Main Body"})
        
        # Verify both exist
        item = self.service.get_item(self.project, instance)
        self.assertEqual(item["stock_size"], "100x50x20")
        self.assertEqual(item["measurementBodyName"], "Main Body")

    def test_persistence_between_instances(self):
        # Create new service instance pointing to same dir
        instance = "Part.2"
        self.service.save_item(self.project, instance, {"stock_size": "200x100x50"})
        
        new_service = BOMCacheService()
        new_service.cache_dir = self.test_dir
        
        loaded = new_service.get_item(self.project, instance)
        self.assertEqual(loaded["stock_size"], "200x100x50")

if __name__ == "__main__":
    unittest.main()
