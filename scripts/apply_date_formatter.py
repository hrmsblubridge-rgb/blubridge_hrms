#!/usr/bin/env python3
"""Bulk-apply the central DD-Mon-YYYY date formatter to all user-facing
date renderings across the HRMS frontend.

What it does (each file is touched only when needed):
1. Inserts `import { formatDate } from '<relative>/lib/dateFormat';` after the
   last top-of-file `import` if any pattern below will be replaced.
2. Replaces ALL of these display patterns with `formatDate(<expr>)`:
     new Date(<expr>).toLocaleDateString()
     new Date(<expr>).toLocaleDateString(<args...>)
     new Date(<expr>).toDateString()
3. Leaves currency formatting `Number(x).toLocaleString('en-IN')` alone.
4. Leaves date arithmetic / Date object math alone (only the rendered string).
5. Skips bulk edits in helper files we want to keep stable.
"""
import os
import re
import sys

ROOT = "/app/frontend/src"
SKIP = {"lib/dateFormat.js"}

# Files in /app/frontend/src/pages → ../lib/dateFormat
# Files in /app/frontend/src/components → ../lib/dateFormat
# Files in /app/frontend/src/components/ui → ../../lib/dateFormat
def relative_import(filepath):
    rel = os.path.relpath(filepath, ROOT)
    depth = rel.count(os.sep)
    return ('../' * depth) + 'lib/dateFormat'


# Pattern A: `new Date(<expr>).toLocaleDateString(<anything>)` and
# Pattern B: `new Date(<expr>).toDateString()`
# We need to capture <expr> (which can contain balanced parens). Use a
# greedy-balanced approach via a tiny scanner.

NEW_DATE_RE = re.compile(r'new\s+Date\s*\(')

def find_balanced_close(s, start_idx, open_ch='(', close_ch=')'):
    """Return index of matching close for the open at start_idx-1."""
    depth = 1
    i = start_idx
    n = len(s)
    in_str = None
    while i < n:
        ch = s[i]
        if in_str:
            if ch == '\\':
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ('"', "'", '`'):
            in_str = ch
            i += 1
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def transform(src):
    out = []
    i = 0
    n = len(src)
    changed = False
    while i < n:
        m = NEW_DATE_RE.search(src, i)
        if not m:
            out.append(src[i:])
            break
        out.append(src[i:m.start()])
        open_at = m.end()  # index right after the '('
        close_at = find_balanced_close(src, open_at)
        if close_at < 0:
            # Malformed, give up on this occurrence
            out.append(src[m.start():m.end()])
            i = m.end()
            continue
        inner = src[open_at:close_at]
        after = close_at + 1
        # Look for the trailing .toLocaleDateString(...) or .toDateString()
        # Allow some whitespace
        tail = src[after:]
        tail_strip = tail.lstrip()
        whitespace = tail[:len(tail) - len(tail_strip)]
        consumed = 0
        method = None
        if tail_strip.startswith('.toLocaleDateString'):
            method = 'toLocaleDateString'
        elif tail_strip.startswith('.toDateString'):
            method = 'toDateString'
        if method is None:
            # Not a display call — keep verbatim
            out.append(src[m.start():after])
            i = after
            continue
        # Find the call's parens
        method_start = after + len(whitespace) + 1 + len(method)  # includes the '.'
        if method_start >= n or src[method_start] != '(':
            out.append(src[m.start():after])
            i = after
            continue
        # Find balanced close of method args
        method_open = method_start + 1
        method_close = find_balanced_close(src, method_open)
        if method_close < 0:
            out.append(src[m.start():after])
            i = after
            continue
        # All good — emit replacement
        out.append(f'formatDate({inner.strip()})')
        i = method_close + 1
        changed = True
    return ''.join(out) if changed else None


def ensure_import(src, rel_path):
    if 'formatDate' not in src:
        return src
    if re.search(r"from\s+['\"][^'\"]*lib/dateFormat['\"]", src):
        return src
    # Find last top-level import
    last_import_end = 0
    for m in re.finditer(r"^import\s+.*?from\s+['\"][^'\"]+['\"]\s*;?\s*$", src, re.MULTILINE):
        last_import_end = m.end()
    line = f"\nimport {{ formatDate }} from '{rel_path}';"
    if last_import_end == 0:
        return line.lstrip() + "\n" + src
    return src[:last_import_end] + line + src[last_import_end:]


def process(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        src = f.read()
    new = transform(src)
    if new is None:
        return False
    new = ensure_import(new, relative_import(filepath))
    if new == src:
        return False
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new)
    return True


def walk():
    changed = []
    for dirpath, _, files in os.walk(ROOT):
        for fn in files:
            if not (fn.endswith('.js') or fn.endswith('.jsx')):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT)
            if rel in SKIP:
                continue
            try:
                if process(full):
                    changed.append(rel)
            except Exception as e:
                print(f"ERR {rel}: {e}", file=sys.stderr)
    return changed


if __name__ == '__main__':
    changed = walk()
    print(f"Touched {len(changed)} files:")
    for c in sorted(changed):
        print(f"  {c}")
