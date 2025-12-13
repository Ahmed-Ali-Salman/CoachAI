"""CoachAI - Multimodal Learning Coach

This package follows a layered architecture:
clients -> repositories -> services -> controllers -> api/ui.
"""

from pathlib import Path
from dotenv import load_dotenv

_root = Path(__file__).parent.parent
_env_file = _root / '.env'
if _env_file.exists():
    load_dotenv(str(_env_file))
else:
    load_dotenv()

from coachai.core.config import Config
from coachai.controllers.coach_controller import CoachController

__all__ = [
    'Config',
    'CoachController',
]
