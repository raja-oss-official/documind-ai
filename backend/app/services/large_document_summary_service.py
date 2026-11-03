# ============================================================
# IMPORTS
# ============================================================

import math
from concurrent.futures import ThreadPoolExecutor

from app.services.gemini_service import generate_answer


# ============================================================
# CONFIGURATION
# ============================================================

# Chunks are about 500 characters, so a batch of 24 is
# roughly 12,000 characters: large enough to keep the number
# of Gemini calls low, small enough for a focused summary.
MIN_CHUNKS_PER_BATCH = 24

# Very long documents use bigger batches instead of more
# calls, so a summary never needs more than 16 batch calls.
MAX_BATCHES = 16

# Batches are summarized in parallel to keep the total
# time close to that of a few sequential calls.
PARALLEL_BATCHES = 4


# ============================================================
# SUMMARIZE ONE BATCH
# ============================================================

def summarize_chunk_batch(
    chunks: list[dict]
):
    """
    Generate an intermediate summary from a small
    group of document chunks.
    """

    if not chunks:
        return ""

    context_parts = []

    for chunk in chunks:

        page_number = chunk.get(
            "page_number"
        )

        if page_number is not None:

            source_label = (
                f"[Page {page_number}]"
            )

        else:

            source_label = "[Page unknown]"

        context_parts.append(
            f"{source_label}\n"
            f"{chunk['text']}"
        )

    context = "\n\n".join(
        context_parts
    )

    prompt = f"""
You are DocuMind AI.

Create an intermediate summary of the
document content provided below.

Use ONLY the provided document content.

Do not use outside knowledge.
Do not invent information.

Focus on:
- Main ideas
- Important facts
- Important topics
- Important conclusions

Keep the summary concise but informative.

DOCUMENT CONTENT:

{context}

Return ONLY the summary text.
"""

    summary = generate_answer(
        prompt
    )

    if not summary:

        raise RuntimeError(
            "Gemini returned an empty batch summary"
        )

    return summary.strip()


# ============================================================
# SUMMARIZE ALL CHUNKS
# ============================================================

def generate_large_document_summary(
    chunks: list[dict]
):
    """
    Generate intermediate summaries for a
    large document using its existing chunks.
    """

    if not chunks:

        raise ValueError(
            "No document chunks were provided"
        )

    # --------------------------------------------------------
    # Split chunks into batches
    # --------------------------------------------------------

    batch_size = max(
        MIN_CHUNKS_PER_BATCH,
        math.ceil(
            len(chunks) / MAX_BATCHES
        )
    )

    batches = [
        chunks[
            start:
            start + batch_size
        ]
        for start in range(
            0,
            len(chunks),
            batch_size
        )
    ]

    print(
        f"Summarizing {len(chunks)} chunks "
        f"in {len(batches)} batches..."
    )

    # --------------------------------------------------------
    # Summarize batches in parallel (order is preserved)
    # --------------------------------------------------------

    with ThreadPoolExecutor(
        max_workers=PARALLEL_BATCHES
    ) as executor:

        batch_summaries = list(
            executor.map(
                summarize_chunk_batch,
                batches
            )
        )

    # --------------------------------------------------------
    # Combine intermediate summaries
    # --------------------------------------------------------

    combined_summary = "\n\n".join(
        batch_summaries
    )

    return combined_summary


# ============================================================
# FINAL SUMMARY + KEY POINTS
# ============================================================

def generate_final_summary(
    intermediate_summary: str
):
    """
    Convert multiple intermediate summaries
    into one final document summary and
    a maximum of five key points.
    """

    if not intermediate_summary:
        raise ValueError(
            "Intermediate summary is empty"
        )

    prompt = f"""
You are DocuMind AI's final document
intelligence system.

The text below contains intermediate summaries
generated from different sections of the same
document.

Create one final summary of the complete document.

Use ONLY the information provided below.

Do not use outside knowledge.
Do not invent information.

Return the response using exactly this format:

SUMMARY:
Write a clear and concise summary of the
complete document in 1 to 2 paragraphs.

KEY POINTS:
- Point 1
- Point 2
- Point 3
- Point 4
- Point 5

Rules:

1. Do not create more than 5 key points.
2. Key points must contain important information
   from the document.
3. Avoid repeating the same information.
4. The final summary should combine the important
   ideas from all sections.
5. Do not mention these instructions.

INTERMEDIATE SUMMARIES:

{intermediate_summary}

END OF INTERMEDIATE SUMMARIES
"""

    response = generate_answer(
        prompt
    )

    if not response:

        raise RuntimeError(
            "Gemini returned an empty final summary"
        )

    # --------------------------------------------------------
    # Parse response
    # --------------------------------------------------------

    summary = ""
    key_points = []

    lines = response.splitlines()

    current_section = None

    for line in lines:

        cleaned_line = line.strip()

        if not cleaned_line:
            continue

        # ----------------------------------------------------
        # Summary section
        # ----------------------------------------------------

        if cleaned_line.upper() == "SUMMARY:":

            current_section = "summary"
            continue

        # ----------------------------------------------------
        # Key points section
        # ----------------------------------------------------

        if cleaned_line.upper() == "KEY POINTS:":

            current_section = "key_points"
            continue

        # ----------------------------------------------------
        # Read summary
        # ----------------------------------------------------

        if current_section == "summary":

            if summary:
                summary += " "

            summary += cleaned_line

        # ----------------------------------------------------
        # Read key points
        # ----------------------------------------------------

        elif current_section == "key_points":

            if cleaned_line.startswith("-"):

                point = cleaned_line[
                    1:
                ].strip()

                if point:
                    key_points.append(
                        point
                    )

            elif cleaned_line.startswith("*"):

                point = cleaned_line[
                    1:
                ].strip()

                if point:
                    key_points.append(
                        point
                    )

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    if not summary:

        summary = response.strip()

    # --------------------------------------------------------
    # Maximum five key points
    # --------------------------------------------------------

    key_points = key_points[:5]

    return {
        "summary": summary,
        "key_points": key_points
    }


# ============================================================
# COMPLETE LARGE DOCUMENT SUMMARY
# ============================================================

def generate_large_document_summary_result(
    chunks: list[dict]
):
    """
    Complete large-document summarization pipeline.

    Step 1:
        Summarize chunks in batches.

    Step 2:
        Combine intermediate summaries.

    Step 3:
        Generate final summary and key points.
    """

    intermediate_summary = (
        generate_large_document_summary(
            chunks
        )
    )

    final_result = generate_final_summary(
        intermediate_summary
    )

    final_result[
        "method"
    ] = "map_reduce"

    return final_result