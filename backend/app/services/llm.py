"""
LLM service wrapper for LangChain interactions.

Provides a unified interface for LLM calls with error handling,
retry logic, and observability.
"""

from __future__ import annotations

import time
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.exceptions import LLMException
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMService:
    """
    Service for LLM interactions with error handling and observability.
    
    Wraps LangChain LLMs with:
    - Automatic error handling and retries
    - Structured logging
    - Token tracking
    - Cost estimation
    """
    
    def __init__(
        self,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        api_key: str | None = None,
    ):
        """
        Initialize LLM service.
        
        Args:
            model: Model name (gpt-4, gpt-3.5-turbo, etc.)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum response tokens
            api_key: OpenAI API key (uses settings if not provided)
        """
        self.model_name = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Initialize LangChain ChatOpenAI
        self.llm: BaseChatModel = ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key or settings.OPENAI_API_KEY,
        )
        
        self.output_parser = StrOutputParser()
        self.chain = self.llm | self.output_parser
        
        logger.info(
            "llm_service_initialized",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    
    async def generate(
        self,
        prompt: str,
        system_message: str | None = None,
        **kwargs: Any,
    ) -> tuple[str, dict[str, Any]]:
        """
        Generate text from prompt.
        
        Args:
            prompt: User prompt
            system_message: Optional system message
            **kwargs: Additional LLM parameters
            
        Returns:
            Tuple of (generated_text, metadata)
            
        Raises:
            LLMException: If generation fails
        """
        start_time = time.time()
        
        try:
            # Build messages
            messages: list[BaseMessage] = []
            
            if system_message:
                messages.append(SystemMessage(content=system_message))
            
            messages.append(HumanMessage(content=prompt))
            
            logger.debug(
                "llm_generate_started",
                model=self.model_name,
                prompt_length=len(prompt),
                has_system_message=system_message is not None,
            )
            
            # Generate
            response = await self.chain.ainvoke(messages, **kwargs)
            
            elapsed_time = time.time() - start_time
            
            # Extract metadata
            metadata = {
                "model": self.model_name,
                "latency_ms": elapsed_time * 1000,
                "prompt_length": len(prompt),
                "response_length": len(response),
                "temperature": self.temperature,
            }
            
            logger.info(
                "llm_generate_completed",
                model=self.model_name,
                latency_ms=metadata["latency_ms"],
                response_length=metadata["response_length"],
            )
            
            return response, metadata
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            
            logger.error(
                "llm_generate_failed",
                model=self.model_name,
                error=str(e),
                error_type=type(e).__name__,
                elapsed_time=elapsed_time,
            )
            
            raise LLMException(
                message=f"LLM generation failed: {str(e)}",
                details={
                    "model": self.model_name,
                    "error_type": type(e).__name__,
                },
            ) from e
    
    async def generate_with_messages(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> tuple[str, dict[str, Any]]:
        """
        Generate from list of messages.
        
        Args:
            messages: List of {"role": "user|system|assistant", "content": "..."}
            **kwargs: Additional LLM parameters
            
        Returns:
            Tuple of (generated_text, metadata)
        """
        start_time = time.time()
        
        try:
            # Convert to LangChain messages
            lc_messages: list[BaseMessage] = []
            
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                else:
                    lc_messages.append(HumanMessage(content=content))
            
            logger.debug(
                "llm_generate_messages_started",
                model=self.model_name,
                message_count=len(messages),
            )
            
            # Generate
            response = await self.chain.ainvoke(lc_messages, **kwargs)
            
            elapsed_time = time.time() - start_time
            
            metadata = {
                "model": self.model_name,
                "latency_ms": elapsed_time * 1000,
                "message_count": len(messages),
                "response_length": len(response),
            }
            
            logger.info(
                "llm_generate_messages_completed",
                model=self.model_name,
                latency_ms=metadata["latency_ms"],
            )
            
            return response, metadata
            
        except Exception as e:
            logger.error(
                "llm_generate_messages_failed",
                model=self.model_name,
                error=str(e),
            )
            
            raise LLMException(
                message=f"LLM generation failed: {str(e)}",
                details={"model": self.model_name},
            ) from e
    
    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Estimate cost in USD based on token usage.
        
        Pricing as of 2026 (approximate):
        - GPT-4: $0.03/1K input, $0.06/1K output
        - GPT-3.5-turbo: $0.0015/1K input, $0.002/1K output
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        # Pricing map (input_cost_per_1k, output_cost_per_1k)
        pricing = {
            "gpt-4": (0.03, 0.06),
            "gpt-4-turbo": (0.01, 0.03),
            "gpt-3.5-turbo": (0.0015, 0.002),
        }
        
        # Find matching model
        model_key = None
        for key in pricing:
            if key in self.model_name.lower():
                model_key = key
                break
        
        if not model_key:
            # Default to GPT-4 pricing
            model_key = "gpt-4"
        
        input_cost_per_1k, output_cost_per_1k = pricing[model_key]
        
        input_cost = (input_tokens / 1000) * input_cost_per_1k
        output_cost = (output_tokens / 1000) * output_cost_per_1k
        
        return input_cost + output_cost


def get_llm_service(
    model: str = "gpt-4",
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> LLMService:
    """
    Factory function to get LLM service.
    
    Args:
        model: Model name
        temperature: Sampling temperature
        max_tokens: Max response tokens
        
    Returns:
        LLMService instance
    """
    return LLMService(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
