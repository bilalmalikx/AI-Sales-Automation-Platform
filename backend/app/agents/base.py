"""
Base agent framework for AI agents.

All agents inherit from BaseAgent and implement the standard lifecycle.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar
from uuid import uuid4

from app.core.exceptions import AgentException, LowConfidenceException
from app.core.logging import get_logger

logger = get_logger(__name__)

# Type variable for agent input/output
TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


@dataclass
class AgentConfig:
    """
    Configuration for agent execution.
    
    Attributes:
        model: LLM model name (e.g., "gpt-4", "gpt-3.5-turbo")
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum tokens in response
        timeout: Execution timeout in seconds
        max_retries: Maximum retry attempts on failure
        retry_delay: Initial delay between retries in seconds
        confidence_threshold: Minimum confidence score (0.0-1.0)
        enable_fallback: Whether to use fallback models on failure
    """
    
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0
    confidence_threshold: float = 0.7
    enable_fallback: bool = True
    
    def __post_init__(self) -> None:
        """Validate configuration values."""
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0.0 and 1.0")


@dataclass
class AgentResult(Generic[TOutput]):
    """
    Standardized agent execution result.
    
    Attributes:
        success: Whether execution succeeded
        data: Output data (if successful)
        error: Error message (if failed)
        confidence: Confidence score (0.0-1.0)
        metadata: Additional metadata (tokens, latency, etc.)
        execution_id: Unique execution ID for tracking
        agent_name: Name of the agent that produced this result
    """
    
    success: bool
    data: TOutput | None = None
    error: str | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_id: str = field(default_factory=lambda: str(uuid4()))
    agent_name: str = ""
    
    def __post_init__(self) -> None:
        """Validate result consistency."""
        if self.success and self.data is None:
            raise ValueError("Successful result must have data")
        if not self.success and self.error is None:
            raise ValueError("Failed result must have error message")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")


@dataclass
class AgentExecutionContext:
    """
    Context for agent execution with shared state.
    
    Attributes:
        execution_id: Unique execution ID
        agent_name: Name of executing agent
        config: Agent configuration
        start_time: Execution start timestamp
        metadata: Shared metadata across lifecycle
    """
    
    execution_id: str = field(default_factory=lambda: str(uuid4()))
    agent_name: str = ""
    config: AgentConfig = field(default_factory=AgentConfig)
    start_time: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def elapsed_time(self) -> float:
        """Get elapsed execution time in seconds."""
        return time.time() - self.start_time


class BaseAgent(ABC, Generic[TInput, TOutput]):
    """
    Abstract base class for all AI agents.
    
    Agents follow a standard lifecycle:
    1. prepare() - Setup and validation
    2. execute() - Main agent logic
    3. validate() - Output validation
    4. cleanup() - Resource cleanup (always called)
    
    Subclasses must implement:
    - execute_impl() - Core agent logic
    - validate_output() - Output validation
    
    Optional overrides:
    - prepare_impl() - Custom preparation
    - cleanup_impl() - Custom cleanup
    """
    
    def __init__(
        self,
        name: str,
        config: AgentConfig | None = None,
    ):
        """
        Initialize agent.
        
        Args:
            name: Agent name for logging and tracking
            config: Agent configuration (uses defaults if not provided)
        """
        self.name = name
        self.config = config or AgentConfig()
        self.logger = get_logger(f"agent.{name}")
    
    async def run(self, input_data: TInput) -> AgentResult[TOutput]:
        """
        Execute agent with full lifecycle management.
        
        Args:
            input_data: Input data for agent
            
        Returns:
            AgentResult with output or error
        """
        context = AgentExecutionContext(
            agent_name=self.name,
            config=self.config,
        )
        
        self.logger.info(
            "agent_execution_started",
            execution_id=context.execution_id,
            agent=self.name,
            config=self.config.__dict__,
        )
        
        try:
            # Lifecycle: prepare → execute → validate
            await self.prepare(input_data, context)
            output = await self.execute(input_data, context)
            validated_output = await self.validate(output, context)
            
            # Check confidence threshold
            confidence = context.metadata.get("confidence", 1.0)
            if confidence < self.config.confidence_threshold:
                raise LowConfidenceException(
                    message=f"Agent confidence {confidence:.2f} below threshold {self.config.confidence_threshold}",
                    details={"confidence": confidence, "threshold": self.config.confidence_threshold},
                )
            
            result = AgentResult(
                success=True,
                data=validated_output,
                confidence=confidence,
                metadata={
                    **context.metadata,
                    "elapsed_time": context.elapsed_time,
                },
                execution_id=context.execution_id,
                agent_name=self.name,
            )
            
            self.logger.info(
                "agent_execution_completed",
                execution_id=context.execution_id,
                agent=self.name,
                success=True,
                confidence=confidence,
                elapsed_time=context.elapsed_time,
            )
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(
                "agent_execution_failed",
                execution_id=context.execution_id,
                agent=self.name,
                error=error_msg,
                error_type=type(e).__name__,
                elapsed_time=context.elapsed_time,
            )
            
            return AgentResult(
                success=False,
                error=error_msg,
                confidence=0.0,
                metadata={
                    **context.metadata,
                    "elapsed_time": context.elapsed_time,
                    "error_type": type(e).__name__,
                },
                execution_id=context.execution_id,
                agent_name=self.name,
            )
        
        finally:
            # Always cleanup resources
            try:
                await self.cleanup(context)
            except Exception as cleanup_error:
                self.logger.warning(
                    "agent_cleanup_failed",
                    execution_id=context.execution_id,
                    agent=self.name,
                    error=str(cleanup_error),
                )
    
    async def prepare(self, input_data: TInput, context: AgentExecutionContext) -> None:
        """
        Prepare agent for execution (setup, validation).
        
        Args:
            input_data: Input data to validate
            context: Execution context
            
        Raises:
            AgentException: If preparation fails
        """
        self.logger.debug(
            "agent_prepare_started",
            execution_id=context.execution_id,
            agent=self.name,
        )
        
        try:
            await self.prepare_impl(input_data, context)
        except Exception as e:
            raise AgentException(
                message=f"Agent preparation failed: {str(e)}",
                details={"agent": self.name, "phase": "prepare"},
            ) from e
    
    async def execute(self, input_data: TInput, context: AgentExecutionContext) -> TOutput:
        """
        Execute agent main logic with retry.
        
        Args:
            input_data: Input data
            context: Execution context
            
        Returns:
            Agent output
            
        Raises:
            AgentException: If execution fails after retries
        """
        self.logger.debug(
            "agent_execute_started",
            execution_id=context.execution_id,
            agent=self.name,
        )
        
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                output = await self.execute_impl(input_data, context)
                
                if attempt > 0:
                    self.logger.info(
                        "agent_execute_retry_success",
                        execution_id=context.execution_id,
                        agent=self.name,
                        attempt=attempt + 1,
                    )
                
                return output
                
            except Exception as e:
                last_error = e
                
                if attempt < self.config.max_retries:
                    delay = self.config.retry_delay * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(
                        "agent_execute_retry",
                        execution_id=context.execution_id,
                        agent=self.name,
                        attempt=attempt + 1,
                        max_retries=self.config.max_retries,
                        error=str(e),
                        retry_delay=delay,
                    )
                    
                    import asyncio
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(
                        "agent_execute_failed_all_retries",
                        execution_id=context.execution_id,
                        agent=self.name,
                        attempts=attempt + 1,
                        error=str(e),
                    )
        
        raise AgentException(
            message=f"Agent execution failed after {self.config.max_retries + 1} attempts: {str(last_error)}",
            details={"agent": self.name, "phase": "execute", "attempts": self.config.max_retries + 1},
        ) from last_error
    
    async def validate(self, output: TOutput, context: AgentExecutionContext) -> TOutput:
        """
        Validate agent output.
        
        Args:
            output: Agent output to validate
            context: Execution context
            
        Returns:
            Validated output
            
        Raises:
            AgentException: If validation fails
        """
        self.logger.debug(
            "agent_validate_started",
            execution_id=context.execution_id,
            agent=self.name,
        )
        
        try:
            return await self.validate_output(output, context)
        except Exception as e:
            raise AgentException(
                message=f"Agent output validation failed: {str(e)}",
                details={"agent": self.name, "phase": "validate"},
            ) from e
    
    async def cleanup(self, context: AgentExecutionContext) -> None:
        """
        Cleanup resources after execution.
        
        Args:
            context: Execution context
        """
        self.logger.debug(
            "agent_cleanup_started",
            execution_id=context.execution_id,
            agent=self.name,
        )
        
        try:
            await self.cleanup_impl(context)
        except Exception as e:
            # Log but don't raise - cleanup failures shouldn't break the flow
            self.logger.warning(
                "agent_cleanup_error",
                execution_id=context.execution_id,
                agent=self.name,
                error=str(e),
            )
    
    # ── Abstract methods to implement ────────────────────────────────────────
    
    @abstractmethod
    async def execute_impl(self, input_data: TInput, context: AgentExecutionContext) -> TOutput:
        """
        Core agent logic. Must be implemented by subclasses.
        
        Args:
            input_data: Input data
            context: Execution context
            
        Returns:
            Agent output
        """
        pass
    
    @abstractmethod
    async def validate_output(self, output: TOutput, context: AgentExecutionContext) -> TOutput:
        """
        Validate agent output. Must be implemented by subclasses.
        
        Args:
            output: Agent output to validate
            context: Execution context
            
        Returns:
            Validated output (may be modified)
            
        Raises:
            ValueError: If output is invalid
        """
        pass
    
    # ── Optional hooks ────────────────────────────────────────────────────────
    
    async def prepare_impl(self, input_data: TInput, context: AgentExecutionContext) -> None:
        """
        Optional preparation hook. Override for custom setup.
        
        Args:
            input_data: Input data to prepare
            context: Execution context
        """
        pass
    
    async def cleanup_impl(self, context: AgentExecutionContext) -> None:
        """
        Optional cleanup hook. Override for custom cleanup.
        
        Args:
            context: Execution context
        """
        pass
