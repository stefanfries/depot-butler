from depotbutler.models import Edition


def create_filename(edition: Edition) -> str:
    """
    Create a safe filename for the edition PDF.
    Example: 2025-12-10_Der-Aktionär-Edition_01-26.pdf

    Args:
        edition: Edition object with title and publication_date

    Returns:
        Formatted filename: {date}_{Title-Cased-Title}_{issue}.pdf
    """
    # Title case the title (e.g., "DER AKTIONÄR EDITION 01/26" -> "Der Aktionär Edition 01/26")
    title_formatted = edition.title.title()

    # Find the last space (typically before issue number) and replace it with a placeholder
    last_space_idx = title_formatted.rfind(" ")
    if last_space_idx != -1:
        # Replace the last space with a temporary placeholder
        title_formatted = (
            title_formatted[:last_space_idx]
            + "###"
            + title_formatted[last_space_idx + 1 :]
        )

    # Replace all remaining spaces with hyphens
    title_formatted = title_formatted.replace(" ", "-")

    # Replace the placeholder with underscore (separates title from issue number)
    title_formatted = title_formatted.replace("###", "_")

    # Replace forward slashes with hyphens (e.g., "01/26" -> "01-26")
    title_formatted = title_formatted.replace("/", "-")

    # Combine with date prefix
    filename = f"{edition.publication_date}_{title_formatted}.pdf"

    return filename
