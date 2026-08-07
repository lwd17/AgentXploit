import argparse
import asyncio
import logging
import os
import sys
from typing import Optional

# Setup logger
logger = logging.getLogger(__name__)

from google.adk.runners import InMemoryRunner
from google.genai import types
from .agent import root_agent
from .config import settings


def setup_environment():
    """Set up environment variables and logging."""
    # Set up OpenAI API key if provided
    if not os.environ.get("OPENAI_API_KEY"):
        try:
            api_key = getattr(settings, 'DEFAULT_OPENAI_API_KEY', None)
            if api_key and api_key.startswith('sk-'):
                os.environ["OPENAI_API_KEY"] = api_key
                logging.info("OpenAI API key set from configuration")
        except Exception:
            pass

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('agentxploit.log'),
            logging.StreamHandler()
        ]
    )


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="AgentXploit - Advanced AI Security Research and Exploit Agent"
    )

    parser.add_argument(
        "command",
        choices=['static', 'dynamic'],
        help="Command to execute: static (analysis agent) or dynamic (exploit agent)"
    )

    parser.add_argument(
        "-r", "--repository",
        help="Repository path for analysis"
    )

    parser.add_argument(
        "-p", "--payload",
        help="Custom payload or task description for dynamic mode"
    )

    parser.add_argument(
        "--image",
        help="Docker image to use for deployment (default: python:3.12)"
    )

    # Get default max_files from settings
    try:
        from .config import settings
        default_max_files = getattr(settings, 'MAX_FILES', 50)
    except:
        default_max_files = 50

    parser.add_argument(
        "--max-files",
        type=int,
        default=default_max_files,
        help="Maximum number of files to read during static analysis"
    )

    # Get default max_steps from settings
    try:
        from .config import settings
        default_max_steps = getattr(settings, 'MAX_STEPS', 150)
    except:
        default_max_steps = 150

    parser.add_argument(
        "--max-steps",
        type=int,
        default=default_max_steps,
        help="Maximum number of analysis steps to execute"
    )

    parser.add_argument(
        "--analysis-mode",
        choices=['intelligent', 'simple'],
        default='intelligent',
        help="Analysis mode: intelligent (iterative) or simple (batch)"
    )

    # Get default timeout from environment or settings
    try:
        default_timeout = int(os.getenv("TIMEOUT", "600"))
    except ValueError:
        default_timeout = 600

    parser.add_argument(
        "--timeout",
        type=int,
        default=default_timeout,
        help=f"Timeout in seconds for Docker command execution (default: {default_timeout}, from env TIMEOUT)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without making actual changes"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--live-output",
        action="store_true",
        default=True,
        help="Enable real-time output streaming (default: True)"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Disable real-time output streaming (overrides --live-output)"
    )

    return parser


async def execute_command(args: argparse.Namespace) -> int:
    """Execute the specified command with given arguments."""
    try:
        # Handle dynamic command separately
        if args.command == 'dynamic':
            return await execute_dynamic_command(args)

        # Handle static command
        elif args.command == 'static':
            if not args.repository:
                logging.error("Repository path required for static command")
                return 1

            # Use analysis agent for static analysis
            logging.info(f"Starting analysis agent static analysis of: {args.repository}")
            try:
                from .agents.analysis_agent import AnalysisAgent

                max_files = getattr(args, 'max_files', getattr(settings, 'MAX_FILES', 50))
                max_steps = getattr(args, 'max_steps', getattr(settings, 'MAX_STEPS', 150))
                logging.info(f"Analysis will process up to {max_files} files and {max_steps} steps")

                analyzer = AnalysisAgent(args.repository)
                result = analyzer.analyze(
                    max_steps=max_steps,
                    save_results=True,
                    focus=None  # Let LLM generate dynamic focus
                )

                logging.info("Static analysis completed successfully")
                logging.info(f"Result: Analysis completed with {result['execution_summary']['steps_completed']} steps")
                return 0

            except Exception as e:
                raise
                logging.error(f"Static analysis failed: {e}")
                return 1

        else:
            logging.error(f"Unknown command: {args.command}")
            return 1

    except Exception as e:
        raise
        logging.error(f"Error executing command: {e}")
        if args.verbose:
            logging.exception("Full error details:")
        return 1


async def execute_dynamic_command(args: argparse.Namespace) -> int:
    """Execute dynamic command with interactive Docker setup."""
    try:
        if not args.repository:
            logging.error("Repository path required for dynamic command (-r)")
            return 1

        logging.info(f"Starting dynamic analysis for: {args.repository}")

        print("\nAgentXploit Unified Workflow Analysis")
        print("=" * 40)
        print("4-Phase Workflow:")
        print("  Phase 1: Docker Setup (from .env)")
        print("  Phase 2: Run Agent (no injection)")
        print("  Phase 3: Generate Injection")
        print("  Phase 4: Rerun with Injection")
        print("=" * 40)

        # Import the unified workflow system
        from .agents.exploit_agent import execute_workflow_analysis

        # Configuration
        target_path = args.repository

        # 确定是否启用实时输出
        live_output = args.live_output and not args.quiet

        print(f"\nConfiguration:")
        print(f"  Target path: {target_path}")
        print(f"  Mode: Unified 4-Phase Workflow")
        print(f"  Timeout: {args.timeout} seconds")
        print(f"  Live output: {'Enabled' if live_output else 'Disabled'}")

        # Handle dry-run mode
        if args.dry_run:
            print("\n[DRY RUN] Would proceed with unified workflow analysis")
            return 0

        print(f"\nStarting workflow execution...")

        # Execute unified workflow (auto-detects workflow type from path)
        result = await execute_workflow_analysis(
            target_path=target_path,
            workflow_type="auto",
            timeout=args.timeout
        )

        # Display results
        if result["success"]:
            print(f"\n✓ Unified workflow completed successfully!")
            print(f"\nExecution Summary:")
            print(f"  - Workflow ID: {result.get('workflow_id', 'N/A')}")
            print(f"  - Workflow type: {result.get('workflow_type', 'auto')}")
            print(f"  - Target path: {result['target_path']}")
            print(f"  - Deployment ID: {result.get('deployment_id', 'N/A')}")

            # Phase results
            phase_results = result.get('phase_results', {})
            print(f"\nPhase Results:")
            for phase, phase_result in phase_results.items():
                status = "✓" if phase_result.get('success', False) else "✗"
                print(f"  {status} {phase.upper()}")
                if phase == 'phase2' and 'report_path' in phase_result:
                    print(f"     Report: {phase_result['report_path']}")
                elif phase == 'phase3' and 'workflow_type' in phase_result:
                    print(f"     Type: {phase_result['workflow_type']}")

            # Injection success
            injection_successful = result.get('injection_successful', False)
            print(f"\nInjection Analysis:")
            print(f"  - Injection successful: {'YES' if injection_successful else 'NO'}")

            # Detailed results
            detailed = result.get('detailed_results', {})
            if detailed:
                print(f"\nDetailed Analysis:")
                if 'injection_points' in detailed:
                    for i, point in enumerate(detailed['injection_points'][:3], 1):
                        point_type = point.get('type', 'unknown')
                        risk = point.get('risk', 'unknown')
                        print(f"  {i}. {point_type.title()} injection (risk: {risk})")
                        if 'description' in point:
                            print(f"     {point['description'][:80]}...")

            print(f"\n📁 Analysis results available in logs")

        else:
            error_msg = result.get('error', 'Unknown error')
            print(f"\n❌ LLM-driven dynamic analysis failed: {error_msg}")
            return 1

        return 0

    except Exception as e:
        logging.error(f"Dynamic command execution failed: {e}")
        if args.verbose:
            logging.exception("Full error details:")
        return 1


def main() -> int:
    """Main entry point for the CLI."""
    setup_environment()

    parser = create_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        return asyncio.run(execute_command(args))
    except KeyboardInterrupt:
        logging.info("Operation cancelled by user")
        return 130
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())