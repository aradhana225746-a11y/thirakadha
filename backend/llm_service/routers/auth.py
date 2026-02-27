from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db, User, IRCTCCredential
from schemas import (
    SignupRequest, LoginRequest, AuthResponse,
    IRCTCCredentialRequest, IRCTCCredentialResponse
)
from auth_utils import (
    hash_password, verify_password,
    create_access_token, generate_id,
    encrypt_irctc_password, decrypt_irctc_password
)
from dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


# ─── SIGNUP ───────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=AuthResponse, status_code=201)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new user.
    Checks for duplicate email and mobile before creating.
    """

    # Check email exists
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check mobile exists
    result = await db.execute(select(User).where(User.mobile == body.mobile))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Mobile number already registered")

    # Validate mobile (basic)
    if len(body.mobile) != 10 or not body.mobile.isdigit():
        raise HTTPException(status_code=400, detail="Enter a valid 10-digit mobile number")

    # Validate password length
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    user = User(
        id=generate_id(),
        name=body.name.strip(),
        email=body.email.lower().strip(),
        mobile=body.mobile.strip(),
        password=hash_password(body.password)
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.email)

    return AuthResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        email=user.email
    )


# ─── LOGIN ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email + password. Returns JWT token."""

    result = await db.execute(select(User).where(User.email == body.email.lower().strip()))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    token = create_access_token(user.id, user.email)

    return AuthResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        email=user.email
    )


# ─── PROFILE ──────────────────────────────────────────────────────────────────

@router.get("/profile")
async def get_profile(user: User = Depends(get_current_user)):
    """Get current logged-in user's profile"""
    return {
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "mobile": user.mobile,
        "created_at": user.created_at
    }


# ─── IRCTC CREDENTIALS ────────────────────────────────────────────────────────

@router.post("/irctc-credentials", response_model=IRCTCCredentialResponse)
async def save_irctc_credentials(
    body: IRCTCCredentialRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Save or update IRCTC username + password for the logged-in user.
    Password is encrypted before storing — never saved as plain text.
    Browser agent will decrypt it only when needed for booking.
    """

    # Check if credentials already exist for this user
    result = await db.execute(
        select(IRCTCCredential).where(IRCTCCredential.user_id == user.id)
    )
    existing = result.scalar_one_or_none()

    encrypted_password = encrypt_irctc_password(body.irctc_password)

    if existing:
        # Update existing
        existing.irctc_username = body.irctc_username
        existing.irctc_password = encrypted_password
        if body.upi_id:
            existing.upi_id = body.upi_id
        await db.commit()
        message = "IRCTC credentials updated successfully"
    else:
        # Create new
        cred = IRCTCCredential(
            id=generate_id(),
            user_id=user.id,
            irctc_username=body.irctc_username,
            irctc_password=encrypted_password,
            upi_id=body.upi_id
        )
        db.add(cred)
        await db.commit()
        message = "IRCTC credentials saved successfully"

    return IRCTCCredentialResponse(
        message=message,
        irctc_username=body.irctc_username
    )


@router.get("/irctc-credentials")
async def get_irctc_credentials(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Check if user has saved IRCTC credentials (returns username only, never password)"""

    result = await db.execute(
        select(IRCTCCredential).where(IRCTCCredential.user_id == user.id)
    )
    cred = result.scalar_one_or_none()

    if not cred:
        return {"has_credentials": False, "irctc_username": None, "has_upi": False}

    return {
        "has_credentials": True,
        "irctc_username": cred.irctc_username,
        "has_upi": bool(cred.upi_id)
    }


@router.delete("/irctc-credentials")
async def delete_irctc_credentials(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete saved IRCTC credentials"""

    result = await db.execute(
        select(IRCTCCredential).where(IRCTCCredential.user_id == user.id)
    )
    cred = result.scalar_one_or_none()

    if cred:
        await db.delete(cred)
        await db.commit()

    return {"message": "IRCTC credentials removed"}