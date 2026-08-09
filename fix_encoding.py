# The .html.bak has BOM + corrupted content
# But the ORIGINAL good content was valid UTF-8 before PowerShell touched it.
# The PowerShell Get-Content read the UTF-8 file as system default (likely cp936/GBK),
# producing mojibake, then Set-Content -Encoding UTF8 wrote the mojibake as UTF-8.
#
# So: original UTF-8 bytes -> read as GBK -> mojibake unicode -> write as UTF-8
#
# To reverse: read as UTF-8 -> encode as GBK -> original UTF-8 bytes
# The problem was that some characters couldn't round-trip through GBK.
#
# Let's try a different approach: since the corrupted bytes ARE the result of
# reading UTF-8 as GBK then writing as UTF-8, we need to:
# 1. Read current file as UTF-8 (get mojibake text)
# 2. For each mojibake character, find what original UTF-8 byte sequence produced it
#
# Actually, the simplest fix: just do the byte-level reverse
# Current file = UTF-8 encoding of (GBK interpretation of original UTF-8 bytes)
# So: current_bytes = encode_utf8(decode_gbk(original_utf8_bytes))
# Reverse: original_utf8_bytes = encode_gbk(decode_utf8(current_bytes))

with open(r'e:\hiagent\DEMO3\TOtal\defense-ppt\defense-ppt.html.bak', 'rb') as f:
    current_bytes = f.read()

# Skip BOM
if current_bytes[:3] == b'\xef\xbb\xbf':
    current_bytes = current_bytes[3:]

# Step 1: decode current bytes as UTF-8
mojibake_text = current_bytes.decode('utf-8')

# Step 2: encode as GBK to get original UTF-8 bytes
# Use errors='replace' for characters that can't map
original_bytes = mojibake_text.encode('gbk', errors='replace')

# Check if result looks like valid UTF-8
try:
    original_text = original_bytes.decode('utf-8')
    if '目录' in original_text and '汇报大纲' in original_text:
        print("SUCCESS!")
        with open(r'e:\hiagent\DEMO3\TOtal\defense-ppt\defense-ppt-recovered.html', 'w', encoding='utf-8', newline='\r\n') as f:
            f.write('\ufeff' + original_text)
        print("Recovered file written")
    else:
        print("Decoded but Chinese not found")
        idx = original_text.find('<title>')
        if idx >= 0:
            print("Title area:", repr(original_text[idx:idx+100]))
except Exception as e:
    print(f"Decode failed: {e}")
    # Show what we got
    print("First 200 chars:", repr(original_text[:200]))
