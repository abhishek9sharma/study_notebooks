#!/usr/bin/env python3
"""
Demo script showing how to use the Python Project Analyzer.

This script demonstrates:
1. Basic usage from command line
2. Programmatic usage with custom configuration
3. Working with analysis results
"""

import os
from pathlib import Path
from arize_training.repo_analyzer import (
    main,
    CodeAnalyzer,
    get_files,
    read_file,
    determine_submodules,
    get_project_structure,
)


def demo_basic_usage():
    """Demo 1: Basic command-line style usage."""
    print("\n" + "=" * 70)
    print("DEMO 1: Basic Usage (Analyze current directory)")
    print("=" * 70)
    print("""
    Usage:
        python python_project_analyzer.py
    or
        python python_project_analyzer.py /path/to/project

    This will:
    1. Scan all Python files
    2. Extract functions, classes, and imports
    3. Analyze project structure
    4. Generate README.md using GPT-OSS-120B
    5. Save to project directory
    """)


def demo_direct_tools():
    """Demo 2: Using tools directly without the workflow."""
    print("\n" + "=" * 70)
    print("DEMO 2: Using Analysis Tools Directly")
    print("=" * 70)

    project_path = "."

    # Get all Python files
    print("\n📂 Listing Python files:")
    files = get_files(project_path)
    for f in files[:5]:
        print(f"   - {f}")
    if len(files) > 5:
        print(f"   ... and {len(files) - 5} more")

    # Analyze a specific file
    print("\n📝 Analyzing python_project_analyzer.py:")
    content = read_file(project_path, "python_project_analyzer.py")
    if content:
        functions = CodeAnalyzer.extract_functions(content)
        classes = CodeAnalyzer.extract_classes(content)
        imports = CodeAnalyzer.extract_imports(content)

        print(f"   Functions: {len(functions)}")
        for func in functions[:3]:
            print(f"      - {func['name']}({', '.join(func['args'])})")

        print(f"   Classes: {len(classes)}")
        for cls in classes[:3]:
            print(f"      - {cls['name']}")

        print(f"   Imports: {len(imports)}")
        for imp in imports[:5]:
            print(f"      - {imp}")

    # Get project structure
    print("\n🏗️  Project Structure:")
    structure = get_project_structure(project_path)
    print(f"   Root files: {structure['root_files']}")
    print(f"   Root dirs: {structure['directories']}")
    print(f"   Has setup.py: {structure['has_setup_py']}")
    print(f"   Has pyproject.toml: {structure['has_pyproject_toml']}")

    # Get submodules
    print("\n📦 Submodules:")
    submodules = determine_submodules(project_path)
    if submodules:
        for pkg, modules in submodules.items():
            print(f"   {pkg}: {modules}")
    else:
        print("   (none found)")


def demo_custom_project():
    """Demo 3: Analyzing a specific project with custom settings."""
    print("\n" + "=" * 70)
    print("DEMO 3: Custom Project Analysis")
    print("=" * 70)
    print("""
    To analyze a specific project:

    from python_project_analyzer import main

    # Analyze with default settings
    result = main("/path/to/myproject")

    # Access results
    print(result["readme_content"])
    print(f"Functions found: {sum(len(f) for f in result['functions_by_file'].values())}")
    print(f"Files analyzed: {len(result['file_contents'])}")
    """)


def demo_with_arize():
    """Demo 4: Using with Arize tracing."""
    print("\n" + "=" * 70)
    print("DEMO 4: Enable Arize Tracing")
    print("=" * 70)
    print("""
    To enable Arize tracing:

    1. Set environment variables:
       export ARIZE_API_KEY="your-api-key"
       export ARIZE_SPACE_KEY="your-space-key"
       export OPENAI_API_KEY="your-openai-key"

    2. Run the analyzer:
       python python_project_analyzer.py /path/to/project

    3. View traces at:
       https://app.arize.com

    The agent will automatically trace:
    - Workflow execution
    - LLM calls
    - File analysis
    - README generation
    """)


def demo_extending():
    """Demo 5: Extending with custom analysis."""
    print("\n" + "=" * 70)
    print("DEMO 5: Extending the Analyzer")
    print("=" * 70)
    print("""
    Add custom analysis tools:

    from python_project_analyzer import CodeAnalyzer, read_file
    import ast

    def extract_async_functions(code: str):
        '''Find all async functions'''
        tree = ast.parse(code)
        async_funcs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                async_funcs.append(node.name)
        return async_funcs

    # Use in analysis
    content = read_file(".", "some_file.py")
    async_funcs = extract_async_functions(content)
    """)


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🚀 Python Project Analyzer - Demo Guide")
    print("=" * 70)

    # Show all demos
    demo_basic_usage()
    demo_direct_tools()
    demo_custom_project()
    demo_with_arize()
    demo_extending()

    print("\n" + "=" * 70)
    print("📖 For more information, see USAGE.md")
    print("=" * 70 + "\n")
