# Manuscript

LaTeX source files for the paper. This directory is synced with Overleaf via GitHub integration.

## Files

- `main.tex` - Main document
- `references.bib` - Bibliography

## Figures and Tables

Reference outputs directly from the `outputs/` directory:

```latex
\includegraphics{../outputs/figures/result_2yr_spending_obesity.png}
\input{../outputs/tables/design_table.tex}
```

## Compiling

The paper can be compiled in Overleaf (synced via GitHub) or locally from the **project root** with:

```bash
latexmk -pdf manuscript/main.tex
```

Output goes to `manuscript/build/` (configured in `.latexmkrc`).
