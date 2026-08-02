@echo off
REM @nova-adjacent: voice_gateway — one-time model fetch for the voice pipeline.
REM Tiered like requirements.txt: you only need what the tier you're testing uses.
title voice_gateway - fetch voice models
cd /d "%~dp0..\.."

echo ============================================================================
echo   Nova voice gateway - model fetch
echo ============================================================================
echo.
echo Tier 1 (transport + committer smoke): NO MODELS NEEDED.
echo   pip install websockets
echo   python general_tools\voice_gateway\gateway.py --smoke-link "hey nova"
echo.
echo Tier 2 (TTS out) - pick ONE:
echo   [A] Chatterbox (expressive, recommended):
echo         pip install torch chatterbox-tts
echo         (first run downloads the model automatically; set tts_reference_wav
echo          in _admin\voice_gateway.json to a ~10s clip to clone a voice)
echo   [B] llama.cpp TTS (uses llama\llama-tts.exe already here):
echo         download a TTS gguf (e.g. OuteTTS) into models\voice\ and set
echo         tts_backend='llamacpp' + llamacpp_tts_model in the config.
echo.
echo Tier 3 (microphone in):
echo   pip install sounddevice numpy onnxruntime useful-moonshine-onnx silero-vad
echo   (Moonshine + Silero download on first use; until then use stt_backend='stdin')
echo.
echo Nothing is downloaded automatically by this script - it prints the exact steps
echo so each tier is a deliberate, reviewable install. Copy the line for the tier you
echo want and run it.
echo.
pause
