"""
General-purpose Docker command executor for analysis agent.
Allows LLM to execute arbitrary commands in Docker containers.
"""
import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def execute_docker_command(
    container_name: str,
    command: str,
    timeout: int = 30
) -> dict:
    """Execute arbitrary shell command in Docker container.

    This is a general-purpose tool that allows the LLM to run any command
    in the target container. The LLM is responsible for constructing the
    appropriate command (cat, ls, grep, find, etc.).

    Args:
        container_name: Name or ID of the Docker container
        command: Shell command to execute in the container
        timeout: Command timeout in seconds (default: 30)

    Returns:
        dict: {
            "success": bool,
            "exit_code": int,
            "stdout": str,
            "stderr": str,
            "command": str,
            "container": str,
            "message": str
        }

    Note:
        The LLM should construct appropriate commands based on its needs.
        This tool provides maximum flexibility while keeping implementation simple.
    """
    try:
        logger.info(f"Executing in container '{container_name}': {command}")

        # Execute command via docker exec with shell
        result = subprocess.run(
            ["docker", "exec", container_name, "sh", "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr

        success = exit_code == 0

        logger.info(f"Command completed: exit_code={exit_code}, success={success}")

        if not success:
            logger.warning(f"Command failed: {stderr}")

        return {
            "success": success,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "command": command,
            "container": container_name,
            "message": f"Command {'succeeded' if success else 'failed'} with exit code {exit_code}"
        }

    except subprocess.TimeoutExpired:
        error_msg = f"Command timed out after {timeout} seconds"
        logger.error(error_msg)
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": error_msg,
            "command": command,
            "container": container_name,
            "message": error_msg
        }

    except FileNotFoundError:
        error_msg = "Docker command not found. Is Docker installed and in PATH?"
        logger.error(error_msg)
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": error_msg,
            "command": command,
            "container": container_name,
            "message": error_msg
        }

    except Exception as e:
        error_msg = f"Error executing command: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": error_msg,
            "command": command,
            "container": container_name,
            "message": error_msg
        }


__all__ = ["execute_docker_command"]
