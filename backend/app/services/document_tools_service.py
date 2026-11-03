# ============================================================
# IMPORTS
# ============================================================

from app.services.gemini_service import (
    generate_answer,
    generate_json,
)

from app.services.rag_service import (
    load_document_chunks,
    sample_chunks_evenly,
)


# ============================================================
# CONFIGURATION
# ============================================================

# Characters of document text sent to Gemini per request.
# Larger documents are sampled evenly from start to end.
TOOL_CONTEXT_CHAR_LIMIT = 30000

STUDY_TYPES = {
    "quiz",
    "flashcards"
}

MIN_STUDY_ITEMS = 3
MAX_STUDY_ITEMS = 15

FACT_CATEGORIES = (
    "date",
    "deadline",
    "amount",
    "person",
    "organization",
    "location",
    "other"
)

MAX_FACTS = 60

LANGUAGE_RULE = """
Write in the same language as the document.
Keep names, numbers, and quoted terms exactly as they
appear in the document.
"""


# ============================================================
# DOCUMENT TEXT FOR AI
# ============================================================

def document_text_for_ai(
    user_id: str,
    document_id: str,
    char_budget: int = TOOL_CONTEXT_CHAR_LIMIT
) -> str:
    """
    Return a document's text with page labels, sampled
    evenly when it is longer than the character budget.
    """

    chunks = load_document_chunks(
        user_id=user_id,
        document_id=document_id
    )

    if not chunks:
        return ""

    total_chars = sum(
        len(chunk.get("text", ""))
        for chunk in chunks
    )

    if total_chars > char_budget:

        chunks = sample_chunks_evenly(
            chunks,
            char_budget
        )

    parts = []

    for chunk in chunks:

        text = chunk.get(
            "text",
            ""
        ).strip()

        if not text:
            continue

        page_number = chunk.get(
            "page_number"
        )

        label = (
            f"[Page {page_number}]"
            if page_number is not None
            else "[Section]"
        )

        parts.append(
            f"{label}\n{text}"
        )

    return "\n\n".join(
        parts
    )


# ============================================================
# COMPARE TWO DOCUMENTS
# ============================================================

def compare_documents(
    user_id: str,
    documents: list[dict],
    focus: str | None = None
) -> str:
    """
    Compare two documents the user can read and return a
    Markdown answer: overview, similarities, differences
    (as a table), and what is only in one document.

    `documents` are document records with "_id" and
    "filename". `focus` optionally narrows the comparison,
    e.g. "pricing" or "deadlines".
    """

    if len(documents) != 2:

        raise ValueError(
            "Exactly two documents are required"
        )

    # --------------------------------------------------------
    # Each document gets half of the context budget
    # --------------------------------------------------------

    sections = []

    for label, document in zip(
        ("A", "B"),
        documents
    ):

        text = document_text_for_ai(
            user_id=user_id,
            document_id=str(
                document["_id"]
            ),
            char_budget=TOOL_CONTEXT_CHAR_LIMIT // 2
        )

        if not text:

            raise ValueError(
                f"{document.get('filename', 'A document')} "
                "has no processed text to compare"
            )

        sections.append(
            f"DOCUMENT {label}: {document.get('filename')}\n\n"
            f"{text}\n\n"
            f"END OF DOCUMENT {label}"
        )

    focus_line = (
        f"Focus the comparison on: {focus.strip()}"
        if focus and focus.strip()
        else "Compare the documents as a whole."
    )

    prompt = f"""
You are DocuMind AI. Compare the two documents below.

Use ONLY the information in the two documents.
Do not use outside knowledge and do not invent facts.
Refer to the documents by their names.

{focus_line}

Format the answer in Markdown:

### Overview
One or two sentences on what each document is about.

### Similarities
Bullet points of what both documents share.

### Differences
A Markdown table with columns: Topic | {documents[0].get('filename')} | {documents[1].get('filename')}

### Only in one document
Bullet points of important information that appears in
only one of the documents, saying which one.

### Key takeaway
One sentence.

If the documents are unrelated, say so clearly in the
overview and keep the rest short.

Reply in the same language as the user's focus text when
one is given, otherwise in the documents' language.

{sections[0]}

{sections[1]}
"""

    answer = generate_answer(
        prompt
    )

    if not answer or not answer.strip():

        raise RuntimeError(
            "Gemini returned an empty comparison"
        )

    return answer.strip()


# ============================================================
# QUIZ AND FLASHCARDS
# ============================================================

def clean_quiz_item(
    item: dict
):
    """
    Return a valid multiple-choice question, or None.

    A valid item has a question, exactly four distinct
    options, and an answer index between 0 and 3.
    """

    if not isinstance(
        item,
        dict
    ):
        return None

    question = str(
        item.get("question") or ""
    ).strip()

    options = item.get(
        "options"
    )

    answer_index = item.get(
        "answer_index"
    )

    if not question or not isinstance(
        options,
        list
    ):
        return None

    options = [
        str(option).strip()
        for option in options
        if str(option).strip()
    ]

    if len(options) != 4 or len(set(options)) != 4:
        return None

    if not isinstance(
        answer_index,
        int
    ) or not 0 <= answer_index < 4:
        return None

    return {
        "question": question,
        "options": options,
        "answer_index": answer_index,
        "explanation": str(
            item.get("explanation") or ""
        ).strip(),
        "page_number": item.get(
            "page_number"
        )
        if isinstance(item.get("page_number"), int)
        else None,
    }


def clean_flashcard(
    item: dict
):
    """
    Return a valid flashcard (front and back), or None.
    """

    if not isinstance(
        item,
        dict
    ):
        return None

    front = str(
        item.get("front") or ""
    ).strip()

    back = str(
        item.get("back") or ""
    ).strip()

    if not front or not back:
        return None

    return {
        "front": front,
        "back": back,
    }


def generate_study_set(
    user_id: str,
    document_id: str,
    study_type: str,
    count: int = 8
) -> list[dict]:
    """
    Generate a multiple-choice quiz or flashcards from one
    document. Malformed items from Gemini are dropped.
    """

    if study_type not in STUDY_TYPES:

        raise ValueError(
            "Study type must be quiz or flashcards"
        )

    count = max(
        MIN_STUDY_ITEMS,
        min(
            MAX_STUDY_ITEMS,
            int(count)
        )
    )

    text = document_text_for_ai(
        user_id=user_id,
        document_id=document_id
    )

    if not text:

        raise ValueError(
            "This document has no processed text yet"
        )

    # --------------------------------------------------------
    # Prompt
    # --------------------------------------------------------

    if study_type == "quiz":

        task = f"""
Create {count} multiple-choice questions that test
understanding of the document's most important ideas.

Return ONLY a JSON array. Each item:

{{
  "question": "…",
  "options": ["…", "…", "…", "…"],
  "answer_index": 0,
  "explanation": "One sentence on why the answer is right.",
  "page_number": 3
}}

Rules:
- Exactly four options, one correct, all plausible.
- answer_index is the 0-based index of the correct option.
- Vary the position of the correct answer.
- page_number is the page the answer comes from, or null.
"""

    else:

        task = f"""
Create {count} flashcards covering the document's key
terms, definitions, facts, and ideas.

Return ONLY a JSON array. Each item:

{{
  "front": "A term or a short question",
  "back": "The definition or answer, one or two sentences"
}}
"""

    prompt = f"""
You are DocuMind AI's study assistant.

Use ONLY the document below. Do not use outside
knowledge. Every answer must be supported by the document.

{LANGUAGE_RULE}

{task}

DOCUMENT:

{text}

END OF DOCUMENT
"""

    items = generate_json(
        prompt
    )

    if not isinstance(
        items,
        list
    ):
        items = []

    cleaner = (
        clean_quiz_item
        if study_type == "quiz"
        else clean_flashcard
    )

    cleaned = [
        result
        for result in (
            cleaner(item)
            for item in items
        )
        if result
    ]

    if not cleaned:

        raise RuntimeError(
            "Gemini did not return usable study items"
        )

    return cleaned[:count]


# ============================================================
# KEY FACTS
# ============================================================

def clean_fact(
    item: dict
):
    """
    Return a valid fact row, or None.
    """

    if not isinstance(
        item,
        dict
    ):
        return None

    value = str(
        item.get("value") or ""
    ).strip()

    if not value:
        return None

    category = str(
        item.get("category") or "other"
    ).strip().lower()

    if category not in FACT_CATEGORIES:
        category = "other"

    page_number = item.get(
        "page_number"
    )

    return {
        "category": category,
        "value": value,
        "context": str(
            item.get("context") or ""
        ).strip(),
        "page_number": page_number
        if isinstance(page_number, int)
        else None,
    }


def extract_key_facts(
    user_id: str,
    document_id: str
) -> list[dict]:
    """
    Extract dates, deadlines, amounts, people,
    organizations, and locations from one document.
    """

    text = document_text_for_ai(
        user_id=user_id,
        document_id=document_id
    )

    if not text:

        raise ValueError(
            "This document has no processed text yet"
        )

    categories = ", ".join(
        FACT_CATEGORIES
    )

    prompt = f"""
You are DocuMind AI's fact extraction system.

Extract the important facts from the document below:
dates, deadlines, amounts (money, quantities,
percentages), people, organizations, and locations.

Use ONLY the document. Do not invent or infer facts.

{LANGUAGE_RULE}

Return ONLY a JSON array (at most {MAX_FACTS} items).
Each item:

{{
  "category": "one of: {categories}",
  "value": "the fact itself, e.g. 15 March 2026 or ₹2,40,000",
  "context": "a short phrase saying what it refers to",
  "page_number": 2
}}

Use "deadline" for dates something must be done by.
page_number is the page the fact appears on, or null.
List facts in the order they appear in the document.

DOCUMENT:

{text}

END OF DOCUMENT
"""

    items = generate_json(
        prompt
    )

    if not isinstance(
        items,
        list
    ):
        items = []

    facts = [
        result
        for result in (
            clean_fact(item)
            for item in items
        )
        if result
    ]

    return facts[:MAX_FACTS]
