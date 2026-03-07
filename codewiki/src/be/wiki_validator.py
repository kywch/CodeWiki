"""
Validator for wiki pages. Checks for broken links, invalid mermaid diagrams,
and missing required sections.
"""

import os
import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from pathlib import Path

from codewiki.src.be.utils import extract_mermaid_blocks, validate_single_diagram

logger = logging.getLogger(__name__)

REQUIRED_SECTIONS = ["## Overview", "## Architecture", "## Core Components"]


@dataclass
class PageIssue:
    """A single validation issue found in a wiki page."""
    category: str  # "broken_link", "mermaid", "missing_section", "empty"
    message: str


@dataclass
class PageValidationResult:
    """Validation result for a single wiki page."""
    filename: str
    issues: List[PageIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.issues) == 0


def validate_wiki_page(
    md_path: str,
    wiki_dir: str,
    repo_path: str,
) -> PageValidationResult:
    """
    Validate a single wiki page for common issues.

    Checks:
    - Page is not empty or near-empty (< 100 chars of content)
    - Required sections exist (Overview, Architecture, Core Components)
    - Code file links point to files that exist in the repo
    - Line anchors (#L123) reference valid line numbers
    - Wiki cross-reference links point to existing wiki pages

    Args:
        md_path: Absolute path to the markdown file
        wiki_dir: Absolute path to the wiki directory
        repo_path: Absolute path to the repository root

    Returns:
        PageValidationResult with any issues found
    """
    filename = os.path.basename(md_path)
    result = PageValidationResult(filename=filename)

    try:
        content = Path(md_path).read_text(encoding="utf-8")
    except Exception as e:
        result.issues.append(PageIssue("empty", f"Cannot read file: {e}"))
        return result

    # Check empty/near-empty
    stripped = content.strip()
    if len(stripped) < 100:
        result.issues.append(PageIssue("empty", f"Page is nearly empty ({len(stripped)} chars)"))
        return result

    # Check required sections (skip for overview.md which has different structure)
    if filename != "overview.md":
        for section in REQUIRED_SECTIONS:
            if section not in content:
                result.issues.append(
                    PageIssue("missing_section", f"Missing required section: {section}")
                )

    # Check markdown links
    _validate_links(content, wiki_dir, repo_path, result)

    return result


def _validate_links(
    content: str,
    wiki_dir: str,
    repo_path: str,
    result: PageValidationResult,
) -> None:
    """Validate all markdown links in the content."""
    # Match markdown links: [text](url)
    link_pattern = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')

    for match in link_pattern.finditer(content):
        link_text = match.group(1)
        link_target = match.group(2)

        # Skip external URLs
        if link_target.startswith(("http://", "https://", "mailto:")):
            continue

        # Split off anchor
        if "#" in link_target:
            file_part, anchor = link_target.rsplit("#", 1)
        else:
            file_part = link_target
            anchor = None

        if not file_part:
            continue

        # Resolve the path relative to wiki_dir
        resolved = os.path.normpath(os.path.join(wiki_dir, file_part))

        if not os.path.exists(resolved):
            result.issues.append(
                PageIssue(
                    "broken_link",
                    f"Broken link: [{link_text}]({link_target}) -> file not found: {file_part}",
                )
            )
            continue

        # Validate line anchor if present
        if anchor and anchor.startswith("L") and anchor[1:].isdigit():
            line_num = int(anchor[1:])
            try:
                with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                    total_lines = sum(1 for _ in f)
                if line_num > total_lines:
                    result.issues.append(
                        PageIssue(
                            "broken_link",
                            f"Invalid line anchor: [{link_text}]({link_target}) -> "
                            f"file has {total_lines} lines but references L{line_num}",
                        )
                    )
            except Exception:
                pass  # If we can't read the file, skip anchor check


async def validate_mermaid_in_page(
    md_path: str,
    result: PageValidationResult,
) -> None:
    """Validate mermaid diagrams in a wiki page and append issues to result."""
    try:
        content = Path(md_path).read_text(encoding="utf-8")
    except Exception:
        return

    mermaid_blocks = extract_mermaid_blocks(content)
    if not mermaid_blocks:
        return

    for i, (line_start, diagram_content) in enumerate(mermaid_blocks, 1):
        error_msg = await validate_single_diagram(diagram_content, i, line_start)
        if error_msg:
            result.issues.append(PageIssue("mermaid", error_msg))


async def validate_wiki(
    wiki_dir: str,
    repo_path: str,
    check_mermaid: bool = True,
) -> Dict[str, PageValidationResult]:
    """
    Validate all wiki pages in a directory.

    Args:
        wiki_dir: Path to the wiki directory
        repo_path: Path to the repository root
        check_mermaid: Whether to validate mermaid diagrams (slower)

    Returns:
        Dict mapping filename to validation result
    """
    results: Dict[str, PageValidationResult] = {}

    for fname in sorted(os.listdir(wiki_dir)):
        if not fname.endswith(".md"):
            continue

        md_path = os.path.join(wiki_dir, fname)
        result = validate_wiki_page(md_path, wiki_dir, repo_path)

        if check_mermaid:
            await validate_mermaid_in_page(md_path, result)

        results[fname] = result

    return results
