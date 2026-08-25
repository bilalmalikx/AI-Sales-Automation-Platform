"""
Email Generator Agent - generates personalized cold emails.

Uses LLM to craft compelling, personalized emails based on lead/company data.
"""

from __future__ import annotations

import json

from app.agents.base import BaseAgent, AgentConfig, AgentExecutionContext
from app.agents.schemas import EmailGeneratorInput, EmailGeneratorOutput
from app.core.config import settings
from app.services.llm import LLMService


class EmailGeneratorAgent(BaseAgent[EmailGeneratorInput, EmailGeneratorOutput]):
    """
    Agent that generates personalized cold emails.
    
    Capabilities:
    - Compelling subject lines
    - Personalized email body
    - Clear call-to-action
    - Tone adjustment (professional, casual, friendly)
    - Readability optimization
    
    Personalization elements:
    - Recipient name and title
    - Company-specific references
    - Industry context
    - Recent news/events
    - Value proposition alignment
    """
    
    def __init__(self, config: AgentConfig | None = None):
        """Initialize email generator agent."""
        super().__init__(name="email_generator_agent", config=config)
        
        # Initialize LLM service with creative temperature
        self.llm_service = LLMService(
            model=settings.OPENAI_MODEL,
            temperature=0.8,  # More creative for email writing
            max_tokens=1000,
        )
    
    async def prepare_impl(
        self,
        input_data: EmailGeneratorInput,
        context: AgentExecutionContext,
    ) -> None:
        """Validate input data."""
        if not input_data.recipient_name:
            raise ValueError("Recipient name is required")
        
        if not input_data.recipient_company:
            raise ValueError("Recipient company is required")
        
        # Validate tone
        valid_tones = ["professional", "casual", "friendly"]
        if input_data.tone not in valid_tones:
            raise ValueError(f"Tone must be one of: {', '.join(valid_tones)}")
        
        # Validate max_length
        if input_data.max_length < 50 or input_data.max_length > 500:
            raise ValueError("Max length must be between 50 and 500 words")
        
        context.metadata["tone"] = input_data.tone
        context.metadata["max_length"] = input_data.max_length
    
    async def execute_impl(
        self,
        input_data: EmailGeneratorInput,
        context: AgentExecutionContext,
    ) -> EmailGeneratorOutput:
        """Generate personalized email using LLM."""
        
        # Build email generation prompt
        system_message = f"""You are an expert B2B sales copywriter. Write compelling, personalized cold emails 
that get responses. 

Tone: {input_data.tone}
Max length: {input_data.max_length} words

Provide your response in JSON format:
{{
  "subject_line": "Compelling subject (5-8 words)",
  "email_body": "Email content with proper formatting",
  "call_to_action": "Clear, specific CTA",
  "personalization_elements": ["element1", "element2"],
  "estimated_readability_score": 60-80,
  "confidence_score": 0.0-1.0
}}

Best practices:
- Start with personalized hook related to recipient/company
- Keep it concise and value-focused
- Use specific examples, not generic claims
- Clear call-to-action
- Professional but conversational
- Avoid buzzwords and hype"""
        
        # Build context for email
        context_parts = [
            f"Recipient: {input_data.recipient_name}",
            f"Company: {input_data.recipient_company}",
        ]
        
        if input_data.recipient_title:
            context_parts.append(f"Title: {input_data.recipient_title}")
        
        if input_data.company_description:
            context_parts.append(f"Company Context: {input_data.company_description}")
        
        if input_data.company_industry:
            context_parts.append(f"Industry: {input_data.company_industry}")
        
        if input_data.recent_news:
            context_parts.append(f"Recent News: {input_data.recent_news}")
        
        if input_data.product_value_prop:
            context_parts.append(f"Our Value Proposition: {input_data.product_value_prop}")
        
        context_parts.append(f"Sender: {input_data.sender_name} from {input_data.sender_company}")
        
        prompt = "Generate a personalized cold email:\n\n" + "\n".join(context_parts)
        
        # Generate email
        response, llm_metadata = await self.llm_service.generate(
            prompt=prompt,
            system_message=system_message,
        )
        
        # Parse JSON response
        try:
            email_data = json.loads(response)
        except json.JSONDecodeError:
            # Fallback: extract JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                email_data = json.loads(json_match.group())
            else:
                raise ValueError("LLM response is not valid JSON")
        
        # Build output
        output = EmailGeneratorOutput(
            subject_line=email_data.get("subject_line", ""),
            email_body=email_data.get("email_body", ""),
            call_to_action=email_data.get("call_to_action", ""),
            personalization_elements=email_data.get("personalization_elements", []),
            estimated_readability_score=email_data.get("estimated_readability_score", 70.0),
            confidence_score=email_data.get("confidence_score", 0.7),
        )
        
        # Track metadata
        context.metadata["confidence"] = output.confidence_score
        context.metadata["model_used"] = llm_metadata["model"]
        context.metadata["latency_ms"] = llm_metadata["latency_ms"]
        context.metadata["email_length_words"] = len(output.email_body.split())
        context.metadata["personalization_count"] = len(output.personalization_elements)
        
        return output
    
    async def validate_output(
        self,
        output: EmailGeneratorOutput,
        context: AgentExecutionContext,
    ) -> EmailGeneratorOutput:
        """Validate generated email."""
        
        # Validate required fields
        if not output.subject_line:
            raise ValueError("Subject line is required")
        
        if not output.email_body:
            raise ValueError("Email body is required")
        
        if not output.call_to_action:
            raise ValueError("Call-to-action is required")
        
        # Validate confidence score
        if not 0.0 <= output.confidence_score <= 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        
        # Validate readability score
        if not 0.0 <= output.estimated_readability_score <= 100.0:
            raise ValueError("Readability score must be between 0.0 and 100.0")
        
        # Check word count
        word_count = len(output.email_body.split())
        max_length = context.metadata.get("max_length", 200)
        
        if word_count > max_length * 1.2:  # Allow 20% over
            raise ValueError(f"Email too long: {word_count} words (max: {max_length})")
        
        # Must have at least one personalization element
        if not output.personalization_elements:
            raise ValueError("Email must have personalization elements")
        
        context.metadata["validation_passed"] = True
        
        return output
