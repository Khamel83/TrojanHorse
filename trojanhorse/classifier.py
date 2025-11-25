"""Classification and summarization using LLM."""

from dataclasses import dataclass
from typing import List
import logging

from .llm_client import LLMClient, LLMClientError

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Result of classifying and summarizing a text."""
    class_type: str      # "work" | "personal"
    category: str        # "email" | "slack" | "meeting" | "idea" | "task" | "log" | "other"
    project: str         # short snake_case identifier
    summary: str         # 1-3 sentences summary
    tags: List[str]      # array of short snake_case tags


class Classifier:
    """Classifier that uses LLM to categorize and summarize text."""

    def __init__(self, llm_client: LLMClient):
        """Initialize classifier with LLM client."""
        self.llm_client = llm_client

    def _build_classification_prompt(self, text: str) -> List[dict]:
        """Build the prompt for classification."""
        system_message = """You are a classifier and summarizer for a personal/work notes system.
Given arbitrary text that may be an email dump, Slack conversation, voice note, or meeting transcript, you must output a single JSON object with:
- class_type: "work" or "personal"
- category: one of ["email", "slack", "meeting", "idea", "task", "log", "other"]
- project: a short snake_case identifier (e.g. "warn_dashboard", "hub_ops", "none") inferred from context if possible
- summary: 1-3 sentences summarizing the content in plain English
- tags: an array of 1-6 short snake_case tags

Prefer "work" if the content clearly relates to employment, USC, HREC, HR, data, budgets, analytics, meetings, or similar.
Prefer "personal" otherwise.

Return ONLY valid JSON, no extra text."""

        user_message = f"Classify and summarize this text:\n\n{text}"

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]

    def _fallback_classification(self, text: str) -> ClassificationResult:
        """Provide a fallback classification when LLM fails."""
        text_lower = text.lower()

        # Simple heuristic-based fallback
        if any(keyword in text_lower for keyword in ["meeting", "sync", "standup", "review"]):
            category = "meeting"
            class_type = "work"
        elif any(keyword in text_lower for keyword in ["email", "sent", "received"]):
            category = "email"
            class_type = "work" if any(keyword in text_lower for keyword in ["work", "project", "team"]) else "personal"
        elif any(keyword in text_lower for keyword in ["slack", "channel", "message"]):
            category = "slack"
            class_type = "work"
        elif any(keyword in text_lower for keyword in ["todo", "task", "action"]):
            category = "task"
            class_type = "personal"  # Tasks are often personal unless clearly work
        else:
            category = "other"
            class_type = "personal"  # Default to personal for unknown content

        # Generate basic summary
        sentences = text.split('. ')
        summary = sentences[0] if sentences else "No content available"
        if len(summary) > 200:
            summary = summary[:200] + "..."

        return ClassificationResult(
            class_type=class_type,
            category=category,
            project="none",
            summary=summary,
            tags=[category, class_type]
        )

    def classify_and_summarize(self, text: str) -> ClassificationResult:
        """
        Classify and summarize the given text.

        Args:
            text: Text content to classify

        Returns:
            ClassificationResult with classification and summary
        """
        # Truncate very long text to avoid token limits
        if len(text) > 10000:
            logger.warning(f"Text too long ({len(text)} chars), truncating to 10000")
            text = text[:10000] + "..."

        try:
            logger.debug(f"Classifying text of length: {len(text)}")

            prompt = self._build_classification_prompt(text)
            result_dict = self.llm_client.call_structured(prompt)

            # Validate and normalize the result
            class_type = result_dict.get("class_type", "personal").lower()
            if class_type not in ["work", "personal"]:
                class_type = "personal"

            valid_categories = ["email", "slack", "meeting", "idea", "task", "log", "other"]
            category = result_dict.get("category", "other").lower()
            if category not in valid_categories:
                category = "other"

            project = result_dict.get("project", "none").lower()
            if not project or not isinstance(project, str):
                project = "none"
            # Ensure project is snake_case
            project = project.replace(" ", "_").replace("-", "_")

            summary = result_dict.get("summary", "")
            if not isinstance(summary, str):
                summary = str(summary)

            tags = result_dict.get("tags", [])
            if not isinstance(tags, list):
                tags = []

            # Normalize tags - ensure they're lowercase snake_case
            normalized_tags = []
            for tag in tags:
                if isinstance(tag, str):
                    tag = tag.lower().replace(" ", "_").replace("-", "_")
                    if tag:
                        normalized_tags.append(tag)

            # Ensure we have at least some basic tags
            if not normalized_tags:
                normalized_tags = [category]

            result = ClassificationResult(
                class_type=class_type,
                category=category,
                project=project,
                summary=summary,
                tags=normalized_tags
            )

            logger.debug(f"Classification result: {result}")
            return result

        except LLMClientError as e:
            logger.error(f"LLM classification failed: {e}")
            logger.info("Using fallback classification")
            return self._fallback_classification(text)

        except Exception as e:
            logger.error(f"Unexpected error in classification: {e}")
            logger.info("Using fallback classification")
            return self._fallback_classification(text)