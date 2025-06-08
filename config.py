import json
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from models import FilterCondition


class MonitorConfig(BaseModel):
    """监视器配置"""
    check_interval: int = Field(default=90, description="检查间隔（秒）")  # 考虑到API+CF双重缓存60秒，设置为90秒
    expire_threshold: int = Field(default=300, description="过期阈值（秒）")
    enable_system_notification: bool = Field(default=True, description="启用系统通知")
    enable_sound_notification: bool = Field(default=True, description="启用声音提醒")
    base_url: str = Field(default="http://xivpf.littlenightmare.top/api", description="API基础URL")
    
    
class FilterConfig(BaseModel):
    """过滤器配置"""
    name: str = Field(description="过滤器名称")
    condition: FilterCondition = Field(description="过滤条件")
    enabled: bool = Field(default=True, description="是否启用")
    
    
class Config(BaseModel):
    """应用配置"""
    monitor: MonitorConfig = Field(default_factory=MonitorConfig)
    filters: List[FilterConfig] = Field(default_factory=list)
    monitor_targets: List[int] = Field(default_factory=list, description="监视目标ID列表")
    
    @classmethod
    def load_from_file(cls, filepath: str = "config.json") -> "Config":
        """从文件加载配置"""
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls(**data)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
                return cls()
        return cls()
        
    def save_to_file(self, filepath: str = "config.json"):
        """保存配置到文件"""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.model_dump(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            
    def add_filter(self, name: str, condition: FilterCondition):
        """添加过滤器"""
        filter_config = FilterConfig(name=name, condition=condition)
        self.filters.append(filter_config)
        
    def remove_filter(self, name: str):
        """移除过滤器"""
        self.filters = [f for f in self.filters if f.name != name]
        
    def get_enabled_filters(self) -> List[FilterConfig]:
        """获取启用的过滤器"""
        return [f for f in self.filters if f.enabled]
        
    def toggle_filter(self, name: str):
        """切换过滤器状态"""
        for filter_config in self.filters:
            if filter_config.name == name:
                filter_config.enabled = not filter_config.enabled
                break
                
    def add_monitor_target(self, listing_id: int):
        """添加监视目标"""
        if listing_id not in self.monitor_targets:
            self.monitor_targets.append(listing_id)
            
    def remove_monitor_target(self, listing_id: int):
        """移除监视目标"""
        if listing_id in self.monitor_targets:
            self.monitor_targets.remove(listing_id)


# 预设的过滤器示例
PRESET_FILTERS = [
    FilterConfig(
        name="高难度副本-莫古力",
        condition=FilterCondition(
            category="HighEndDuty",
            datacenter="莫古力"
        )
    ),
    FilterConfig(
        name="极神挑战",
        condition=FilterCondition(
            search="极",
            min_slots_available=1
        )
    ),
    FilterConfig(
        name="零式团队",
        condition=FilterCondition(
            search="零式",
            min_slots_available=2
        )
    ),
    FilterConfig(
        name="需要坦克的队伍",
        condition=FilterCondition(
            min_slots_available=1,
            exclude_jobs=[19, 21, 32, 37]  # 排除已有骑士、战士、暗黑、绝枪的队伍
        )
    ),
    FilterConfig(
        name="需要治疗的队伍", 
        condition=FilterCondition(
            min_slots_available=1,
            exclude_jobs=[24, 28, 33, 40]  # 排除已有白魔、学者、占星、贤者的队伍
        )
    ),
    FilterConfig(
        name="速通团队",
        condition=FilterCondition(
            content_keywords="速通 速刷 刷子",
            min_slots_available=1
        )
    ),
    FilterConfig(
        name="练习向团队",
        condition=FilterCondition(
            content_keywords="练习 新手 萌新 学习",
            min_slots_available=1
        )
    ),
    FilterConfig(
        name="固定队招募",
        condition=FilterCondition(
            content_keywords="固定 固定队 长期 招固定",
            min_slots_available=1
        )
    )
] 