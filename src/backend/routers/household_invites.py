import hashlib
import secrets

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.backend.db import get_db
from src.backend.dependencies import get_current_user
from src.backend.models import (
    User,
    Household,
    HouseholdMember,
    HouseholdInvite
)
from src.backend.schemas import (
    HouseholdInviteCreate,
    HouseholdInviteResponse
)

router = APIRouter(
    prefix="/households",
    tags=["Household Invites"]
)
@router.post(
    "/{household_id}/invites",
    status_code=status.HTTP_201_CREATED
)
def create_household_invite(
    household_id: int,
    invite_data: HouseholdInviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Kiểm tra thành viên và quyền tạo lời mời
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=404,
            detail="Household not found"
        )

    if membership.role not in ["owner", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to invite members"
        )

    # 2. Kiểm tra email đã thuộc hộ gia đình chưa
    existing_user = db.query(User).filter(
        User.email == invite_data.email
    ).first()

    if existing_user:
        existing_member = db.query(HouseholdMember).filter(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == existing_user.id
        ).first()

        if existing_member:
            raise HTTPException(
                status_code=409,
                detail="User is already a household member"
            )

    # 3. Tạo invitation token
    raw_token = secrets.token_urlsafe(32)

    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    # 4. Thiết lập thời hạn 7 ngày
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    # 5. Lưu lời mời
    invitation = HouseholdInvite(
        household_id=household_id,
        invited_by=current_user.id,
        email=invite_data.email,
        role=invite_data.role,
        token_hash=token_hash,
        expires_at=expires_at
    )

    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    # 6. Trả token gốc một lần cho người tạo lời mời
    return {
        "status": "success",
        "message": "Household invitation created successfully",
        "invitation": HouseholdInviteResponse.model_validate(invitation),
        "invitation_token": raw_token
    }
@router.post("/invites/accept")
def accept_household_invite(
    invitation_token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Hash token nhận được
    token_hash = hashlib.sha256(
        invitation_token.encode("utf-8")
    ).hexdigest()

    # 2. Tìm lời mời
    invitation = db.query(HouseholdInvite).filter(
        HouseholdInvite.token_hash == token_hash
    ).first()

    if invitation is None:
        raise HTTPException(
            status_code=404,
            detail="Invitation not found"
        )

    # 3. Kiểm tra thời hạn
    if invitation.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Invitation has expired"
        )

    # 4. Kiểm tra lời mời đã được sử dụng chưa
    if invitation.accepted_at is not None:
        raise HTTPException(
            status_code=409,
            detail="Invitation has already been accepted"
        )

    # 5. Kiểm tra email người nhận
    if invitation.email.lower() != current_user.email.lower():
        raise HTTPException(
            status_code=403,
            detail="This invitation belongs to another email"
        )

    # 6. Kiểm tra thành viên đã tồn tại
    existing_member = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == invitation.household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if existing_member:
        raise HTTPException(
            status_code=409,
            detail="User is already a household member"
        )

    # 7. Thêm thành viên vào hộ gia đình
    new_membership = HouseholdMember(
        household_id=invitation.household_id,
        user_id=current_user.id,
        role=invitation.role
    )

    invitation.accepted_at = datetime.now(timezone.utc)

    try:
        db.add(new_membership)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not accept invitation"
        )

    return {
        "status": "success",
        "message": "Invitation accepted successfully",
        "household_id": invitation.household_id,
        "role": invitation.role
    }