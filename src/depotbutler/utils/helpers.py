import re

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
