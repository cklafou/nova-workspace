import re

with open('C:/Users/lafou/Project_Nova/workspace/general_tools/nova_chat/static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

buttons = re.findall(r'<button[^>]*id=\"([^\"]+)\"', text)
for b in buttons:
    match = re.search(r'const\s+(\w+)\s*=\s*document\.getElementById\([\'\"]' + b + r'[\'\"]\)', text)
    if match:
        var_name = match.group(1)
        if f'{var_name}.addEventListener' not in text and f'{var_name}?.addEventListener' not in text:
            print(f'UNWIRED: {b} (var {var_name})')
    else:
        if f'document.getElementById(\'{b}\').addEventListener' not in text and f'document.getElementById(\"{b}\").addEventListener' not in text:
            print(f'UNWIRED (no var): {b}')
