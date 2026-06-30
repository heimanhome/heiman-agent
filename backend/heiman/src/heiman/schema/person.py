from pydantic import BaseModel, Field, field_validator


def _normalize_optional_str(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


def _require_nonempty_name(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    if not v:
        raise ValueError("name 不可为空")
    return v


class PersonCreate(BaseModel):
    name: str = Field(min_length=1)
    role: str | None = None

    _strip_name = field_validator("name")(_require_nonempty_name)
    _norm_role = field_validator("role")(_normalize_optional_str)


class PersonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    role: str | None = None

    _strip_name = field_validator("name")(_require_nonempty_name)
    _norm_role = field_validator("role")(_normalize_optional_str)


class Person(BaseModel):
    id: str
    name: str
    role: str | None = None
    user_id: str | None = None
    home_id: str | None = None
    home_name: str | None = None
    user_account: str | None = None
    alias_name: str | None = None
    head_img_url: str | None = None
    is_home_root: int | None = None
    role_type: int | None = None
    status: int | None = None
    remark: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
