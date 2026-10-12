# ============================================================
# IMPORTS
# ============================================================

import re

from pypdf import PdfReader


# ============================================================
# CLEAN EXTRACTED TEXT
# ============================================================

def clean_extracted_text(text: str) -> str:
    """
    Clean raw text extracted from a PDF.
    """

    # Normalize line endings
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Replace tabs with spaces
    text = text.replace("\t", " ")

    # Remove spaces before punctuation
    text = re.sub(
        r"\s+([,.!?;:])",
        r"\1",
        text
    )

    # Reduce multiple spaces
    text = re.sub(
        r"[ ]{2,}",
        " ",
        text
    )

    # Reduce excessive blank lines
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    # Clean individual lines
    lines = []

    for line in text.split("\n"):
        cleaned_line = line.strip()

        if cleaned_line:
            lines.append(cleaned_line)

    return "\n".join(lines).strip()


# ============================================================
# EXTRACT TEXT FROM PDF
# ============================================================

def extract_text_from_pdf(file_path: str):
    """
    Extract text from every PDF page.

    Returns both:
    - complete document text
    - page-aware text
    """

    reader = PdfReader(file_path)

    pages = []
    combined_text_parts = []

    pages_with_text = 0

    for page_number, page in enumerate(
        reader.pages,
        start=1
    ):

        # Extract raw page text
        page_text = page.extract_text() or ""

        # Clean extracted text
        page_text = clean_extracted_text(
            page_text
        )

        # Store page information
        if page_text:

            pages_with_text += 1

            page_data = {
                "page_number": page_number,
                "text": page_text
            }

            pages.append(page_data)

            # Add page marker to combined text
            combined_text_parts.append(
                f"[Page {page_number}]\n{page_text}"
            )

    # Combine all pages
    text = "\n\n".join(
        combined_text_parts
    )

    # Final cleaning
    text = clean_extracted_text(text)

    page_count = len(reader.pages)

    # Detect image/scanned PDF
    is_scanned = (
        page_count > 0
        and pages_with_text == 0
    )

    return {
        "text": text,
        "pages": pages,
        "page_count": page_count,
        "pages_with_text": pages_with_text,
        "is_scanned": is_scanned
    }