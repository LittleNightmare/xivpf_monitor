import aiohttp
from typing import List, Optional, Dict, Any
from models import Listing, ListingsResponse, FilterCondition
import json
from datetime import datetime
import logging
from job_mappings import get_job_codes_from_string, get_job_ids_from_codes

logger = logging.getLogger(__name__)


class XIVPFApiClient:
    def __init__(self, base_url: str = "http://xivpf.littlenightmare.top/api"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def get_listings(
        self,
        page: int = 1,
        per_page: int = 20,
        filter_condition: Optional[FilterCondition] = None
    ) -> ListingsResponse:
        """获取招募列表"""
        if not self.session:
            raise RuntimeError("Session not initialized. Use async with statement.")
            
        params = {
            "page": str(page),
            "per_page": str(min(per_page, 100))  # 最大100
        }
        
        if filter_condition:
            if filter_condition.category:
                params["category"] = filter_condition.category
            if filter_condition.world:
                params["world"] = filter_condition.world
            if filter_condition.datacenter:
                params["datacenter"] = filter_condition.datacenter
            if filter_condition.search:
                params["search"] = filter_condition.search
            if filter_condition.jobs:
                params["jobs"] = ",".join(str(j) for j in filter_condition.jobs)
            if filter_condition.duty:
                params["duty"] = ",".join(str(d) for d in filter_condition.duty)
                
        try:
            async with self.session.get(f"{self.base_url}/listings", params=params) as response:
                response.raise_for_status()
                data = await response.json()
                return ListingsResponse(**data)
        except aiohttp.ClientError as e:
            logger.error(f"API request failed: {e}")
            raise
            
    async def get_listing_detail(self, listing_id: int) -> Listing:
        """获取招募详情"""
        if not self.session:
            raise RuntimeError("Session not initialized. Use async with statement.")
            
        try:
            async with self.session.get(f"{self.base_url}/listing/{listing_id}") as response:
                if response.status == 404:
                    raise ValueError(f"Listing {listing_id} not found")
                response.raise_for_status()
                data = await response.json()
                return Listing(**data)
        except aiohttp.ClientError as e:
            logger.error(f"API request failed for listing {listing_id}: {e}")
            raise
            
    async def get_all_listings(
        self,
        filter_condition: Optional[FilterCondition] = None,
        max_pages: Optional[int] = None
    ) -> List[Listing]:
        """获取所有符合条件的招募（自动处理分页）"""
        all_listings = []
        page = 1
        
        while True:
            response = await self.get_listings(
                page=page,
                per_page=100,  # 使用最大值以减少请求次数
                filter_condition=filter_condition
            )
            
            all_listings.extend(response.data)
            
            if page >= response.pagination.total_pages:
                break
                
            if max_pages and page >= max_pages:
                break
                
            page += 1
            
        return all_listings
        
    async def check_advanced_filters(
        self,
        listing: Listing,
        filter_condition: FilterCondition
    ) -> bool:
        """检查高级过滤条件（需要详情数据）"""
        # 如果没有高级过滤条件，直接返回True
        if not any([
            filter_condition.exclude_jobs,
            filter_condition.min_slots_available,
            filter_condition.max_slots_filled,
            filter_condition.beginners_welcome is not None,
            filter_condition.content_keywords
        ]):
            return True
            
        # 获取详细信息
        try:
            detailed_listing = await self.get_listing_detail(listing.id)
        except ValueError:
            # 招募可能已经不存在
            return False
            
        # 检查排除的职业
        if filter_condition.exclude_jobs and detailed_listing.slots:
            for slot in detailed_listing.slots:
                if slot.filled and slot.job:
                    # 解析职业代码，可能包含多个职业
                    job_codes = get_job_codes_from_string(slot.job)
                    existing_job_ids = get_job_ids_from_codes(job_codes)
                    
                    # 检查是否有需要排除的职业
                    for exclude_job_id in filter_condition.exclude_jobs:
                        if exclude_job_id in existing_job_ids:
                            return False  # 找到了需要排除的职业，过滤掉这个招募
                        
        # 检查空位数
        if filter_condition.min_slots_available is not None:
            if detailed_listing.slots_available < filter_condition.min_slots_available:
                return False
                
        # 检查已填充位数
        if filter_condition.max_slots_filled is not None:
            if detailed_listing.slots_filled > filter_condition.max_slots_filled:
                return False
                
        # 检查是否欢迎新手
        if filter_condition.beginners_welcome is not None:
            if detailed_listing.beginners_welcome != filter_condition.beginners_welcome:
                return False
                
        # 检查内容关键词
        if filter_condition.content_keywords:
            keywords = [kw.strip().lower() for kw in filter_condition.content_keywords.split() if kw.strip()]
            if keywords:
                # 将招募内容转换为小写进行比较
                content_lower = detailed_listing.description.lower()
                
                # 检查是否包含任意一个关键词
                has_keyword = any(keyword in content_lower for keyword in keywords)
                if not has_keyword:
                    return False
                
        return True 