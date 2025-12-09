import enum


class status_Grade(str, enum.Enum):
    checked = "checked"
    rated = "rated"
    not_verified = "not verified"


class status_Course(str, enum.Enum):
    public = "public"
    private = "private"
    draft = "draft"

