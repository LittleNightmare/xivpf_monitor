import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Tuple
from models import Listing, FilterCondition, MonitorTarget
from api_client import XIVPFApiClient
from notifier import Notifier
from time_utils import format_local_time, get_time_ago_str

logger = logging.getLogger(__name__)


class XIVPFMonitor:
    def __init__(
        self,
        api_client: XIVPFApiClient,
        notifier: Notifier,
        check_interval: int = 30,  # 检查间隔（秒）
        expire_threshold: int = 300  # 过期阈值（秒）
    ):
        self.api_client = api_client
        self.notifier = notifier
        self.check_interval = check_interval
        self.expire_threshold = expire_threshold
        
        # 存储已通知的招募ID，避免重复通知
        self.notified_listings: Set[int] = set()
        
        # 监视目标
        self.monitor_targets: Dict[int, MonitorTarget] = {}
        
        # 上一次的招募列表（用于判断过期）
        self.last_listings: List[Listing] = []
        
        # 上一次显示的招募ID集合（用于判断是否有新招募）
        self.last_displayed_ids: Set[int] = set()
        
        # 运行状态控制
        self.running: bool = False
        
    async def search_listings(
        self,
        filter_condition: FilterCondition,
        filter_name: str = "",
        notify: bool = True
    ) -> List[Listing]:
        """搜索符合条件的招募"""
        try:
            # 获取基础过滤后的招募
            listings = await self.api_client.get_all_listings(filter_condition)
            
            # 应用高级过滤
            filtered_listings = []
            for listing in listings:
                if await self.api_client.check_advanced_filters(listing, filter_condition):
                    filtered_listings.append(listing)
                    
            # 过滤掉已通知的招募
            new_listings = [
                l for l in filtered_listings 
                if l.id not in self.notified_listings
            ]
            
            # 通知新找到的招募
            if notify and new_listings:
                # 如果存在监视目标，不发送系统通知，只显示控制台输出
                has_monitor_targets = len(self.monitor_targets) > 0
                self.notifier.notify_found(
                    new_listings, 
                    filter_name, 
                    enable_system_notification=not has_monitor_targets
                )
                # 记录已通知的招募
                for listing in new_listings:
                    self.notified_listings.add(listing.id)
                    
            return filtered_listings
            
        except Exception as e:
            logger.error(f"Search listings failed: {e}")
            return []
            
    async def add_monitor_target(self, listing_id: int):
        """添加监视目标"""
        try:
            listing = await self.api_client.get_listing_detail(listing_id)
            self.monitor_targets[listing_id] = MonitorTarget(
                listing_id=listing_id,
                last_update=listing.updated_at
            )
            self.notifier.show_status(
                f"开始监视招募 {listing_id} - {listing.name}",
                "green"
            )
        except Exception as e:
            logger.error(f"Add monitor target failed: {e}")
            self.notifier.show_status(
                f"添加监视目标失败: {listing_id}",
                "red"
            )
            
    def remove_monitor_target(self, listing_id: int):
        """移除监视目标"""
        if listing_id in self.monitor_targets:
            del self.monitor_targets[listing_id]
            self.notifier.show_status(
                f"停止监视招募 {listing_id}",
                "yellow"
            )
            
    async def show_monitor_targets(self):
        """显示当前监视目标"""
        if not self.monitor_targets:
            return
            
        self.notifier.show_status(f"当前监视目标 ({len(self.monitor_targets)}个):", "cyan")
        
        for listing_id, target in self.monitor_targets.items():
            try:
                # 获取最新信息来显示名称
                listing = await self.api_client.get_listing_detail(listing_id)
                
                # 使用工具函数显示时间
                time_display = get_time_ago_str(target.last_update)
                
                self.notifier.show_status(
                    f"  📍 {listing_id} - {listing.name} "
                    f"({listing.slots_filled}/{listing.slots_available}, {time_display})",
                    "dim"
                )
            except Exception as e:
                # 如果获取详情失败，只显示ID
                self.notifier.show_status(
                    f"  📍 {listing_id} (获取详情失败)",
                    "red"
                )
            
    async def check_monitor_targets(self):
        """检查监视目标的状态"""
        for listing_id, target in list(self.monitor_targets.items()):
            try:
                # 获取最新信息
                listing = await self.api_client.get_listing_detail(listing_id)
                
                # 检查是否更新
                if listing.updated_at > target.last_update:
                    # 招募已更新
                    # changes = f"人数变化: {listing.slots_filled}/{listing.slots_available}"
                    self.notifier.notify_updated(listing)
                    target.last_update = listing.updated_at
                    target.time_without_update = 0
                else:
                    # 计算没有更新的时间
                    target.time_without_update = (
                        datetime.now() - target.last_update
                    ).total_seconds()
                    
                    # 检查是否超过阈值
                    if target.time_without_update > self.expire_threshold:
                        self.notifier.notify_expired(
                            listing,
                            f"超过 {int(self.expire_threshold/60)} 分钟没有更新"
                        )
                        self.remove_monitor_target(listing_id)
                        
            except ValueError:
                # 招募不存在了
                self.notifier.show_status(
                    f"招募 {listing_id} 已结束或删除",
                    "red"
                )
                self.remove_monitor_target(listing_id)
            except Exception as e:
                logger.error(f"Check monitor target {listing_id} failed: {e}")
                
    async def check_expired_by_order(self, listings: List[Listing]):
        """通过排序规则检查过期的监控目标
        
        规则：如果招募i的剩余时间 < 招募i-1的剩余时间，
        那么招募i-1就是最后一个最新的招募
        """
        if len(listings) < 2 or not self.monitor_targets:
            return
            
        # 找到最后一个"新"的招募
        last_new_index = len(listings) - 1
        for i in range(1, len(listings)):
            if listings[i].time_left < listings[i-1].time_left:
                last_new_index = i - 1
                break
                
        # 检查之前的列表中哪些监控目标现在过期了
        if self.last_listings:
            previous_ids = {l.id for l in self.last_listings[:last_new_index+1]}
            current_ids = {l.id for l in listings}
            
            # 找出消失的招募，但只处理监控目标
            expired_ids = previous_ids - current_ids
            monitor_target_ids = set(self.monitor_targets.keys())
            expired_monitor_targets = expired_ids & monitor_target_ids
            
            for listing in self.last_listings:
                if listing.id in expired_monitor_targets:
                    self.notifier.notify_expired(
                        listing,
                        "招募已从列表中消失"
                    )
                    # 从监控目标中移除
                    self.remove_monitor_target(listing.id)
                    
        # 更新上一次的列表
        self.last_listings = listings.copy()
        
    async def continuous_search(
        self,
        filter_conditions: List[Tuple[FilterCondition, str]],
        enable_expire_check: bool = True
    ):
        """持续搜索招募"""
        self.notifier.show_status("开始监视...", "green")
        self.notifier.show_status("按 'q' + Enter 停止监视", "yellow")
        
        self.running = True
        while self.running:
            try:
                all_listings = []
                
                # 检查所有过滤条件
                for condition, name in filter_conditions:
                    listings = await self.search_listings(condition, name)
                    all_listings.extend(listings)
                    
                # 根据后端排序规则对招募列表进行排序
                all_listings.sort(
                    key=lambda l: (
                        l.updated_at.replace(second=0, microsecond=0),
                        l.duty_type,
                        -l.time_left  # 升序 time_left, key 使用负值
                    ),
                    reverse=True
                )
                    
                # 检查监视目标
                if self.monitor_targets:
                    # 显示当前监视目标
                    await self.show_monitor_targets()
                    
                    # 通过排序规则检查监视目标是否过期（从列表中消失）
                    if enable_expire_check and all_listings:
                        await self.check_expired_by_order(all_listings)
                        
                    # 检查监视目标状态（更新/超时）
                    await self.check_monitor_targets()
                else:
                    # 没有监视目标时，只有发现新招募才显示表格
                    if all_listings:
                        current_ids = {listing.id for listing in all_listings}
                        # 检查是否有新招募
                        new_ids = current_ids - self.last_displayed_ids
                        
                        if new_ids:
                            # 有新招募，显示表格
                            self.notifier.show_listings_table(
                                all_listings, 
                                "当前招募列表", 
                                max_count=20
                            )
                            # 更新已显示的招募ID集合
                            self.last_displayed_ids = current_ids.copy()
                        # 如果没有新招募，不显示表格，只在状态日志中显示数量
                    
                # 显示状态
                self.notifier.show_status(
                    f"检查完成 - 找到 {len(all_listings)} 个招募，"
                    f"监视 {len(self.monitor_targets)} 个目标",
                    "dim"
                )
                
                # 等待下一次检查
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                if self.running:  # 只在运行时记录错误
                    logger.error(f"Continuous search error: {e}")
                    self.notifier.show_status(f"错误: {e}", "red")
                    await asyncio.sleep(self.check_interval)
                else:
                    # 如果已停止，跳出循环
                    break
                    
        self.notifier.show_status("监视循环已结束", "dim")
                
    def clear_notified_listings(self):
        """清除已通知的招募记录"""
        self.notified_listings.clear()
        self.notifier.show_status("已清除通知记录", "yellow")
        
    def clear_displayed_listings(self):
        """清除已显示的招募记录"""
        self.last_displayed_ids.clear()
        self.notifier.show_status("已清除显示记录，下次检查将重新显示招募列表", "yellow")
        
    def stop_monitoring(self):
        """停止监视"""
        self.running = False
        self.notifier.show_status("正在停止监视...", "yellow") 