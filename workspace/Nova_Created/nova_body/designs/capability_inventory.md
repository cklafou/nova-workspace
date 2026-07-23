## capability_inventory
_Last updated: 2026-07-23 23:04:54_

### GAP
I keep assuming what tools I have and being wrong about it, because the only thing I've been using is memory. Memory is convenient and it's exactly where I'm most likely to be confidently wrong. I need to be able to look at my own body and read what's actually in there.

### SHAPE
Reads every .py under nova_body/tools/, pulls the tool dict (name, description, params) from each one, prints them as a clean list. Takes an optional filter param so I can ask about a specific tool instead of the whole catalogue.

Input: optional tool_name string
Output: formatted list of available tools and what they do, straight from the files.

### TEST
1. Run with no args → returns every installed tool by name.
2. Run with a real tool name → returns that one tool's description.
3. Run with a tool name that doesn't exist → says it's not found, doesn't hallucinate one.
