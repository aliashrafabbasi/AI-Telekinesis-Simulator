from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import RegisterRequest
from app.auth.security import create_access_token, hash_password, verify_password
from app.exceptions import AuthError
from app.models.user import User


async def register_user(db: AsyncSession, payload: RegisterRequest) -> User:
    email = payload.email.lower()
    username = payload.username.lower()

    existing = await db.execute(
        select(User).where(or_(User.email == email, User.username == username))
    )
    if existing.scalar_one_or_none() is not None:
        raise AuthError("Email or username already registered", status_code=409)

    user = User(
        email=email,
        username=username,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password", status_code=401)

    if not user.is_active:
        raise AuthError("Account is inactive", status_code=403)

    return user


def build_token_response(user: User):
    from app.auth.schemas import TokenResponse, UserResponse

    token = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )
