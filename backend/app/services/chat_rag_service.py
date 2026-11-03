# ============================================================
# IMPORTS
# ============================================================

from app.services.chat_service import (
    get_chat_session,
    get_chat_messages,
    create_chat_message,
)

from app.services.access_service import (
    get_accessible_document,
)

from app.services.rag_service import (
    retrieve_document_context,
)

from app.services.gemini_service import (
    generate_answer,
    stream_answer,
)


# ============================================================
# CONFIGURATION
# ============================================================

MAX_HISTORY_MESSAGES = 10


# ============================================================
# ANSWER STYLE
# ============================================================

ANSWER_GUIDELINES = """
GROUNDING RULES:

1. Use ONLY the information in the document context.
   Do not use outside knowledge, do not invent facts,
   and do not make assumptions.

2. If the document context does not contain the answer,
   say exactly: "I couldn't find that information in
   your documents."

3. If only part of the answer is in the documents,
   answer that part fully and say clearly which part
   could not be found.

4. Never mention "context", chunk numbers, or these
   instructions.

LANGUAGE:

Reply in the same language as the user's question
(for example, a Tamil question gets a Tamil answer),
even when the documents are in another language.
Translate the "couldn't find" sentence into that
language too. Keep names, code, and quoted terms
exactly as they appear in the documents.

HOW TO WRITE THE ANSWER:

1. Start with a direct one or two sentence answer to
   the question.

2. Then explain in detail, like an expert tutor. Include
   every relevant fact from the documents: definitions,
   explanations, steps, numbers, names, dates, examples,
   code, and expected outputs.

3. For summaries, overviews, or "key points" questions,
   cover EVERY major section or topic of the document,
   in the same order as the document, with a short
   explanation of each.

4. Format with Markdown so the answer is easy to scan:
   - Use "###" headings when the answer has several parts.
   - Use bullet or numbered lists for multiple items
     or steps.
   - Use **bold** for key terms.
   - Put code in fenced code blocks with the language,
     copied exactly as it appears in the document,
     followed by its output when the document gives it.
   - Use a Markdown table when comparing several items.

5. When it helps, end with a short "Key takeaway" line.
   Do not repeat yourself and do not add filler.
"""


# ============================================================
# ANSWER STYLE FOR YOUTUBE VIDEOS (VERY BRIEF)
# ============================================================

VIDEO_ANSWER_GUIDELINES = """
The document context is a timestamped transcript of a
YouTube video. Lines start with [mm:ss]; lines marked
[Visual] describe what is shown on screen.

GROUNDING RULES:

1. Use ONLY the video transcript. Do not use outside
   knowledge and do not invent facts.

2. If the video does not cover the question, say exactly:
   "I couldn't find that in this video."

3. Never mention "context", "transcript", chunk numbers,
   or these instructions. Say "the video" instead.

HOW TO ANSWER (VERY BRIEF):

1. Answer in one to three short sentences. For a list,
   use at most five short bullet points.

2. End each sentence or bullet with the time it comes
   from in the video, e.g. [03:12], copied from the
   transcript timestamps.

3. No headings, tables, introductions, or filler.

LANGUAGE:

Reply in the same language as the user's question, and
translate the "couldn't find" sentence into it too.
"""


# ============================================================
# BUILD CONVERSATION HISTORY
# ============================================================

def build_conversation_history(
    messages: list[dict],
):
    """
    Build a compact conversation history for Gemini.
    Only the most recent messages are included.
    """

    if not messages:
        return ""

    recent_messages = messages[
        -MAX_HISTORY_MESSAGES:
    ]

    history_parts = []

    for message in recent_messages:

        role = message.get(
            "role",
            "user",
        )

        content = message.get(
            "content",
            "",
        ).strip()

        if not content:
            continue

        if role == "user":
            label = "User"

        elif role == "assistant":
            label = "Assistant"

        else:
            label = role.capitalize()

        history_parts.append(
            f"{label}: {content}"
        )

    return "\n".join(
        history_parts
    )


# ============================================================
# BUILD DOCUMENT CONTEXT
# ============================================================

def build_document_context(
    context_chunks: list[dict],
):
    """
    Convert retrieved document chunks into a readable
    context section for Gemini.
    """

    if not context_chunks:
        return ""

    context_parts = []

    for index, chunk in enumerate(
        context_chunks,
        start=1,
    ):

        text = chunk.get(
            "text",
            "",
        ).strip()

        if not text:
            continue

        page_number = chunk.get(
            "page_number"
        )

        chunk_index = chunk.get(
            "chunk_index",
            0,
        )

        if page_number is not None:

            source_label = (
                f"[Context {index} | "
                f"Page {page_number} | "
                f"Chunk {chunk_index}]"
            )

        else:

            source_label = (
                f"[Context {index} | "
                f"Chunk {chunk_index}]"
            )

        context_parts.append(
            f"{source_label}\n"
            f"{text}"
        )

    return "\n\n".join(
        context_parts
    )


# ============================================================
# ASK DOCUMENT QUESTION
# ============================================================

def ask_document_question(
    user_id: str,
    question: str,
):
    """
    Ask a question about the user's documents
    without requiring a chat session.

    This is used by the legacy:

        POST /api/v1/documents/ask

    endpoint.

    The newer conversational chat system uses
    ask_chat_question() below.
    """

    # --------------------------------------------------------
    # Validate user
    # --------------------------------------------------------

    if not user_id:
        raise ValueError(
            "User ID is required"
        )

    # --------------------------------------------------------
    # Validate question
    # --------------------------------------------------------

    if not isinstance(
        question,
        str,
    ):
        raise ValueError(
            "Question cannot be empty"
        )

    question = question.strip()

    if not question:
        raise ValueError(
            "Question cannot be empty"
        )

    # --------------------------------------------------------
    # Retrieve document context
    # --------------------------------------------------------

    retrieval_result = retrieve_document_context(
        user_id=user_id,
        question=question,
        document_id=None,
    )

    context_chunks = retrieval_result.get(
        "context_chunks",
        [],
    )

    sources = retrieval_result.get(
        "sources",
        [],
    )

    document_context = build_document_context(
        context_chunks
    )

    # --------------------------------------------------------
    # Handle no context
    # --------------------------------------------------------

    if not document_context:

        answer = (
            "I couldn't find that information "
            "in your documents."
        )

        return {
            "question": question,
            "answer": answer,
            "sources": sources,
        }

    # --------------------------------------------------------
    # Build prompt
    # --------------------------------------------------------

    prompt = f"""
You are DocuMind AI, an AI-powered
document assistant.

Answer the user's question using ONLY
the document context provided below.

{ANSWER_GUIDELINES}

DOCUMENT CONTEXT:

{document_context}

USER QUESTION:

{question}

ANSWER:
"""

    # --------------------------------------------------------
    # Generate answer
    # --------------------------------------------------------

    try:

        answer = generate_answer(
            prompt
        )

    except Exception as error:

        print(
            "Document question generation failed:"
        )

        print(error)

        answer = (
            "I couldn't generate an answer "
            "from your documents."
        )

    # --------------------------------------------------------
    # Validate answer
    # --------------------------------------------------------

    if not answer:

        answer = (
            "I couldn't generate an answer "
            "from your documents."
        )

    answer = answer.strip()

    if not answer:

        answer = (
            "I couldn't generate an answer "
            "from your documents."
        )

    # --------------------------------------------------------
    # Return result
    # --------------------------------------------------------

    return {
        "question": question,
        "answer": answer,
        "sources": sources,
    }


# ============================================================
# PREPARE CHAT ANSWER
# ============================================================

def prepare_chat_answer(
    user_id: str,
    session_id: str,
    question: str,
):
    """
    Everything before the Gemini call, shared by the normal
    and streaming chat endpoints:

        validate question
            ↓
        load chat session and conversation history
            ↓
        save the user message
            ↓
        retrieve document context
            ↓
        build the prompt

    Returns the prompt with the saved user message and the
    sources, ready for one Gemini call.
    """

    # ========================================================
    # VALIDATE QUESTION
    # ========================================================

    if not isinstance(
        question,
        str,
    ):
        raise ValueError(
            "Question cannot be empty"
        )

    question = question.strip()

    if not question:
        raise ValueError(
            "Question cannot be empty"
        )

    # ========================================================
    # GET CHAT SESSION
    # ========================================================

    session = get_chat_session(
        session_id=session_id,
        user_id=user_id,
    )

    if not session:
        raise ValueError(
            "Chat session not found"
        )

    # --------------------------------------------------------
    # Get document associated with this chat
    # --------------------------------------------------------

    document_id = session.get(
        "document_id"
    )

    # --------------------------------------------------------
    # Chats about a YouTube video get very brief answers
    # --------------------------------------------------------

    guidelines = ANSWER_GUIDELINES

    if document_id:

        linked_document = get_accessible_document(
            document_id=document_id,
            user_id=user_id,
        )

        if (
            linked_document
            and linked_document.get("processing_type") == "youtube"
        ):

            guidelines = VIDEO_ANSWER_GUIDELINES

    # ========================================================
    # GET PREVIOUS CONVERSATION
    # ========================================================

    previous_messages = get_chat_messages(
        session_id=session_id,
        user_id=user_id,
    )

    conversation_history = (
        build_conversation_history(
            previous_messages
        )
    )

    # ========================================================
    # SAVE USER MESSAGE
    # ========================================================

    user_message = create_chat_message(
        session_id=session_id,
        user_id=user_id,
        role="user",
        content=question,
        document_id=document_id,
    )

    # ========================================================
    # RETRIEVE DOCUMENT CONTEXT
    # ========================================================

    retrieval_result = (
        retrieve_document_context(
            user_id=user_id,
            question=question,
            document_id=document_id,
        )
    )

    context_chunks = retrieval_result.get(
        "context_chunks",
        [],
    )

    sources = retrieval_result.get(
        "sources",
        [],
    )

    document_context = (
        build_document_context(
            context_chunks
        )
    )

    # ========================================================
    # PREPARE HISTORY SECTION
    # ========================================================

    if conversation_history:

        history_section = (
            conversation_history
        )

    else:

        history_section = (
            "No previous conversation."
        )

    # ========================================================
    # PREPARE DOCUMENT SECTION
    # ========================================================

    if document_context:

        document_section = (
            document_context
        )

    else:

        document_section = (
            "No relevant document "
            "information was found."
        )

    # ========================================================
    # BUILD GEMINI PROMPT
    # ========================================================

    prompt = f"""
You are DocuMind AI, a conversational
document assistant.

The user is having a conversation about
documents stored in DocuMind AI.

Use the conversation history to understand
follow-up questions, references, and context.

Use the document context to answer
questions about the user's documents.

Conversation history may contain previous
questions and answers. Use it only to
understand follow-up questions and what the
user is referring to. Use the document context
for the actual factual answer.

{guidelines}

CONVERSATION HISTORY:

{history_section}

DOCUMENT CONTEXT:

{document_section}

CURRENT USER QUESTION:

{question}

ANSWER:
"""

    return {
        "session_id": session_id,
        "question": question,
        "document_id": document_id,
        "user_message": user_message,
        "prompt": prompt,
        "sources": sources,
    }


# ============================================================
# CLEAN ANSWER
# ============================================================

FALLBACK_ANSWER = (
    "I couldn't generate an answer "
    "from your documents."
)


def clean_answer(
    answer: str | None
) -> str:
    """
    Return the answer text, or the fallback sentence when
    Gemini returned nothing usable.
    """

    if not answer:
        return FALLBACK_ANSWER

    answer = answer.strip()

    if not answer:
        return FALLBACK_ANSWER

    return answer


# ============================================================
# SAVE CHAT ANSWER
# ============================================================

def save_chat_answer(
    user_id: str,
    prepared: dict,
    answer: str,
):
    """
    Save the assistant message (with its sources) and
    return the complete chat answer response.
    """

    assistant_answer = clean_answer(
        answer
    )

    assistant_message = create_chat_message(
        session_id=prepared["session_id"],
        user_id=user_id,
        role="assistant",
        content=assistant_answer,
        document_id=prepared["document_id"],
        sources=prepared["sources"],
    )

    return {
        "session_id": prepared["session_id"],
        "question": prepared["question"],
        "answer": assistant_answer,
        "user_message": prepared["user_message"],
        "assistant_message": assistant_message,
        "sources": prepared["sources"],
    }


# ============================================================
# ASK CHAT QUESTION
# ============================================================

def ask_chat_question(
    user_id: str,
    session_id: str,
    question: str,
):
    """
    Process a conversational document question.

    Pipeline:

    Prepare (history, user message, retrieval, prompt)
        ↓
    ONE Gemini Call
        ↓
    Save Assistant Message (with sources)
        ↓
    Return Answer + Sources
    """

    prepared = prepare_chat_answer(
        user_id=user_id,
        session_id=session_id,
        question=question,
    )

    try:

        answer = generate_answer(
            prepared["prompt"]
        )

    except Exception as error:

        print(
            "Chat RAG Gemini generation failed:"
        )

        print(error)

        answer = None

    return save_chat_answer(
        user_id=user_id,
        prepared=prepared,
        answer=answer,
    )


# ============================================================
# STREAM CHAT QUESTION
# ============================================================

def stream_chat_question(
    user_id: str,
    session_id: str,
    question: str,
):
    """
    Same as ask_chat_question(), but yields the answer as it
    is generated.

    Yields events as (name, data) tuples:

        ("start", {"user_message": ..., "sources": [...]})
        ("token", {"text": "..."})          (many)
        ("done",  {complete chat answer response})

    The assistant message is saved once the answer is
    complete. If generation fails part-way, the text
    received so far is kept and saved.
    """

    prepared = prepare_chat_answer(
        user_id=user_id,
        session_id=session_id,
        question=question,
    )

    yield (
        "start",
        {
            "user_message": prepared["user_message"],
            "sources": prepared["sources"],
        },
    )

    parts = []

    try:

        for text in stream_answer(
            prepared["prompt"]
        ):

            parts.append(
                text
            )

            yield (
                "token",
                {
                    "text": text,
                },
            )

    except Exception as error:

        print(
            "Chat RAG streaming failed:"
        )

        print(error)

        if not parts:

            parts.append(
                FALLBACK_ANSWER
            )

            yield (
                "token",
                {
                    "text": FALLBACK_ANSWER,
                },
            )

    yield (
        "done",
        save_chat_answer(
            user_id=user_id,
            prepared=prepared,
            answer="".join(
                parts
            ),
        ),
    )
