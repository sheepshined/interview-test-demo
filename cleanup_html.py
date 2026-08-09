import re

src = r'c:\Users\Lenovo\.trae-cn\attachments\6a5057bb17d8e6de67def83a\a96ba138-b032-42fd-97d0-e6d425291696_5aad55a9-a1a4-4e2c-ae8d-03fd62d2fe14_新建 文本文档.txt'
dst = r'e:\hiagent\DEMO3\TOtal\defense-ppt\defense-ppt.html'

with open(src, 'r', encoding='utf-8') as f:
    html = f.read()

# Step 1: Fix script paths
html = html.replace('src="./AI \u6a21\u62df\u9762\u8bd5\u5b98\u7cfb\u7edf - \u7b54\u8fa9\u6f14\u793a_files/runtime.js"', 'src="./runtime.js"')
html = html.replace('src="./AI \u6a21\u62df\u9762\u8bd5\u5b98\u7cfb\u7edf - \u7b54\u8fa9\u6f14\u793a_files/echarts-theme-sync.js"', 'src="./echarts-theme-sync.js"')

# Step 2: Remove scroll-mode
html = html.replace(' class="scroll-mode"', '')
html = re.sub(r'<body>\s*<body[^>]*>', '<body>', html)

# Step 3: Remove @media print block
html = re.sub(
    r'/\* === Print / PDF Export.*?\*/\s*@page\s*\{[^}]*\}\s*@media\s*print\s*\{.*?\}',
    '', html, flags=re.DOTALL
)

# Step 4: Find and extract ONLY clean sections (no inline style)
# Strategy: Find all <section> tags, extract each section as a whole,
# then keep only those WITHOUT style="position: absolute"

# Find all section starts
section_starts = []
for m in re.finditer(r'<section\s', html):
    section_starts.append(m.start())

# Extract each section by tracking depth
sections = []
for start in section_starts:
    depth = 0
    end = -1
    i = start
    while i < len(html):
        if html[i:i+9] == '<section':
            depth += 1
            # Skip to end of tag
            gt = html.find('>', i)
            i = gt + 1
        elif html[i:i+10] == '</section>':
            depth -= 1
            if depth == 0:
                end = i + 10
                break
            i += 10
        else:
            i += 1
    if end > 0:
        section_html = html[start:end]
        has_position_style = 'style="position: absolute' in section_html[:200]
        has_overlay = 'inset: 0px' in section_html[:200] if len(section_html) > 200 else False
        if has_position_style:
            continue  # Skip rendered sections
        sections.append(section_html)

print(f"Clean sections extracted: {len(sections)}")
for i, s in enumerate(sections):
    title_m = re.search(r'data-title="([^"]*)"', s[:200])
    title = title_m.group(1) if title_m else "?"
    print(f"  {i+1:2d}. {title[:35]} ({len(s)} chars)")

# Step 5: Remove overlays from the clean sections
cleaned = []
for s in sections:
    # Remove overlay divs that are direct children of slide-scroll-wrapper
    s = re.sub(r'<div style="position:\s*absolute;\s*inset:\s*0px;[^"]*?</div></div></div>', '', s, flags=re.DOTALL)
    cleaned.append(s)

# Step 6: Build final file
body_pos = html.find('<body>')
header = html[:body_pos]
body_content = html[body_pos:]

# Get scripts
scripts = re.findall(r'<script[^>]*src="[^"]*"[^>]*></script>', body_content)

# Find <style> blocks in body
styles = re.findall(r'<style[^>]*>.*?</style>', body_content, re.DOTALL)

# Assemble
result = header + '\n<body>\n'
for s in styles:
    result += s + '\n'
result += '<div class="deck">\n'
for s in cleaned:
    result += s + '\n\n'
result += '</div>\n'
for s in scripts:
    result += s + '\n'
result += '</body>\n</html>\n'

with open(dst, 'w', encoding='utf-8', newline='\r\n') as f:
    f.write(result)

# Verify
with open(dst, 'r', encoding='utf-8') as f:
    check = f.read()
titles = re.findall(r'data-title="([^"]*)"', check)
overlay_count = len(re.findall(r'inset:\s*0px', check))
print(f"\nFinal: {len(check)} chars, {len(titles)} sections, {overlay_count} overlays")
print(f"runtime.js path OK: {'./runtime.js' in check}")
