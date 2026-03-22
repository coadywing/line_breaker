# Semantic Line Breaker

A Python tool and GitHub Action that converts between paragraph format and one-sentence-per-line format for academic documents (LaTeX, Markdown, Quarto).

- **Split mode (`--split`):** Paragraph → one sentence per line (for clean git diffs)
- **Join mode (`--join`):** One sentence per line → paragraph (for Overleaf/editor readability)

## Usage

### CLI

```bash
pip install pysbd

# Split: paragraph → sentence-per-line
python semantic_linebreak.py --split manuscript/intro.tex

# Join: sentence-per-line → paragraph
python semantic_linebreak.py --join manuscript/intro.tex

# Dry run (print to stdout, don't modify file)
python semantic_linebreak.py --split manuscript/intro.tex --dry-run

# Process multiple files listed in a config file
python semantic_linebreak.py --split --files .linebreakfiles
```

### GitHub Action

In your research paper repo, add a `.linebreakfiles` listing the files to process:

```
manuscript/0_abstract.tex
manuscript/1_introduction.tex
manuscript/2_data.tex
```

Then reference the action in a workflow:

```yaml
uses: coadywing/semantic-linebreak-action@v1
with:
  mode: split  # or join
  files: .linebreakfiles
```

## Development

```bash
pip install pysbd pytest
pytest tests/ -v
```
