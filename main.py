import asyncio
import logging
import sys
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint
from api_client import XIVPFApiClient
from monitor import XIVPFMonitor
from notifier import Notifier
from config import Config, FilterConfig, PRESET_FILTERS
from models import FilterCondition
from time_utils import format_local_time, get_time_ago_str, is_recent_update

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('xivpf_monitor.log', encoding='utf-8'),
    ]
)

logger = logging.getLogger(__name__)

console = Console()


class XIVPFMonitorApp:
    def __init__(self):
        self.config = Config.load_from_file()
        self.api_client: Optional[XIVPFApiClient] = None
        self.monitor: Optional[XIVPFMonitor] = None
        self.notifier = Notifier(self.config.monitor.enable_system_notification)
        self.running = False
        
    async def initialize(self):
        """初始化应用"""
        self.api_client = XIVPFApiClient(self.config.monitor.base_url)
        await self.api_client.__aenter__()
        
        self.monitor = XIVPFMonitor(
            self.api_client,
            self.notifier,
            self.config.monitor.check_interval,
            self.config.monitor.expire_threshold
        )
        
        # 恢复监视目标
        for listing_id in self.config.monitor_targets:
            await self.monitor.add_monitor_target(listing_id)
            
    async def cleanup(self):
        """清理资源"""
        if self.api_client:
            await self.api_client.__aexit__(None, None, None)
            
    def show_main_menu(self):
        """显示主菜单"""
        console.clear()
        console.print(Panel(
            "[bold cyan]XIVPF 招募监视器[/bold cyan]\n"
            "[dim]监视 Final Fantasy XIV 招募信息[/dim]",
            style="cyan"
        ))
        
        console.print("\n[bold]主菜单:[/bold]")
        console.print("1. 开始监视")
        console.print("2. 管理过滤器")
        console.print("3. 管理监视目标")
        console.print("4. 搜索招募")
        console.print("5. 设置")
        console.print("6. 退出")
        
    def show_filters(self):
        """显示过滤器列表"""
        if not self.config.filters:
            console.print("[yellow]还没有设置过滤器[/yellow]")
            return
            
        table = Table(title="过滤器列表")
        table.add_column("序号", style="cyan")
        table.add_column("名称", style="green")
        table.add_column("状态", style="yellow")
        table.add_column("条件", style="blue")
        
        for i, filter_config in enumerate(self.config.filters, 1):
            status = "✓ 启用" if filter_config.enabled else "✗ 禁用"
            conditions = []
            cond = filter_config.condition
            
            if cond.category:
                conditions.append(f"分类={cond.category}")
            if cond.datacenter:
                conditions.append(f"大区={cond.datacenter}")
            if cond.world:
                conditions.append(f"服务器={cond.world}")
            if cond.search:
                conditions.append(f"搜索={cond.search}")
            if cond.jobs:
                conditions.append(f"职业={cond.jobs}")
            if cond.duty:
                conditions.append(f"副本={cond.duty}")
            if cond.exclude_jobs:
                from job_mappings import JOB_ID_TO_CODE, get_job_names_from_codes
                excluded_codes = [JOB_ID_TO_CODE.get(job_id, str(job_id)) for job_id in cond.exclude_jobs]
                excluded_names = get_job_names_from_codes(excluded_codes)
                conditions.append(f"排除职业={', '.join(excluded_names)}")
            if cond.min_slots_available:
                conditions.append(f"最少空位={cond.min_slots_available}")
            if cond.max_slots_filled:
                conditions.append(f"最多已填={cond.max_slots_filled}")
                
            table.add_row(
                str(i),
                filter_config.name,
                status,
                ", ".join(conditions) or "无"
            )
            
        console.print(table)
        
    async def add_filter(self):
        """添加过滤器"""
        console.print("\n[bold]添加过滤器[/bold]")
        
        # 询问是否使用预设
        use_preset = Confirm.ask("是否使用预设过滤器？")
        
        if use_preset:
            console.print("\n预设过滤器:")
            for i, preset in enumerate(PRESET_FILTERS, 1):
                console.print(f"{i}. {preset.name}")
                
            choice = IntPrompt.ask("选择预设", default=1)
            if 1 <= choice <= len(PRESET_FILTERS):
                preset = PRESET_FILTERS[choice - 1]
                self.config.add_filter(preset.name, preset.condition)
                console.print(f"[green]已添加过滤器: {preset.name}[/green]")
                self.config.save_to_file()
                return
                
        # 手动创建过滤器
        name = Prompt.ask("过滤器名称")
        condition = FilterCondition()
        
        # 设置条件
        if Confirm.ask("设置分类？", default=False):
            category = Prompt.ask("分类 (如: HighEndDuty, None)")
            condition.category = category
            
        if Confirm.ask("设置大区？", default=False):
            datacenter = Prompt.ask("大区 (如: 豆豆柴, 猫小胖, 莫古力, 陆行鸟)")
            condition.datacenter = datacenter
            
        if Confirm.ask("设置服务器？", default=False):
            world = Prompt.ask("服务器 (如: 水晶塔, 紫水栈桥)")
            condition.world = world
            
        if Confirm.ask("设置搜索关键字？", default=False):
            search = Prompt.ask("搜索关键字")
            condition.search = search
            
# 移除职业过滤选项，因为API的jobs参数是过滤开放职业，一般没有用处
        # if Confirm.ask("设置职业过滤？", default=False):
        #     jobs_str = Prompt.ask("职业ID列表 (逗号分隔，如: 1,2,8)")
        #     condition.jobs = [int(j.strip()) for j in jobs_str.split(",")]
            
        if Confirm.ask("设置副本过滤？", default=False):
            duty_str = Prompt.ask("副本ID列表 (逗号分隔，如: 1006,1007)")
            condition.duty = [int(d.strip()) for d in duty_str.split(",")]
            
        # 高级条件
        if Confirm.ask("设置高级条件？", default=False):
            if Confirm.ask("设置最少空位数？", default=False):
                condition.min_slots_available = IntPrompt.ask("最少空位数", default=1)
                
            if Confirm.ask("设置最多已填充位数？", default=False):
                condition.max_slots_filled = IntPrompt.ask("最多已填充位数", default=7)
                
            if Confirm.ask("排除已有特定职业的招募？", default=False):
                console.print("\n[yellow]常用职业代码：[/yellow]")
                console.print("坦克: PLD(骑士) WAR(战士) DRK(暗黑) GNB(绝枪)")
                console.print("治疗: WHM(白魔) SCH(学者) AST(占星) SGE(贤者)")
                console.print("近战: DRG(龙骑) MNK(武僧) NIN(忍者) SAM(武士) RPR(钐镰) VPR(蝰蛇)")
                console.print("远程: BRD(诗人) MCH(机工) DNC(舞者)")
                console.print("法师: BLM(黑魔) SMN(召唤) RDM(赤魔) PCT(绘灵)")
                
                exclude_jobs_str = Prompt.ask("要排除的职业代码 (空格分隔，如: BLM WHM DRG)", default="")
                if exclude_jobs_str:
                    from job_mappings import get_job_codes_from_string, get_job_ids_from_codes
                    job_codes = get_job_codes_from_string(exclude_jobs_str)
                    condition.exclude_jobs = get_job_ids_from_codes(job_codes)
                    
                    from job_mappings import get_job_names_from_codes
                    job_names = get_job_names_from_codes(job_codes)
                    console.print(f"[green]将排除已有以下职业的招募: {', '.join(job_names)}[/green]")
                    
            if Confirm.ask("设置招募内容关键词过滤？", default=False):
                console.print("\n[yellow]输入关键词，用空格分隔，不区分大小写[/yellow]")
                console.print("[dim]例如: 速通 练习 固定队 周本[/dim]")
                keywords = Prompt.ask("关键词", default="")
                if keywords.strip():
                    condition.content_keywords = keywords.strip()
                    console.print(f"[green]将只显示包含以下关键词的招募: {keywords}[/green]")
                
        self.config.add_filter(name, condition)
        console.print(f"[green]已添加过滤器: {name}[/green]")
        self.config.save_to_file()
        
    async def manage_filters(self):
        """管理过滤器"""
        while True:
            console.clear()
            console.print(Panel("[bold]过滤器管理[/bold]", style="cyan"))
            self.show_filters()
            
            console.print("\n操作:")
            console.print("1. 添加过滤器")
            console.print("2. 删除过滤器")
            console.print("3. 启用/禁用过滤器")
            console.print("4. 返回主菜单")
            
            choice = Prompt.ask("选择操作", default="4")
            
            if choice == "1":
                await self.add_filter()
            elif choice == "2":
                if self.config.filters:
                    idx = IntPrompt.ask("输入要删除的过滤器序号") - 1
                    if 0 <= idx < len(self.config.filters):
                        name = self.config.filters[idx].name
                        self.config.remove_filter(name)
                        console.print(f"[red]已删除过滤器: {name}[/red]")
                        self.config.save_to_file()
            elif choice == "3":
                if self.config.filters:
                    idx = IntPrompt.ask("输入要切换的过滤器序号") - 1
                    if 0 <= idx < len(self.config.filters):
                        name = self.config.filters[idx].name
                        self.config.toggle_filter(name)
                        console.print(f"[yellow]已切换过滤器状态: {name}[/yellow]")
                        self.config.save_to_file()
            elif choice == "4":
                break
                
            if choice != "4":
                Prompt.ask("\n按回车继续...")
                
    async def manage_monitor_targets(self):
        """管理监视目标"""
        while True:
            console.clear()
            console.print(Panel("[bold]监视目标管理[/bold]", style="cyan"))
            
            if self.config.monitor_targets:
                console.print("当前监视目标:")
                for i, target_id in enumerate(self.config.monitor_targets, 1):
                    console.print(f"{i}. 招募ID: {target_id}")
            else:
                console.print("[yellow]还没有监视目标[/yellow]")
                
            console.print("\n操作:")
            console.print("1. 添加监视目标")
            console.print("2. 删除监视目标")
            console.print("3. 返回主菜单")
            
            choice = Prompt.ask("选择操作", default="3")
            
            if choice == "1":
                listing_id = IntPrompt.ask("输入要监视的招募ID")
                if self.monitor:
                    await self.monitor.add_monitor_target(listing_id)
                self.config.add_monitor_target(listing_id)
                self.config.save_to_file()
            elif choice == "2":
                if self.config.monitor_targets:
                    idx = IntPrompt.ask("输入要删除的序号") - 1
                    if 0 <= idx < len(self.config.monitor_targets):
                        target_id = self.config.monitor_targets[idx]
                        if self.monitor:
                            self.monitor.remove_monitor_target(target_id)
                        self.config.remove_monitor_target(target_id)
                        self.config.save_to_file()
                        console.print(f"[red]已删除监视目标: {target_id}[/red]")
            elif choice == "3":
                break
                
            if choice != "3":
                Prompt.ask("\n按回车继续...")
                
    async def search_listings(self):
        """搜索招募"""
        console.clear()
        console.print(Panel("[bold]搜索招募[/bold]", style="cyan"))
        
        # 选择搜索方式
        console.print("搜索方式:")
        console.print("1. 使用现有过滤器")
        console.print("2. 创建临时过滤条件")
        
        search_mode = Prompt.ask("选择搜索方式", choices=["1", "2"], default="1")
        
        condition = None
        filter_name = "临时搜索"
        
        if search_mode == "1" and self.config.filters:
            # 使用现有过滤器
            console.print("\n现有过滤器:")
            for i, filter_config in enumerate(self.config.filters, 1):
                status = "✓" if filter_config.enabled else "✗"
                console.print(f"{i}. {status} {filter_config.name}")
                
            filter_choice = IntPrompt.ask("选择过滤器", default=1)
            if 1 <= filter_choice <= len(self.config.filters):
                selected_filter = self.config.filters[filter_choice - 1]
                condition = selected_filter.condition
                filter_name = selected_filter.name
        
        if condition is None:
            # 创建临时过滤条件
            console.print("\n[bold]创建临时过滤条件[/bold]")
            condition = FilterCondition()
            
            search_term = Prompt.ask("搜索关键字 (可选)", default="")
            if search_term:
                condition.search = search_term
                
            datacenter = Prompt.ask("大区 (可选)", default="")
            if datacenter:
                condition.datacenter = datacenter
                
            world = Prompt.ask("服务器 (可选)", default="")
            if world:
                condition.world = world
                
            category = Prompt.ask("分类 (可选，如: HighEndDuty)", default="")
            if category:
                condition.category = category
            
        # 执行搜索
        console.print(f"\n[yellow]使用过滤器 '{filter_name}' 搜索中...[/yellow]")
        listings = await self.monitor.search_listings(
            condition,
            filter_name,
            notify=False
        )
        
        if listings:
            # 使用统一的表格显示函数
            self.notifier.show_listings_table(
                listings, 
                f"搜索结果 ({filter_name})", 
                max_count=20
            )
            
            # 询问是否添加到监视
            if Confirm.ask("\n是否将某个招募添加到监视？"):
                listing_id = IntPrompt.ask("输入招募ID")
                if self.monitor:
                    await self.monitor.add_monitor_target(listing_id)
                self.config.add_monitor_target(listing_id)
                self.config.save_to_file()
        else:
            console.print("[red]没有找到匹配的招募[/red]")
            
        Prompt.ask("\n按回车继续...")
        
    async def settings(self):
        """设置"""
        console.clear()
        console.print(Panel("[bold]设置[/bold]", style="cyan"))
        
        console.print(f"当前设置:")
        console.print(f"- 检查间隔: {self.config.monitor.check_interval} 秒")
        console.print(f"- 过期阈值: {self.config.monitor.expire_threshold} 秒")
        console.print(f"- 系统通知: {'启用' if self.config.monitor.enable_system_notification else '禁用'}")
        console.print(f"- API地址: {self.config.monitor.base_url}")
        
        console.print("\n[yellow]API缓存信息:[/yellow]")
        console.print("- API服务器缓存: 30秒（相同查询参数）")
        console.print("- Cloudflare缓存: 30秒")
        console.print("- 最大数据延迟: 60秒")
        console.print("- 建议检查间隔: ≥90秒")
        
        console.print("\n操作选项:")
        console.print("1. 修改设置")
        console.print("2. 清除通知记录")
        console.print("3. 清除显示记录")
        console.print("4. 返回主菜单")
        
        choice = Prompt.ask("选择操作", choices=["1", "2", "3", "4"], default="4")
        
        if choice == "1":
            # 修改设置
            new_interval = IntPrompt.ask(
                "检查间隔（秒）",
                default=self.config.monitor.check_interval
            )
            
            # 提醒用户关于缓存的影响
            if new_interval < 90:
                console.print("[yellow]警告: 检查间隔少于90秒可能无法获取最新数据（由于API缓存机制）[/yellow]")
                if not Confirm.ask("是否继续？"):
                    return
                    
            self.config.monitor.check_interval = new_interval
            self.config.monitor.expire_threshold = IntPrompt.ask(
                "过期阈值（秒）",
                default=self.config.monitor.expire_threshold
            )
            self.config.monitor.enable_system_notification = Confirm.ask(
                "启用系统通知？",
                default=self.config.monitor.enable_system_notification
            )
            
            self.config.save_to_file()
            console.print("[green]设置已保存[/green]")
            
            # 更新监视器设置
            if self.monitor:
                self.monitor.check_interval = self.config.monitor.check_interval
                self.monitor.expire_threshold = self.config.monitor.expire_threshold
            self.notifier.enable_system_notification = self.config.monitor.enable_system_notification
        elif choice == "2":
            # 清除通知记录
            if self.monitor:
                self.monitor.clear_notified_listings()
            else:
                console.print("[yellow]监视器未初始化[/yellow]")
        elif choice == "3":
            # 清除显示记录
            if self.monitor:
                self.monitor.clear_displayed_listings()
            else:
                console.print("[yellow]监视器未初始化[/yellow]")
                
        if choice != "4":
            Prompt.ask("\n按回车继续...")
        
    async def start_monitoring(self):
        """开始监视"""
        console.clear()
        console.print(Panel(
            "[bold green]监视运行中[/bold green]\n"
            "[dim]在下方输入 'q' 并按回车停止监视[/dim]\n"
            "[dim]输入 'status' 查看状态[/dim]\n"
            "[dim]输入 'clear' 清除显示记录[/dim]",
            style="green"
        ))
        
        # 获取启用的过滤器
        enabled_filters = self.config.get_enabled_filters()
        if not enabled_filters:
            console.print("[yellow]警告: 没有启用的过滤器[/yellow]")
            
        filter_conditions = [
            (f.condition, f.name) for f in enabled_filters
        ]
        
        # 创建监视任务和输入监听任务
        import asyncio
        
        async def input_listener():
            """监听用户输入"""
            loop = asyncio.get_event_loop()
            
            while self.monitor.running:
                try:
                    # 异步读取用户输入
                    user_input = await loop.run_in_executor(None, input, "")
                    user_input = user_input.strip().lower()
                    
                    if user_input == 'q' or user_input == 'quit':
                        self.monitor.stop_monitoring()
                        break
                    elif user_input == 'status':
                        console.print(f"[blue]状态: 监视运行中，监控目标: {len(self.monitor.monitor_targets)}个[/blue]")
                    elif user_input == 'clear':
                        self.monitor.clear_displayed_listings()
                    elif user_input == 'help':
                        console.print("[blue]可用命令: q(退出), status(状态), clear(清除显示记录), help(帮助)[/blue]")
                    elif user_input:
                        console.print(f"[yellow]未知命令: {user_input}，输入 'help' 查看可用命令[/yellow]")
                        
                except EOFError:
                    # 处理Ctrl+D
                    self.monitor.stop_monitoring()
                    break
                except Exception as e:
                    # 输入异常，继续监听
                    logger.debug(f"Input error: {e}")
                    
        try:
            # 同时运行监视和输入监听
            await asyncio.gather(
                self.monitor.continuous_search(filter_conditions),
                input_listener()
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]收到中断信号，停止监视...[/yellow]")
            self.monitor.stop_monitoring()
        finally:
            console.print("[green]监视已停止[/green]")
            
    async def run(self):
        """运行应用"""
        try:
            await self.initialize()
            
            while True:
                self.show_main_menu()
                choice = Prompt.ask("\n选择操作", default="1")
                
                if choice == "1":
                    await self.start_monitoring()
                elif choice == "2":
                    await self.manage_filters()
                elif choice == "3":
                    await self.manage_monitor_targets()
                elif choice == "4":
                    await self.search_listings()
                elif choice == "5":
                    await self.settings()
                elif choice == "6":
                    if Confirm.ask("确定要退出吗？"):
                        break
                        
        except KeyboardInterrupt:
            console.print("\n[yellow]程序被中断[/yellow]")
        except Exception as e:
            console.print(f"\n[red]发生错误: {e}[/red]")
            logging.exception("Application error")
        finally:
            await self.cleanup()
            console.print("[green]再见！[/green]")


async def main():
    """主函数"""
    app = XIVPFMonitorApp()
    await app.run()


if __name__ == "__main__":
    # Windows 系统需要设置事件循环策略
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main()) 