import os

import pytesseract

from pdf2image import convert_from_path


# ============================================================
# OCR CONFIGURATION
# ============================================================

OCR_LANGUAGE = "eng"


# ============================================================
# OCR PDF
# ============================================================

def extract_text_from_scanned_pdf(
    file_path: str
):
    """
    Convert scanned PDF pages into images and
    extract text using Tesseract OCR.

    Returns:

    {
        "text": "...",
        "pages": [
            {
                "page_number": 1,
                "text": "..."
            }
        ],
        "page_count": 2
    }
    """

    if not os.path.exists(file_path):

        raise FileNotFoundError(
            f"PDF file not found: {file_path}"
        )

    # --------------------------------------------------------
    # Convert PDF pages to images
    # --------------------------------------------------------

    images = convert_from_path(
        file_path,
        dpi=200
    )

    pages = []

    combined_text_parts = []

    # --------------------------------------------------------
    # Process every page
    # --------------------------------------------------------

    for page_number, image in enumerate(
        images,
        start=1
    ):

        # ----------------------------------------------------
        # Run OCR
        # ----------------------------------------------------

        page_text = pytesseract.image_to_string(
            image,
            lang=OCR_LANGUAGE
        )

        page_text = page_text.strip()

        # ----------------------------------------------------
        # Store page information
        # ----------------------------------------------------

        if page_text:

            pages.append({
                "page_number": page_number,
                "text": page_text
            })

            combined_text_parts.append(
                f"[Page {page_number}]\n"
                f"{page_text}"
            )

    # --------------------------------------------------------
    # Combine all OCR text
    # --------------------------------------------------------

    combined_text = "\n\n".join(
        combined_text_parts
    )

    return {
        "text": combined_text.strip(),
        "pages": pages,
        "page_count": len(images)
    }