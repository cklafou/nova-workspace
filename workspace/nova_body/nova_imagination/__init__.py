# Last updated: 2026-05-27
# @nova: Nova's imagination — her visual-creation faculty. Turns intent into images by
#        driving a local ComfyUI server (the GPU-side renderer, like llama.cpp is the
#        GPU-side mind). She uses this to express herself, sketch ideas, and draw schematics.
#        When she draws HERSELF, her self-LoRA is auto-applied so she stays consistent.
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
