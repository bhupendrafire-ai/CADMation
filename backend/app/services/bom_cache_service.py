import json
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class BOMCacheService:
    """
    Persists measurement progress and body selections to disk.
    This allows CADMation to 'resume' seamlessly after a crash or restart.
    """
    def __init__(self):
        # We store the cache in %TEMP%\CADMation to ensure it survives re-installs 
        # but stays tied to the local machine and user.
        self.cache_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), "CADMation", "bom_brain")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, project_name: str) -> str:
        # Normalise: "MyProject.CATProduct" -> "MyProject"
        base_name = os.path.splitext(str(project_name))[0]
        safe_name = "".join([c if c.isalnum() else "_" for c in base_name])
        new_path = os.path.join(self.cache_dir, f"{safe_name}_cache.json")
        
        # Legacy check: Did we save this from an older version with the extension?
        full_safe = "".join([c if c.isalnum() else "_" for c in str(project_name)])
        old_path = os.path.join(self.cache_dir, f"{full_safe}_cache.json")
        
        if os.path.exists(old_path) and not os.path.exists(new_path):
            logger.info(f"BOMCache: Migrating legacy cache {old_path} -> {new_path}")
            try:
                os.rename(old_path, new_path)
            except:
                return old_path # If rename fails, use the old one
                
        return new_path

    def save_item(self, project_name: str, instance_name: str, data: Dict[str, Any]):
        """Persists selection/progress for a specific BOM item."""
        try:
            path = self._get_cache_path(project_name)
            cache = self.load_all(project_name)
            
            # Merge data (preserve existing keys like stock_size if data only has measurementBodyName)
            if instance_name not in cache:
                cache[instance_name] = {}
            
            cache[instance_name].update(data)
            
            with open(path, "w") as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            logger.error(f"BOMCache: Failed to save item {instance_name}: {e}")

    def load_all(self, project_name: str) -> Dict[str, Any]:
        """Loads all cached items for a project."""
        path = self._get_cache_path(project_name)
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"BOMCache: Failed to load cache from {path}: {e}")
            return {}

    def get_item(self, project_name: str, instance_name: str) -> Dict[str, Any] | None:
        """Retrieves cached data for a specific instance."""
        cache = self.load_all(project_name)
        return cache.get(instance_name)

bom_cache = BOMCacheService()
