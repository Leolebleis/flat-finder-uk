from pathlib import Path

from fastapi.templating import Jinja2Templates

_pkg_dir = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(_pkg_dir / "templates"))
