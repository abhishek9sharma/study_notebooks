#!/usr/bin/env python3
"""
LangGraph-based Python Project Analyzer with README Generator and Arize Tracing.

This agent analyzes Python projects, extracts information about modules, functions,
imports, and structure, then generates a comprehensive README.md file.
"""

import os
import ast
import json
import re
from pathlib import Path
from typing import Any, Optional
from collections import defaultdict

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from typing_extensions import TypedDict, Annotated

from arize.otel import register
import os


# ============================================================================
# ARIZE TRACING
# ============================================================================
arize_api_key = os.environ["ARIZE_API_KEY"]
tracer_provider = register(
    space_id="U3BhY2U6OTkyNDpMazh1",
    api_key=arize_api_key,
    project_name="ABHISHEK_REPO_ANALYZER",  # name this to whatever you would like
)

from openinference.instrumentation.langchain import LangChainInstrumentor

LangChainInstrumentor().instrument(tracer_provider=tracer_provider)


# ============================================================================
# STATE DEFINITION
# ============================================================================
class AnalysisState(TypedDict):
    """State for the analysis workflow."""

    project_path: str
    python_files: list[str]
    file_contents: dict[str, str]
    functions_by_file: dict[str, list[dict]]
    imports_by_file: dict[str, list[str]]
    submodules: dict[str, list[str]]
    classes_by_file: dict[str, list[dict]]
    readme_content: str
    analysis_complete: bool


# ============================================================================
# AST-BASED TOOLS
# ============================================================================
class CodeAnalyzer:
    """AST-based code analysis utilities."""

    @staticmethod
    def extract_functions(code: str) -> list[dict]:
        """Extract all functions from Python code using AST."""
        try:
            tree = ast.parse(code)
            functions = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    docstring = ast.get_docstring(node)
                    args = [arg.arg for arg in node.args.args]
                    functions.append(
                        {
                            "name": node.name,
                            "args": args,
                            "docstring": docstring,
                            "lineno": node.lineno,
                        }
                    )
            return functions
        except Exception as e:
            return []

    @staticmethod
    def extract_classes(code: str) -> list[dict]:
        """Extract all classes from Python code using AST."""
        try:
            tree = ast.parse(code)
            classes = []

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    docstring = ast.get_docstring(node)
                    methods = []
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            methods.append(item.name)

                    classes.append(
                        {
                            "name": node.name,
                            "methods": methods,
                            "docstring": docstring,
                            "lineno": node.lineno,
                        }
                    )
            return classes
        except Exception as e:
            return []

    @staticmethod
    def extract_imports(code: str) -> list[str]:
        """Extract all imports from Python code using AST."""
        try:
            tree = ast.parse(code)
            imports = []

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        imports.append(
                            f"{module}.{alias.name}" if module else alias.name
                        )

            return sorted(list(set(imports)))
        except Exception as e:
            return []


# ============================================================================
# TOOL FUNCTIONS
# ============================================================================
def get_files(project_path: str) -> list[str]:
    """Get all Python files in the project."""
    python_files = []
    project_path = Path(project_path)

    for py_file in project_path.rglob("*.py"):
        if "__pycache__" not in str(py_file) and ".venv" not in str(py_file):
            python_files.append(str(py_file.relative_to(project_path)))

    return sorted(python_files)


def read_file(project_path: str, file_path: str) -> Optional[str]:
    """Read a Python file from the project."""
    try:
        full_path = Path(project_path) / file_path
        if full_path.exists() and full_path.is_file():
            return full_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return None


def extract_functions(project_path: str, file_path: str) -> list[dict]:
    """Extract functions from a Python file."""
    content = read_file(project_path, file_path)
    if content:
        return CodeAnalyzer.extract_functions(content)
    return []


def extract_classes(project_path: str, file_path: str) -> list[dict]:
    """Extract classes from a Python file."""
    content = read_file(project_path, file_path)
    if content:
        return CodeAnalyzer.extract_classes(content)
    return []


def resolve_imports(project_path: str, file_path: str) -> list[str]:
    """Resolve imports from a Python file."""
    content = read_file(project_path, file_path)
    if content:
        return CodeAnalyzer.extract_imports(content)
    return []


def determine_submodules(project_path: str) -> dict[str, list[str]]:
    """Determine submodules by analyzing __init__.py files."""
    submodules = defaultdict(list)
    project_path = Path(project_path)

    for init_file in project_path.rglob("__init__.py"):
        if "__pycache__" in str(init_file):
            continue

        package_dir = init_file.parent
        relative_package = str(package_dir.relative_to(project_path)).replace("/", ".")

        # Get all Python files in this package
        for py_file in package_dir.glob("*.py"):
            if py_file.name != "__init__.py":
                module_name = py_file.stem
                submodules[relative_package].append(module_name)

    return dict(submodules)


def get_project_structure(project_path: str) -> dict:
    """Get overall project structure."""
    structure = {
        "root_files": [],
        "directories": [],
        "has_setup_py": False,
        "has_pyproject_toml": False,
        "has_requirements": False,
    }

    project_path = Path(project_path)

    for item in project_path.iterdir():
        if item.is_file() and item.suffix == ".py":
            structure["root_files"].append(item.name)
        elif item.is_dir() and not item.name.startswith("."):
            structure["directories"].append(item.name)

    structure["has_setup_py"] = (project_path / "setup.py").exists()
    structure["has_pyproject_toml"] = (project_path / "pyproject.toml").exists()
    structure["has_requirements"] = (project_path / "requirements.txt").exists()

    return structure


# ============================================================================
# NODE FUNCTIONS
# ============================================================================
def node_get_files(state: AnalysisState) -> Command[AnalysisState]:
    """Node: Get all Python files in the project."""
    print(f"\n🔍 Getting Python files from {state['project_path']}...")

    files = get_files(state["project_path"])
    print(f"   Found {len(files)} Python files")

    return Command(
        update={
            "python_files": files,
            "file_contents": {},
            "functions_by_file": {},
            "imports_by_file": {},
            "classes_by_file": {},
        },
        goto="analyze_files",
    )


def node_analyze_files(state: AnalysisState) -> Command[AnalysisState]:
    """Node: Analyze all Python files."""
    print("\n📊 Analyzing Python files...")

    file_contents = {}
    functions_by_file = {}
    imports_by_file = {}
    classes_by_file = {}

    for file_path in state["python_files"][:15]:  # Limit to first 15 files for demo
        print(f"   Analyzing {file_path}...")

        # Read file
        content = read_file(state["project_path"], file_path)
        if content:
            file_contents[file_path] = content

            # Extract functions and classes
            functions_by_file[file_path] = extract_functions(
                state["project_path"], file_path
            )
            classes_by_file[file_path] = extract_classes(
                state["project_path"], file_path
            )
            imports_by_file[file_path] = resolve_imports(
                state["project_path"], file_path
            )

    return Command(
        update={
            "file_contents": file_contents,
            "functions_by_file": functions_by_file,
            "classes_by_file": classes_by_file,
            "imports_by_file": imports_by_file,
        },
        goto="analyze_structure",
    )


def node_analyze_structure(state: AnalysisState) -> Command[AnalysisState]:
    """Node: Analyze project structure and submodules."""
    print("\n🏗️  Analyzing project structure...")

    submodules = determine_submodules(state["project_path"])
    print(f"   Found {len(submodules)} packages")

    return Command(
        update={"submodules": submodules},
        goto="generate_readme",
    )


def node_generate_readme(state: AnalysisState) -> Command[AnalysisState]:
    """Node: Generate README content using LLMs."""
    print("\n✍️  Generating README.")

    # Prepare context for Claude
    project_structure = get_project_structure(state["project_path"])

    # Count statistics
    total_functions = sum(len(funcs) for funcs in state["functions_by_file"].values())
    total_classes = sum(len(classes) for classes in state["classes_by_file"].values())

    context = f"""
Project Analysis Summary:
- Python Files: {len(state['python_files'])}
- Analyzed Files: {len(state['file_contents'])}
- Total Functions: {total_functions}
- Total Classes: {total_classes}
- Packages: {list(state['submodules'].keys())}
- Root Files: {project_structure['root_files']}
- Root Directories: {project_structure['directories']}

File Analysis:
"""

    for file_path, functions in state["functions_by_file"].items():
        context += f"\n{file_path}:\n"
        if functions:
            context += "  Functions:\n"
            for func in functions[:5]:  # Limit to 5 functions per file
                context += f"    - {func['name']}({', '.join(func['args'])})\n"

        if file_path in state["classes_by_file"]:
            classes = state["classes_by_file"][file_path]
            if classes:
                context += "  Classes:\n"
                for cls in classes:
                    methods_str = ", ".join(cls["methods"][:3])
                    context += f"    - {cls['name']}: {methods_str}\n"

    # Use GPT-OSS-120B to generate README
    # gpt-oss-120b
    llm = ChatOpenAI(
        model="gpt-3.5-turbo", temperature=0.7, api_key=os.getenv("OPENAI_API_KEY")
    )

    prompt = f"""Based on the following Python project analysis, generate a comprehensive README.md file.

{context}

Create a README that includes:
1. Project Overview (what the project does)
2. Features (inferred from the code structure)
3. Project Structure (directory layout)
4. Key Modules and Components
5. Installation
6. Usage Examples (inferred from main functions)
7. Development Notes

Format the output as valid Markdown. Be concise but informative."""

    response = llm.invoke(prompt)
    readme_content = response.content

    return Command(
        update={
            "readme_content": readme_content,
            "analysis_complete": True,
        },
        goto=END,
    )


# ============================================================================
# WORKFLOW SETUP
# ============================================================================
def create_workflow():
    """Create the LangGraph workflow."""
    workflow = StateGraph(AnalysisState)

    # Add nodes
    workflow.add_node("get_files", node_get_files)
    workflow.add_node("analyze_files", node_analyze_files)
    workflow.add_node("analyze_structure", node_analyze_structure)
    workflow.add_node("generate_readme", node_generate_readme)

    # Add edges
    workflow.add_edge(START, "get_files")

    return workflow.compile()


# ============================================================================
# MAIN EXECUTION
# ============================================================================
def main(project_path: str = "."):
    """Main entry point for the analyzer."""
    print("=" * 70)
    print("🚀 Python Project Analyzer with README Generator")
    print("=" * 70)

    # Validate project path
    if not Path(project_path).exists():
        print(f"❌ Project path does not exist: {project_path}")
        return

    # Create workflow
    print("\n📦 Creating LangGraph workflow...")
    workflow = create_workflow()

    # Initialize state
    initial_state: AnalysisState = {
        "project_path": project_path,
        "python_files": [],
        "file_contents": {},
        "functions_by_file": {},
        "imports_by_file": {},
        "submodules": {},
        "classes_by_file": {},
        "readme_content": "",
        "analysis_complete": False,
    }

    # Execute workflow with Arize tracing if available
    print("\n🔄 Executing analysis workflow...\n")
    final_state = workflow.invoke(initial_state)

    # Output results
    print("\n" + "=" * 70)
    print("📋 GENERATED README.MD")
    print("=" * 70)
    print(final_state["readme_content"])
    print("=" * 70)

    # Save README to file
    readme_path = Path(project_path) / "README.md"
    readme_path.write_text(final_state["readme_content"])
    print(f"\n✅ README saved to {readme_path}")

    # Print summary statistics
    print("\n📊 Analysis Summary:")
    print(f"   - Python Files Found: {len(final_state['python_files'])}")
    print(f"   - Files Analyzed: {len(final_state['file_contents'])}")
    print(
        f"   - Total Functions: {sum(len(f) for f in final_state['functions_by_file'].values())}"
    )
    print(
        f"   - Total Classes: {sum(len(c) for c in final_state['classes_by_file'].values())}"
    )
    print(f"   - Packages: {len(final_state['submodules'])}")

    return final_state


if __name__ == "__main__":
    import sys

    # Get project path from command line or use current directory
    project_path = sys.argv[1] if len(sys.argv) > 1 else "."

    result = main(project_path)
