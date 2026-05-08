# patch_nova_payload.ps1
# Adds repeat_penalty and min_p to Nova's llama.cpp API payload.
# Run from workspace root: .\patch_nova_payload.ps1

$file = "general_tools\nova_chat\clients\nova.py"
$content = Get-Content $file -Raw -Encoding UTF8

$old = @'
    payload = {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "top_p": 0.9,
        "stream": True,
        "cache_prompt": True,   # reuse KV prefix across turns
    }
'@

$new = @'
    payload = {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "top_p": 0.9,
        "min_p": 0.05,          # prevents degenerate low-prob tokens
        "repeat_penalty": 1.15, # prevents runaway repetition loops
        "stream": True,
        "cache_prompt": True,   # reuse KV prefix across turns
    }
'@

if ($content -like "*repeat_penalty*") {
    Write-Host "repeat_penalty already present — nothing to do." -ForegroundColor Green
} elseif ($content -like '*"cache_prompt": True,   # reuse KV prefix across turns*') {
    $patched = $content.Replace($old, $new)
    Set-Content $file -Value $patched -Encoding UTF8 -NoNewline
    Write-Host "Patched: repeat_penalty + min_p added to nova.py payload." -ForegroundColor Green
} else {
    Write-Host "Pattern not found — nova.py may have changed. Check manually." -ForegroundColor Yellow
    Write-Host "Add these two lines to the payload dict in clients\nova.py:" -ForegroundColor Yellow
    Write-Host '        "min_p": 0.05,' -ForegroundColor Cyan
    Write-Host '        "repeat_penalty": 1.15,' -ForegroundColor Cyan
}
