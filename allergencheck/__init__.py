"""AllergenCheck: scan a food label and check it against your allergies and diet."""
from .engine import Profile, Report, analyze

__all__ = ["Profile", "Report", "analyze"]
