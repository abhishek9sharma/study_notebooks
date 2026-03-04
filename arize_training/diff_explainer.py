#!/usr/bin/env python3
"""
LangGraph-based Diff to Commit Explainer with Arize Tracing.

Takes a git diff from multiple sources (GitHub PR/commit URL, Bitbucket URL,
local file, or `git diff` CLI) and explains it in plain English, generating:
- One-line commit message
- Bullet-point summary of changes
- Potential concerns
"""

import re
import subprocess
from pathlib import Path
from typing import Optional

import requests
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from typing_extensions import TypedDict

from arize.otel import register
import os


# ============================================================================
# ARIZE TRACING
# ============================================================================
arize_api_key = os.environ["ARIZE_API_KEY"]
tracer_provider = register(
    space_id="U3BhY2U6OTkyNDpMazh1",
    api_key=arize_api_key,
    project_name="DIFF_EXPLAINER",
)

from openinference.instrumentation.langchain import LangChainInstrumentor

LangChainInstrumentor().instrument(tracer_provider=tracer_provider)


# ============================================================================
# STATE DEFINITION
# ============================================================================
class DiffExplainerState(TypedDict):
    """State for the diff explainer workflow."""

    source_type: str  # "github" | "bitbucket" | "file" | "git"
    source_input: str  # URL, file path, or repo path
    raw_diff: str  # fetched/read diff text
    explanation: str  # final output


# ============================================================================
# DIFF FETCHING FUNCTIONS
# ============================================================================
def fetch_github_diff(url: str) -> Optional[str]:
    """Fetch diff from GitHub PR or commit URL.

    Supports:
    - https://github.com/owner/repo/commit/abc123
    - https://github.com/owner/repo/pull/123
    """
    try:
        # Extract owner and repo from URL
        match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
        if not match:
            print(f"❌ Invalid GitHub URL: {url}")
            return None

        owner, repo = match.groups()

        # Check if it's a commit or PR
        if "/commit/" in url:
            sha = url.split("/commit/")[-1].split("#")[0]
            api_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
            print(f"📡 Fetching GitHub commit diff: {api_url}")

            headers = {}
            if token := os.getenv("GITHUB_TOKEN"):
                headers["Authorization"] = f"token {token}"

            response = requests.get(api_url, headers=headers)
            response.raise_for_status()

            data = response.json()
            # Reconstruct diff from patch field
            patch_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}.patch"
            patch_response = requests.get(patch_url, headers=headers)
            patch_response.raise_for_status()
            return patch_response.text

        elif "/pull/" in url:
            pr_number = url.split("/pull/")[-1].split("#")[0]
            api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
            print(f"📡 Fetching GitHub PR diff: {api_url}")

            headers = {}
            if token := os.getenv("GITHUB_TOKEN"):
                headers["Authorization"] = f"token {token}"

            # Get the diff
            headers["Accept"] = "application/vnd.github.v3.diff"
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            return response.text

        else:
            print(f"❌ Unsupported GitHub URL format: {url}")
            return None

    except Exception as e:
        print(f"❌ Error fetching GitHub diff: {e}")
        return None


def fetch_bitbucket_diff(url: str) -> Optional[str]:
    """Fetch diff from Bitbucket REST API.

    Supports:
    - https://bitbucket.org/workspace/repo/commits/abc123
    """
    try:
        # Extract workspace and repo from URL
        match = re.search(r"bitbucket\.org/([^/]+)/([^/]+)", url)
        if not match:
            print(f"❌ Invalid Bitbucket URL: {url}")
            return None

        workspace, repo = match.groups()

        # Check if it's a commit
        if "/commits/" in url:
            commit_hash = url.split("/commits/")[-1].split("#")[0]
            api_url = (
                f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo}"
                f"/commit/{commit_hash}/diff"
            )
            print(f"📡 Fetching Bitbucket commit diff: {api_url}")

            # Bitbucket API auth (optional)
            auth = None
            if user := os.getenv("BITBUCKET_USER"):
                if pwd := os.getenv("BITBUCKET_PASSWORD"):
                    auth = (user, pwd)

            response = requests.get(api_url, auth=auth)
            response.raise_for_status()
            return response.text

        else:
            print(f"❌ Unsupported Bitbucket URL format: {url}")
            return None

    except Exception as e:
        print(f"❌ Error fetching Bitbucket diff: {e}")
        return None


def read_file_diff(file_path: str) -> Optional[str]:
    """Read diff from a local .diff or .patch file."""
    try:
        path = Path(file_path)
        if not path.exists():
            print(f"❌ File not found: {file_path}")
            return None

        if not path.suffix in [".diff", ".patch"]:
            print(f"⚠️  Warning: file extension is {path.suffix}, expected .diff or .patch")

        content = path.read_text(encoding="utf-8")
        print(f"📖 Read diff from file: {file_path}")
        return content

    except Exception as e:
        print(f"❌ Error reading diff file: {e}")
        return None


def run_git_diff(repo_path: str) -> Optional[str]:
    """Run `git diff` in a given repository."""
    try:
        repo_path = Path(repo_path)
        if not (repo_path / ".git").exists():
            print(f"❌ Not a git repository: {repo_path}")
            return None

        print(f"🔧 Running `git diff` in {repo_path}...")

        result = subprocess.run(
            ["git", "diff"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )

        if not result.stdout:
            print("⚠️  No changes found (working directory is clean)")
            return ""

        return result.stdout

    except subprocess.CalledProcessError as e:
        print(f"❌ Git command failed: {e.stderr}")
        return None
    except Exception as e:
        print(f"❌ Error running git diff: {e}")
        return None


# ============================================================================
# NODE FUNCTIONS
# ============================================================================
def node_fetch_diff(state: DiffExplainerState) -> Command[DiffExplainerState]:
    """Node: Fetch raw diff based on source type."""
    print(f"\n🔍 Fetching diff from source_type: {state['source_type']}")
    print(f"   Input: {state['source_input']}")

    raw_diff = None

    if state["source_type"] == "github":
        raw_diff = fetch_github_diff(state["source_input"])

    elif state["source_type"] == "bitbucket":
        raw_diff = fetch_bitbucket_diff(state["source_input"])

    elif state["source_type"] == "file":
        raw_diff = read_file_diff(state["source_input"])

    elif state["source_type"] == "git":
        raw_diff = run_git_diff(state["source_input"])

    else:
        print(f"❌ Unknown source_type: {state['source_type']}")
        return Command(update={"raw_diff": ""}, goto=END)

    if raw_diff is None:
        print("❌ Failed to fetch diff")
        return Command(update={"raw_diff": ""}, goto=END)

    if not raw_diff:
        print("⚠️  Empty diff (no changes)")

    return Command(
        update={"raw_diff": raw_diff},
        goto="explain_diff",
    )


def node_explain_diff(state: DiffExplainerState) -> Command[DiffExplainerState]:
    """Node: Send diff to LLM for explanation."""
    print("\n✍️  Generating explanation...")

    if not state["raw_diff"]:
        explanation = "No changes to explain (empty diff)."
        return Command(
            update={"explanation": explanation},
            goto=END,
        )

    # Truncate very large diffs to avoid token limits
    diff_text = state["raw_diff"]
    if len(diff_text) > 8000:
        print(f"⚠️  Diff is large ({len(diff_text)} chars), truncating for analysis...")
        diff_text = diff_text[:8000] + "\n... (truncated)"

    llm = ChatOpenAI(
        model="gpt-3.5-turbo",
        temperature=0.7,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    prompt = f"""Analyze the following git diff and provide a clear, concise explanation suitable for a commit message and summary.

DIFF:
```
{diff_text}
```

Please provide:
1. **Commit Message**: A single-line summary (50 chars max) of what changed and why.
2. **Summary**: Bullet-point list of:
   - Files changed and what happened to them
   - Key changes made (added, modified, removed features)
   - Why these changes were made (if apparent)
3. **Potential Concerns** (if any):
   - Breaking changes
   - Incomplete implementations
   - Security implications
   - Performance impacts

Format your response clearly with these sections."""

    response = llm.invoke(prompt)
    explanation = response.content

    print("   ✅ Explanation generated")

    return Command(
        update={"explanation": explanation},
        goto=END,
    )


# ============================================================================
# WORKFLOW SETUP
# ============================================================================
def create_workflow():
    """Create the LangGraph workflow."""
    workflow = StateGraph(DiffExplainerState)

    # Add nodes
    workflow.add_node("fetch_diff", node_fetch_diff)
    workflow.add_node("explain_diff", node_explain_diff)

    # Add edges
    workflow.add_edge(START, "fetch_diff")

    return workflow.compile()


# ============================================================================
# MAIN EXECUTION
# ============================================================================
def main(
    mode: str,
    input_value: str,
    path: Optional[str] = None,
) -> DiffExplainerState:
    """Main entry point for the diff explainer.

    Args:
        mode: "github", "bitbucket", "file", or "git"
        input_value: URL (github/bitbucket) or file path (file)
        path: Repository path for git mode
    """
    print("=" * 70)
    print("🚀 Diff to Commit Explainer")
    print("=" * 70)

    # Validate inputs
    if mode not in ["github", "bitbucket", "file", "git"]:
        print(f"❌ Invalid mode: {mode}")
        print("   Supported modes: github, bitbucket, file, git")
        return {
            "source_type": mode,
            "source_input": input_value,
            "raw_diff": "",
            "explanation": "Invalid mode",
        }

    # For git mode, use path if provided, else current directory
    source_input = path if mode == "git" else input_value

    # Create workflow
    print("\n📦 Creating LangGraph workflow...")
    workflow = create_workflow()

    # Initialize state
    initial_state: DiffExplainerState = {
        "source_type": mode,
        "source_input": source_input,
        "raw_diff": "",
        "explanation": "",
    }

    # Execute workflow
    print("\n🔄 Executing workflow...\n")
    final_state = workflow.invoke(initial_state)

    # Output results
    print("\n" + "=" * 70)
    print("📋 DIFF EXPLANATION")
    print("=" * 70)
    print(final_state["explanation"])
    print("=" * 70)

    return final_state


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Explain git diffs using LLM and LangGraph"
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["github", "bitbucket", "file", "git"],
        required=True,
        help="Source type for the diff",
    )

    parser.add_argument(
        "--input",
        type=str,
        help="Input value (URL for github/bitbucket, file path for file)",
    )

    parser.add_argument(
        "--path",
        type=str,
        default=".",
        help="Repository path (for git mode)",
    )

    args = parser.parse_args()

    # Validate required arguments
    if args.mode in ["github", "bitbucket", "file"] and not args.input:
        parser.error(f"--input is required for mode '{args.mode}'")

    result = main(mode=args.mode, input_value=args.input, path=args.path)
