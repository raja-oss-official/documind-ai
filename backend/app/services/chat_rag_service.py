# ============================================================
# IMPORTS
# ============================================================

from app.services.chat_service import (
    get_chat_session,
    get_chat_messages,
    create_chat_message,
)

from app.services.rag_service import (
    retrieve_document_context,
)

from app.services.gemini_service import (
    generate_answer,
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

    Chat Session
        ↓
    Conversation History
        ↓
    Save User Message
        ↓
    Document Retrieval
        ↓
    ONE Gemini Call
        ↓
    Save Assistant Message
        ↓
    Return Answer + Sources
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

{ANSWER_GUIDELINES}

CONVERSATION HISTORY:

{history_section}

DOCUMENT CONTEXT:

{document_section}

CURRENT USER QUESTION:

{question}

ANSWER:
"""

    # ========================================================
    # ONE GEMINI CALL
    # ========================================================

    try:

        assistant_answer = generate_answer(
            prompt
        )

    except Exception as error:

        print(
            "Chat RAG Gemini generation failed:"
        )

        print(error)

        assistant_answer = (
            "I couldn't generate an answer "
            "from your documents."
        )

    # ========================================================
    # VALIDATE ANSWER
    # ========================================================

    if not assistant_answer:

        assistant_answer = (
            "I couldn't generate an answer "
            "from your documents."
        )

    assistant_answer = (
        assistant_answer.strip()
    )

    if not assistant_answer:

        assistant_answer = (
            "I couldn't generate an answer "
            "from your documents."
        )

    # ========================================================
    # SAVE ASSISTANT MESSAGE
    # ========================================================

    assistant_message = create_chat_message(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        content=assistant_answer,
        document_id=document_id,
    )

    # ========================================================
    # RETURN RESULT
    # ========================================================

    return {
        "session_id": session_id,
        "question": question,
        "answer": assistant_answer,
        "user_message": user_message,
        "assistant_message": assistant_message,
        "sources": sources,
    }