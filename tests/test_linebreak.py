"""Tests for semantic_linebreak.py."""

import os
import subprocess
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'semantic_linebreak.py')
FIXTURES = os.path.join(ROOT, 'tests', 'fixtures')
EXPECTED = os.path.join(FIXTURES, 'expected')
EXAMPLE_MANUSCRIPTS = os.path.join(ROOT, 'example_manuscripts')


def run_slb(mode, input_text, file_ext='.tex'):
    """Run semantic_linebreak.py on input_text, return output."""
    with tempfile.NamedTemporaryFile(
        mode='w', suffix=file_ext, delete=False, encoding='utf-8'
    ) as f:
        f.write(input_text)
        f.flush()
        tmp_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, SCRIPT, f'--{mode}', tmp_path, '--dry-run'],
            capture_output=True, text=True, cwd=ROOT,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        return result.stdout
    finally:
        os.unlink(tmp_path)


def run_slb_file(mode, filepath):
    """Run semantic_linebreak.py --dry-run on an existing file, return output."""
    result = subprocess.run(
        [sys.executable, SCRIPT, f'--{mode}', filepath, '--dry-run'],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    return result.stdout


def read_fixture(name):
    """Read a fixture file."""
    with open(os.path.join(FIXTURES, name), encoding='utf-8') as f:
        return f.read()


def read_expected(name):
    """Read an expected output file."""
    with open(os.path.join(EXPECTED, name), encoding='utf-8') as f:
        return f.read()


# ---------------------------------------------------------------------------
# Basic split / join
# ---------------------------------------------------------------------------

class TestBasicSplitJoin:
    def test_basic_split(self):
        output = run_slb_file('split', os.path.join(FIXTURES, 'basic.tex'))
        expected = read_expected('basic_split.tex')
        assert output == expected

    def test_basic_join(self):
        """Joining an already-joined file should produce the same output."""
        output = run_slb_file('join', os.path.join(FIXTURES, 'basic.tex'))
        expected = read_expected('basic_join.tex')
        assert output == expected

    def test_split_two_sentences(self):
        output = run_slb('split', 'First sentence. Second sentence.\n')
        assert output == 'First sentence.\nSecond sentence.\n'

    def test_join_two_lines(self):
        output = run_slb('join', 'First sentence.\nSecond sentence.\n')
        assert output == 'First sentence. Second sentence.\n'

    def test_preserves_paragraph_breaks(self):
        output = run_slb('split', 'Paragraph one.\n\nParagraph two.\n')
        assert output == 'Paragraph one.\n\nParagraph two.\n'


# ---------------------------------------------------------------------------
# Abbreviations
# ---------------------------------------------------------------------------

class TestAbbreviations:
    def test_et_al_no_split(self):
        text = 'Smith et al. showed this result. The next sentence follows.\n'
        output = run_slb('split', text)
        lines = output.strip().split('\n')
        # "et al." should NOT cause a split in the middle
        assert any('et al.' in line for line in lines)
        # But there should still be two sentences
        assert len(lines) == 2

    def test_eg_no_split(self):
        text = 'For example, e.g., the value is large. Another sentence.\n'
        output = run_slb('split', text)
        lines = output.strip().split('\n')
        assert len(lines) == 2
        assert 'e.g.,' in lines[0]

    def test_fig_no_split(self):
        text = 'See Fig. 1 for details. The results are clear.\n'
        output = run_slb('split', text)
        lines = output.strip().split('\n')
        assert len(lines) == 2
        assert 'Fig.' in lines[0]

    def test_eq_no_split(self):
        text = 'As shown in Eq. 3, the model fits well. Next sentence.\n'
        output = run_slb('split', text)
        lines = output.strip().split('\n')
        assert len(lines) == 2
        assert 'Eq.' in lines[0]

    def test_abbreviations_fixture(self):
        output = run_slb_file('split', os.path.join(FIXTURES, 'abbreviations.tex'))
        lines = output.strip().split('\n')
        # Should have 5 sentences, none split at abbreviations
        assert len(lines) == 5
        assert 'et al.' in lines[0]
        assert 'Fig.' in lines[1]
        assert 'e.g.,' in lines[2]


# ---------------------------------------------------------------------------
# Math
# ---------------------------------------------------------------------------

class TestMath:
    def test_inline_math_not_split(self):
        text = 'The sample includes $N = 140{,}562$ infants. We continue.\n'
        output = run_slb('split', text)
        lines = output.strip().split('\n')
        assert len(lines) == 2
        assert '$N = 140{,}562$' in lines[0]

    def test_inline_math_with_period(self):
        text = 'We set $\\beta = 3.14$ as the parameter. Next sentence.\n'
        output = run_slb('split', text)
        lines = output.strip().split('\n')
        assert len(lines) == 2
        assert '$\\beta = 3.14$' in lines[0]

    def test_display_math_preserved(self):
        output = run_slb_file('split', os.path.join(FIXTURES, 'math.tex'))
        assert '\\begin{equation}' in output
        assert 'y = mx + b' in output
        assert '\\end{equation}' in output

    def test_display_math_dollars_preserved(self):
        text = 'Text before.\n\n$$\nx^2 + y^2 = z^2\n$$\n\nText after.\n'
        output = run_slb('split', text)
        assert '$$' in output
        assert 'x^2 + y^2 = z^2' in output


# ---------------------------------------------------------------------------
# Display math with internal blank lines (the block scanner bug)
# ---------------------------------------------------------------------------

class TestDisplayMathBlankLines:
    def test_figure_with_blank_lines(self):
        output = run_slb_file('split', os.path.join(FIXTURES, 'display_math_blank_lines.tex'))
        # The entire figure environment should be preserved verbatim
        assert '\\begin{figure}[htbp]' in output
        assert '\\end{figure}' in output
        # Caption should NOT be sentence-split
        assert '\\caption{This is the caption for figure 1. It spans multiple sentences. The figure shows results.}' in output

    def test_align_with_blank_lines(self):
        text = (
            '\\begin{align*}\n'
            'x &= y + z \\\\\n'
            '\n'
            'a &= b + c\n'
            '\\end{align*}\n'
        )
        output = run_slb('split', text)
        # Should be preserved exactly
        assert output == text


# ---------------------------------------------------------------------------
# Nested LaTeX commands
# ---------------------------------------------------------------------------

class TestNestedCommands:
    def test_footnote_with_citation(self):
        text = 'See the results.\\footnote{See \\citet{smith2024} for details.} More text here.\n'
        output = run_slb('split', text)
        # The footnote should be intact (not broken mid-brace)
        assert '\\footnote{See \\citet{smith2024} for details.}' in output

    def test_textbf_textit_nested(self):
        text = 'We use \\textbf{\\textit{bold italic}} in our text. Next sentence.\n'
        output = run_slb('split', text)
        assert '\\textbf{\\textit{bold italic}}' in output

    def test_href_nested(self):
        text = 'Visit \\href{http://example.com}{the link}. Next sentence.\n'
        output = run_slb('split', text)
        assert '\\href{http://example.com}{the link}' in output

    def test_custom_macro_empty_braces(self):
        text = 'The value is \\rxObSevenNineEmw{} per 100 months. This is significant.\n'
        output = run_slb('split', text)
        assert '\\rxObSevenNineEmw{}' in output


# ---------------------------------------------------------------------------
# Structural commands
# ---------------------------------------------------------------------------

class TestStructuralCommands:
    def test_section_stays_on_own_line(self):
        output = run_slb_file('split', os.path.join(FIXTURES, 'structural_commands.tex'))
        expected = read_expected('structural_commands_split.tex')
        assert output == expected

    def test_section_star(self):
        text = '\\section*{Results}\nThe results show improvement. They are significant.\n'
        output = run_slb('split', text)
        lines = output.strip().split('\n')
        assert lines[0] == '\\section*{Results}'

    def test_label_stays_on_own_line(self):
        text = '\\label{sec:intro}\nFirst sentence. Second sentence.\n'
        output = run_slb('split', text)
        lines = output.strip().split('\n')
        assert lines[0] == '\\label{sec:intro}'

    def test_bigskip_preserved(self):
        text = 'First sentence.\n\n\\bigskip\n'
        output = run_slb('split', text)
        assert '\\bigskip' in output

    def test_structural_join(self):
        """Structural commands should stay on own line in join mode too."""
        text = '\\section{Intro}\n\\label{sec:intro}\nFirst.\nSecond.\n'
        output = run_slb('join', text)
        lines = output.strip().split('\n')
        assert lines[0] == '\\section{Intro}'
        assert lines[1] == '\\label{sec:intro}'
        assert 'First. Second.' in lines[2]


# ---------------------------------------------------------------------------
# Trailing comments
# ---------------------------------------------------------------------------

class TestTrailingComments:
    def test_comment_preserved_in_split(self):
        output = run_slb_file('split', os.path.join(FIXTURES, 'trailing_comments.tex'))
        assert '% this is a comment' in output

    def test_comment_line_not_joined(self):
        text = 'First line. % a comment\nSecond line.\n'
        output = run_slb('join', text)
        # Line with comment should not be joined with next
        assert '% a comment' in output


# ---------------------------------------------------------------------------
# Citations
# ---------------------------------------------------------------------------

class TestCitations:
    def test_latex_citep(self):
        text = 'Results show growth \\citep{smith2024}. The next finding is clear.\n'
        output = run_slb('split', text)
        assert '\\citep{smith2024}' in output

    def test_latex_citet(self):
        text = '\\citet{brown2022} demonstrated this. We extend their work.\n'
        output = run_slb('split', text)
        assert '\\citet{brown2022}' in output

    def test_markdown_citation(self):
        text = 'Results are consistent [@smith2024; @jones2023]. The end.\n'
        output = run_slb('split', text, file_ext='.md')
        assert '[@smith2024; @jones2023]' in output

    def test_markdown_citation_with_page(self):
        text = 'See [@brown2022, p. 5] for details. Another point.\n'
        output = run_slb('split', text, file_ext='.md')
        assert '[@brown2022, p. 5]' in output


# ---------------------------------------------------------------------------
# YAML frontmatter and code blocks
# ---------------------------------------------------------------------------

class TestFrontmatterAndCode:
    def test_yaml_frontmatter_preserved(self):
        output = run_slb_file('split', os.path.join(FIXTURES, 'yaml_frontmatter.qmd'))
        assert 'title: "My Document"' in output
        assert 'author: "Author Name"' in output
        assert '---' in output

    def test_code_block_preserved(self):
        output = run_slb_file('split', os.path.join(FIXTURES, 'yaml_frontmatter.qmd'))
        assert 'x = 1' in output
        assert 'y = 2' in output
        assert 'print(x + y)' in output

    def test_code_block_not_split(self):
        text = '```\nFirst line. Second line.\nThird line.\n```\n'
        output = run_slb('split', text, file_ext='.md')
        # Code should be preserved verbatim
        assert 'First line. Second line.' in output


# ---------------------------------------------------------------------------
# Protected environments
# ---------------------------------------------------------------------------

class TestProtectedEnvironments:
    def test_itemize_preserved(self):
        text = (
            '\\begin{itemize}\n'
            '\\item First item. Has detail.\n'
            '\\item Second item.\n'
            '\\end{itemize}\n'
        )
        output = run_slb('split', text)
        assert output == text

    def test_enumerate_preserved(self):
        text = (
            '\\begin{enumerate}\n'
            '\\item Step one. Do this.\n'
            '\\item Step two.\n'
            '\\end{enumerate}\n'
        )
        output = run_slb('split', text)
        assert output == text

    def test_table_preserved(self):
        text = (
            '\\begin{table}[htbp]\n'
            '\\centering\n'
            '\\begin{tabular}{ll}\n'
            'A & B \\\\\n'
            'C & D \\\\\n'
            '\\end{tabular}\n'
            '\\end{table}\n'
        )
        output = run_slb('split', text)
        assert output == text

    def test_comment_block_preserved(self):
        text = '% This is a comment.\n% Another comment line.\n'
        output = run_slb('split', text)
        assert output == text


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_split_idempotent_basic(self):
        text = 'First sentence. Second sentence. Third sentence.\n'
        split1 = run_slb('split', text)
        split2 = run_slb('split', split1)
        assert split1 == split2

    def test_join_idempotent_basic(self):
        text = 'First sentence.\nSecond sentence.\nThird sentence.\n'
        join1 = run_slb('join', text)
        join2 = run_slb('join', join1)
        assert join1 == join2

    def test_split_idempotent_complex(self):
        text = read_fixture('structural_commands.tex')
        split1 = run_slb('split', text)
        split2 = run_slb('split', split1)
        assert split1 == split2

    def test_split_idempotent_math(self):
        text = read_fixture('math.tex')
        split1 = run_slb('split', text)
        split2 = run_slb('split', split1)
        assert split1 == split2


# ---------------------------------------------------------------------------
# Round-trip stability
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_split_join_split(self):
        """split → join → split must equal split."""
        text = 'First sentence. Second sentence. Third sentence.\n'
        split1 = run_slb('split', text)
        joined = run_slb('join', split1)
        split2 = run_slb('split', joined)
        assert split1 == split2

    def test_join_split_join(self):
        """join → split → join must equal join."""
        text = 'First sentence.\nSecond sentence.\nThird sentence.\n'
        join1 = run_slb('join', text)
        split = run_slb('split', join1)
        join2 = run_slb('join', split)
        assert join1 == join2

    def test_round_trip_complex(self):
        text = read_fixture('structural_commands.tex')
        split1 = run_slb('split', text)
        joined = run_slb('join', split1)
        split2 = run_slb('split', joined)
        assert split1 == split2

    def test_round_trip_math(self):
        text = read_fixture('math.tex')
        split1 = run_slb('split', text)
        joined = run_slb('join', split1)
        split2 = run_slb('split', joined)
        assert split1 == split2


# ---------------------------------------------------------------------------
# Integration tests on example manuscripts
# ---------------------------------------------------------------------------

PROSE_FILES = [
    'infant_drug_tests/manuscript_for_journal/manuscript/00_abstract.tex',
    'infant_drug_tests/manuscript_for_journal/manuscript/01_intro.tex',
    'infant_drug_tests/manuscript_for_journal/manuscript/02_data.tex',
    'infant_drug_tests/manuscript_for_journal/manuscript/03_methods.tex',
    'infant_drug_tests/manuscript_for_journal/manuscript/04_results.tex',
    'infant_drug_tests/manuscript_for_journal/manuscript/05_discussion.tex',
    'medicaid_glp/manuscript/00_abstract.tex',
    'medicaid_glp/manuscript/01_introduction.tex',
    'medicaid_glp/manuscript/02_background.tex',
    'medicaid_glp/manuscript/03_methods.tex',
    'medicaid_glp/manuscript/04_data.tex',
    'medicaid_glp/manuscript/05_results.tex',
    'medicaid_glp/manuscript/06_discussion.tex',
]


def _get_prose_file_paths():
    """Get full paths for prose files that exist."""
    paths = []
    for relpath in PROSE_FILES:
        fullpath = os.path.join(EXAMPLE_MANUSCRIPTS, relpath)
        if os.path.exists(fullpath):
            paths.append(fullpath)
    return paths


@pytest.mark.parametrize('filepath', _get_prose_file_paths(),
                         ids=[os.path.basename(p) for p in _get_prose_file_paths()])
class TestExampleManuscripts:
    def test_split_idempotent(self, filepath):
        """split(file) == split(split(file))"""
        split1 = run_slb_file('split', filepath)
        split2 = run_slb('split', split1)
        assert split1 == split2, f"Split not idempotent for {filepath}"

    def test_round_trip(self, filepath):
        """split(file) == split(join(split(file)))"""
        split1 = run_slb_file('split', filepath)
        joined = run_slb('join', split1)
        split2 = run_slb('split', joined)
        assert split1 == split2, f"Round-trip failed for {filepath}"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_file(self):
        output = run_slb('split', '')
        assert output == ''

    def test_only_blank_lines(self):
        output = run_slb('split', '\n\n\n')
        assert output.strip() == ''

    def test_trailing_newline_preserved(self):
        output = run_slb('split', 'Hello world.\n')
        assert output.endswith('\n')

    def test_no_trailing_newline_preserved(self):
        # Write file without trailing newline
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.tex', delete=False, encoding='utf-8'
        ) as f:
            f.write('Hello world.')
            tmp_path = f.name
        try:
            result = subprocess.run(
                [sys.executable, SCRIPT, '--split', tmp_path, '--dry-run'],
                capture_output=True, text=True, cwd=ROOT,
            )
            assert not result.stdout.endswith('\n')
        finally:
            os.unlink(tmp_path)

    def test_single_sentence(self):
        output = run_slb('split', 'Just one sentence.\n')
        assert output == 'Just one sentence.\n'

    def test_multiple_blank_lines_between_paragraphs(self):
        text = 'Paragraph one.\n\n\nParagraph two.\n'
        output = run_slb('split', text)
        assert 'Paragraph one.' in output
        assert 'Paragraph two.' in output

    def test_escaped_percent_not_treated_as_comment(self):
        text = 'The rate was 50\\% of the total. Next sentence.\n'
        output = run_slb('split', text)
        assert '50\\%' in output
