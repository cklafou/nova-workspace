# Last updated: 2026-07-08 23:05:00
# @nova: Nova's imagination — her visual-creation faculty; drives a local ComfyUI server to turn intent into images (self-expression, sketches, schematics), auto-applying her self-LoRA when she draws herself.
"""
nova_imagination -- Nova's visual-creation faculty.

Public API:
    from nova_imagination import generate_image, comfy_status, build_workflow

ComfyUI itself is external infrastructure (a local server on :8188), exactly the way
llama.cpp is the external mind on :8080. This package is the *faculty* that decides what
to draw, builds the workflow, submits it, and brings the finished image home into the
workspace. Pure stdlib (urllib) — no torch/GPU import here, so it loads cleanly whether or
not ComfyUI is running, and survives the pluck-test (no chat/server dependency).
"""

from nova_imagination.imagination import (  # noqa: F401
    generate_image,
    comfy_status,
    build_workflow,
)

__all__ = ["generate_image", "comfy_status", "build_workflow"]
