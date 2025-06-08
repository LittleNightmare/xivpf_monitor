import logging
from typing import List, Optional
from datetime import datetime
from plyer import notification
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from models import Listing, NotificationType
from time_utils import format_local_time, get_time_ago_str, is_recent_update
import platform

logger = logging.getLogger(__name__)
console = Console()


class Notifier:
    def __init__(self, enable_system_notification: bool = True):
        self.enable_system_notification = enable_system_notification
        self.is_windows = platform.system() == "Windows"
        
    def show_listings_table(self, listings: List[Listing], title: str = "招募列表", max_count: int = 10):
        """显示招募列表表格"""
        if not listings:
            return
            
        console.print(f"\n[green]{title} ({len(listings)}个)[/green]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=12)
        table.add_column("玩家名", style="green")
        table.add_column("副本", style="blue")
        table.add_column("招募内容", style="magenta")
        table.add_column("空位", style="red")
        table.add_column("剩余时间", style="magenta")
        table.add_column("更新时间", style="magenta")
        
        for listing in listings[:max_count]:  # 限制显示数量
            time_left_min = int(listing.time_left / 60)
            # 使用相对时间显示更新时间
            time_ago = get_time_ago_str(listing.updated_at)
                
            # 如果是最近更新的，加上标记
            if is_recent_update(listing.updated_at, 2):  # 2分钟内
                time_display = f"{time_ago} 🔥"
            else:
                time_display = time_ago
                
            # 限制招募内容长度
            description = listing.description[:20] + "..." if len(listing.description) > 20 else listing.description
            
            table.add_row(
                str(listing.id),
                listing.name,
                listing.duty,
                description,
                f"{listing.slots_filled}/{listing.slots_available}",
                f"{time_left_min}分钟",
                time_display
            )
            
        console.print(table)
        
    def notify_found(self, listings: List[Listing], filter_name: str = "", enable_system_notification: bool = True):
        """通知找到匹配的招募"""
        if not listings:
            return
            
        # 控制台输出
        title = f"✓ 找到匹配的招募"
        if filter_name:
            title += f" ({filter_name})"
        
        self.show_listings_table(listings, title, max_count=10)
        
        # 系统通知 - 只有在启用系统通知且参数允许时才发送
        if self.enable_system_notification and enable_system_notification:
            try:
                title = f"找到 {len(listings)} 个招募"
                message = f"第一个招募: {listings[0].name} - {listings[0].duty}"
                if filter_name:
                    message += f"\n条件: {filter_name}"
                
                if hasattr(notification, 'notify') and notification.notify:
                    notification.notify(
                        title=title,
                        message=message,
                        app_name="XIVPF Monitor",
                        timeout=30
                    )
            except Exception as e:
                logger.error(f"System notification failed: {e}")
        elif not enable_system_notification:
            # 如果禁用了系统通知，显示提示信息
            console.print("[dim]💡 存在监视目标，已禁用搜索结果的系统通知[/dim]")
                
    def notify_expired(self, listing: Listing, reason: str = ""):
        """通知招募过期"""
        # 控制台输出
        console.print(f"\n[red]✗ 招募过期[/red]")
        console.print(Panel(
            f"[yellow]ID:[/yellow] {listing.id}\n"
            f"[yellow]名称:[/yellow] {listing.name}\n"
            f"[yellow]服务器:[/yellow] {listing.created_world}/{listing.datacenter}\n"
            f"[yellow]副本:[/yellow] {listing.duty}\n"
            f"[yellow]原因:[/yellow] {reason or '招募已结束或删除'}",
            title="过期招募",
            border_style="red"
        ))
        # 系统通知
        if self.enable_system_notification:
            try:
                if hasattr(notification, 'notify') and notification.notify:
                    notification.notify(
                        title="招募过期",
                        message=f"{listing.name} - {listing.duty}\n{reason}",
                        app_name="XIVPF Monitor",
                        timeout=30
                    )
            except Exception as e:
                logger.error(f"System notification failed: {e}")
                
    def notify_updated(self, listing: Listing, changes: str = ""):
        """通知招募更新"""
        # 控制台输出
        console.print(f"\n[blue]↻ 招募更新[/blue]")
        console.print(Panel(
            f"[yellow]ID:[/yellow] {listing.id}\n"
            f"[yellow]玩家名:[/yellow] {listing.name}\n"
            f"[yellow]服务器:[/yellow] {listing.created_world}/{listing.datacenter}\n"
            f"[yellow]副本:[/yellow] {listing.duty}\n"
            f"[yellow]内容:[/yellow] {listing.description}\n"
            f"[yellow]当前人数:[/yellow] {listing.slots_filled}/{listing.slots_available}\n"
            f"[yellow]剩余时间:[/yellow] {int(listing.time_left / 60)}分钟\n"
            f"[yellow]更新内容:[/yellow] {changes or '未知'}",
            title="招募更新",
            border_style="blue"
        ))
        
        # 招募更新不发送系统通知，只有过期/消失时才发送
        logger.info(f"Listing {listing.id} updated: {changes}")
                
    def show_status(self, message: str, style: str = ""):
        """显示状态消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        if style:
            console.print(f"[dim]{timestamp}[/dim] [{style}]{message}[/{style}]")
        else:
            console.print(f"[dim]{timestamp}[/dim] {message}") 