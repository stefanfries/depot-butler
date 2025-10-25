from depotbutler.models import Edition


def create_filename(edition: Edition) -> str:
    """
    Create a safe filename for the edition PDF corresponding to a specific pattern
    Example: 2025-10-23_MegatrendFolger_43-2025.pdf
    Args:
    """

    filename = f"{edition.publication_date}_{edition.title}.pdf"
    filename = filename.replace(" ", "", count=1).replace(" ", "_").replace("/", "-")

    return filename
