import csv
import os

# 从游戏数据表加载职业映射
def load_job_mappings():
    """从ClassJob.csv加载职业映射表"""
    job_code_to_id = {}
    job_id_to_code = {}
    job_name_map = {}
    
    csv_path = os.path.join("data", "ClassJob.csv")
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            lines = list(reader)
            
            # 跳过前三行（key行、列名行、类型定义行）
            for line in lines[3:]:
                if len(line) > 31:  # 确保有足够的列
                    try:
                        job_id = int(line[0])  # key列
                        job_name = line[1]     # Name列
                        job_code = line[2]     # Abbreviation列
                        
                        # 只处理有效的职业代码（排除空字符串和特殊情况）
                        if job_code and job_code != "" and job_name != "冒险者":
                            job_code_to_id[job_code] = job_id
                            job_id_to_code[job_id] = job_code
                            job_name_map[job_code] = job_name
                    except (ValueError, IndexError):
                        # 跳过无法解析的行
                        continue
                        
    except FileNotFoundError:
        print(f"警告: 找不到 {csv_path} 文件，使用默认映射")
        # 如果文件不存在，使用基本的映射作为备用
        return _get_fallback_mappings()
    except Exception as e:
        print(f"警告: 读取职业数据文件失败: {e}，使用默认映射")
        return _get_fallback_mappings()
        
    return job_code_to_id, job_id_to_code, job_name_map

def _get_fallback_mappings():
    """备用的基础职业映射"""
    basic_mapping = {
        "GLA": 1, "PLD": 19, "MRD": 3, "WAR": 21, "DRK": 32, "GNB": 37,
        "PGL": 2, "MNK": 20, "LNC": 4, "DRG": 22, "ROG": 29, "NIN": 30,
        "SAM": 34, "RPR": 39, "VPR": 41, "ARC": 5, "BRD": 23, "MCH": 31,
        "DNC": 38, "THM": 7, "BLM": 25, "ACN": 26, "SMN": 27, "RDM": 35,
        "BLU": 36, "PCT": 42, "CNJ": 6, "WHM": 24, "SCH": 28, "AST": 33, "SGE": 40
    }
    basic_names = {
        "GLA": "剑术师", "PLD": "骑士", "MRD": "斧术师", "WAR": "战士",
        "DRK": "暗黑骑士", "GNB": "绝枪战士", "PGL": "格斗家", "MNK": "武僧",
        "LNC": "枪术师", "DRG": "龙骑士", "ROG": "双剑师", "NIN": "忍者",
        "SAM": "武士", "RPR": "钐镰客", "VPR": "蝰蛇剑士", "ARC": "弓箭手",
        "BRD": "吟游诗人", "MCH": "机工士", "DNC": "舞者", "THM": "咒术师",
        "BLM": "黑魔法师", "ACN": "秘术师", "SMN": "召唤师", "RDM": "赤魔法师",
        "BLU": "青魔法师", "PCT": "绘灵法师", "CNJ": "幻术师", "WHM": "白魔法师",
        "SCH": "学者", "AST": "占星术士", "SGE": "贤者"
    }
    return basic_mapping, {v: k for k, v in basic_mapping.items()}, basic_names

# 加载映射表
JOB_CODE_TO_ID, JOB_ID_TO_CODE, JOB_NAME_MAP = load_job_mappings()

def get_job_ids_from_codes(job_codes: list) -> list:
    """将职业代码列表转换为ID列表"""
    job_ids = []
    for code in job_codes:
        code = code.strip().upper()
        if code in JOB_CODE_TO_ID:
            job_ids.append(JOB_CODE_TO_ID[code])
    return job_ids

def get_job_codes_from_string(job_string: str) -> list:
    """从职业字符串中提取职业代码列表"""
    if not job_string:
        return []
    return [code.strip().upper() for code in job_string.split() if code.strip()]

def get_job_names_from_codes(job_codes: list) -> list:
    """获取职业代码对应的中文名称"""
    return [JOB_NAME_MAP.get(code.upper(), code) for code in job_codes] 