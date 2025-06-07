from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class SlotInfo(BaseModel):
    filled: bool
    role: Optional[str]
    job: str


class Listing(BaseModel):
    id: int
    name: str
    description: str
    created_world: str
    home_world: str
    category: str
    duty: str
    min_item_level: int
    slots_filled: int
    slots_available: int
    time_left: float
    updated_at: datetime
    is_cross_world: bool
    datacenter: str
    
    @field_validator('updated_at', mode='before')
    @classmethod
    def convert_utc_to_local(cls, v):
        """将UTC时间转换为本地时间"""
        if isinstance(v, str):
            # 解析ISO格式的时间字符串
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
        elif isinstance(v, datetime):
            dt = v
        else:
            return v
            
        # 如果没有时区信息，假设是UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        # 转换为本地时间
        local_dt = dt.astimezone()
        
        # 返回不带时区信息的本地时间（为了兼容性）
        return local_dt.replace(tzinfo=None)
    
    # Additional fields from detail endpoint
    beginners_welcome: Optional[bool] = None
    duty_type: Optional[str] = None
    objective: Optional[str] = None
    conditions: Optional[str] = None
    loot_rules: Optional[str] = None
    slots: Optional[List[SlotInfo]] = None


class Pagination(BaseModel):
    total: int
    page: int
    per_page: int
    total_pages: int


class ListingsResponse(BaseModel):
    data: List[Listing]
    pagination: Pagination


class FilterCondition(BaseModel):
    """过滤条件"""
    # 基础过滤条件（通过 /listings 端点）
    category: Optional[str] = None
    world: Optional[str] = None
    datacenter: Optional[str] = None
    search: Optional[str] = None
    jobs: Optional[List[int]] = None
    duty: Optional[List[int]] = None
    
    # 高级过滤条件（需要 /listing/{id} 详情）
    exclude_jobs: Optional[List[int]] = None  # 排除已有指定职业的招募
    min_slots_available: Optional[int] = None  # 最少空位数
    max_slots_filled: Optional[int] = None  # 最多已填充位数
    beginners_welcome: Optional[bool] = None
    content_keywords: Optional[str] = None  # 招募内容关键词过滤（空格分割，不区分大小写）


class MonitorTarget(BaseModel):
    """监视目标"""
    listing_id: int
    last_update: datetime
    time_without_update: float = 0  # 没有更新的时间（秒）
    
    @field_validator('last_update', mode='before')
    @classmethod
    def convert_utc_to_local(cls, v):
        """将UTC时间转换为本地时间"""
        if isinstance(v, str):
            # 解析ISO格式的时间字符串
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
            
            # 如果没有时区信息，假设是UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            
            # 转换为本地时间
            local_dt = dt.astimezone()
            
            # 返回不带时区信息的本地时间（为了兼容性）
            return local_dt.replace(tzinfo=None)
        elif isinstance(v, datetime):
            # 如果是datetime对象，直接返回（假设已经是正确的时间）
            return v
        else:
            return v
    
    
class NotificationType(str, Enum):
    FOUND = "found"  # 找到匹配的招募
    EXPIRED = "expired"  # 招募过期
    UPDATED = "updated"  # 招募更新 