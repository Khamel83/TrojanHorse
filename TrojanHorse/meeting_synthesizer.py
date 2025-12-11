"""Meeting synthesis module for combining notes with transcripts."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import Config
from .llm_client import LLMClient, LLMClientError
from .models import NoteMeta, generate_note_id, write_markdown, slugify

logger = logging.getLogger(__name__)


@dataclass
class MeetingType:
    """Detected meeting type with confidence."""
    type_name: str  # "one_on_one" | "committee" | "vendor" | "default"
    confidence: float
    signals: List[str]


@dataclass
class SynthesisResult:
    """Result of meeting synthesis."""
    title: str
    meeting_type: str
    participants: List[str]
    duration_minutes: Optional[int]
    summary: str
    key_points: List[str]
    decisions: List[str]
    action_items: List[Dict[str, str]]  # {"item": str, "owner": str, "due": str}
    followups: List[str]
    user_notes: str
    raw_transcript_preview: str


class MeetingSynthesizer:
    """Synthesizes meeting notes with transcripts into structured summaries."""

    # Meeting type detection patterns
    ONE_ON_ONE_SIGNALS = [
        r'\b1[:\-]1\b', r'\bone[:\-]on[:\-]one\b', r'\bcheck[:\-]?in\b',
        r'\bcareer\b', r'\bperformance\b', r'\bfeedback\b', r'\bcoaching\b'
    ]

    COMMITTEE_SIGNALS = [
        r'\bcommittee\b', r'\bboard\b', r'\bcouncil\b', r'\bpolicy\b',
        r'\bagenda\b', r'\bmotion\b', r'\bvote\b', r'\bquorum\b',
        r'\bminutes\b', r'\bchair\b'
    ]

    VENDOR_SIGNALS = [
        r'\bvendor\b', r'\bcontract\b', r'\bproposal\b', r'\brfp\b',
        r'\bprocurement\b', r'\bsales\b', r'\bdemo\b', r'\bpricing\b',
        r'\bimplementation\b', r'\bonboarding\b'
    ]

    def __init__(self, config: Config, llm_client: Optional[LLMClient] = None):
        """
        Initialize meeting synthesizer.

        Args:
            config: TrojanHorse configuration
            llm_client: Optional LLM client (creates one if not provided)
        """
        self.config = config
        self.llm_client = llm_client or LLMClient(
            api_key=config.openrouter_api_key,
            model=config.openrouter_model
        )
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, str]:
        """Load meeting templates from templates directory."""
        templates = {}

        # Check for templates in multiple locations
        template_dirs = [
            self.config.state_dir / "templates",
            Path(__file__).parent / "templates",
        ]

        for template_dir in template_dirs:
            if template_dir.exists():
                for template_file in template_dir.glob("*.md"):
                    template_name = template_file.stem
                    if template_name not in templates:
                        templates[template_name] = template_file.read_text()
                        logger.debug(f"Loaded template: {template_name} from {template_dir}")

        # Ensure we have at least the default template
        if "default" not in templates:
            templates["default"] = self._get_fallback_default_template()

        return templates

    def _get_fallback_default_template(self) -> str:
        """Return fallback default template if no template files exist."""
        return """# {{title}}
**Date:** {{date}} | **Duration:** {{duration}}
**Participants:** {{participants}}

## Summary
{{summary}}

## Key Points Discussed
{{key_points}}

## Decisions
{{decisions}}

## Action Items
| Item | Owner | Due |
|------|-------|-----|
{{action_items_table}}

## My Notes
{{user_notes}}

---
*Synthesized by TrojanHorse*
"""

    def detect_meeting_type(self, content: str, filename: str = "") -> MeetingType:
        """
        Detect meeting type from content and filename.

        Args:
            content: Combined notes and transcript text
            filename: Original filename (may contain hints)

        Returns:
            MeetingType with detected type and confidence
        """
        combined_text = f"{filename} {content}".lower()

        scores = {
            "one_on_one": 0,
            "committee": 0,
            "vendor": 0,
        }
        signals_found = {
            "one_on_one": [],
            "committee": [],
            "vendor": [],
        }

        # Count signal matches
        for pattern in self.ONE_ON_ONE_SIGNALS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                scores["one_on_one"] += 1
                signals_found["one_on_one"].append(pattern)

        for pattern in self.COMMITTEE_SIGNALS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                scores["committee"] += 1
                signals_found["committee"].append(pattern)

        for pattern in self.VENDOR_SIGNALS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                scores["vendor"] += 1
                signals_found["vendor"].append(pattern)

        # Count participants (rough heuristic for 1:1 vs committee)
        speaker_pattern = r'speaker\s*\d+|^[A-Z][a-z]+:'
        speaker_matches = len(set(re.findall(speaker_pattern, content, re.MULTILINE)))

        if speaker_matches == 2:
            scores["one_on_one"] += 2
            signals_found["one_on_one"].append("2_speakers_detected")
        elif speaker_matches >= 4:
            scores["committee"] += 1
            signals_found["committee"].append(f"{speaker_matches}_speakers_detected")

        # Find highest score
        max_score = max(scores.values())
        if max_score == 0:
            return MeetingType(
                type_name="default",
                confidence=1.0,
                signals=["no_specific_signals_detected"]
            )

        # Get winner(s)
        winners = [k for k, v in scores.items() if v == max_score]

        if len(winners) == 1:
            winner = winners[0]
            confidence = min(max_score / 3.0, 1.0)  # Normalize to 0-1
            return MeetingType(
                type_name=winner,
                confidence=confidence,
                signals=signals_found[winner]
            )
        else:
            # Tie - use default
            return MeetingType(
                type_name="default",
                confidence=0.5,
                signals=["multiple_types_tied"]
            )

    def parse_hyprnote_export(self, path: Path) -> Tuple[str, str, Dict]:
        """
        Parse a Hyprnote export file.

        Hyprnote exports contain both notes and transcript in markdown format.

        Args:
            path: Path to Hyprnote export file

        Returns:
            Tuple of (user_notes, transcript, metadata_dict)
        """
        content = path.read_text(encoding="utf-8")

        metadata = {
            "source": "hyprnote",
            "filename": path.name,
            "file_created": datetime.fromtimestamp(path.stat().st_mtime),
        }

        # Hyprnote format typically has notes at top, transcript below
        # Look for transcript section markers
        transcript_markers = [
            "## Transcript",
            "---\n## Transcript",
            "# Transcript",
        ]

        user_notes = content
        transcript = ""

        for marker in transcript_markers:
            if marker in content:
                parts = content.split(marker, 1)
                user_notes = parts[0].strip()
                transcript = parts[1].strip() if len(parts) > 1 else ""
                break

        return user_notes, transcript, metadata

    def parse_macwhisper_transcript(self, path: Path) -> Tuple[str, Dict]:
        """
        Parse a MacWhisper transcript file.

        Args:
            path: Path to MacWhisper export file

        Returns:
            Tuple of (transcript_text, metadata_dict)
        """
        content = path.read_text(encoding="utf-8")

        metadata = {
            "source": "macwhisper",
            "filename": path.name,
            "file_created": datetime.fromtimestamp(path.stat().st_mtime),
        }

        # Extract speaker labels if present
        speaker_pattern = r'^(Speaker\s*\d+):\s*'
        speakers = list(set(re.findall(speaker_pattern, content, re.MULTILINE)))
        if speakers:
            metadata["speakers"] = speakers

        # Extract timestamps if present (format: [00:00:00] or 00:00:00)
        timestamp_pattern = r'\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?'
        timestamps = re.findall(timestamp_pattern, content)
        if timestamps and len(timestamps) >= 2:
            # Estimate duration from first and last timestamp
            try:
                first = timestamps[0]
                last = timestamps[-1]
                metadata["estimated_duration"] = last
            except Exception:
                pass

        return content, metadata

    def find_matching_backup(self, primary_path: Path) -> Optional[Path]:
        """
        Find a MacWhisper backup transcript that matches a Hyprnote export.

        Matching is done by date and approximate filename similarity.

        Args:
            primary_path: Path to primary file (e.g., Hyprnote export)

        Returns:
            Path to matching backup file, or None
        """
        # Get the date from the primary file
        primary_date = datetime.fromtimestamp(primary_path.stat().st_mtime).date()

        # Look in TranscriptsRaw directory
        transcripts_raw = self.config.vault_root / "TranscriptsRaw"
        if not transcripts_raw.exists():
            return None

        # Find files from the same day
        candidates = []
        for transcript_file in transcripts_raw.glob("*.md"):
            file_date = datetime.fromtimestamp(transcript_file.stat().st_mtime).date()
            if file_date == primary_date:
                candidates.append(transcript_file)

        for transcript_file in transcripts_raw.glob("*.txt"):
            file_date = datetime.fromtimestamp(transcript_file.stat().st_mtime).date()
            if file_date == primary_date:
                candidates.append(transcript_file)

        if not candidates:
            return None

        # If only one candidate, return it
        if len(candidates) == 1:
            return candidates[0]

        # Try to match by filename similarity
        primary_stem = primary_path.stem.lower()
        for candidate in candidates:
            candidate_stem = candidate.stem.lower()
            # Simple substring matching
            if primary_stem in candidate_stem or candidate_stem in primary_stem:
                return candidate

        # Return most recent as fallback
        return max(candidates, key=lambda p: p.stat().st_mtime)

    def _build_synthesis_prompt(
        self,
        user_notes: str,
        transcript: str,
        meeting_type: str
    ) -> List[dict]:
        """Build the LLM prompt for synthesis."""

        system_message = f"""You are an HR meeting assistant synthesizing notes for a university HR Strategy professional.

Given:
1. USER_NOTES: Brief notes typed during the meeting
2. TRANSCRIPT: Full audio transcript (may include speaker labels like "Speaker 1:", "Speaker 2:")

For this {meeting_type.replace('_', ' ')} meeting, produce a JSON object with:
- title: A descriptive meeting title (infer from content)
- participants: Array of participant names/roles (infer from speakers or mentions)
- duration_minutes: Estimated duration in minutes (null if unknown)
- summary: 2-3 sentence summary of the meeting
- key_points: Array of 3-7 key discussion points
- decisions: Array of decisions made (empty if none)
- action_items: Array of objects with "item", "owner", and "due" fields
- followups: Array of items needing follow-up before next meeting

HR-specific considerations:
- Identify any confidential HR matters
- Track commitments and verbal agreements
- Note policy implications
- Flag compliance concerns if mentioned

Return ONLY valid JSON, no extra text."""

        user_message = f"""USER_NOTES:
{user_notes}

TRANSCRIPT:
{transcript}"""

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]

    def _truncate_for_llm(self, text: str, max_chars: int = 20000) -> str:
        """Truncate text for LLM processing while preserving structure."""
        if len(text) <= max_chars:
            return text

        # Try to truncate at a sentence boundary
        truncated = text[:max_chars]
        last_period = truncated.rfind('.')
        if last_period > max_chars * 0.8:
            truncated = truncated[:last_period + 1]

        return truncated + "\n\n[... transcript truncated for processing ...]"

    def synthesize(
        self,
        user_notes: str,
        transcript: str,
        meeting_type: Optional[str] = None
    ) -> SynthesisResult:
        """
        Synthesize notes and transcript into structured meeting summary.

        Args:
            user_notes: User's typed notes during meeting
            transcript: Full transcript from audio
            meeting_type: Override meeting type detection

        Returns:
            SynthesisResult with structured meeting data
        """
        # Detect meeting type if not provided
        if not meeting_type:
            combined = f"{user_notes}\n\n{transcript}"
            detected_type = self.detect_meeting_type(combined)
            meeting_type = detected_type.type_name
            logger.info(f"Detected meeting type: {meeting_type} (confidence: {detected_type.confidence:.2f})")

        # Truncate for LLM
        truncated_transcript = self._truncate_for_llm(transcript)
        truncated_notes = self._truncate_for_llm(user_notes, 5000)

        try:
            # Build prompt and call LLM
            prompt = self._build_synthesis_prompt(truncated_notes, truncated_transcript, meeting_type)
            result_dict = self.llm_client.call_structured(prompt)

            # Parse and validate result
            return SynthesisResult(
                title=result_dict.get("title", "Untitled Meeting"),
                meeting_type=meeting_type,
                participants=result_dict.get("participants", []),
                duration_minutes=result_dict.get("duration_minutes"),
                summary=result_dict.get("summary", ""),
                key_points=result_dict.get("key_points", []),
                decisions=result_dict.get("decisions", []),
                action_items=result_dict.get("action_items", []),
                followups=result_dict.get("followups", []),
                user_notes=user_notes[:2000] if user_notes else "",
                raw_transcript_preview=transcript[:500] + "..." if len(transcript) > 500 else transcript
            )

        except LLMClientError as e:
            logger.error(f"LLM synthesis failed: {e}")
            # Return a minimal fallback result
            return self._fallback_synthesis(user_notes, transcript, meeting_type)

        except Exception as e:
            logger.error(f"Unexpected error in synthesis: {e}")
            return self._fallback_synthesis(user_notes, transcript, meeting_type)

    def _fallback_synthesis(
        self,
        user_notes: str,
        transcript: str,
        meeting_type: str
    ) -> SynthesisResult:
        """Provide fallback synthesis when LLM fails."""
        # Extract any ACTION: or DECISION: markers from notes
        action_items = []
        for line in user_notes.split('\n'):
            if 'ACTION:' in line.upper():
                item = line.split(':', 1)[-1].strip()
                action_items.append({"item": item, "owner": "TBD", "due": "TBD"})

        decisions = []
        for line in user_notes.split('\n'):
            if 'DECISION:' in line.upper():
                decisions.append(line.split(':', 1)[-1].strip())

        # Generate basic summary from first paragraph of notes
        summary_lines = [l for l in user_notes.split('\n') if l.strip()][:3]
        summary = ' '.join(summary_lines)[:300] if summary_lines else "Meeting notes captured."

        return SynthesisResult(
            title="Meeting Summary",
            meeting_type=meeting_type,
            participants=[],
            duration_minutes=None,
            summary=summary,
            key_points=[],
            decisions=decisions,
            action_items=action_items,
            followups=[],
            user_notes=user_notes[:2000] if user_notes else "",
            raw_transcript_preview=transcript[:500] + "..." if len(transcript) > 500 else transcript
        )

    def render_to_template(self, result: SynthesisResult, template_name: Optional[str] = None) -> str:
        """
        Render synthesis result using a template.

        Args:
            result: SynthesisResult to render
            template_name: Template to use (defaults to meeting_type)

        Returns:
            Rendered markdown string
        """
        template_name = template_name or result.meeting_type
        template = self.templates.get(template_name, self.templates["default"])

        # Prepare substitution values
        now = datetime.now()

        # Format participants
        participants = ", ".join(result.participants) if result.participants else "Not specified"

        # Format duration
        duration = f"{result.duration_minutes} minutes" if result.duration_minutes else "Unknown"

        # Format key points as bullet list
        key_points = "\n".join(f"- {point}" for point in result.key_points) if result.key_points else "- None captured"

        # Format decisions as bullet list
        decisions = "\n".join(f"- {decision}" for decision in result.decisions) if result.decisions else "- None recorded"

        # Format action items as table rows
        action_items_table = ""
        for item in result.action_items:
            action_items_table += f"| {item.get('item', '')} | {item.get('owner', 'TBD')} | {item.get('due', 'TBD')} |\n"
        if not action_items_table:
            action_items_table = "| No action items | - | - |\n"

        # Format followups
        followups = "\n".join(f"- {f}" for f in result.followups) if result.followups else "- None"

        # Perform substitutions
        rendered = template
        substitutions = {
            "{{title}}": result.title,
            "{{meeting_title}}": result.title,
            "{{date}}": now.strftime("%Y-%m-%d"),
            "{{duration}}": duration,
            "{{participants}}": participants,
            "{{attendees}}": participants,
            "{{summary}}": result.summary,
            "{{key_points}}": key_points,
            "{{decisions}}": decisions,
            "{{action_items}}": "\n".join(f"- {item.get('item', '')}" for item in result.action_items),
            "{{action_items_table}}": action_items_table,
            "{{followups}}": followups,
            "{{user_notes}}": result.user_notes,

            # Type-specific placeholders
            "{{participant}}": result.participants[0] if result.participants else "Unknown",
            "{{checkin_notes}}": "",
            "{{discussion_points}}": key_points,
            "{{career_notes}}": "",
            "{{agenda_summary}}": "",
            "{{discussions}}": key_points,
            "{{deferred}}": "",
            "{{next_meeting}}": "",
            "{{vendor_name}}": "",
            "{{purpose}}": result.summary,
            "{{their_commitments}}": "",
            "{{our_commitments}}": "",
            "{{next_steps}}": followups,
            "{{budget_notes}}": "",
        }

        for placeholder, value in substitutions.items():
            rendered = rendered.replace(placeholder, value)

        return rendered

    def process_hyprnote_export(self, path: Path, output_dir: Optional[Path] = None) -> Path:
        """
        Process a Hyprnote export file through the full synthesis pipeline.

        Args:
            path: Path to Hyprnote export file
            output_dir: Optional output directory (defaults to MeetingsSynthesized)

        Returns:
            Path to the synthesized output file
        """
        logger.info(f"Processing Hyprnote export: {path}")

        # Parse the Hyprnote export
        user_notes, transcript, metadata = self.parse_hyprnote_export(path)

        # Try to find matching MacWhisper backup
        backup_path = self.find_matching_backup(path)
        if backup_path:
            logger.info(f"Found matching backup transcript: {backup_path}")
            backup_transcript, backup_metadata = self.parse_macwhisper_transcript(backup_path)
            # If Hyprnote transcript is shorter, prefer backup
            if len(backup_transcript) > len(transcript) * 1.2:
                logger.info("Using MacWhisper transcript (longer)")
                transcript = backup_transcript
                metadata.update(backup_metadata)

        # Detect meeting type and synthesize
        result = self.synthesize(user_notes, transcript)

        # Render to markdown
        rendered = self.render_to_template(result)

        # Determine output path
        output_dir = output_dir or (self.config.vault_root / "MeetingsSynthesized")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        date_str = datetime.now().strftime("%Y-%m-%d")
        slug = slugify(result.title)
        output_filename = f"{date_str}_{result.meeting_type}_{slug}.md"
        output_path = output_dir / output_filename

        # Create metadata for TrojanHorse processing
        note_id = generate_note_id(path, path.stat().st_mtime)
        meta = NoteMeta(
            id=note_id,
            source="hyprnote",
            raw_type="meeting_transcript",
            class_type="work",
            category="meeting",
            project="none",
            created_at=metadata.get("file_created", datetime.now()),
            processed_at=datetime.now(),
            summary=result.summary,
            tags=[result.meeting_type, "synthesized"],
            original_path=str(path.absolute())
        )

        # Write output file
        write_markdown(output_path, meta, rendered)
        logger.info(f"Wrote synthesized meeting to: {output_path}")

        return output_path

    def process_directory(self, directory: Optional[Path] = None) -> List[Path]:
        """
        Process all new meeting files in a directory.

        Args:
            directory: Directory to scan (defaults to HyprnoteExport)

        Returns:
            List of output file paths created
        """
        directory = directory or (self.config.vault_root / "HyprnoteExport")

        if not directory.exists():
            logger.warning(f"Directory does not exist: {directory}")
            return []

        output_paths = []

        for file_path in directory.glob("*.md"):
            try:
                output_path = self.process_hyprnote_export(file_path)
                output_paths.append(output_path)
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")

        return output_paths
