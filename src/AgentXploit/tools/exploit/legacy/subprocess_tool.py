"""
Subprocess-based tool for bash execution and docker deployment.
Provides functionality to execute bash commands and deploy to docker environments using subprocess.
"""

import asyncio
import logging
import subprocess
import shlex
import time
import uuid
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of command execution."""
    stdout: str
    stderr: str
    exit_code: int
    success: bool


@dataclass
class SessionInfo:
    """Information about a bash session."""
    session_id: str
    deployment_type: str
    container_id: Optional[str] = None
    image: Optional[str] = None


class CommandExecutor:
    """
    Subprocess-based tool for bash execution and docker environment deployment.
    Supports docker deployments with command execution via subprocess.
    """
    
    def __init__(self):
        self.deployments: Dict[str, Dict[str, Any]] = {}
        self.sessions: Dict[str, SessionInfo] = {}
        self.active_deployment: Optional[str] = None
        
    async def create_local_deployment(self, deployment_id: str = "local") -> str:
        """
        Create a local deployment (using host system).
        
        Args:
            deployment_id: Unique identifier for the deployment
            
        Returns:
            deployment_id: The ID of the created deployment
        """
        try:
            self.deployments[deployment_id] = {
                "type": "local",
                "container_id": None,
                "image": None,
                "created_at": time.time()
            }
            self.active_deployment = deployment_id
            
            logger.info(f"Local deployment '{deployment_id}' created successfully")
            return deployment_id
            
        except Exception as e:
            logger.error(f"Failed to create local deployment: {e}")
            raise
    
    async def create_docker_deployment(
        self, 
        image: str = "python:3.12",
        deployment_id: str = "docker",
        **kwargs
    ) -> str:
        """
        Create a docker deployment using subprocess.
        
        Args:
            image: Docker image to use (default: python:3.12)
            deployment_id: Unique identifier for the deployment
            **kwargs: Additional arguments (ignored for subprocess implementation)
            
        Returns:
            deployment_id: The ID of the created deployment
        """
        try:
            # Generate unique container name
            container_name = f"{deployment_id}_{int(time.time())}"
            
            # Build docker run command
            docker_cmd = [
                "docker", "run", "-d", "--name", container_name,
                "-w", "/workspace", image, "tail", "-f", "/dev/null"
            ]
            
            # Execute docker run command
            result = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                error_msg = f"Docker run failed: {stderr.decode()}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            container_id = stdout.decode().strip()
            
            self.deployments[deployment_id] = {
                "type": "docker",
                "container_id": container_id,
                "container_name": container_name,
                "image": image,
                "created_at": time.time()
            }
            self.active_deployment = deployment_id
            
            logger.info(f"Docker deployment '{deployment_id}' created successfully with image '{image}'")
            return deployment_id
            
        except Exception as e:
            logger.error(f"Failed to create docker deployment: {e}")
            raise
    
    async def create_openhands_deployment(
        self,
        deployment_id: str = "openhands",
        **kwargs
    ) -> str:
        """
        Create a specialized deployment for OpenHands agent integration.
        
        Args:
            deployment_id: Unique identifier for the deployment
            **kwargs: Additional arguments for docker deployment
            
        Returns:
            deployment_id: The ID of the created deployment
        """
        try:
            # Use a suitable base image for OpenHands agent
            image = kwargs.get('image', 'python:3.12')
            return await self.create_docker_deployment(image, deployment_id, **kwargs)
            
        except Exception as e:
            logger.error(f"Failed to create OpenHands deployment: {e}")
            raise
    
    async def execute_command(
        self, 
        command: Union[str, List[str]],
        deployment_id: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute a one-off command using subprocess.
        
        Args:
            command: Command to execute (string or list of strings)
            deployment_id: ID of deployment to use (uses active if None)
            
        Returns:
            ExecutionResult containing stdout, stderr, exit_code, and success flag
        """
        deployment_id = deployment_id or self.active_deployment
        if not deployment_id or deployment_id not in self.deployments:
            raise ValueError(f"No deployment found with ID: {deployment_id}")
        
        deployment = self.deployments[deployment_id]
        
        try:
            if deployment["type"] == "docker":
                # Execute in Docker container
                container_id = deployment["container_id"]
                if isinstance(command, list):
                    command_str = " ".join(shlex.quote(str(c)) for c in command)
                else:
                    command_str = command
                
                docker_cmd = ["docker", "exec", container_id, "bash", "-c", command_str]
                
                result = await asyncio.create_subprocess_exec(
                    *docker_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                return ExecutionResult(
                    stdout=stdout.decode('utf-8', errors='replace'),
                    stderr=stderr.decode('utf-8', errors='replace'),
                    exit_code=result.returncode or 0,
                    success=result.returncode == 0
                )
            else:
                # Execute locally
                if isinstance(command, str):
                    shell_cmd = command
                    shell = True
                else:
                    shell_cmd = command
                    shell = False
                
                result = await asyncio.create_subprocess_shell(
                    shell_cmd if shell else " ".join(command),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    shell=shell
                )
                stdout, stderr = await result.communicate()
                
                return ExecutionResult(
                    stdout=stdout.decode('utf-8', errors='replace'),
                    stderr=stderr.decode('utf-8', errors='replace'),
                    exit_code=result.returncode or 0,
                    success=result.returncode == 0
                )
            
        except Exception as e:
            logger.error(f"Failed to execute command: {e}")
            return ExecutionResult(
                stdout="",
                stderr=str(e),
                exit_code=-1,
                success=False
            )
    
    async def create_bash_session(
        self,
        session_id: str,
        deployment_id: Optional[str] = None
    ) -> str:
        """
        Create a persistent bash session.
        
        Args:
            session_id: Unique identifier for the session
            deployment_id: ID of deployment to use (uses active if None)
            
        Returns:
            session_id: The ID of the created session
        """
        deployment_id = deployment_id or self.active_deployment
        if not deployment_id or deployment_id not in self.deployments:
            raise ValueError(f"No deployment found with ID: {deployment_id}")
        
        deployment = self.deployments[deployment_id]
        
        try:
            # Store session info
            self.sessions[session_id] = SessionInfo(
                session_id=session_id,
                deployment_type=deployment["type"],
                container_id=deployment.get("container_id"),
                image=deployment.get("image")
            )
            
            logger.info(f"Bash session '{session_id}' created successfully")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to create bash session: {e}")
            raise
    
    async def run_in_session(
        self,
        command: str,
        session_id: str,
        deployment_id: Optional[str] = None
    ) -> ExecutionResult:
        """
        Run a command in a persistent bash session.
        Environment state persists between commands in the same session.
        
        Args:
            command: Command to execute
            session_id: ID of the bash session
            deployment_id: ID of deployment to use (uses active if None)
            
        Returns:
            ExecutionResult containing stdout, stderr, exit_code, and success flag
        """
        deployment_id = deployment_id or self.active_deployment
        if not deployment_id or deployment_id not in self.deployments:
            raise ValueError(f"No deployment found with ID: {deployment_id}")
        
        if session_id not in self.sessions:
            raise ValueError(f"No session found with ID: {session_id}")
        
        # For subprocess implementation, use the same execute_command
        return await self.execute_command(command, deployment_id)
    
    async def stop_deployment(self, deployment_id: str) -> bool:
        """
        Stop and clean up a deployment.
        
        Args:
            deployment_id: ID of deployment to stop
            
        Returns:
            bool: True if successful, False otherwise
        """
        if deployment_id not in self.deployments:
            logger.warning(f"No deployment found with ID: {deployment_id}")
            return False
        
        try:
            deployment = self.deployments[deployment_id]
            
            if deployment["type"] == "docker":
                container_id = deployment["container_id"]
                
                # Stop and remove container
                stop_result = await asyncio.create_subprocess_exec(
                    "docker", "stop", container_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await stop_result.communicate()
                
                rm_result = await asyncio.create_subprocess_exec(
                    "docker", "rm", container_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await rm_result.communicate()
            
            # Clean up sessions associated with this deployment
            sessions_to_remove = [
                sid for sid, info in self.sessions.items()
                if sid.startswith(f"{deployment_id}_")
            ]
            for sid in sessions_to_remove:
                del self.sessions[sid]
            
            del self.deployments[deployment_id]
            
            if self.active_deployment == deployment_id:
                self.active_deployment = None
            
            logger.info(f"Deployment '{deployment_id}' stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop deployment: {e}")
            return False
    
    async def stop_all_deployments(self) -> bool:
        """
        Stop all active deployments.
        
        Returns:
            bool: True if all deployments stopped successfully
        """
        success = True
        for deployment_id in list(self.deployments.keys()):
            if not await self.stop_deployment(deployment_id):
                success = False
        return success
    
    def list_deployments(self) -> Dict[str, Dict[str, Any]]:
        """
        List all active deployments.
        
        Returns:
            Dictionary mapping deployment IDs to their information
        """
        result = {}
        for deployment_id, deployment in self.deployments.items():
            result[deployment_id] = {
                'type': deployment["type"],
                'image': deployment.get("image"),
                'container_id': deployment.get("container_id"),
                'is_active': deployment_id == self.active_deployment,
                'created_at': deployment.get("created_at")
            }
        
        return result
    
    def list_sessions(self) -> Dict[str, SessionInfo]:
        """
        List all active bash sessions.
        
        Returns:
            Dictionary mapping session IDs to their information
        """
        return self.sessions.copy()
    
    def get_active_deployment(self) -> Optional[str]:
        """
        Get the currently active deployment ID.
        
        Returns:
            Active deployment ID or None if no active deployment
        """
        return self.active_deployment
    
    def set_active_deployment(self, deployment_id: str) -> bool:
        """
        Set the active deployment.
        
        Args:
            deployment_id: ID of deployment to set as active
            
        Returns:
            bool: True if successful, False if deployment doesn't exist
        """
        if deployment_id in self.deployments:
            self.active_deployment = deployment_id
            return True
        return False


# Global instance for easy access
command_executor = CommandExecutor()


# Convenience functions for common operations
async def execute_bash_command(
    command: Union[str, List[str]],
    deployment_id: Optional[str] = None
) -> ExecutionResult:
    """
    Execute a bash command using the global command executor instance.
    
    Args:
        command: Command to execute
        deployment_id: Deployment to use (uses active if None)
        
    Returns:
        ExecutionResult with command output
    """
    return await command_executor.execute_command(command, deployment_id)


async def create_docker_environment(
    image: str = "python:3.12",
    deployment_id: str = "docker"
) -> str:
    """
    Create a docker environment using the global command executor instance.
    
    Args:
        image: Docker image to use
        deployment_id: Unique identifier for the deployment
        
    Returns:
        deployment_id: The ID of the created deployment
    """
    return await command_executor.create_docker_deployment(image, deployment_id)


async def create_local_environment(deployment_id: str = "local") -> str:
    """
    Create a local environment using the global command executor instance.
    
    Args:
        deployment_id: Unique identifier for the deployment
        
    Returns:
        deployment_id: The ID of the created deployment
    """
    return await command_executor.create_local_deployment(deployment_id)


async def setup_openhands_environment(deployment_id: str = "openhands") -> str:
    """
    Setup an environment compatible with OpenHands agent.
    
    Args:
        deployment_id: Unique identifier for the deployment
        
    Returns:
        deployment_id: The ID of the created deployment
    """
    return await command_executor.create_openhands_deployment(deployment_id)


async def run_workflow_analysis(
    target_agent_path: str,
    deployment_id: Optional[str] = None
) -> ExecutionResult:
    """
    Run workflow analysis on a target agent using bash commands.
    
    Args:
        target_agent_path: Path to the target agent to analyze
        deployment_id: Deployment to use for analysis
        
    Returns:
        ExecutionResult with analysis output
    """
    # First check if the path exists
    path_check = await command_executor.execute_command(f"ls -la '{target_agent_path}'", deployment_id)
    if path_check.exit_code != 0:
        # Try to find the actual path
        alt_paths = [
            f"/srv{target_agent_path}",  # In case we're in a different container
            f"{target_agent_path}",      # Original path
            ".",                         # Current directory
            "/srv/home/shiqiu/injection_agent",  # Possible alternative
        ]
        
        found_path = None
        for alt_path in alt_paths:
            check = await command_executor.execute_command(f"ls -la '{alt_path}' 2>/dev/null", deployment_id)
            if check.exit_code == 0:
                found_path = alt_path
                break
        
        if found_path:
            target_agent_path = found_path
        else:
            return ExecutionResult(
                stdout=f"Could not find target path: {target_agent_path}",
                stderr=f"Path not found: {target_agent_path}",
                exit_code=1,
                success=False
            )
    
    # Create analysis commands
    analysis_commands = [
        f"find '{target_agent_path}' -name '*.py' | head -20",
        f"ls -la '{target_agent_path}'",
        f"grep -r 'class.*Agent' '{target_agent_path}' | head -10",
        f"grep -r 'def.*execute\\|def.*run\\|def.*process' '{target_agent_path}' | head -10"
    ]
    
    results = []
    for cmd in analysis_commands:
        result = await command_executor.execute_command(cmd, deployment_id)
        results.append(f"Command: {cmd}\n{result.stdout}\n{result.stderr}\n")
    
    return ExecutionResult(
        stdout="\n".join(results),
        stderr="",
        exit_code=0,
        success=True
    )


# Alias for backward compatibility
SWEReXTool = CommandExecutor