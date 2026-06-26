from client import get_display_name
from models import User


def test_get_display_name() -> None:
    user = User(id=1, username="ada")
    assert get_display_name(user) == "ada"
