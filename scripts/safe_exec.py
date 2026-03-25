#!/usr/bin/env python3
"""
Safe Command Executor

A helper script for executing shell commands with safety checks,
input validation, and timeout control.

Usage:
    python safe_exec.py "ls -la"
    python safe_exec.py "rm -rf /tmp/cache" --confirm
    python safe_exec.py "curl https://example.com" --timeout 30
"""

import argparse
import subprocess
import sys
import shlex
import re
from typing import Tuple, List, Optional

# Dangerous command patterns that require confirmation
DANGEROUS_PATTERNS = [
    r'\brm\s+-rf\b',
    r'\brm\s+-r\b',
    r'\brm\s*-.*f\b',
    r'\bmkfs\b',
    r'\bdd\b.*of=',
    r'\bformat\b',
    r'\bshutdown\b',
    r'\breboot\b',
    r'\binit\s+0\b',
    r'\binit\s+6\b',
    r'\bhalt\b',
    r'\bpoweroff\b',
    r'>\s*/dev/',  # Writing to device files
    r'\bchmod\s+777\b',
    r'\bchown\b.*root',
]

# Blocked commands (never allowed)
BLOCKED_PATTERNS = [
    r'\brm\s+-rf\s+/\s*$',
    r'\brm\s+-rf\s+/\*',
    r'\brm\s+-rf\s+~',
    r'>\s*/dev/sd[a-z]',
    r'\bmkfs\b.*/dev/sd[a-z]',
]


def validate_command(cmd: str) -> Tuple[bool, str, bool]:
    """
    Validate a command for safety.
    
    Returns:
        (is_safe, message, requires_confirmation)
    """
    # Check blocked patterns
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return False, f"BLOCKED: Command matches dangerous pattern: {pattern}", False
    
    # Check dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return True, f"WARNING: Command may be destructive. Requires confirmation.", True
    
    return True, "Command appears safe.", False


def execute_command(
    cmd: str,
    timeout: Optional[int] = None,
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    shell: bool = True
) -> Tuple[int, str, str]:
    """
    Execute a shell command.
    
    Args:
        cmd: Command to execute
        timeout: Timeout in seconds
        cwd: Working directory
        env: Environment variables
        shell: Whether to use shell
        
    Returns:
        (exit_code, stdout, stderr)
    """
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        return -1, "", str(e)


def main():
    parser = argparse.ArgumentParser(
        description="Safe command executor with validation and timeout"
    )
    parser.add_argument("command", help="Command to execute")
    parser.add_argument("--timeout", "-t", type=int, default=None,
                        help="Timeout in seconds")
    parser.add_argument("--cwd", "-c", type=str, default=None,
                        help="Working directory")
    parser.add_argument("--confirm", "-y", action="store_true",
                        help="Auto-confirm dangerous commands")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Only validate, don't execute")
    parser.add_argument("--json", "-j", action="store_true",
                        help="Output in JSON format")
    
    args = parser.parse_args()
    
    # Validate command
    is_safe, message, requires_confirmation = validate_command(args.command)
    
    if args.json:
        import json
        result = {
            "command": args.command,
            "is_safe": is_safe,
            "message": message,
            "requires_confirmation": requires_confirmation
        }
        
        if not is_safe or args.dry_run:
            print(json.dumps(result, indent=2))
            sys.exit(1 if not is_safe else 0)
        
        if requires_confirmation and not args.confirm:
            result["executed"] = False
            result["message"] = "Command requires confirmation. Use --confirm to proceed."
            print(json.dumps(result, indent=2))
            sys.exit(2)
        
        # Execute
        exit_code, stdout, stderr = execute_command(
            args.command,
            timeout=args.timeout,
            cwd=args.cwd
        )
        result["executed"] = True
        result["exit_code"] = exit_code
        result["stdout"] = stdout
        result["stderr"] = stderr
        print(json.dumps(result, indent=2))
        sys.exit(exit_code if exit_code > 0 else 0)
    
    # Non-JSON output
    print(f"Command: {args.command}")
    print(f"Validation: {message}")
    
    if not is_safe:
        print("ERROR: Command blocked for safety.")
        sys.exit(1)
    
    if args.dry_run:
        print("Dry run: Command not executed.")
        sys.exit(0)
    
    if requires_confirmation and not args.confirm:
        print("WARNING: This command may be destructive.")
        print("Use --confirm to proceed.")
        sys.exit(2)
    
    print("-" * 40)
    
    # Execute
    exit_code, stdout, stderr = execute_command(
        args.command,
        timeout=args.timeout,
        cwd=args.cwd
    )
    
    if stdout:
        print(stdout)
    if stderr:
        print(f"STDERR: {stderr}", file=sys.stderr)
    
    print("-" * 40)
    print(f"Exit code: {exit_code}")
    
    sys.exit(exit_code if exit_code > 0 else 0)


if __name__ == "__main__":
    main()
