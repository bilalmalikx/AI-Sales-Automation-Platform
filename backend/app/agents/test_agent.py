"""
Simple test agent for framework validation.

This agent demonstrates the BaseAgent implementation pattern.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.base import BaseAgent, AgentExecutionContext


@dataclass
class TestAgentInput:
    """Input for test agent."""
    
    text: str
    multiplier: int = 1


@dataclass
class TestAgentOutput:
    """Output from test agent."""
    
    result: str
    length: int
    original: str


class SimpleTestAgent(BaseAgent[TestAgentInput, TestAgentOutput]):
    """
    Simple test agent that processes text input.
    
    Demonstrates:
    - Input validation in prepare_impl
    - Basic processing in execute_impl
    - Output validation in validate_output
    - Metadata tracking in context
    """
    
    async def prepare_impl(
        self,
        input_data: TestAgentInput,
        context: AgentExecutionContext,
    ) -> None:
        """Validate input data."""
        if not input_data.text:
            raise ValueError("Input text cannot be empty")
        
        if input_data.multiplier < 1:
            raise ValueError("Multiplier must be at least 1")
        
        context.metadata["input_length"] = len(input_data.text)
        context.metadata["multiplier"] = input_data.multiplier
    
    async def execute_impl(
        self,
        input_data: TestAgentInput,
        context: AgentExecutionContext,
    ) -> TestAgentOutput:
        """Process text by repeating it."""
        # Simulate processing
        result = " ".join([input_data.text] * input_data.multiplier)
        
        # Track processing metadata
        context.metadata["processing_complete"] = True
        context.metadata["confidence"] = 0.95
        
        return TestAgentOutput(
            result=result,
            length=len(result),
            original=input_data.text,
        )
    
    async def validate_output(
        self,
        output: TestAgentOutput,
        context: AgentExecutionContext,
    ) -> TestAgentOutput:
        """Validate output structure."""
        if not output.result:
            raise ValueError("Output result cannot be empty")
        
        if output.length != len(output.result):
            raise ValueError("Output length mismatch")
        
        if not output.original:
            raise ValueError("Original text must be preserved")
        
        context.metadata["output_length"] = output.length
        context.metadata["validation_passed"] = True
        
        return output
    
    async def cleanup_impl(self, context: AgentExecutionContext) -> None:
        """Log cleanup (example)."""
        self.logger.debug(
            "test_agent_cleanup",
            execution_id=context.execution_id,
            metadata=context.metadata,
        )
