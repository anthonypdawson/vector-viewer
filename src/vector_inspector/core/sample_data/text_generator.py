"""Text-based sample data generator for testing vector databases."""

import random
from enum import Enum
from typing import Any


class SampleDataType(Enum):
    """Types of sample data that can be generated."""

    TEXT = "text"
    MARKDOWN = "markdown"
    JSON = "json"
    SUBTITLES = "subtitles"


# Sample text corpora for generating realistic-looking data
TOPICS = [
    "artificial intelligence",
    "machine learning",
    "natural language processing",
    "computer vision",
    "robotics",
    "data science",
    "cybersecurity",
    "cloud computing",
    "quantum computing",
    "blockchain",
    "internet of things",
    "augmented reality",
    "virtual reality",
    "edge computing",
    "5G networks",
]

SENTENCES = [
    "is transforming the way we work and live",
    "has seen rapid advancement in recent years",
    "continues to evolve at an unprecedented pace",
    "offers new opportunities for innovation",
    "presents both challenges and opportunities",
    "is reshaping multiple industries simultaneously",
    "requires careful consideration of ethical implications",
    "has become increasingly accessible to developers",
    "demonstrates remarkable potential for growth",
    "remains an active area of research and development",
    "integrates seamlessly with existing technologies",
    "enables new forms of human-computer interaction",
    "provides solutions to complex real-world problems",
    "has attracted significant investment and attention",
    "will likely define the future of technology",
    "is driving productivity gains across sectors",
    "is unlocking new abilities for small teams",
    "is improving decision-making through better insights",
    "is increasingly being adopted in production systems",
    "is enabling developers to build smarter applications",
    "is creating new roles and job functions",
    "is challenging existing regulatory frameworks",
    "is lowering the barrier to entry for innovation",
    "is powering breakthroughs in data-driven research",
    "is helping automate repetitive tasks effectively",
    "is evolving alongside improvements in hardware",
    "is prompting a rethinking of traditional workflows",
    "is bridging gaps between disciplines and teams",
    "is influencing curriculum and education trends",
    "is fostering research collaborations worldwide",
]


MARKDOWN_SECTIONS = [
    (
        "Introduction",
        "This section provides an overview of the topic and its significance in modern technology.",
    ),
    (
        "Key Concepts",
        "Understanding the fundamental principles is essential for grasping the broader implications.",
    ),
    (
        "Applications",
        "Practical applications span numerous industries including healthcare, finance, and education.",
    ),
    ("Challenges", "Despite significant progress, several obstacles remain to be addressed."),
    ("Future Directions", "Ongoing research continues to push the boundaries of what's possible."),
    ("Best Practices", "Following established guidelines helps ensure successful implementation."),
    ("Case Studies", "Real-world examples demonstrate the practical value of these technologies."),
    (
        "Tools and Frameworks",
        "A variety of platforms and libraries facilitate development and deployment.",
    ),
    (
        "Performance Metrics",
        "Measuring success requires appropriate benchmarks and evaluation criteria.",
    ),
    ("Conclusion", "The field continues to evolve with promising developments on the horizon."),
]

JSON_TITLES = [
    "Getting Started Guide",
    "Advanced Techniques",
    "Performance Optimization",
    "Security Best Practices",
    "Architecture Overview",
    "API Reference",
    "Troubleshooting Common Issues",
    "Integration Patterns",
    "Design Principles",
    "Deployment Strategies",
    "Monitoring and Observability",
    "Scaling Considerations",
    "Data Management",
    "Testing Approaches",
    "Version Migration Guide",
]

JSON_DESCRIPTIONS = [
    "A comprehensive introduction to fundamental concepts and techniques.",
    "Deep dive into advanced methodologies and optimization strategies.",
    "Practical guide for improving system performance and efficiency.",
    "Essential practices for maintaining security and data protection.",
    "Detailed overview of system architecture and component interactions.",
    "Complete reference for available APIs and integration methods.",
    "Solutions to frequently encountered problems and error messages.",
    "Common patterns for integrating with external systems and services.",
    "Core principles guiding system design and implementation decisions.",
    "Strategies for deploying applications across different environments.",
    "Guidelines for effective monitoring, logging, and observability.",
    "Approaches to scaling systems to handle increased load and data.",
    "Best practices for data modeling, storage, and retrieval.",
    "Comprehensive testing strategies including unit, integration, and E2E tests.",
    "Step-by-step instructions for migrating between major versions.",
]


def generate_sample_data(
    count: int, data_type: SampleDataType = SampleDataType.TEXT, randomize: bool = True
) -> list[dict[str, Any]]:
    """Generate sample data for testing vector databases.

    Args:
        count: Number of items to generate
        data_type: Type of data to generate (text, markdown, or json)

    Returns:
        List of dictionaries with 'text' and 'metadata' keys
    """
    if isinstance(data_type, str):
        data_type = SampleDataType(data_type)

    if data_type == SampleDataType.TEXT:
        return _generate_text_samples(count, randomize=randomize)
    if data_type == SampleDataType.MARKDOWN:
        return _generate_markdown_samples(count, randomize=randomize)
    if data_type == SampleDataType.JSON:
        return _generate_json_samples(count, randomize=randomize)
    if data_type == SampleDataType.SUBTITLES:
        # For subtitles we expect a source file path in the `randomize`-position if caller
        # supplies it as a string. To keep backwards compatibility the function signature
        # remains stable; callers can instead call `generate_subtitles_from_file` directly.
        raise ValueError("Use `generate_subtitles_from_file(filepath, count, randomize=True)` to load subtitles")
    raise ValueError(f"Unknown data type: {data_type}")


def generate_subtitles_from_file(filepath: str, count: int = 0, randomize: bool = True) -> list[dict[str, Any]]:
    """Generate sample items from a subtitles file (SRT-like format).

    Args:
        filepath: Path to the subtitles (.srt) file.
        count: Maximum number of items to return. 0 means all cues.
        randomize: If True, randomly sample `count` items; otherwise deterministic order.

    Returns:
        List of sample dicts with `text` and `metadata`.
    """
    cues = _parse_srt(filepath)
    if not cues:
        return []

    total = len(cues)
    indices = list(range(total))
    if count and count < total:
        if randomize:
            indices = random.sample(indices, k=count)
        else:
            indices = indices[:count]

    samples: list[dict[str, Any]] = []
    for i, idx in enumerate(indices):
        cue = cues[idx]
        samples.append(
            {
                "text": cue["text"],
                "metadata": {
                    "source": filepath,
                    "type": "subtitles",
                    "index": i,
                    "cue_index": idx,
                    "start": cue.get("start"),
                    "end": cue.get("end"),
                },
            }
        )

    return samples


def _parse_srt(filepath: str) -> list[dict[str, str]]:
    """Basic SRT parser: returns list of cues with `text`, `start`, `end`.

    This is intentionally small and permissive — it's suitable for loading test
    subtitles files. It does not implement full SRT spec (no HTML parsing).
    """
    try:
        with open(filepath, encoding="utf-8") as fh:
            content = fh.read()
    except FileNotFoundError:
        return []

    # Split blocks by empty lines (handles Windows/Unix line endings)
    blocks = [b.strip() for b in content.splitlines()]
    # Re-join into cue blocks separated by blank lines
    cues_raw: list[str] = []
    current: list[str] = []
    for line in blocks:
        if line == "":
            if current:
                cues_raw.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        cues_raw.append("\n".join(current))

    cues: list[dict[str, str]] = []
    for block in cues_raw:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue

        # Find time line (contains -->)
        time_line = None
        for ln in lines:
            if "-->" in ln:
                time_line = ln
                break

        if not time_line:
            # Could be malformed; treat whole block as text
            text = " ".join(lines[1:]) if len(lines) > 1 else lines[0]
            cues.append({"text": text, "start": "", "end": ""})
            continue

        # text lines follow the time line
        try:
            t_idx = lines.index(time_line)
        except ValueError:
            t_idx = 0
        text_lines = lines[t_idx + 1 :]
        text = " ".join(text_lines)
        parts = time_line.split("-->")
        start = parts[0].strip()
        end = parts[1].strip() if len(parts) > 1 else ""
        cues.append({"text": text, "start": start, "end": end})

    return cues


def _generate_text_samples(count: int, randomize: bool = True) -> list[dict[str, Any]]:
    """Generate simple text samples."""
    samples = []

    for i in range(count):
        if randomize:
            topic = random.choice(TOPICS)
            sentence = random.choice(SENTENCES)
        else:
            topic = TOPICS[i % len(TOPICS)]
            sentence = SENTENCES[i % len(SENTENCES)]
        text = f"{topic.capitalize()} {sentence}."

        # Add some variety with occasional two-sentence entries
        add_second = random.random() < 0.3 if randomize else i % 10 < 3
        if add_second:
            second_sentence = random.choice(SENTENCES) if randomize else SENTENCES[(i + 1) % len(SENTENCES)]
            text += f" It {second_sentence}."

        samples.append(
            {
                "text": text,
                "metadata": {"source": "sample", "type": "text", "index": i, "topic": topic},
            }
        )

    return samples


def _generate_markdown_samples(count: int, randomize: bool = True) -> list[dict[str, Any]]:
    """Generate markdown formatted samples."""
    samples = []

    for i in range(count):
        # Use section headers as titles

        section_idx = i % len(MARKDOWN_SECTIONS)
        title, content = MARKDOWN_SECTIONS[section_idx]

        # Add a topic-specific sentence
        if randomize:
            topic = random.choice(TOPICS)
            sentence = random.choice(SENTENCES)
        else:
            topic = TOPICS[i % len(TOPICS)]
            sentence = SENTENCES[i % len(SENTENCES)]
        additional_content = f"{topic.capitalize()} {sentence}."

        markdown_text = f"## {title}\n\n{content} {additional_content}"

        # Occasionally add a list
        add_list = random.random() < 0.3 if randomize else i % 10 < 3
        if add_list:
            markdown_text += "\n\n- Key point one\n- Key point two\n- Key point three"

        samples.append(
            {
                "text": markdown_text,
                "metadata": {
                    "source": "sample",
                    "type": "markdown",
                    "index": i,
                    "section": title,
                    "topic": topic,
                },
            }
        )

    return samples


def _generate_json_samples(count: int, randomize: bool = True) -> list[dict[str, Any]]:
    """Generate JSON-like structured samples."""
    samples = []

    for i in range(count):
        title_idx = i % len(JSON_TITLES)
        desc_idx = i % len(JSON_DESCRIPTIONS)

        title = JSON_TITLES[title_idx]
        description = JSON_DESCRIPTIONS[desc_idx]
        topic = random.choice(TOPICS) if randomize else TOPICS[i % len(TOPICS)]

        # Create a text representation of structured data
        text = f"Title: {title}\n\nDescription: {description}\n\nTopic: {topic.capitalize()}"

        # Occasionally add tags
        add_tags = random.random() < 0.5 if randomize else i % 2 == 0
        if add_tags:
            if randomize:
                tags = random.sample(TOPICS, k=min(3, len(TOPICS)))
            else:
                # deterministic tag selection
                tags = [TOPICS[(i + j) % len(TOPICS)] for j in range(min(3, len(TOPICS)))]
            text += f"\n\nTags: {', '.join(tags)}"

        samples.append(
            {
                "text": text,
                "metadata": {
                    "source": "sample",
                    "type": "json",
                    "index": i,
                    "title": title,
                    "topic": topic,
                    "category": random.choice(["tutorial", "reference", "guide", "documentation"]),
                },
            }
        )

    return samples
