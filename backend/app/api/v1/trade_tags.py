"""交易标签接口。"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundException
from app.core.permissions import reject_viewer_write
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.trade_tag import (
    TradeTagCreate,
    TradeTagMergeRequest,
    TradeTagMergeResponse,
    TradeTagResponse,
    TradeTagUpdate,
)
from app.services.trade_tag_service import TradeTagService
from app.utils.audit import write_audit_log

router = APIRouter(
    prefix="/trade-tags",
    tags=["交易标签"],
    dependencies=[Depends(reject_viewer_write)],
)


@router.get("", summary="获取标签列表")
async def list_tags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用户全部标签（按使用次数降序）。"""
    service = TradeTagService(db)
    tags = await service.list_tags(current_user.id)
    return ApiResponse(
        data=[TradeTagResponse.model_validate(t) for t in tags]
    )


@router.post("", summary="创建标签")
async def create_tag(
    data: TradeTagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建标签（user_id + name 唯一）。"""
    service = TradeTagService(db)
    tag = await service.create_tag(current_user.id, data)
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="create",
        resource_type="trade_tag",
        resource_id=tag.id,
        detail={"name": tag.name, "color": tag.color},
    )
    return ApiResponse(data=TradeTagResponse.model_validate(tag))


@router.patch("/{tag_id}", summary="更新标签")
async def update_tag(
    tag_id: uuid.UUID,
    data: TradeTagUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新标签名称或颜色。"""
    service = TradeTagService(db)
    tag = await service.update_tag(tag_id, current_user.id, data)
    if tag is None:
        raise NotFoundException(
            message="标签不存在", detail={"tag_id": str(tag_id)}
        )
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="update",
        resource_type="trade_tag",
        resource_id=tag.id,
        detail=data.model_dump(exclude_unset=True, exclude_none=True),
    )
    return ApiResponse(data=TradeTagResponse.model_validate(tag))


@router.delete("/{tag_id}", summary="删除标签")
async def delete_tag(
    tag_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除标签（同时从所有交易记录的 tags 数组中移除）。"""
    service = TradeTagService(db)
    deleted = await service.delete_tag(tag_id, current_user.id)
    if not deleted:
        raise NotFoundException(
            message="标签不存在", detail={"tag_id": str(tag_id)}
        )
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="delete",
        resource_type="trade_tag",
        resource_id=tag_id,
    )
    return ApiResponse(data={"deleted": True})


@router.post("/merge", summary="合并标签")
async def merge_tags(
    data: TradeTagMergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """合并标签：将 source_tags 合并到 target_tag。"""
    service = TradeTagService(db)
    result = await service.merge_tags(
        current_user.id, data.source_tag_ids, data.target_tag_id
    )
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="update",
        resource_type="trade_tag",
        resource_id=data.target_tag_id,
        detail={
            "action": "merge",
            "source_tag_ids": [str(sid) for sid in data.source_tag_ids],
            **result,
        },
    )
    return ApiResponse(data=TradeTagMergeResponse(**result))
