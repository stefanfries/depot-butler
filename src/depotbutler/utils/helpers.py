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
    # Title case the title (e.g., "DER AKTIONÄR EDITION" -> "Der Aktionär Edition")
    title_formatted = edition.title.title()
    
    # Replace spaces with hyphens and forward slashes with hyphens
    title_formatted = title_formatted.replace(" ", "-").replace("/", "-")
    
    # Combine with date prefix
    filename = f"{edition.publication_date}_{title_formatted}.pdf"
    
    return filename
