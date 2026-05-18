"""Per-language regex pattern configurations for Tier 3 languages.

Each module defines a RegexLanguageConfig and registers it with the
regex_parser module on import. Importing this package auto-registers
all configs.
"""

from . import abap  # noqa: F401
from . import algol  # noqa: F401
from . import assembly  # noqa: F401
from . import forth  # noqa: F401
from . import mumps  # noqa: F401
from . import postscript  # noqa: F401
from . import rpg  # noqa: F401
from . import tcl  # noqa: F401
