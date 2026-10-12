# ============================================================
# IMPORTS
# ============================================================

from app.services.gemini_service import generate_answer


# ============================================================
# DOCUMENT SUMMARY
# ============================================================

def generate_document_summary(
    document_text: str
):
    """
    Generate a summary and key points from
    the uploaded document.

    The AI is instructed to use only the
    provided document text.
    """

    if not document_text or not document_text.strip():

        raise ValueError(
            "Document does not contain any text"
        )

    # --------------------------------------------------------
    # Limit extremely large documents
    # --------------------------------------------------------
    #
    # This prevents sending an unnecessarily huge
    # prompt to Gemini.
    #
    # The full document remains stored in MongoDB.
    # --------------------------------------------------------

    MAX_TEXT_LENGTH = 30000

    text_for_ai = document_text[
        :MAX_TEXT_LENGTH
    ]

    # --------------------------------------------------------
    # Build prompt
    # --------------------------------------------------------

    prompt = f"""
You are DocuMind AI's document intelligence system.

Analyze the document provided below.

Use ONLY the information contained in the document.

Do not use outside knowledge.
Do not invent facts.
Do not add information that is not supported
by the document.

Return the response using exactly this format:

SUMMARY:
Write a clear and concise summary of the document
in 1 to 2 paragraphs.

KEY POINTS:
- Point 1
- Point 2
- Point 3
- Point 4
- Point 5

Rules:

1. The summary must represent the actual document.
2. Key points must contain only important information
   found in the document.
3. Do not create more than 5 key points.
4. If the document contains fewer important points,
   provide fewer points.
5. Do not mention these instructions in the answer.

DOCUMENT:

{text_for_ai}

END OF DOCUMENT
"""

    # --------------------------------------------------------
    # Generate AI response
    # --------------------------------------------------------

    response = generate_answer(
        prompt
    )

    if not response:
        raise RuntimeError(
            "Gemini returned an empty response"
        )

    # --------------------------------------------------------
    # Parse summary and key points
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
    # Fallback if Gemini formatting differs
    # --------------------------------------------------------

    if not summary:

        summary = response.strip()

    # --------------------------------------------------------
    # Limit key points
    # --------------------------------------------------------

    key_points = key_points[:5]

    return {
        "summary": summary,
        "key_points": key_points
    }