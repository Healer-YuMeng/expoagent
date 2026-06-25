from pydantic import ValidationError

from app.models.user import UserCreateRequest, UserSchema
from app.routers.auth import LoginRequest


def test_teacher_can_use_custom_account_identifier():
    user = UserSchema(
        phone="sales_01",
        password_hash="plain:test123",
        role="sales",
    )

    assert user.phone == "sales_01"


def test_legacy_role_aliases_are_normalized():
    admin_user = UserSchema(
        phone="admin_alias",
        password_hash="plain:test123",
        role="school_admin",
    )
    sales_user = UserSchema(
        phone="sales_alias",
        password_hash="plain:test123",
        role="teacher",
    )

    assert admin_user.role == "admin"
    assert sales_user.role == "sales"


def test_parent_must_use_phone_number():
    try:
        UserSchema(
            phone="teacher_01",
            password_hash="plain:test123",
            role="parent",
        )
    except ValidationError as exc:
        assert "家长账号必须使用11位手机号" in str(exc)
    else:
        raise AssertionError("parent 角色应当拒绝自定义账号")


def test_login_request_accepts_custom_account_identifier():
    request = LoginRequest(phone="teacher_01", password="123456")

    assert request.phone == "teacher_01"


def test_parent_registration_rejects_custom_account_identifier():
    try:
        UserCreateRequest(
            phone="teacher_01",
            password="123456",
            role="parent",
        )
    except ValidationError as exc:
        assert "家长账号必须使用11位手机号" in str(exc)
    else:
        raise AssertionError("家长注册应当拒绝自定义账号")
