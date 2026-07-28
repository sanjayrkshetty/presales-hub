"""
CopilotRunner — central orchestrator for the copilot pipeline.

Pipeline per call:
  1. Input safety validation (injection block, length cap)
  2. Prompt rendering (versioned template from registry)
  3. LLM call (provider abstraction)
  4. Output safety validation (warning-level claim detection)
  5. Grounding validation (citation + keyword overlap)
  6. Response evaluation (JSON validity + quality score)
  7. Return CopilotResponse (fully auditable)
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from copilot_engine.providers.base import LLMProvider, LLMResponse
from copilot_engine.providers.factory import get_llm_provider
from copilot_engine.prompts.registry import registry as prompt_registry
from copilot_engine.grounding.validator import validate_grounding
from copilot_engine.safety.guardrails import validate_input, validate_output
from copilot_engine.evaluators.response_eval import evaluate_response
from memory_engine.storage.base import SearchResult
from telemetry.langfuse_client import observe_pipeline, log_generation, log_span, update_observation

logger = logging.getLogger("copilot_engine.runner")


@dataclass
class CopilotResponse:
    content: str
    provider: str
    model: str
    prompt_name: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    grounding: dict
    evaluation: dict
    safety_warnings: list[str] = field(default_factory=list)
    retrieved_chunks: int = 0

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "meta": {
                "provider": self.provider,
                "model": self.model,
                "prompt_name": self.prompt_name,
                "prompt_version": self.prompt_version,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "latency_ms": round(self.latency_ms, 1),
                "retrieved_chunks": self.retrieved_chunks,
            },
            "grounding": self.grounding,
            "evaluation": self.evaluation,
            "safety_warnings": self.safety_warnings,
        }


class CopilotRunner:
    """Orchestrates the full copilot pipeline for any assistant."""

    def __init__(
        self,
        db: Session,
        provider: Optional[LLMProvider] = None,
    ):
        self._db = db
        self._provider = provider or get_llm_provider()

    async def run(
        self,
        prompt_name: str,
        prompt_vars: dict,
        user_query: str = "",
        context_chunks: list[SearchResult] = None,
        expected_json_fields: list[str] = None,
        max_tokens: int = 1500,
    ) -> CopilotResponse:
        t0 = time.monotonic()
        safety_warnings: list[str] = []
        chunks = context_chunks or []

        # 1. Input safety
        if user_query:
            input_safety = validate_input(user_query)
            if not input_safety.passed:
                logger.warning("Input safety hard-block: %s", input_safety.violations)
                # Return a blocked response immediately
                return CopilotResponse(
                    content='{"error": "Request blocked by safety guardrails."}',
                    provider=self._provider.provider_name,
                    model=self._provider.model_name,
                    prompt_name=prompt_name,
                    prompt_version="blocked",
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=(time.monotonic() - t0) * 1000,
                    grounding={"grounding_score": 0.0},
                    evaluation={"quality_score": 0.0},
                    safety_warnings=input_safety.violations,
                )
            safety_warnings.extend(input_safety.violations)
            prompt_vars = {**prompt_vars, "user_query": input_safety.sanitized_input}

        # 2. Render prompt
        prompt = prompt_registry.get(prompt_name)
        system_prompt = prompt.render_system(**prompt_vars)
        user_prompt = prompt.render_user(**prompt_vars)

        with observe_pipeline(
            "run-copilot-assistant",
            as_type="chain",
            input={"prompt_name": prompt_name, "query_len": len(user_query or "")},
            metadata={
                "prompt_name": prompt_name,
                "prompt_version": prompt.version,
                "provider": self._provider.provider_name,
                "model": self._provider.model_name,
                "retrieved_chunks": len(chunks),
            },
            tags=["copilot", prompt_name],
            feature="copilot",
        ) as lf:
            log_span(
                lf,
                name="retrieve-context",
                as_type="retriever",
                output_data={"chunk_count": len(chunks)},
            )

            # 3. LLM call
            llm_response: LLMResponse = await self._provider.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
            )
            log_generation(
                lf,
                name="generate-response",
                model=llm_response.model,
                input_text=f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}",
                output_text=llm_response.content,
                provider=llm_response.provider,
                input_tokens=llm_response.input_tokens,
                output_tokens=llm_response.output_tokens,
                latency_ms=llm_response.latency_ms,
                metadata={"prompt_name": prompt_name, "prompt_version": prompt.version},
            )

            # 4. Output safety
            output_safety = validate_output(llm_response.content)
            if output_safety.violations:
                safety_warnings.extend(output_safety.violations)
                logger.warning("Output safety warnings: %s", output_safety.violations)
            log_span(
                lf,
                name="scrub-output",
                as_type="guardrail",
                output_data={"warnings": list(output_safety.violations)},
            )

            # 5. Grounding validation
            grounding = validate_grounding(
                response=llm_response.content,
                context_chunks=chunks,
                require_citations=False,
            )
            log_span(
                lf,
                name="evaluate-grounding",
                as_type="evaluator",
                output_data=grounding.to_dict(),
            )

            # 6. Response evaluation
            evaluation = evaluate_response(
                response=llm_response.content,
                expected_json_fields=expected_json_fields,
            )
            log_span(
                lf,
                name="evaluate-quality",
                as_type="evaluator",
                output_data=evaluation.to_dict(),
                metadata={"safety_warnings": safety_warnings},
            )

            total_latency = (time.monotonic() - t0) * 1000
            update_observation(
                lf,
                output={
                    "provider": llm_response.provider,
                    "model": llm_response.model,
                    "grounding_score": grounding.grounding_score,
                    "quality_score": evaluation.quality_score,
                },
            )

            logger.info(
                "Copilot run complete",
                extra={
                    "prompt": prompt_name,
                    "provider": llm_response.provider,
                    "model": llm_response.model,
                    "input_tokens": llm_response.input_tokens,
                    "output_tokens": llm_response.output_tokens,
                    "latency_ms": round(total_latency, 1),
                    "grounding_score": grounding.grounding_score,
                    "quality_score": evaluation.quality_score,
                    "chunks": len(chunks),
                },
            )

            return CopilotResponse(
                content=llm_response.content,
                provider=llm_response.provider,
                model=llm_response.model,
                prompt_name=prompt_name,
                prompt_version=prompt.version,
                input_tokens=llm_response.input_tokens,
                output_tokens=llm_response.output_tokens,
                latency_ms=total_latency,
                grounding=grounding.to_dict(),
                evaluation=evaluation.to_dict(),
                safety_warnings=safety_warnings,
                retrieved_chunks=len(chunks),
            )
