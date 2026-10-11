"""ComfyUI-Accelerated-Downloader: aria2-based fast model downloader.

Install by copying this folder to <ComfyUI>/custom_nodes/ and restarting
ComfyUI, or run install.ps1 in this folder to do it automatically.
"""
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
