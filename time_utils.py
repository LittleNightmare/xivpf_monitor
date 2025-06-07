from datetime import datetime, timezone


def format_local_time(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化本地时间显示"""
    if dt is None:
        return "未知"
    return dt.strftime(format_str)


def get_time_ago_str(dt: datetime) -> str:
    """获取相对时间描述（如：5分钟前）"""
    if dt is None:
        return "未知"
    
    now = datetime.now()
    diff = now - dt
    
    total_seconds = int(diff.total_seconds())
    
    if total_seconds < 60:
        return f"{total_seconds}秒前"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        return f"{minutes}分钟前"
    elif total_seconds < 86400:
        hours = total_seconds // 3600
        return f"{hours}小时前"
    else:
        days = total_seconds // 86400
        return f"{days}天前"


def is_recent_update(dt: datetime, threshold_minutes: int = 3) -> bool:
    """检查是否是最近更新的（默认3分钟内）"""
    if dt is None:
        return False
    
    now = datetime.now()
    diff = now - dt
    return diff.total_seconds() < (threshold_minutes * 60) 