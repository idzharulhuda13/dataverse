from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class TraceEvent:
    """A single step in the agent's thought process or tool usage."""
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str = "thought"  # e.g., "thought", "agent_call", "tool_call", "usage"
    agent_name: str = "orchestrator"
    detail: str = ""
    metadata: dict = field(default_factory=dict)  # For storing code, tool args, etc.

@dataclass
class SessionUsage:
    """Tracks token usage and cost for a single DataVerse session."""
    session_id: str
    api_calls: int = 0
    turns: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    image_tokens: int = 0
    trace: list[TraceEvent] = field(default_factory=list)
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.image_tokens
    
    @property
    def estimated_cost_usd(self) -> float:
        """
        Rough estimate based on Gemini 1.5 Flash pricing:
        - $0.075 / 1M input tokens
        - $0.30 / 1M output tokens
        """
        # Costs per 1M tokens
        INPUT_COST = 0.075
        OUTPUT_COST = 0.30
        
        input_cost = (self.input_tokens / 1_000_000) * INPUT_COST
        output_cost = (self.output_tokens / 1_000_000) * OUTPUT_COST
        
        # Note: image_tokens are typically part of input_tokens in usage_metadata
        return input_cost + output_cost

    def record_api_call(self, usage_metadata: dict):
        """Record usage from a single API request."""
        self.api_calls += 1
        self.input_tokens += usage_metadata.get('prompt_token_count', 0)
        self.output_tokens += usage_metadata.get('candidates_token_count', 0)
        # Note: some SDKs use 'total_token_count' or different keys.
        # We'll normalize to candidates/prompt for input/output.

    def record_turn(self):
        """Record a completed conversation turn (User + Assistant)."""
        self.turns += 1

    def record_trace(self, event_type: str, agent_name: str, detail: str, metadata: dict = None):
        """Add an event to the activity trace."""
        self.trace.append(TraceEvent(
            event_type=event_type,
            agent_name=agent_name,
            detail=detail,
            metadata=metadata or {}
        ))

    def clear_trace(self):
        """Clear trace history (e.g., at start of new request if desired)."""
        self.trace = []
