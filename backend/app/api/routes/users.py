from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.models.user import User, UserCreate, UserResponse, UserUpdate
from app.services import user_service
from app.utils.auth import require_role

router = APIRouter(dependencies=[Depends(require_role("admin"))])


@router.get("/", response_model=List[UserResponse])
def list_users():
    return user_service.list_users()


@router.post("/", response_model=UserResponse, status_code=201)
def create_user(payload: UserCreate):
    try:
        return user_service.create_user(payload)
    except user_service.EmailTaken as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, payload: UserUpdate, admin: User = Depends(require_role("admin"))):
    # Refusing self-edits is what guarantees at least one admin always remains.
    if user_id == admin.id:
        raise HTTPException(status_code=409, detail="You can't change your own role or access")
    user = user_service.update_user(user_id, payload)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
