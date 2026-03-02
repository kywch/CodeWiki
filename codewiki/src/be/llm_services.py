"""
LLM service factory for creating configured LLM clients.
"""

from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIModelSettings
from pydantic_ai.models.fallback import FallbackModel
from openai import OpenAI

from codewiki.src.config import Config


def create_main_model(config: Config) -> OpenAIModel:
    """Create the main LLM model from configuration."""
    return OpenAIModel(
        model_name=config.main_model,
        provider=OpenAIProvider(base_url=config.llm_base_url, api_key=config.llm_api_key),
        settings=OpenAIModelSettings(temperature=0.0, max_tokens=config.max_tokens),
    )


def create_fallback_model(config: Config) -> OpenAIModel:
    """Create the fallback LLM model from configuration."""
    return OpenAIModel(
        model_name=config.fallback_model,
        provider=OpenAIProvider(base_url=config.llm_base_url, api_key=config.llm_api_key),
        settings=OpenAIModelSettings(temperature=0.0, max_tokens=config.max_tokens),
    )


def create_fallback_models(config: Config) -> FallbackModel:
    """Create fallback models chain from configuration."""
    main = create_main_model(config)
    fallback = create_fallback_model(config)
    return FallbackModel(main, fallback)


def create_openai_client(config: Config) -> OpenAI:
    """Create OpenAI client from configuration."""
    return OpenAI(base_url=config.llm_base_url, api_key=config.llm_api_key)


def call_llm(prompt: str, config: Config, model: str = None, temperature: float = 0.0) -> str:
    """
    Call LLM with the given prompt.

    Args:
        prompt: The prompt to send
        config: Configuration containing LLM settings
        model: Model name (defaults to config.main_model)
        temperature: Temperature setting

    Returns:
        LLM response text
    """
    import subprocess
    import logging
    import tempfile
    import os

    logger = logging.getLogger(__name__)

    if model is None:
        model = config.main_model

    if getattr(config, "use_gemini_cli", False):
        prompt_bytes = len(prompt.encode("utf-8"))
        # Sandbox relaunch re-passes stdin buffer as args; >100KB triggers E2BIG
        STDIN_SAFE_LIMIT = 100_000

        if prompt_bytes > STDIN_SAFE_LIMIT:
            logger.info(f"Prompt is {prompt_bytes:,} bytes — writing to temp file to avoid E2BIG")
            fd, temp_path = tempfile.mkstemp(suffix=".md", prefix="codewiki_prompt_")
            try:
                with os.fdopen(fd, "w") as f:
                    f.write(prompt)
                cmd = [
                    "gemini",
                    "-y",
                    "-p",
                    f"Read the ENTIRE contents of {temp_path}. "
                    f"That file contains your complete instructions and all source code context. "
                    f"Follow every instruction in that file exactly.",
                ]
                if model:
                    cmd.extend(["-m", model])
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                return result.stdout.strip()
            except subprocess.CalledProcessError as e:
                logger.error(f"Gemini CLI call failed with return code {e.returncode}")
                logger.error(f"stderr: {e.stderr}")
                raise e
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        else:
            cmd = ["gemini", "-y", "-p", ""]
            if model:
                cmd.extend(["-m", model])
            try:
                result = subprocess.run(
                    cmd, input=prompt, capture_output=True, text=True, check=True
                )
                return result.stdout.strip()
            except subprocess.CalledProcessError as e:
                logger.error(f"Gemini CLI call failed with return code {e.returncode}")
                logger.error(f"stderr: {e.stderr}")
                raise e

    client = create_openai_client(config)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=config.max_tokens,
    )
    return response.choices[0].message.content
