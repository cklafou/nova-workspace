"""
markdown.py — Convert markdown text to styled HTML for QTextBrowser.

Uses markdown2 if available, falls back to basic manual conversion.
"""
import re
import html as html_mod

try:
    import markdown2
    _MD2 = True
except ImportError:
    _MD2 = False

from .theme import NOVA, CLAUDE, GEMINI, COLE, TEXT, TEXT_DIM, BG_CARD, BG_ALT, BORDER

# ── CSS injected into every rendered message ───────────────────────────────────
_MSG_CSS = f"""
<style>
body {{ margin: 0; padding: 0; font-size: 13px; line-height: 1.6; color: {TEXT}; }}
p {{ margin: 0 0 8px 0; }}
pre {{
    background: {BG_ALT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 12px 14px;
    overflow-x: auto;
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 12px;
    margin: 8px 0;
}}
code {{
    background: {BG_CARD};
    border-radius: 3px;
    padding: 1px 5px;
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 12px;
    color: #e2e8f0;
}}
pre code {{
    background: transparent;
    padding: 0;
    border-radius: 0;
}}
blockquote {{
    border-left: 3px solid {NOVA};
    margin: 8px 0;
    padding: 4px 12px;
    color: {TEXT_DIM};
}}
h1, h2, h3, h4 {{
    color: #ffffff;
    margin: 12px 0 6px 0;
    font-weight: 600;
}}
h1 {{ font-size: 18px; }}
h2 {{ font-size: 15px; }}
h3 {{ font-size: 14px; }}
ul, ol {{ margin: 6px 0; padding-left: 20px; }}
li {{ margin: 2px 0; }}
a {{ color: {NOVA}; text-decoration: none; }}
table {{ border-collapse: collapse; width: 100%; margin: 8px 0; }}
th, td {{ border: 1px solid {BORDER}; padding: 6px 10px; font-size: 12px; }}
th {{ background: {BG_CARD}; color: {TEXT_DIM}; font-weight: 600; }}
hr {{ border: none; border-top: 1px solid {BORDER}; margin: 12px 0; }}
</style>
"""


def render(text: str) -> str:
    """Convert markdown string to full HTML document for QTextBrowser."""
    if _MD2:
        body = markdown2.markdown(
            text,
            extras=["fenced-code-blocks", "tables", "strike", "code-friendly",
                    "break-on-newline", "header-ids"]
        )
    else:
        body = _fallback_render(text)

    return f"<html><head>{_MSG_CSS}</head><body>{body}</body></html>"


def _fallback_render(text: str) -> str:
    """Minimal markdown→HTML without external deps."""
    t = html_mod.escape(text)

    # Code blocks (``` ... ```)
    def code_block(m):
        lang = m.group(1) or ""
        code = m.group(2)
        return f'<pre><code class="language-{lang}">{code}</code></pre>'
    t = re.sub(r'```(\w*)\n?(.*?)```', code_block, t, flags=re.DOTALL)

    # Inline code
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)

    # Headers
    t = re.sub(r'^### (.+)$', r'<h3>\1</h3>', t, flags=re.MULTILINE)
    t = re.sub(r'^## (.+)$',  r'<h2>\1</h2>', t, flags=re.MULTILINE)
    t = re.sub(r'^# (.+)$',   r'<h1>\1</h1>', t, flags=re.MULTILINE)

    # Bold / italic
    t = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', t)
    t = re.sub(r'\*\*(.+?)\*\*',     r'<b>\1</b>', t)
    t = re.sub(r'\*(.+?)\*',         r'<i>\1</i>', t)

    # Blockquote
    t = re.sub(r'^&gt; (.+)$', r'<blockquote>\1</blockquote>', t, flags=re.MULTILINE)

    # Unordered list (basic)
    t = re.sub(r'^\s*[-*] (.+)$', r'<li>\1</li>', t, flags=re.MULTILINE)
    t = re.sub(r'(<li>.*</li>)', r'<ul>\1</ul>', t, flags=re.DOTALL)

    # Line breaks → paragraphs
    paragraphs = re.split(r'\n\n+', t)
    parts = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith(('<h', '<ul', '<ol', '<pre', '<blockquote')):
            parts.append(p)
        else:
            parts.append(f'<p>{p.replace(chr(10), "<br>")}</p>')
    return "\n".join(parts)


# ── Role colors ────────────────────────────────────────────────────────────────
ROLE_COLORS = {
    "Nova":   NOVA,
    "Claude": CLAUDE,
    "Gemini": GEMINI,
    "Cole":   COLE,
    "System": TEXT_DIM,
}

def role_color(role: str) -> str:
    return ROLE_COLORS.get(role, TEXT)
