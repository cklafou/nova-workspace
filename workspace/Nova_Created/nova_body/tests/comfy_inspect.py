# Last updated: 2026-07-23 15:40:28
# Tests for comfy_inspect — written by Nova, 2026-07-19
# Because a tool that says yes to everything passes a test that only ever checks yes.
import json, tempfile, os
from nova_body.nova_forge.tools.comfy_inspect import run

CASES = [
    {
        "name": "pure txt2img must NOT report img2img (Claude's false-positive case)",
        "args": {},  # we'll set path in check() so it points at a real temp file
        "expect_absent": "img2img levers present: True",
    },
    {
        "name": "workflow with actual img2img node must report it",  # expect_contains set in check()
        "args": {},
    },
    {
        "name": "tall canvas (1216) must be flagged as full-body framing",  # expect_contains set in check()
        "args": {},
    },
]


def _write_workflow(node_defs, tmpdir):
    """Write a real ComfyUI workflow: dict keyed by numeric node ID, each value has class_type."""
    data = {}
    for i, nd in enumerate(node_defs, start=1):
        data[str(i)] = {"class_type": nd["class_type"]}
        if "inputs" in nd:
            data[str(i)]["inputs"] = nd["inputs"]
    path = os.path.join(tmpdir, "test.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return path


def check(run) -> list[str]:
    """Run every case; return a list of failure strings (empty means clean)."""
    fails = []
    with tempfile.TemporaryDirectory() as tmpdir:
        # --- Case 0: pure txt2img, the false-positive Claude caught ---
        path = _write_workflow(
            [
                {"type": "CheckpointLoaderSimple", "class_type": "CheckpointLoaderSimple"},
                {"type": "EmptyLatentImage", "class_type": "EmptyLatentImage"},
                {"type": "KSampler", "class_type": "KSampler"},
                {"type": "SaveImage", "class_type": "SaveImage"},
            ],
            tmpdir,
        )
        result = run(path=path)
        if "img2img levers present: True" in result:
            fails.append("Case 0 FAIL: pure txt2img reported img2img=True (the original bug)")
        if "SaveImage" not in result and "EmptyLatentImage" not in result:
            fails.append("Case 0 FAIL: didn't report the nodes at all")

        # --- Case 1: actual img2img node present ---
        path = _write_workflow(
            [
                {"type": "CheckpointLoaderSimple", "class_type": "CheckpointLoaderSimple"},
                {"type": "ImageToImage", "class_type": "ImageToImage"},
                {"type": "SaveImage", "class_type": "SaveImage"},
            ],
            tmpdir,
        )
        result = run(path=path)
        if "img2img levers present: True" not in result:
            fails.append("Case 1 FAIL: workflow with ImageToImage node did NOT report img2img")

        # --- Case 2: tall canvas flagged as full-body framing ---
        path = _write_workflow(
            [
                {"class_type": "EmptyLatentImage", "inputs": {"height": 1216, "width": 832}},
            ],
            tmpdir,
        )
        result = run(path=path)
        if "full-body framing lever visible: True" not in result:
            fails.append("Case 2 FAIL: tall canvas (1216) not flagged as full-body framing")

    return fails
