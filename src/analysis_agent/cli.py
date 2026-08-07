#!/usr/bin/env python3
"""Command-line interface for Analysis Agent."""

import os
import sys
import logging
import argparse

from analysis_agent import AnalysisAgent, STYLE_PROMPT_INJECTION, STYLE_TRADITIONAL, VALID_STYLES

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("analysis_agent.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def main():
    """Command-line interface for analysis agent."""
    parser = argparse.ArgumentParser(
        description="Analysis Agent - Analyze agent codebases for security vulnerabilities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze for prompt injection vulnerabilities (default)
  python cli.py --target-path /home/shiqiu/gpt-researcher --style prompt_injection

  # Analyze for traditional security vulnerabilities (RCE, XSS, CSRF, etc.)
  python cli.py --target-path /home/shiqiu/gpt-researcher --style traditional

  # Analyze with custom max turns
  python cli.py --target-path /home/shiqiu/gpt-researcher --max-turns 30

  # Analyze a containerized agent
  python cli.py --target-path /app/agent --container-name agent_container --style prompt_injection
        """
    )

    parser.add_argument(
        "--target-path",
        type=str,
        required=True,
        help="Absolute path to target agent codebase (required)"
    )

    parser.add_argument(
        "--style",
        type=str,
        choices=VALID_STYLES,
        default=STYLE_PROMPT_INJECTION,
        help=f"Analysis style: '{STYLE_PROMPT_INJECTION}' for AI agent/prompt injection analysis, "
             f"'{STYLE_TRADITIONAL}' for traditional security vulnerabilities (RCE, XSS, etc.) "
             f"(default: {STYLE_PROMPT_INJECTION})"
    )

    parser.add_argument(
        "--max-turns",
        type=int,
        default=20,
        help="Maximum number of agent turns (default: 20)"
    )

    parser.add_argument(
        "--container-name",
        type=str,
        default=None,
        help="Docker container name if target is containerized (optional)"
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)"
    )

    args = parser.parse_args()

    # Validate target path
    if not os.path.isabs(args.target_path):
        logger.error(f"Target path must be absolute: {args.target_path}")
        return 1

    # Initialize and run agent
    logger.info("=" * 80)
    logger.info("Analysis Agent Starting")
    logger.info(f"Target Path: {args.target_path}")
    logger.info(f"Style: {args.style}")
    logger.info(f"Max Turns: {args.max_turns}")
    if args.container_name:
        logger.info(f"Container: {args.container_name}")
    logger.info("=" * 80)

    try:
        agent = AnalysisAgent(
            target_path=args.target_path,
            style=args.style,
            container_name=args.container_name,
            config_path=args.config
        )

        result = agent.run(max_turns=args.max_turns)

        # Print summary
        logger.info(f"\n" + "=" * 80)
        logger.info("Analysis Complete")
        logger.info(f"Session ID: {result.get('session_id', 'N/A')}")
        logger.info(f"Events: {len(result.get('events', []))}")

        if result.get('error'):
            logger.error(f"Error: {result['error']}")
            return 1

        if result.get('final_response'):
            logger.info(f"\nFinal Response:\n{result['final_response']}")

        logger.info(f"=" * 80)
        return 0

    except Exception as e:
        logger.error(f"Failed to run analysis: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
