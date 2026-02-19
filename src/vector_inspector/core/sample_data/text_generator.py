"""Text-based sample data generator for testing vector databases."""

import random
from enum import Enum
from typing import Any


class SampleDataType(Enum):
    """Types of sample data that can be generated."""

    TEXT = "text"
    MARKDOWN = "markdown"
    JSON = "json"


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
    count: int, data_type: SampleDataType = SampleDataType.TEXT
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
        return _generate_text_samples(count)
    if data_type == SampleDataType.MARKDOWN:
        return _generate_markdown_samples(count)
    if data_type == SampleDataType.JSON:
        return _generate_json_samples(count)
    raise ValueError(f"Unknown data type: {data_type}")


def _generate_text_samples(count: int) -> list[dict[str, Any]]:
    """Generate simple text samples."""
    samples = []

    for i in range(count):
        topic = random.choice(TOPICS)
        sentence = random.choice(SENTENCES)
        text = f"{topic.capitalize()} {sentence}."

        # Add some variety with occasional two-sentence entries
        if random.random() < 0.3:
            second_sentence = random.choice(SENTENCES)
            text += f" It {second_sentence}."

        samples.append(
            {
                "text": text,
                "metadata": {"source": "sample", "type": "text", "index": i, "topic": topic},
            }
        )

    return samples


def _generate_markdown_samples(count: int) -> list[dict[str, Any]]:
    """Generate markdown formatted samples."""
    samples = []

    for i in range(count):
        # Use section headers as titles
        section_idx = i % len(MARKDOWN_SECTIONS)
        title, content = MARKDOWN_SECTIONS[section_idx]

        # Add a topic-specific sentence
        topic = random.choice(TOPICS)
        sentence = random.choice(SENTENCES)
        additional_content = f"{topic.capitalize()} {sentence}."

        markdown_text = f"## {title}\n\n{content} {additional_content}"

        # Occasionally add a list
        if random.random() < 0.3:
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


def _generate_json_samples(count: int) -> list[dict[str, Any]]:
    """Generate JSON-like structured samples."""
    samples = []

    for i in range(count):
        title_idx = i % len(JSON_TITLES)
        desc_idx = i % len(JSON_DESCRIPTIONS)

        title = JSON_TITLES[title_idx]
        description = JSON_DESCRIPTIONS[desc_idx]
        topic = random.choice(TOPICS)

        # Create a text representation of structured data
        text = f"Title: {title}\n\nDescription: {description}\n\nTopic: {topic.capitalize()}"

        # Occasionally add tags
        if random.random() < 0.5:
            tags = random.sample(TOPICS, k=min(3, len(TOPICS)))
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
