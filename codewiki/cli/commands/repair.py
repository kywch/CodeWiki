"""
Repair command for fixing broken wiki pages.

Validates existing wiki pages and regenerates only the broken ones,
keeping the module tree and dependency graph intact.
"""

import sys
import os
import re
import logging
import traceback
import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any
import time
import click

from codewiki.cli.config_manager import ConfigManager
from codewiki.cli.utils.errors import (
    ConfigurationError,
    RepositoryError,
    APIError,
    handle_error,
    EXIT_SUCCESS,
)
from codewiki.cli.utils.logging import create_logger
from codewiki.cli.models.config import AgentInstructions


@click.command(name="repair")
@click.option(
    "--wiki-dir",
    "-w",
    type=click.Path(exists=True),
    default="wiki",
    help="Path to existing wiki directory (default: ./wiki)",
)
@click.option(
    "--no-mermaid",
    is_flag=True,
    help="Skip mermaid diagram validation (faster)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Only validate and report issues, don't regenerate",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed progress and debug information",
)
@click.option(
    "--max-tokens",
    type=int,
    default=None,
    help="Maximum tokens for LLM response (overrides config)",
)
@click.option(
    "--use-gemini-cli",
    is_flag=True,
    help="Use local Gemini CLI instead of OpenAI API",
)
@click.pass_context
def repair_command(
    ctx,
    wiki_dir: str,
    no_mermaid: bool,
    dry_run: bool,
    verbose: bool,
    max_tokens: Optional[int],
    use_gemini_cli: bool,
):
    """
    Validate and repair broken wiki pages.

    Checks existing wiki pages for broken links, invalid mermaid diagrams,
    missing sections, and empty pages. Regenerates only the broken pages
    while keeping the module tree and dependency graph intact.

    Examples:

    \b
    # Validate and repair wiki
    $ codewiki repair

    \b
    # Dry run - only show issues without fixing
    $ codewiki repair --dry-run

    \b
    # Skip mermaid validation for speed
    $ codewiki repair --no-mermaid

    \b
    # Repair wiki in a custom directory
    $ codewiki repair --wiki-dir docs/wiki
    """
    logger = create_logger(verbose=verbose)
    start_time = time.time()

    # Suppress httpx INFO logs
    logging.getLogger("httpx").setLevel(logging.WARNING)

    try:
        # Validate wiki directory
        wiki_path = Path(wiki_dir).expanduser().resolve()
        if not wiki_path.exists():
            raise RepositoryError(f"Wiki directory not found: {wiki_path}")

        module_tree_path = wiki_path / "module_tree.json"
        if not module_tree_path.exists():
            raise RepositoryError(
                f"module_tree.json not found in {wiki_path}.\n\n"
                "This directory doesn't look like a CodeWiki output.\n"
                "Run 'codewiki generate' first to create the wiki."
            )

        repo_path = Path.cwd()

        # Stage 1: Validate
        logger.step("Validating wiki pages...", 1, 3 if not dry_run else 1)

        broken_pages = asyncio.run(
            _validate_wiki(wiki_path, repo_path, not no_mermaid, logger, verbose)
        )

        if not broken_pages:
            logger.success("All wiki pages are valid. Nothing to repair.")
            return

        logger.warning(f"Found {len(broken_pages)} broken page(s)")

        if dry_run:
            click.echo()
            elapsed = time.time() - start_time
            logger.info(f"Dry run completed in {elapsed:.1f}s. Use 'codewiki repair' to fix.")
            return

        # Stage 2: Load config and prepare
        logger.step("Preparing for regeneration...", 2, 3)

        config_manager = ConfigManager()
        if not config_manager.load() and not use_gemini_cli:
            raise ConfigurationError(
                "Configuration not found. Run 'codewiki config set' first."
            )
        if not config_manager.is_configured() and not use_gemini_cli:
            raise ConfigurationError(
                "Configuration is incomplete. Run 'codewiki config validate'."
            )

        config = config_manager.get_config()
        if config is None and use_gemini_cli:
            from codewiki.cli.models.config import Configuration

            config = Configuration(
                base_url="",
                main_model="",
                cluster_model="",
                fallback_model="",
                agent_instructions=AgentInstructions(),
            )

        api_key = config_manager.get_api_key() or ""
        logger.success("Configuration valid")

        # Stage 3: Regenerate only broken pages
        logger.step("Regenerating broken pages...", 3, 3)
        click.echo()

        asyncio.run(
            _regenerate_broken_pages(
                broken_pages=broken_pages,
                wiki_path=wiki_path,
                repo_path=repo_path,
                config=config,
                api_key=api_key,
                max_tokens=max_tokens,
                use_gemini_cli=use_gemini_cli,
                verbose=verbose,
                logger=logger,
            )
        )

        elapsed = time.time() - start_time
        logger.success(
            f"Repair completed in {elapsed:.1f}s. "
            f"Regenerated {len(broken_pages)} page(s)."
        )

    except ConfigurationError as e:
        logger.error(e.message)
        if verbose:
            logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(e.exit_code)
    except RepositoryError as e:
        logger.error(e.message)
        if verbose:
            logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(e.exit_code)
    except APIError as e:
        logger.error(e.message)
        if verbose:
            logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(e.exit_code)
    except KeyboardInterrupt:
        click.echo("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        sys.exit(handle_error(e, verbose=verbose))


async def _validate_wiki(wiki_path, repo_path, check_mermaid, logger, verbose):
    """Run validation and return list of broken page filenames."""
    from codewiki.src.be.wiki_validator import validate_wiki

    results = await validate_wiki(
        str(wiki_path),
        str(repo_path),
        check_mermaid=check_mermaid,
    )

    broken_pages = []
    for filename, result in results.items():
        if result.is_valid:
            if verbose:
                logger.debug(f"  {filename}: OK")
        else:
            broken_pages.append(filename)
            click.echo(click.style(f"  {filename}:", fg="yellow"))
            for issue in result.issues:
                click.echo(f"    [{issue.category}] {issue.message}")

    return broken_pages


async def _regenerate_broken_pages(
    broken_pages: List[str],
    wiki_path: Path,
    repo_path: Path,
    config,
    api_key: str,
    max_tokens: Optional[int],
    use_gemini_cli: bool,
    verbose: bool,
    logger,
):
    """Regenerate only the broken wiki pages using the agent orchestrator directly."""
    from codewiki.src.config import Config as BackendConfig, set_cli_context
    from codewiki.src.be.agent_orchestrator import AgentOrchestrator
    from codewiki.src.be.utils import sanitize_filename
    from codewiki.src.be.dependency_analyzer.models.core import Node
    from codewiki.src.utils import file_manager

    set_cli_context(True)

    # Configure backend logging
    backend_logger = logging.getLogger("codewiki.src.be")
    backend_logger.handlers.clear()
    if verbose:
        backend_logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        backend_logger.addHandler(handler)
    else:
        backend_logger.setLevel(logging.WARNING)
    backend_logger.propagate = False

    # Create backend config
    backend_config = BackendConfig.from_cli(
        repo_path=str(repo_path),
        output_dir=str(wiki_path),
        llm_base_url=config.base_url,
        llm_api_key=api_key,
        main_model=config.main_model,
        cluster_model=config.cluster_model,
        fallback_model=config.fallback_model,
        max_tokens=max_tokens if max_tokens is not None else config.max_tokens,
        max_token_per_module=config.max_token_per_module,
        max_token_per_leaf_module=config.max_token_per_leaf_module,
        max_depth=config.max_depth,
        use_gemini_cli=use_gemini_cli or config.use_gemini_cli,
    )

    # Load module tree and components from existing wiki data (no re-analysis)
    module_tree = file_manager.load_json(str(wiki_path / "module_tree.json"))

    dep_graph_path = str(wiki_path / "dependency_graph.json")
    raw_components = file_manager.load_json(dep_graph_path)
    components: Dict[str, Any] = {}
    for comp_id, comp_data in raw_components.items():
        try:
            components[comp_id] = Node(**comp_data)
        except Exception:
            pass  # Skip components that don't parse

    # Map filenames back to module names.
    # Normalize both the on-disk filename and module name to a canonical form
    # (lowercase, hyphens/underscores/spaces collapsed) so that mismatches
    # between old (underscore) and new (hyphen) naming styles are handled.
    def _normalize(name: str) -> str:
        """Collapse underscores, hyphens, spaces into a single canonical form."""
        return re.sub(r"[-_\s]+", "-", name.strip().lower())

    filename_to_module: Dict[str, str] = {}
    # Build a normalized lookup from module names
    norm_to_module: Dict[str, str] = {}
    for module_name in module_tree:
        norm_to_module[_normalize(module_name)] = module_name
        # Also index by sanitized and raw forms for exact matches
        filename_to_module[sanitize_filename(module_name) + ".md"] = module_name
        filename_to_module[module_name + ".md"] = module_name

    # For any broken page filename, try exact match first, then normalized match
    def _resolve_module(filename: str) -> Optional[str]:
        if filename in filename_to_module:
            return filename_to_module[filename]
        stem = filename.removesuffix(".md")
        norm = _normalize(stem)
        return norm_to_module.get(norm)

    # Create agent orchestrator
    orchestrator = AgentOrchestrator(backend_config)
    working_dir = str(wiki_path)

    for filename in broken_pages:
        if filename == "overview.md":
            # Overview is a parent doc, handle separately
            click.echo(f"  Skipping overview.md (regenerate with 'codewiki generate')")
            continue

        module_name = _resolve_module(filename)
        if module_name is None:
            click.echo(click.style(f"  {filename}: no matching module found, skipping", fg="yellow"))
            continue

        module_info = module_tree.get(module_name, {})
        core_component_ids = module_info.get("components", [])

        # Back up the broken page
        broken_path = wiki_path / filename
        backup_path = None
        if broken_path.exists():
            backup_fd, backup_path = tempfile.mkstemp(
                prefix=f"codewiki_{filename}_", suffix=".bak"
            )
            os.close(backup_fd)
            shutil.copy2(broken_path, backup_path)
            os.remove(broken_path)

        try:
            click.echo(f"  Regenerating {filename} (module: {module_name})...")
            await orchestrator.process_module(
                module_name=module_name,
                components=components,
                core_component_ids=core_component_ids,
                module_path=[module_name],
                working_dir=working_dir,
            )

            # The agent may produce the file with the new sanitized name (hyphens)
            # instead of the old name (underscores). Check both.
            sanitized_path = wiki_path / (sanitize_filename(module_name) + ".md")
            produced_path = None
            if broken_path.exists():
                produced_path = broken_path
            elif sanitized_path.exists() and sanitized_path != broken_path:
                produced_path = sanitized_path
                # Rename to match the original filename for consistency
                shutil.move(str(sanitized_path), str(broken_path))
                produced_path = broken_path

            if produced_path:
                click.echo(click.style(f"  {filename}: regenerated", fg="green"))
                # Remove backup on success
                if backup_path and os.path.exists(backup_path):
                    os.remove(backup_path)
            else:
                raise RuntimeError(f"Agent did not produce {filename}")

        except Exception as e:
            click.echo(click.style(f"  {filename}: regeneration failed: {e}", fg="red"))
            # Restore from backup
            if backup_path and os.path.exists(backup_path):
                shutil.copy2(backup_path, broken_path)
                os.remove(backup_path)
                click.echo(f"  {filename}: restored from backup")
