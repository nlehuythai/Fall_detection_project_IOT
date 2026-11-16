from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.backend.db import get_db
from src.backend.dependencies import get_current_user
from src.backend.models import User, Household, HouseholdMember
from src.backend.schemas import HouseholdCreate, HouseholdResponse
from src.backend.schemas import HouseholdMemberResponse
from src.backend.schemas import HouseholdUpdate
router = APIRouter(prefix="/households", tags=["Households"])

@router.get(
    "/",
    response_model=list[HouseholdResponse]
)
def get_my_households(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    households = db.query(
        Household
    ).join(
        HouseholdMember,
        HouseholdMember.household_id == Household.id
    ).filter(
        HouseholdMember.user_id == current_user.id
    ).order_by(
        Household.id.asc()
    ).all()

    return households
@router.post(
    "/",
    response_model=HouseholdResponse,
    status_code=status.HTTP_201_CREATED
)
def create_household(
    household_data: HouseholdCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_household = Household(
        household_name=household_data.household_name
    )

    db.add(new_household)

    try:
        db.flush()

        owner_membership = HouseholdMember(
            household_id=new_household.id,
            user_id=current_user.id,
            role="owner"
        )

        db.add(owner_membership)
        db.commit()
        db.refresh(new_household)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create household"
        )

    return new_household
@router.get(
    "/{household_id}",
    response_model=HouseholdResponse
)
def get_household_detail(
    household_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    household = db.query(Household).filter(
        Household.id == household_id
    ).first()

    if household is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    return household
@router.get(
    "/{household_id}/members",
    response_model=list[HouseholdMemberResponse]
)
def get_household_members(
    household_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Kiểm tra người dùng có thuộc household không
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=404,
            detail="Household not found"
        )

    # Lấy danh sách thành viên và thông tin tài khoản
    rows = db.query(
        HouseholdMember,
        User
    ).join(
        User,
        User.id == HouseholdMember.user_id
    ).filter(
        HouseholdMember.household_id == household_id
    ).order_by(
        HouseholdMember.joined_at.asc()
    ).all()

    return [
        {
            "household_id": member.household_id,
            "user_id": member.user_id,
            "full_name": user.full_name,
            "email": user.email,
            "role": member.role,
            "joined_at": member.joined_at
        }
        for member, user in rows
    ]
@router.delete("/{household_id}/members/{user_id}")
def remove_household_member(
    household_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Kiểm tra quyền của người thực hiện
    current_membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if current_membership is None:
        raise HTTPException(
            status_code=404,
            detail="Household not found"
        )

    if current_membership.role not in ["owner", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to remove members"
        )

    # Tìm thành viên cần xóa
    target_membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == user_id
    ).first()

    if target_membership is None:
        raise HTTPException(
            status_code=404,
            detail="Member not found"
        )

    # Không cho phép xóa chủ hộ
    if target_membership.role == "owner":
        raise HTTPException(
            status_code=403,
            detail="Cannot remove the household owner"
        )

    db.delete(target_membership)
    db.commit()

    return {
        "status": "success",
        "message": "Household member removed successfully",
        "household_id": household_id,
        "user_id": user_id
    }
@router.patch("/{household_id}")
def update_household(
    household_id: int,
    household_data: HouseholdUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Kiểm tra thành viên hiện tại
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=404,
            detail="Household not found"
        )

    # Chỉ Owner mới được cập nhật thông tin
    if membership.role != "owner":
        raise HTTPException(
            status_code=403,
            detail="Only household owner can update household information"
        )

    # Tìm household
    household = db.query(Household).filter(
        Household.id == household_id
    ).first()

    if household is None:
        raise HTTPException(
            status_code=404,
            detail="Household not found"
        )

    # Cập nhật tên
    household.household_name = household_data.household_name.strip()

    if not household.household_name:
        raise HTTPException(
            status_code=422,
            detail="Household name cannot be empty"
        )

    db.commit()
    db.refresh(household)

    return {
        "status": "success",
        "message": "Household updated successfully",
        "household": {
            "id": household.id,
            "household_name": household.household_name
        }
    }