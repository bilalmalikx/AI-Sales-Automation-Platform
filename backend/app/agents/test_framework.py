"""
Test script for agent framework.

Run with: python -m app.agents.test_framework
"""

import asyncio
from app.agents.base import AgentConfig
from app.agents.test_agent import SimpleTestAgent, TestAgentInput


async def main():
    """Test agent framework with various scenarios."""
    
    print("=" * 60)
    print("AGENT FRAMEWORK TEST")
    print("=" * 60)
    
    # Test 1: Successful execution
    print("\n[TEST 1] Successful execution")
    print("-" * 60)
    agent = SimpleTestAgent(
        name="test_agent_1",
        config=AgentConfig(
            temperature=0.7,
            confidence_threshold=0.8,
            max_retries=2,
        ),
    )
    
    input_data = TestAgentInput(text="Hello", multiplier=3)
    result = await agent.run(input_data)
    
    print(f"✅ Success: {result.success}")
    print(f"   Data: {result.data}")
    print(f"   Confidence: {result.confidence}")
    print(f"   Execution ID: {result.execution_id}")
    print(f"   Metadata: {result.metadata}")
    
    # Test 2: Low confidence (below threshold)
    print("\n[TEST 2] Low confidence scenario")
    print("-" * 60)
    agent_low_conf = SimpleTestAgent(
        name="test_agent_2",
        config=AgentConfig(
            temperature=0.7,
            confidence_threshold=0.98,  # Higher than agent's 0.95
            max_retries=1,
        ),
    )
    
    result2 = await agent_low_conf.run(input_data)
    
    print(f"❌ Success: {result2.success}")
    print(f"   Error: {result2.error}")
    print(f"   Confidence: {result2.confidence}")
    print(f"   Metadata: {result2.metadata}")
    
    # Test 3: Input validation failure
    print("\n[TEST 3] Input validation failure")
    print("-" * 60)
    agent_validation = SimpleTestAgent(
        name="test_agent_3",
        config=AgentConfig(max_retries=1),
    )
    
    invalid_input = TestAgentInput(text="", multiplier=1)  # Empty text
    result3 = await agent_validation.run(invalid_input)
    
    print(f"❌ Success: {result3.success}")
    print(f"   Error: {result3.error}")
    print(f"   Metadata: {result3.metadata}")
    
    # Test 4: Multiple executions
    print("\n[TEST 4] Multiple parallel executions")
    print("-" * 60)
    agent_parallel = SimpleTestAgent(
        name="test_agent_parallel",
        config=AgentConfig(confidence_threshold=0.5),
    )
    
    tasks = [
        agent_parallel.run(TestAgentInput(text=f"Test {i}", multiplier=2))
        for i in range(5)
    ]
    
    results = await asyncio.gather(*tasks)
    
    successful = sum(1 for r in results if r.success)
    print(f"✅ Successful: {successful}/{len(results)}")
    
    for i, r in enumerate(results):
        print(f"   Execution {i+1}: success={r.success}, confidence={r.confidence}")
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
