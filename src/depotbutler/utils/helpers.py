import re
import unicodedata

from depotbutler.models import Edition


def create_filename(edition: Edition) -> str:
    """
    Create a safe filename for the edition PDF.
    Examples:
        - "DER AKTIONÄR 05/25" -> "2025-XX-XX_Der-Aktionär_05-25.pdf"
        - "DER AKTIONÄR EDITION 01/26" -> "2025-XX-XX_Der-Aktionär-Edition_01-26.pdf"
        - "DER AKTIONÄR 52/25 + 01/26" -> "2025-12-17_Der-Aktionär_52-25+01-26.pdf"

    Args:
        edition: Edition object with title and publication_date

    Returns:
        Formatted filename: {date}_{Title-Cased-Name}_{issue}.pdf
    """

    # Title case the title
    title_formatted = edition.title.title()

    # Replace % with -Prozent for URL-safe filenames
    title_formatted = title_formatted.replace("%", "-Prozent")

    # Match the pattern: publication name followed by issue number(s)
    # Issue pattern: digits/digits, optionally followed by space+space+digits/digits
    match = re.match(r"^(.+?)\s+(\d+/\d+(?:\s*\+\s*\d+/\d+)?)$", title_formatted)

    if match:
        publication_name = match.group(1)
        issue_numbers = match.group(2)

        # Replace spaces with hyphens in publication name
        publication_name = publication_name.replace(" ", "-")

        # Clean up issue numbers: remove spaces around +
        issue_numbers = re.sub(r"\s*\+\s*", "+", issue_numbers)

        # Replace slashes with hyphens in issue numbers
        issue_numbers = issue_numbers.replace("/", "-")

        # Combine: publication_issue
        title_formatted = f"{publication_name}_{issue_numbers}"
    else:
        # Fallback: use the old logic if pattern doesn't match
        last_space_idx = title_formatted.rfind(" ")
        if last_space_idx != -1:
            title_formatted = (
                title_formatted[:last_space_idx]
                + "###"
                + title_formatted[last_space_idx + 1 :]
            )
        title_formatted = title_formatted.replace(" ", "-")
        title_formatted = title_formatted.replace("###", "_")
        title_formatted = title_formatted.replace("/", "-")

    # Combine with date prefix
    filename = f"{edition.publication_date}_{title_formatted}.pdf"

    return filename


def normalize_edition_key(date: str, title: str) -> str:
    """
    Generate a normalized edition key for consistent database lookups.

    Uses lowercase, ASCII-only characters with hyphens and underscores.
    This ensures that the same edition is recognized regardless of source
    (daily job vs OneDrive import).

    Examples:
        - "2025-11-05", "DER AKTIONÄR 05/25" -> "2025-11-05_der-aktionaer_05-25"
        - "2019-05-02", "Megatrend Folger 18/2019" -> "2019-05-02_megatrend-folger_18-2019"
        - "2024-03-21", "Die 800% Strategie 12/2024" -> "2024-03-21_die-800-prozent-strategie_12-2024"

    Args:
        date: Publication date in YYYY-MM-DD format
        title: Edition title (any format)

    Returns:
        Normalized edition key: {date}_{normalized_title}
    """
    # Replace German umlauts with ASCII equivalents before lowercasing
    normalized = (
        title.replace("Ä", "Ae")
        .replace("ä", "ae")
        .replace("Ö", "Oe")
        .replace("ö", "oe")
        .replace("Ü", "Ue")
        .replace("ü", "ue")
        .replace("ß", "ss")
        .replace("%", "-Prozent")
    )

    # Convert to lowercase
    normalized = normalized.lower()

    # Preserve last space as underscore (separates title from edition number)
    # Find last space before digits (e.g., "megatrend folger 01/2025")
    last_space_idx = -1
    for i in range(len(normalized) - 1, -1, -1):
        if (
            normalized[i] == " "
            and i + 1 < len(normalized)
            and normalized[i + 1].isdigit()
        ):
            last_space_idx = i
            break

    if last_space_idx != -1:
        # Replace last space with placeholder before normalization
        normalized = (
            normalized[:last_space_idx] + "###" + normalized[last_space_idx + 1 :]
        )

    # Replace spaces with hyphens, slashes with hyphens
    normalized = normalized.replace(" ", "-").replace("/", "-")

    # Restore placeholder as underscore
    normalized = normalized.replace("###", "_")

    # Normalize Unicode (handles remaining accented characters)
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = normalized.encode("ASCII", "ignore").decode("ASCII")

    # Replace multiple consecutive hyphens with single hyphen
    normalized = re.sub(r"-+", "-", normalized)

    # Build final key
    return f"{date}_{normalized}"


def sanitize_for_blob_metadata(text: str) -> str:
    """
    Sanitize text for Azure Blob Storage metadata (US ASCII only).

    Converts German umlauts and special characters to ASCII equivalents
    while preserving title case formatting.

    Args:
        text: Text to sanitize

    Returns:
        ASCII-safe text suitable for blob metadata
    """
    # Replace German umlauts with ASCII equivalents
    sanitized = (
        text.replace("Ä", "Ae")
        .replace("ä", "ae")
        .replace("Ö", "Oe")
        .replace("ö", "oe")
        .replace("Ü", "Ue")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )

    # Normalize Unicode and encode to ASCII (ignoring non-ASCII chars)
    sanitized = unicodedata.normalize("NFKD", sanitized)
    sanitized = sanitized.encode("ASCII", "ignore").decode("ASCII")

    return sanitized
