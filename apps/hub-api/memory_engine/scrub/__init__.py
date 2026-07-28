"""Text scrubbing for proposal corpus before indexing or cloud LLM calls."""
from memory_engine.scrub.scrubber import scrub_text, ScrubResult

__all__ = ["scrub_text", "ScrubResult"]
