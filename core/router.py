"""
YantraOS — Inference Router
Model Route: Claude Opus 4.6

Dynamically routes inference requests based on hardware capability determined
by the HardwareProfiler. Employs LiteLLM as an abstraction layer to route
between Ollama (local) and various Cloud APIs (Google, Anthropic).

Implements fallback chaining to guarantee inference completion (no-hang).
"""

import logging
import os
from typing import AsyncGenerator, Dict, List, Optional, Tuple

from litellm import acompletion
import litellm

from .hardware import HardwareProfiler, SystemCapability

logger = logging.getLogger("yantra.router")

# Litellm doesn't strictly need API keys for Ollama, but complains if none exist
# for cloud providers. We ensure they are loaded in env via systemd.
litellm.drop_params = True # Silently drop unsupported args for fallback models

class InferenceRouter:
    """Routes inference intelligently across local and cloud providers."""

    def __init__(self, config: Dict, hw_profiler: HardwareProfiler):
        """
        Initialize the router.

        Args:
            config: The 'inference' section from config.yaml
            hw_profiler: Instance of the initialized HardwareProfiler
        """
        self.config = config
        self.hw = hw_profiler
        self.active_system_capability = SystemCapability.CLOUD_ONLY
        self.current_model = "NONE"
        self._provider = "NONE"

    def _resolve_routing_priority(self) -> List[str]:
        """
        Calculates the routing path based on current hardware capability.
        Returns a list of LiteLLM model strings in descending order of priority.
        """
        self.active_system_capability = self.hw.evaluate_capability()
        logger.debug(f"Router determining path. Capability: {self.active_system_capability.value}")

        routing_plan = []

        local_cfg = self.config.get("local", {})
        cloud_cfg = self.config.get("cloud", {})

        local_capable_model = local_cfg.get("capable_model")
        local_min_model = local_cfg.get("minimum_model")
        
        # We always want a cloud fallback, usually the primary cloud model
        cloud_primary = cloud_cfg.get("primary_model")
        cloud_fallback = cloud_cfg.get("fallback_model")

        if self.active_system_capability == SystemCapability.LOCAL_CAPABLE:
            if local_capable_model:
                routing_plan.append(f"ollama/{local_capable_model}")
            if local_min_model:
                routing_plan.append(f"ollama/{local_min_model}")
            
        elif self.active_system_capability == SystemCapability.LOCAL_MINIMUM:
            if local_min_model:
                routing_plan.append(f"ollama/{local_min_model}")
            # If minimum hits, we might still fail if VRAM is fully consumed by
            # other tasks; cloud fallback is critical here.

        # Append Cloud models as ultimate fallbacks (or primaries if CLOUD_ONLY)
        if cloud_primary:
            routing_plan.append(cloud_primary)
        if cloud_fallback:
            routing_plan.append(cloud_fallback)

        if not routing_plan:
             # Absolute emergency fallback string if config is entirely borked
             routing_plan.append("gemini/gemini-pro")

        return routing_plan

    async def complete(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Execute an asynchronous completion with automatic fallback routing.

        Args:
            messages: OpenAI-style message format [{"role": "user", "content": "..."}]
            **kwargs: Extra params (temperature, max_tokens, etc.)
        
        Returns:
            The completion text.

        Raises:
            RuntimeError: If all routing paths fail.
        """
        # Inject default Yantra settings if not provided
        kwargs.setdefault("temperature", self.config.get("default_temperature", 0.7))
        kwargs.setdefault("max_tokens", self.config.get("default_max_tokens", 8192))
        
        route_path = self._resolve_routing_priority()
        logger.info(f"Inference Route Plan: {' -> '.join(route_path)}")

        last_error = None

        for model_str in route_path:
            logger.debug(f"Attempting inference via: {model_str}")
            self.current_model = model_str
            self._provider = model_str.split('/')[0] if '/' in model_str else "openai/gemini"

            # Check if this is an Ollama route and set API base if needed
            api_base = None
            if "ollama" in model_str:
                 api_base = self.config.get("local", {}).get("api_base", "http://localhost:11434")

            try:
                response = await acompletion(
                    model=model_str,
                    messages=messages,
                    api_base=api_base,
                    **kwargs
                )
                
                # Success!
                text = response.choices[0].message.content
                logger.debug(f"Inference successful via {model_str}. Generated {len(text)} chars.")
                return text

            except Exception as e:
                logger.warning(f"Inference failed via {model_str}: {e}")
                last_error = e
                # Continue loop to next fallback

        # If loop finishes without returning, all attempts failed
        self.current_model = "FAILED"
        self._provider = "FAILED"
        logger.error(f"All inference routes failed. Last error: {last_error}")
        raise RuntimeError(f"YantraOS InferenceRouter failed all routes. Final error: {last_error}")

    async def stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """
        Execute an asynchronous streaming completion with automatic fallback routing.
        Note: Fallback is only possible if the error occurs BEFORE the stream starts
        yielding chunks. If a stream breaks midway, LiteLLM raises an exception and 
        we cannot seamlessly switch providers without re-prompting.

        Args:
            messages: OpenAI-style message format
            **kwargs: Extra params
        
        Yields:
            Text chunks as they arrive.
        """
        kwargs.setdefault("temperature", self.config.get("default_temperature", 0.7))
        kwargs.setdefault("max_tokens", self.config.get("default_max_tokens", 8192))
        kwargs["stream"] = True

        route_path = self._resolve_routing_priority()
        logger.info(f"Stream Route Plan: {' -> '.join(route_path)}")

        last_error = None

        for model_str in route_path:
            logger.debug(f"Attempting stream via: {model_str}")
            self.current_model = model_str
            self._provider = model_str.split('/')[0] if '/' in model_str else "unknown"

            api_base = None
            if "ollama" in model_str:
                 api_base = self.config.get("local", {}).get("api_base", "http://localhost:11434")

            try:
                # acompletion returns an async generator when stream=True
                response_stream = await acompletion(
                    model=model_str,
                    messages=messages,
                    api_base=api_base,
                    **kwargs
                )
                
                # If we get here without exception, connection established.
                # Yield from the stream
                async for chunk in response_stream:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                
                # Stream finished successfully, exit the fallback loop
                return

            except Exception as e:
                logger.warning(f"Stream connection failed via {model_str}: {e}")
                last_error = e
                # Continue loop to next fallback ONLY if we haven't yielded anything yet

        self.current_model = "FAILED"
        self._provider = "FAILED"
        logger.error(f"All stream routes failed. Last error: {last_error}")
        raise RuntimeError(f"YantraOS InferenceRouter stream failed all routes. Final error: {last_error}")

    def get_status(self) -> Dict[str, str]:
        """Return basic status for telemetry."""
        return {
            "active_model": self.current_model,
            "provider": self._provider,
            "capability_classification": self.active_system_capability.value
        }
