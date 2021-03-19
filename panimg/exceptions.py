from pathlib import Path
from typing import Dict, List


class ValidationError(Exception):
    pass


class BuilderErrors(Exception):
    def __init__(self, *args, errors: Dict[Path, List[str]]):
        super().__init__(*args)
        self.errors = errors
