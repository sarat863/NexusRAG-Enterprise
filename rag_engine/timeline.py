import re
from typing import List, Dict, Any
from pydantic import BaseModel
from .ingestion import Document, Chunk


class TimelineEvent(BaseModel):
    id: str
    vault_id: str
    doc_title: str
    section_header: str
    timeframe: str
    action_or_rule: str
    urgency_level: str  # "CRITICAL", "HIGH", "MEDIUM", "ROUTINE"
    chunk_id: str


class PolicyTimelineExtractor:
    """
    Automated Policy Timeline & SLA Deadline Extractor.
    Extracts time-critical obligations, SLA benchmarks, and recurring cycles
    across enterprise knowledge vaults.
    """

    TEMPORAL_PATTERNS = [
        (r'\b(\d+\s*(?:seconds|secs))\b', "CRITICAL"),
        (r'\b(\d+\s*(?:minutes|mins))\b', "HIGH"),
        (r'\b(?:within\s+)?(\d+\s*(?:hours|hrs))\b', "HIGH"),
        (r'\b(?:within\s+)?(\d+\s*(?:days|calendar days|business days))\b', "MEDIUM"),
        (r'\b(?:every\s+)?(\d+\s*days)\b', "MEDIUM"),
        (r'\b(weekly|monthly|annually|per month|per calendar year)\b', "ROUTINE")
    ]

    def extract_from_chunk(self, chunk: Chunk, vault_id: str) -> List[TimelineEvent]:
        """Extracts temporal milestones and rules from an individual chunk."""
        events = []
        sentences = re.split(r'(?<=[.!?])\s+', chunk.content)

        event_idx = 0
        for s in sentences:
            s_clean = s.strip()
            if not s_clean:
                continue

            for pattern, urgency in self.TEMPORAL_PATTERNS:
                match = re.search(pattern, s_clean, re.IGNORECASE)
                if match:
                    timeframe = match.group(1).strip()
                    events.append(TimelineEvent(
                        id=f"timeline_{chunk.id}_{event_idx}",
                        vault_id=vault_id,
                        doc_title=chunk.doc_title,
                        section_header=chunk.metadata.get("section_header", "General"),
                        timeframe=timeframe,
                        action_or_rule=s_clean,
                        urgency_level=urgency,
                        chunk_id=chunk.id
                    ))
                    event_idx += 1
                    break

        return events

    def extract_all_timelines(self, vaults: Dict[str, Dict[str, Any]]) -> List[TimelineEvent]:
        """Extracts timeline events across all knowledge vaults and orders by urgency."""
        all_events = []
        for vid, v in vaults.items():
            for chunk in v.get("chunks", []):
                events = self.extract_from_chunk(chunk, vid)
                all_events.extend(events)

        urgency_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "ROUTINE": 3}
        all_events.sort(key=lambda x: urgency_order.get(x.urgency_level, 4))
        return all_events
