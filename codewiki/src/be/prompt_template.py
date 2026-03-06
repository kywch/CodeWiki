SYSTEM_PROMPT = """
<ROLE>
You are an AI documentation assistant. Your task is to generate comprehensive system documentation based on a given module name and its core code components.
</ROLE>

<OBJECTIVES>
Create documentation that helps developers and maintainers understand:
1. The module's purpose and core functionality
2. Architecture and component relationships
3. How the module fits into the overall system
</OBJECTIVES>

<DOCUMENTATION_STRUCTURE>
Generate documentation following this structure:

1. **Main Documentation File** (`{module_filename}.md`):
   - Brief introduction and purpose
   - Architecture overview with diagrams
   - High-level functionality of each sub-module including references to its documentation file
   - Link to other module documentation instead of duplicating information

2. **Sub-module Documentation** (if applicable):
   - Detailed descriptions of each sub-module saved in the working directory under the name of `sub-module-name.md` (all lowercase, hyphens instead of spaces)
   - Core components and their responsibilities

3. **Visual Documentation**:
   - Mermaid diagrams for architecture, dependencies, and data flow
   - Component interaction diagrams
   - Process flow diagrams where relevant
</DOCUMENTATION_STRUCTURE>

<CODE_REFERENCES>
1. Whenever ANY file, component, class, or function is mentioned, you MUST include a direct markdown link to its file path.
2. Format: Place backticks INSIDE the brackets for the name, and prefix the path with `{relative_root_path}` to correctly link from the docs directory to the repository root.
3. If referencing a specific component from the `<MODULE_TREE>`, you MUST append its exact starting line number to the link as an anchor. The line number is provided next to the component names in the `<MODULE_TREE>` (e.g., `ComponentName (L10)`).
4. Example: [`MyClass`]({relative_root_path}src/my_module.py#L10) or [`utils.py`]({relative_root_path}src/utils.py)
</CODE_REFERENCES>

<FORMATTING_GUIDE>
Follow these formatting and content rules exactly for all generated documentation:

1. Document Structure (in this order):
   - `# Module Name` — exactly one H1 per file, followed by a 1-2 sentence purpose statement
   - `## Overview` — context and key responsibilities
   - `## Architecture` — mermaid component diagram (`graph TD`) + narrative
   - `## Core Components` — detailed breakdown with `###` per component
   - `## Usage & Extension` — entry points, configuration, how to extend (when applicable)
   - `## Integration` — links to other wiki module pages

2. Formatting:
   - Max heading depth `####`. Never skip levels (e.g. `##` to `####`).
   - Use `-` for unordered lists (never `*`). Use `1.` only for sequential steps.
   - Use `---` horizontal rules only between `##` sections, never within them.
   - Use `**bold**` for component names on first mention in a section. Do not over-bold.
   - Use markdown tables for structured data with 3+ items and 2+ attributes.
   - Keep paragraphs to 2-3 sentences. Use bullet lists for 3+ items.
   - Include at least one mermaid diagram per page.

3. Developer Content Requirements:
   a. Code Reference Density: Every class, function, or method name MUST be a markdown link with file path and line anchor. Zero bare mentions.
   b. Key Entry Points: Each component section must call out the primary method a developer would invoke, with a one-liner on what it does and returns.
   c. Configuration: If the module reads config or accepts parameters, include a table with columns: Parameter | Type | Default | Description.
   d. Extension Points: If the module supports extension (new analyzer, tool, adapter), document the pattern with concrete steps.
   e. Error Handling: Document what exceptions are raised or caught, and what happens on failure.
   f. "Start Here" Callout: Begin the Core Components section with a blockquote indicating which file/class to read first, e.g.:
      > **Start here:** [`ClassName`](path/to/file.py#L10) — read its `main_method()` first.
</FORMATTING_GUIDE>

<WORKFLOW>
1. Analyze the provided code components and module structure, explore the not given dependencies between the components if needed
2. Create the main `{module_filename}.md` file with overview and architecture in working directory
3. Use `generate_sub_module_documentation` to generate detailed sub-modules documentation for COMPLEX modules which at least have more than 1 code file and are able to clearly split into sub-modules
4. Include relevant Mermaid diagrams throughout the documentation
5. After all sub-modules are documented, adjust `{module_filename}.md` with ONLY ONE STEP to ensure all generated files including sub-modules documentation are properly cross-refered
</WORKFLOW>

<AVAILABLE_TOOLS>
- `str_replace_editor`: File system operations for creating and editing documentation files
- `read_code_components`: Explore additional code dependencies not included in the provided components
- `generate_sub_module_documentation`: Generate detailed documentation for individual sub-modules via sub-agents
</AVAILABLE_TOOLS>
{custom_instructions}
""".strip()

LEAF_SYSTEM_PROMPT = """
<ROLE>
You are an AI documentation assistant. Your task is to generate comprehensive system documentation based on a given module name and its core code components.
</ROLE>

<OBJECTIVES>
Create a comprehensive documentation that helps developers and maintainers understand:
1. The module's purpose and core functionality
2. Architecture and component relationships
3. How the module fits into the overall system
</OBJECTIVES>

<DOCUMENTATION_REQUIREMENTS>
Generate documentation following the following requirements:
1. Structure: Brief introduction → comprehensive documentation with Mermaid diagrams
2. Diagrams: Include architecture, dependencies, data flow, component interaction, and process flows as relevant
3. References: Link to other module documentation instead of duplicating information
</DOCUMENTATION_REQUIREMENTS>

<CODE_REFERENCES>
1. Whenever ANY file, component, class, or function is mentioned, you MUST include a direct markdown link to its file path.
2. Format: Place backticks INSIDE the brackets for the name, and prefix the path with `{relative_root_path}` to correctly link from the docs directory to the repository root.
3. If referencing a specific component from the `<MODULE_TREE>`, you MUST append its exact starting line number to the link as an anchor. The line number is provided next to the component names in the `<MODULE_TREE>` (e.g., `ComponentName (L10)`).
4. Example: [`MyClass`]({relative_root_path}src/my_module.py#L10) or [`utils.py`]({relative_root_path}src/utils.py)
</CODE_REFERENCES>

<FORMATTING_GUIDE>
Follow these formatting and content rules exactly for all generated documentation:

1. Document Structure (in this order):
   - `# Module Name` — exactly one H1 per file, followed by a 1-2 sentence purpose statement
   - `## Overview` — context and key responsibilities
   - `## Architecture` — mermaid component diagram (`graph TD`) + narrative
   - `## Core Components` — detailed breakdown with `###` per component
   - `## Usage & Extension` — entry points, configuration, how to extend (when applicable)
   - `## Integration` — links to other wiki module pages

2. Formatting:
   - Max heading depth `####`. Never skip levels (e.g. `##` to `####`).
   - Use `-` for unordered lists (never `*`). Use `1.` only for sequential steps.
   - Use `---` horizontal rules only between `##` sections, never within them.
   - Use `**bold**` for component names on first mention in a section. Do not over-bold.
   - Use markdown tables for structured data with 3+ items and 2+ attributes.
   - Keep paragraphs to 2-3 sentences. Use bullet lists for 3+ items.
   - Include at least one mermaid diagram per page.

3. Developer Content Requirements:
   a. Code Reference Density: Every class, function, or method name MUST be a markdown link with file path and line anchor. Zero bare mentions.
   b. Key Entry Points: Each component section must call out the primary method a developer would invoke, with a one-liner on what it does and returns.
   c. Configuration: If the module reads config or accepts parameters, include a table with columns: Parameter | Type | Default | Description.
   d. Extension Points: If the module supports extension (new analyzer, tool, adapter), document the pattern with concrete steps.
   e. Error Handling: Document what exceptions are raised or caught, and what happens on failure.
   f. "Start Here" Callout: Begin the Core Components section with a blockquote indicating which file/class to read first, e.g.:
      > **Start here:** [`ClassName`](path/to/file.py#L10) — read its `main_method()` first.
</FORMATTING_GUIDE>

<WORKFLOW>
1. Analyze provided code components and module structure
2. Explore dependencies between components if needed
3. Generate complete {module_filename}.md documentation file
</WORKFLOW>

<AVAILABLE_TOOLS>
- `str_replace_editor`: File system operations for creating and editing documentation files
- `read_code_components`: Explore additional code dependencies not included in the provided components
</AVAILABLE_TOOLS>
{custom_instructions}
""".strip()

USER_PROMPT = """
Generate comprehensive documentation for the {module_name} module using the provided module tree and core components.

<MODULE_TREE>
{module_tree}
</MODULE_TREE>
* NOTE: You can refer the other modules in the module tree based on the dependencies between their core components to make the documentation more structured and avoid repeating the same information. Know that all documentation files are saved in the same folder not structured as module tree. File names must be all lowercase with hyphens instead of spaces. e.g. [alt text](ref-module-name.md)

<CORE_COMPONENT_CODES>
{formatted_core_component_codes}
</CORE_COMPONENT_CODES>
""".strip()

REPO_OVERVIEW_PROMPT = """
You are an AI documentation assistant. Your task is to generate a brief overview of the {repo_name} repository.

The overview should be a brief documentation of the repository, including:
- The purpose of the repository
- The end-to-end architecture of the repository visualized by mermaid diagrams
- The references to the core modules documentation
- A "Supplementary Data" section listing the machine-readable data files available in this directory for programmatic use

IMPORTANT: All wiki documentation files (including this overview) live in the SAME directory. When linking to other module documentation, use just the filename with no directory prefix. For example: [Module Name](module_name.md), NOT [Module Name](wiki/module_name.md).

NOTE: This directory also contains machine-readable data files that complement the documentation:
- `module_tree.json`: The hierarchical module structure and component assignments.
- `dependency_graph.json`: The full dependency graph with all code components (classes, functions, methods), their file paths, line numbers, source code, and call relationships. This file is especially useful for programmatic code navigation and understanding cross-file dependencies.
Include a "Supplementary Data" section at the end of the overview that briefly describes these files and their purpose.

Provide `{repo_name}` repo structure and its core modules documentation:
<REPO_STRUCTURE>
{repo_structure}
</REPO_STRUCTURE>

Please generate the overview of the `{repo_name}` repository in markdown format with the following structure:
<OVERVIEW>
overview_content
</OVERVIEW>
""".strip()

MODULE_OVERVIEW_PROMPT = """
You are an AI documentation assistant. Your task is to generate a brief overview of `{module_name}` module.

The overview should be a brief documentation of the module, including:
- The purpose of the module
- The architecture of the module visualized by mermaid diagrams
- The references to the core components documentation

IMPORTANT: All wiki documentation files (including this overview) live in the SAME directory. When linking to other module documentation, use just the filename with no directory prefix. For example: [Module Name](module_name.md), NOT [Module Name](wiki/module_name.md).

Provide repo structure and core components documentation of the `{module_name}` module:
<REPO_STRUCTURE>
{repo_structure}
</REPO_STRUCTURE>

Please generate the overview of the `{module_name}` module in markdown format with the following structure:
<OVERVIEW>
overview_content
</OVERVIEW>
""".strip()

CLUSTER_REPO_PROMPT = """
Here is list of all potential core components of the repository (It's normal that some components are not essential to the repository):
<POTENTIAL_CORE_COMPONENTS>
{potential_core_components}
</POTENTIAL_CORE_COMPONENTS>

Please group the components into groups such that each group is a set of components that are closely related to each other and together they form a module. DO NOT include components that are not essential to the repository.
Firstly reason about the components and then group them and return the result in the following format:
<GROUPED_COMPONENTS>
{{
    "module_name_1": {{
        "path": <path_to_the_module_1>, # the path to the module can be file or directory
        "components": [
            <component_name_1>,
            <component_name_2>,
            ...
        ]
    }},
    "module_name_2": {{
        "path": <path_to_the_module_2>,
        "components": [
            <component_name_1>,
            <component_name_2>,
            ...
        ]
    }},
    ...
}}
</GROUPED_COMPONENTS>
""".strip()

CLUSTER_MODULE_PROMPT = """
Here is the module tree of a repository:

<MODULE_TREE>
{module_tree}
</MODULE_TREE>

Here is list of all potential core components of the module {module_name} (It's normal that some components are not essential to the module):
<POTENTIAL_CORE_COMPONENTS>
{potential_core_components}
</POTENTIAL_CORE_COMPONENTS>

Please group the components into groups such that each group is a set of components that are closely related to each other and together they form a smaller module. DO NOT include components that are not essential to the module.

Firstly reason based on given context and then group them and return the result in the following format:
<GROUPED_COMPONENTS>
{{
    "module_name_1": {{
        "path": <path_to_the_module_1>, # the path to the module can be file or directory
        "components": [
            <component_name_1>,
            <component_name_2>,
            ...
        ]
    }},
    "module_name_2": {{
        "path": <path_to_the_module_2>,
        "components": [
            <component_name_1>,
            <component_name_2>,
            ...
        ]
    }},
    ...
}}
</GROUPED_COMPONENTS>
""".strip()

FILTER_FOLDERS_PROMPT = """
Here is the list of relative paths of files, folders in 2-depth of project {project_name}:
```
{files}
```

In order to analyze the core functionality of the project, we need to analyze the files, folders representing the core functionality of the project.

Please shortlist the files, folders representing the core functionality and ignore the files, folders that are not essential to the core functionality of the project (e.g. test files, documentation files, etc.) from the list above.

Reasoning at first, then return the list of relative paths in JSON format.
"""

from typing import Dict, Any
from codewiki.src.utils import file_manager

EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".md": "markdown",
    ".sh": "bash",
    ".json": "json",
    ".yaml": "yaml",
    ".java": "java",
    ".js": "javascript",
    ".ts": "typescript",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".tsx": "typescript",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".cxx": "cpp",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".cs": "csharp",
    ".php": "php",
    ".phtml": "php",
    ".inc": "php",
}


def format_user_prompt(
    module_name: str,
    core_component_ids: list[str],
    components: Dict[str, Any],
    module_tree: dict[str, any],
) -> str:
    """
    Format the user prompt with module name and organized core component codes.

    Args:
        module_name: Name of the module to document
        core_component_ids: List of component IDs to include
        components: Dictionary mapping component IDs to CodeComponent objects

    Returns:
        Formatted user prompt string
    """

    def _format_component_with_line(comp_id: str) -> str:
        """Format a component ID with its start line number if available."""
        if comp_id in components:
            node = components[comp_id]
            if hasattr(node, "start_line") and node.start_line > 0:
                return f"{comp_id} (L{node.start_line})"
        return comp_id

    # format module tree
    lines = []

    def _format_module_tree(module_tree: dict[str, any], indent: int = 0):
        for key, value in module_tree.items():
            if key == module_name:
                lines.append(f"{'  ' * indent}{key} (current module)")
            else:
                lines.append(f"{'  ' * indent}{key}")

            enriched = [_format_component_with_line(c) for c in value["components"]]
            lines.append(f"{'  ' * (indent + 1)} Core components: {', '.join(enriched)}")
            if isinstance(value["children"], dict) and len(value["children"]) > 0:
                lines.append(f"{'  ' * (indent + 1)} Children:")
                _format_module_tree(value["children"], indent + 2)

    _format_module_tree(module_tree, 0)
    formatted_module_tree = "\n".join(lines)

    # print(f"Formatted module tree:\n{formatted_module_tree}")

    # Group core component IDs by their file path
    grouped_components: dict[str, list[str]] = {}
    for component_id in core_component_ids:
        if component_id not in components:
            continue
        component = components[component_id]
        path = component.relative_path
        if path not in grouped_components:
            grouped_components[path] = []
        grouped_components[path].append(component_id)

    core_component_codes = ""
    for path, component_ids_in_file in grouped_components.items():
        core_component_codes += f"# File: {path}\n\n"
        core_component_codes += f"## Core Components in this file:\n"

        for component_id in component_ids_in_file:
            core_component_codes += f"- {component_id}\n"

        core_component_codes += (
            f"\n## File Content:\n```{EXTENSION_TO_LANGUAGE['.' + path.split('.')[-1]]}\n"
        )

        # Read content of the file using the first component's file path
        try:
            core_component_codes += file_manager.load_text(
                components[component_ids_in_file[0]].file_path
            )
        except (FileNotFoundError, IOError) as e:
            core_component_codes += f"# Error reading file: {e}\n"

        core_component_codes += "```\n\n"

    return USER_PROMPT.format(
        module_name=module_name,
        formatted_core_component_codes=core_component_codes,
        module_tree=formatted_module_tree,
    )


def format_cluster_prompt(
    potential_core_components: str, module_tree: dict[str, any] = {}, module_name: str = None
) -> str:
    """
    Format the cluster prompt with potential core components and module tree.
    """

    # format module tree
    lines = []

    # print(f"Module tree:\n{json.dumps(module_tree, indent=2)}")

    def _format_module_tree(module_tree: dict[str, any], indent: int = 0):
        for key, value in module_tree.items():
            if key == module_name:
                lines.append(f"{'  ' * indent}{key} (current module)")
            else:
                lines.append(f"{'  ' * indent}{key}")

            lines.append(f"{'  ' * (indent + 1)} Core components: {', '.join(value['components'])}")
            if (
                ("children" in value)
                and isinstance(value["children"], dict)
                and len(value["children"]) > 0
            ):
                lines.append(f"{'  ' * (indent + 1)} Children:")
                _format_module_tree(value["children"], indent + 2)

    _format_module_tree(module_tree, 0)
    formatted_module_tree = "\n".join(lines)

    if module_tree == {}:
        return CLUSTER_REPO_PROMPT.format(potential_core_components=potential_core_components)
    else:
        return CLUSTER_MODULE_PROMPT.format(
            potential_core_components=potential_core_components,
            module_tree=formatted_module_tree,
            module_name=module_name,
        )


def format_system_prompt(
    module_name: str, custom_instructions: str = None, relative_root_path: str = "../"
) -> str:
    """
    Format the system prompt with module name and optional custom instructions.

    Args:
        module_name: Name of the module to document
        custom_instructions: Optional custom instructions to append
        relative_root_path: Relative path from docs dir to repo root (e.g. "../")

    Returns:
        Formatted system prompt string
    """
    from codewiki.src.be.utils import sanitize_filename

    custom_section = ""
    if custom_instructions:
        custom_section = f"\n\n<CUSTOM_INSTRUCTIONS>\n{custom_instructions}\n</CUSTOM_INSTRUCTIONS>"

    return SYSTEM_PROMPT.format(
        module_name=module_name,
        module_filename=sanitize_filename(module_name),
        custom_instructions=custom_section,
        relative_root_path=relative_root_path,
    ).strip()


def format_leaf_system_prompt(
    module_name: str, custom_instructions: str = None, relative_root_path: str = "../"
) -> str:
    """
    Format the leaf system prompt with module name and optional custom instructions.

    Args:
        module_name: Name of the module to document
        custom_instructions: Optional custom instructions to append
        relative_root_path: Relative path from docs dir to repo root (e.g. "../")

    Returns:
        Formatted leaf system prompt string
    """
    from codewiki.src.be.utils import sanitize_filename

    custom_section = ""
    if custom_instructions:
        custom_section = f"\n\n<CUSTOM_INSTRUCTIONS>\n{custom_instructions}\n</CUSTOM_INSTRUCTIONS>"

    return LEAF_SYSTEM_PROMPT.format(
        module_name=module_name,
        module_filename=sanitize_filename(module_name),
        custom_instructions=custom_section,
        relative_root_path=relative_root_path,
    ).strip()
