#!/usr/bin/env python3
"""Semantic Line Breaker — convert between paragraph and sentence-per-line formatting.

Usage:
    python semantic_linebreak.py --split manuscript/intro.tex
    python semantic_linebreak.py --join manuscript/intro.tex
    python semantic_linebreak.py --split --files .linebreakfiles --dry-run
"""

import argparse
import glob
import re
import sys
import uuid

import pysbd

# ---------------------------------------------------------------------------
# Protected environments — preserved verbatim, never sentence-split
# ---------------------------------------------------------------------------

PROTECTED_ENVS = {
    'equation', 'equation*', 'align', 'align*', 'gather', 'gather*',
    'multline', 'multline*', 'eqnarray', 'eqnarray*',
    'table', 'table*', 'tabular', 'tabular*', 'figure', 'figure*',
    'tikzpicture', 'verbatim', 'lstlisting', 'minted',
    'itemize', 'enumerate', 'description',
    'proof', 'theorem', 'lemma', 'proposition', 'corollary',
    'definition', 'assumption', 'remark', 'example',
    'adjustwidth', 'threeparttable', 'subfigure',
    'longtable', 'longtable*', 'landscape',
}

# Structural commands that stay on their own line
STRUCTURAL_COMMANDS = {
    'section', 'subsection', 'subsubsection', 'paragraph', 'subparagraph',
    'chapter', 'part',
    'label', 'input', 'include', 'includeonly',
    'maketitle', 'tableofcontents', 'listoffigures', 'listoftables',
    'newpage', 'clearpage', 'cleardoublepage', 'pagebreak',
    'bibliographystyle', 'bibliography',
    'begin', 'end',
    'bigskip', 'medskip', 'smallskip',
    'vspace', 'hspace',
    'centering',
    'noindent',
}

# Domain abbreviations to protect from sentence splitting
DOMAIN_ABBREVIATIONS = [
    r'et\s+al\.',
    r'cf\.',
    r'Eq\.',
    r'Eqs\.',
    r'Fig\.',
    r'Figs\.',
    r'Tab\.',
    r'Sec\.',
    r'Ch\.',
    r'No\.',
    r'Vol\.',
    r'pp\.',
    r'Ref\.',
    r'Refs\.',
    r'Thm\.',
    r'Prop\.',
    r'Lem\.',
    r'Cor\.',
    r'Def\.',
    r'Rem\.',
    r'Assn\.',
    r'vs\.',
    r'approx\.',
]

# Regex patterns
RE_BEGIN = re.compile(r'\\begin\{([^}]+)\}')
RE_END = re.compile(r'\\end\{([^}]+)\}')
RE_TRAILING_COMMENT = re.compile(r'(?<!\\)%.*$')
RE_INLINE_MATH = re.compile(r'(?<!\$)\$(?!\$)(?:[^$\\]|\\.)*?\$(?!\$)')
RE_MARKDOWN_CITATION = re.compile(r'\[(?:@[^\]]+)\]')
RE_DISPLAY_MATH_DOLLARS = re.compile(r'\$\$.*?\$\$', re.DOTALL)
RE_DISPLAY_MATH_BRACKETS = re.compile(r'\\\[.*?\\\]', re.DOTALL)


# ---------------------------------------------------------------------------
# Protection Manager
# ---------------------------------------------------------------------------

class ProtectionManager:
    """Replace sensitive spans with unique placeholders, then restore them."""

    def __init__(self):
        self.replacements = {}  # placeholder -> original text

    def protect(self, text, pattern, flags=0):
        """Replace all regex matches with unique placeholders."""
        def replacer(match):
            key = f"__PROTECTED_{uuid.uuid4().hex[:12]}__"
            self.replacements[key] = match.group(0)
            return key
        return re.sub(pattern, replacer, text, flags=flags)

    def protect_spans(self, text, spans):
        """Replace spans (from balanced-brace matcher) with placeholders."""
        for start, end in sorted(spans, reverse=True):
            key = f"__PROTECTED_{uuid.uuid4().hex[:12]}__"
            self.replacements[key] = text[start:end]
            text = text[:start] + key + text[end:]
        return text

    def restore(self, text):
        """Restore all placeholders. Iterates until stable (nested placeholders)."""
        changed = True
        while changed:
            changed = False
            for key, value in self.replacements.items():
                if key in text:
                    text = text.replace(key, value)
                    changed = True
        return text


# ---------------------------------------------------------------------------
# Balanced-brace command finder
# ---------------------------------------------------------------------------

def find_command_spans(text):
    r"""Find all \command{...} spans, handling nested braces.

    Returns list of (start, end) tuples for each complete command.
    Handles: \cmd{...}, \cmd[...]{...}, \cmd{...}{...}, \cmd*{...}
    """
    spans = []
    i = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text) and text[i + 1].isalpha():
            start = i
            # Skip command name
            i += 1
            while i < len(text) and text[i].isalpha():
                i += 1
            # Skip optional star
            if i < len(text) and text[i] == '*':
                i += 1
            # Consume optional [...] and required {...} groups
            while i < len(text) and text[i] in ('[', '{'):
                opener = text[i]
                closer = ']' if opener == '[' else '}'
                depth = 1
                i += 1
                while i < len(text) and depth > 0:
                    if text[i] == '\\' and i + 1 < len(text):
                        i += 2  # skip escaped char
                        continue
                    if text[i] == opener and opener != closer:
                        depth += 1
                    elif text[i] == closer:
                        depth -= 1
                    i += 1
                # After closing, continue checking for more groups
            if i > start + 1:  # consumed more than just "\"
                spans.append((start, i))
        else:
            i += 1
    return spans


# ---------------------------------------------------------------------------
# Block scanner (two-pass)
# ---------------------------------------------------------------------------

def count_begins(line):
    """Count \begin{...} occurrences in a line."""
    return len(RE_BEGIN.findall(line))


def count_ends(line):
    r"""Count \end{...} occurrences in a line."""
    return len(RE_END.findall(line))


def is_fence_toggle(line, fence_state):
    """Check if line toggles a fence (code fence, YAML frontmatter, Quarto div).

    Returns the type of fence toggled, or None.
    fence_state: dict with 'type' key (None, 'code', 'yaml', 'quarto')
    """
    stripped = line.strip()
    if stripped.startswith('```'):
        return 'code'
    if stripped == '---':
        return 'yaml'
    if stripped.startswith(':::'):
        return 'quarto'
    return None


def scan_blocks(lines):
    """Split lines into blocks, respecting environment nesting and fences.

    Returns list of blocks, where each block is a list of lines.
    Blank lines at depth 0 become single-element separator blocks.
    """
    blocks = []
    current = []
    env_depth = 0
    fence_type = None  # None, 'code', 'yaml', 'quarto'
    is_first_line = True

    for line in lines:
        # Track fence state
        if fence_type is None:
            toggle = is_fence_toggle(line, {'type': None})
            if toggle:
                if toggle == 'yaml' and not is_first_line:
                    # --- is only YAML frontmatter at the very start
                    pass
                else:
                    fence_type = toggle
        else:
            # Check for closing fence
            stripped = line.strip()
            if fence_type == 'code' and stripped.startswith('```'):
                # This line closes the fence; include it in current block
                current.append(line)
                blocks.append(current)
                current = []
                fence_type = None
                is_first_line = False
                continue
            elif fence_type == 'yaml' and stripped == '---' and not is_first_line:
                current.append(line)
                blocks.append(current)
                current = []
                fence_type = None
                is_first_line = False
                continue
            elif fence_type == 'quarto' and stripped.startswith(':::') and stripped == ':::':
                current.append(line)
                blocks.append(current)
                current = []
                fence_type = None
                is_first_line = False
                continue

        # Track \begin{} / \end{} nesting (only outside fences)
        if fence_type is None:
            env_depth += count_begins(line) - count_ends(line)
            env_depth = max(0, env_depth)  # safety clamp

        if line.strip() == '' and env_depth == 0 and fence_type is None:
            if current:
                blocks.append(current)
                current = []
            # Preserve blank line as separator
            blocks.append([line])
        else:
            current.append(line)

        is_first_line = False

    if current:
        blocks.append(current)
    return blocks


# ---------------------------------------------------------------------------
# Block classification
# ---------------------------------------------------------------------------

def is_blank_block(block):
    """A block that is just blank lines."""
    return all(line.strip() == '' for line in block)


def is_protected_block(block):
    """Determine if a block should be preserved verbatim."""
    text = '\n'.join(block)
    first_stripped = block[0].strip() if block else ''

    # YAML frontmatter
    if first_stripped == '---':
        return True

    # Code fence
    if first_stripped.startswith('```'):
        return True

    # Quarto div fence
    if first_stripped.startswith(':::'):
        return True

    # Contains a protected environment
    for match in RE_BEGIN.finditer(text):
        env_name = match.group(1)
        if env_name in PROTECTED_ENVS:
            return True

    # Display math (block level)
    if RE_DISPLAY_MATH_DOLLARS.search(text) or RE_DISPLAY_MATH_BRACKETS.search(text):
        return True
    # Check for \[ or \] on their own lines
    if first_stripped == '\\[' or first_stripped == '\\]':
        return True

    # Comment-only block
    if all(l.strip().startswith('%') or l.strip() == '' for l in block):
        if any(l.strip().startswith('%') for l in block):
            return True

    # Pure LaTeX command block (all non-empty lines start with \ or %)
    non_empty = [l for l in block if l.strip()]
    if non_empty and all(l.strip().startswith('\\') or l.strip().startswith('%') for l in non_empty):
        return True

    # Markdown tables (lines with |)
    if all(re.match(r'^\s*\|', l) or l.strip() == '' for l in block):
        if any(re.match(r'^\s*\|', l) for l in block):
            return True

    # Markdown lists
    if all(re.match(r'^\s*[-*]\s', l) or re.match(r'^\s*\d+\.\s', l) or l.strip() == '' for l in block):
        if any(re.match(r'^\s*[-*]\s', l) or re.match(r'^\s*\d+\.\s', l) for l in block):
            return True

    return False


# ---------------------------------------------------------------------------
# Structural command detection
# ---------------------------------------------------------------------------

def is_structural_line(line):
    r"""Check if a line is purely a structural LaTeX command.

    e.g., \section{Introduction}, \label{sec:intro}, \bigskip, \noindent
    """
    stripped = line.strip()
    if not stripped or not stripped.startswith('\\'):
        return False

    # Extract command name
    m = re.match(r'\\([a-zA-Z]+)\*?', stripped)
    if not m:
        return False

    cmd_name = m.group(1)
    if cmd_name not in STRUCTURAL_COMMANDS:
        return False

    # For commands that take no arguments, just the command itself is structural
    rest = stripped[m.end():].strip()
    if not rest:
        return True

    # For commands with arguments, check that the line is ONLY the command + args
    # (no prose text following)
    # Use balanced brace matching to skip over arguments
    i = m.end()
    while i < len(stripped) and stripped[i] in (' ', '\t'):
        i += 1

    while i < len(stripped) and stripped[i] in ('[', '{'):
        opener = stripped[i]
        closer = ']' if opener == '[' else '}'
        depth = 1
        i += 1
        while i < len(stripped) and depth > 0:
            if stripped[i] == '\\' and i + 1 < len(stripped):
                i += 2
                continue
            if stripped[i] == opener and opener != closer:
                depth += 1
            elif stripped[i] == closer:
                depth -= 1
            i += 1

    # After consuming all argument groups, only whitespace or comment should remain
    remaining = stripped[i:].strip()
    if not remaining or remaining.startswith('%'):
        return True

    return False


# ---------------------------------------------------------------------------
# Inline protection for prose
# ---------------------------------------------------------------------------

def protect_inline(text, pm, file_ext):
    """Protect inline spans within prose text before sentence segmentation."""
    # 1. LaTeX commands with balanced braces (outermost first)
    spans = find_command_spans(text)
    text = pm.protect_spans(text, spans)

    # 2. Inline math $...$
    text = pm.protect(text, RE_INLINE_MATH)

    # 3. Markdown citations (for .md/.qmd files)
    if file_ext in ('.md', '.qmd'):
        text = pm.protect(text, RE_MARKDOWN_CITATION)

    # 4. Domain abbreviations
    for abbr in DOMAIN_ABBREVIATIONS:
        text = pm.protect(text, abbr)

    return text


# ---------------------------------------------------------------------------
# Comment handling
# ---------------------------------------------------------------------------

def strip_trailing_comment(line):
    """Strip trailing LaTeX comment, return (prose, comment_suffix).

    The comment_suffix includes the leading whitespace and %.
    Returns ('line', '') if no comment found.
    """
    # Find unescaped %
    i = 0
    while i < len(line):
        if line[i] == '\\':
            i += 2
            continue
        if line[i] == '%':
            return line[:i].rstrip(), line[i:]
        i += 1
    return line, ''


# ---------------------------------------------------------------------------
# Split mode
# ---------------------------------------------------------------------------

def split_prose_block(block, file_ext):
    """Split a prose block into one sentence per line.

    Structural command lines stay on their own line.
    Remaining prose runs are collapsed, segmented, and split.
    """
    result_lines = []
    prose_run = []
    comment_map = {}  # original line text -> comment suffix

    def flush_prose_run():
        if not prose_run:
            return
        # Collapse lines into one string
        collapsed = ' '.join(prose_run)
        # Normalize multiple spaces
        collapsed = re.sub(r'  +', ' ', collapsed).strip()

        if not collapsed:
            prose_run.clear()
            return

        # Protect inline spans
        pm = ProtectionManager()
        protected = protect_inline(collapsed, pm, file_ext)

        # Sentence segmentation
        segmenter = pysbd.Segmenter(language="en", clean=False)
        sentences = segmenter.segment(protected)

        # Restore placeholders and emit
        for sent in sentences:
            restored = pm.restore(sent).strip()
            if restored:
                result_lines.append(restored)

        prose_run.clear()

    for line in block:
        if is_structural_line(line):
            flush_prose_run()
            result_lines.append(line.rstrip())
        else:
            # Strip trailing comment
            prose_part, comment = strip_trailing_comment(line)
            if comment:
                # Lines with trailing comments: flush any accumulated prose,
                # then emit this line with its comment preserved
                flush_prose_run()
                result_lines.append(line.rstrip())
            else:
                prose_run.append(prose_part.strip())

    flush_prose_run()
    return result_lines


# ---------------------------------------------------------------------------
# Join mode
# ---------------------------------------------------------------------------

def join_prose_block(block, file_ext):
    """Join a prose block into paragraphs (collapse non-blank newlines into spaces).

    Structural command lines stay on their own line.
    Lines with trailing % comments are preserved as-is.
    """
    result_lines = []
    prose_run = []

    def flush_prose_run():
        if not prose_run:
            return
        joined = ' '.join(prose_run)
        joined = re.sub(r'  +', ' ', joined).strip()
        if joined:
            result_lines.append(joined)
        prose_run.clear()

    for line in block:
        if is_structural_line(line):
            flush_prose_run()
            result_lines.append(line.rstrip())
        else:
            _, comment = strip_trailing_comment(line)
            if comment:
                flush_prose_run()
                result_lines.append(line.rstrip())
            else:
                stripped = line.strip()
                if stripped:
                    prose_run.append(stripped)

    flush_prose_run()
    return result_lines


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def get_file_ext(filepath):
    """Get file extension, lowercase."""
    if '.' in filepath:
        return '.' + filepath.rsplit('.', 1)[1].lower()
    return ''


def process_file(filepath, mode, dry_run=False):
    """Process a single file in split or join mode."""
    try:
        with open(filepath, encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        print(f"WARNING: Cannot decode {filepath} as UTF-8, skipping.", file=sys.stderr)
        return
    except FileNotFoundError:
        print(f"WARNING: File not found: {filepath}, skipping.", file=sys.stderr)
        return

    # Preserve trailing newline state
    has_trailing_newline = content.endswith('\n')

    # Normalize line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')

    lines = content.split('\n')
    # Remove last empty element from split if file ends with \n
    if lines and lines[-1] == '' and has_trailing_newline:
        lines = lines[:-1]

    file_ext = get_file_ext(filepath)

    # Pass 1: scan blocks
    blocks = scan_blocks(lines)

    # Pass 2: classify and process blocks
    output_lines = []
    for block in blocks:
        if is_blank_block(block):
            output_lines.extend(block)
        elif is_protected_block(block):
            # Preserve verbatim
            for line in block:
                output_lines.append(line.rstrip() if line.strip() else line)
        else:
            # Prose block — process
            if mode == 'split':
                processed = split_prose_block(block, file_ext)
            else:
                processed = join_prose_block(block, file_ext)
            output_lines.extend(processed)

    result = '\n'.join(output_lines)
    if has_trailing_newline:
        result += '\n'

    if dry_run:
        sys.stdout.write(result)
    else:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"Processed: {filepath}")


def load_file_list(file_list_path):
    """Load file paths from a .linebreakfiles-style manifest."""
    try:
        with open(file_list_path, encoding='utf-8') as f:
            raw_lines = f.readlines()
    except FileNotFoundError:
        print(f"ERROR: File list not found: {file_list_path}", file=sys.stderr)
        sys.exit(1)

    files = []
    for line in raw_lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # Expand globs
        expanded = glob.glob(line, recursive=True)
        if expanded:
            files.extend(sorted(expanded))
        else:
            # No glob match — treat as literal path
            files.append(line)
    return files


def main():
    parser = argparse.ArgumentParser(
        description='Semantic Line Breaker — convert between paragraph and sentence-per-line formatting.'
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--split', action='store_true', help='Paragraph → sentence-per-line')
    group.add_argument('--join', action='store_true', help='Sentence-per-line → paragraph')

    parser.add_argument('files', nargs='*', help='Files to process')
    parser.add_argument('--files', dest='file_list', metavar='FILE_LIST',
                        help='Path to file listing target files (one per line)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print to stdout instead of modifying files')

    args = parser.parse_args()

    mode = 'split' if args.split else 'join'

    # Collect files to process
    target_files = list(args.files) if args.files else []
    if args.file_list:
        target_files.extend(load_file_list(args.file_list))

    if not target_files:
        print("ERROR: No files specified. Use positional args or --files.", file=sys.stderr)
        sys.exit(1)

    for filepath in target_files:
        process_file(filepath, mode, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
