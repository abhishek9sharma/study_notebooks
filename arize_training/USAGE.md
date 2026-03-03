# Python Project Analyzer - Usage Guide

## Overview

This LangGraph-based agent analyzes Python projects and automatically generates comprehensive README.md files. It uses AST-based tools to extract functions, classes, imports, and structure information.

## Features

### Tools Included

1. **get_files** - Finds all Python files in a project
2. **read_file** - Reads file contents
3. **extract_functions** - Uses AST to extract function definitions
4. **extract_classes** - Uses AST to extract class definitions with methods
5. **resolve_imports** - Uses AST to resolve and list all imports
6. **determine_submodules** - Analyzes package structure via `__init__.py` files
7. **get_project_structure** - Determines overall project layout

### Key Components

- **CodeAnalyzer**: AST-based static analysis utilities
- **LangGraph Workflow**: 4-node workflow for analysis
- **Arize Integration**: Optional tracing for observability
- **GPT-OSS-120B Integration**: Uses open-source model for intelligent README generation

## Installation

```bash
# Install core dependencies
pip install -r requirements.txt

# Set up OpenAI API (for GPT-OSS-120B)
export OPENAI_API_KEY="your-api-key"

# Optional: Install Arize tracing
pip install arize-phoenix>=5.0.0

# Optional: Set up Arize credentials
export ARIZE_API_KEY="your-arize-api-key"
export ARIZE_SPACE_KEY="your-arize-space-key"
```

## Usage

### Basic Usage

```bash
# Analyze current directory
python python_project_analyzer.py

# Analyze a specific project
python python_project_analyzer.py /path/to/project
```

### Workflow Steps

1. **get_files**: Discovers all Python files in the project
2. **analyze_files**: Extracts functions, classes, and imports from each file
3. **analyze_structure**: Determines package structure and submodules
4. **generate_readme**: Uses GPT-OSS-120B to create a comprehensive README

## Example Output

The script generates a README.md with:

```markdown
# Project Name

## Overview
[Project description]

## Features
- Feature 1
- Feature 2

## Project Structure
project/
├── module1/
│   ├── __init__.py
│   └── core.py
└── module2/
    └── utils.py

## Key Modules
- `module1.core`: Core functionality
- `module2.utils`: Utility functions

## Installation
pip install -r requirements.txt

## Usage
[Usage examples based on main functions]
```

## Arize Tracing (Optional)

If Arize credentials are provided, the agent will automatically trace:
- Agent execution flow
- LLM calls to GPT-OSS-120B
- Execution timing
- Input/output data

View traces at: https://app.arize.com

## AST Analysis Details

### Function Extraction
- Function name
- Arguments
- Docstring (if present)
- Line number

### Class Extraction
- Class name
- Methods
- Docstring (if present)
- Line number

### Import Resolution
- Standard library imports
- Third-party imports
- Local module imports

## Limitations

- Analyzes first 15 files by default (configurable in code)
- Requires valid Python syntax
- Large projects may take longer to analyze
- README generation quality depends on code documentation

## Customization

Edit these parameters in `python_project_analyzer.py`:

```python
# Limit files analyzed
for file_path in state["python_files"][:15]:  # Change 15
    ...

# Adjust model or temperature
llm = ChatOpenAI(
    model="gpt-oss-120b",  # Or other model
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY")
)
```

## Troubleshooting

### "OPENAI_API_KEY not found"
Set your API key: `export OPENAI_API_KEY="sk-..."`

### Arize tracing not working
Arize is optional. Install with: `pip install arize-phoenix>=5.0.0`

### README not saved
Check that you have write permissions in the project directory.

### Model not found error
Verify GPT-OSS-120B is available through your OpenAI API account, or switch to another model.

## Example: Analyzing This Script

```bash
python python_project_analyzer.py .
```

This will analyze the analyzer itself and generate a README for it!
