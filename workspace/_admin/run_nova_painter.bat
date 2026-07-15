@echo off
REM Nova's painter. Source of truth lives here; copied to C:\Users\lafou\ComfyUI\.
REM
REM Pinned to the 3090 (index 1). Her mind holds the 4090 and most of the 3090; ComfyUI
REM takes VRAM only while it renders and hands it straight back, so nothing is evicted.
REM
REM DO NOT ADD --normalvram : it no longer exists in current ComfyUI (this was my bug).
REM DO NOT ADD --lowvram    : it is a documented no-op under dynamic vram, which is the
REM                           default. ComfyUI manages the card better than my guesswork did.
REM DO NOT ADD --listen     : local-only is correct and private.
REM --cache-none           : don't keep node/model caches resident between runs.
REM --disable-pinned-memory: it pinned 13GB of the 32GB system RAM and left 2.6GB free.
REM                          That, plus holding the whole 3090, is what killed the stack
REM                          the first time she tried to look at her own picture.
REM
REM The painter ALSO calls POST /free after every render (nova_imagination.release()).
REM Belt and braces: her eyes and her hands share one card, and sharing means letting go.
set CUDA_VISIBLE_DEVICES=1
cd /d C:\Users\lafou\ComfyUI
C:\Users\lafou\ComfyUI\venv\Scripts\python.exe main.py --port 8188 --cache-none --disable-pinned-memory
