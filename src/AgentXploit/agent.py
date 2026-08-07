import os
import logging
from .agents import build_root_agent
from .config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set OpenAI API key if available
try:
    os.environ["OPENAI_API_KEY"] = settings.get_openai_api_key()
except ValueError as e:
    logger.warning(f"OpenAI API key configuration: {e}")

# Create the root agent using the new Agent-as-a-Tool architecture
root_agent = build_root_agent() 