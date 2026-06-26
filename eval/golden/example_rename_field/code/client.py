from models import User


def get_display_name(user: User) -> str:
    return user.user_name
