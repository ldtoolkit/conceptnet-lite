import re
from pathlib import Path
from typing import Union


PathOrStr = Union[Path, str]


def _to_snake_case(s: str) -> str:
    regex = re.compile('((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))')
    return regex.sub(r'_\1', s).lower()
