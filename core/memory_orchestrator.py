import gc
import time
import psutil

class MemoryOrchestrator:
    def __init__(self):
        self.current_loaded_model = None

    def load_model(self, model_id: str, loader_func, required_ram_gb: float = 0.0):
        # 1. Check current RAM
        available = self.get_available_ram_gb()
        if available < required_ram_gb and self.current_loaded_model != model_id:
            # We must unload current and clean up
            self.unload_model()
            available = self.get_available_ram_gb()
            if available < required_ram_gb:
                raise MemoryError(f"Insufficient RAM for {model_id}. Required: {required_ram_gb}GB, Available: {available}GB.")
        
        # 2. Check current_loaded_model
        if self.current_loaded_model == model_id:
            return # Already loaded
        elif self.current_loaded_model is not None:
            self.unload_model()
            
        # 3. Load new
        print(f"[MemoryOrchestrator] Loading model: {model_id} (Available RAM: {self.get_available_ram_gb():.2f} GB)")
        loader_func()
        self.current_loaded_model = model_id

    def unload_model(self) -> None:
        if self.current_loaded_model is None:
            return
        
        print(f"[MemoryOrchestrator] Unloading model: {self.current_loaded_model}")
        # Explicit unload hook could go here if backends register objects
        self.current_loaded_model = None
        gc.collect()
        time.sleep(1) # Give OS a moment
        # Re-check
        print(f"[MemoryOrchestrator] After unload, Available RAM: {self.get_available_ram_gb():.2f} GB")

    def get_available_ram_gb(self) -> float:
        return psutil.virtual_memory().available / 1e9

orchestrator = MemoryOrchestrator()
