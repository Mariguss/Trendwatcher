from datetime import (
    timezone,
    datetime,
)


def get_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)
