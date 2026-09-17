# 山东石油化工学院 教务系统配置（青果/强智风格 /new/ 系统）

# 教务系统首页（登录入口）
JWXT_URL = "https://jwxt.sdipct.edu.cn/"

# 登录成功后跳转的欢迎页（用于判断是否已登录）
WELCOME_URL = "https://jwxt.sdipct.edu.cn/new/welcome.page?ui=new"

# 个人课表页面（在浏览器中打开后会自动请求数据接口）
SCHEDULE_PAGE_URL = "https://jwxt.sdipct.edu.cn/new/student/xsgrkb/main.page"

# 课表数据接口（POST，按周请求：xnxqdm=学期, zc=周次, d1/d2=该周周一/周日）
SCHEDULE_API = "https://jwxt.sdipct.edu.cn/new/student/xsgrkb/getCalendarWeekDatas"

# 课表接口 URL 关键字（用于在浏览器网络请求中自动识别）
SCHEDULE_URL_KEYWORD = "getCalendarWeekDatas"

# 学年学期代码（202601 = 2026-2027 学年第一学期）
TERM_CODE = "202601"

# 判断 JSON 是否为课表数据的字段特征（命中即认定）
SCHEDULE_JSON_HINTS = ["kcmc", "jxcdmc", "teaxms", "jcdm", "xnxqdm"]

# 课表名称：由学期代码自动识别（202601 -> 2026-2027学年第一学期）
def _term_name(code):
    """学期代码 -> 小爱课表名称。如 202601 -> 2026-2027学年第一学期。"""
    c = str(code).strip()
    if len(c) == 6 and c.isdigit():
        year, seq = int(c[:4]), c[4:]
        half = "第一学期" if seq == "01" else "第二学期"
        return f"{year}-{year + 1}学年{half}"
    return f"{c}学期"


TABLE_NAME = _term_name(TERM_CODE)

# 开学日期兜底值（第1周周一）。
# 工具会优先从教务系统课表页自动读取真实开学日；读不到时才用此值。
FIRST_DAY = "2026-09-07"

# 总周数
TOTAL_WEEK = 20

# 一天各时段的节数（上午/下午/晚上），晚上只有 2 节
MORNING_NUM = 4
AFTERNOON_NUM = 4
NIGHT_NUM = 2

# 一周起始日：1=周一 ... 7=周日（与课程 day 字段编号一致）。
# 设为 1 表示“周一开学”，第1周从周一开始。
WEEK_START = 1

# 作息时间表（依据学校实际上下课时间，共 10 节，与 4/4/2 对应）
SECTIONS = [
    {"i": 1,  "s": "08:00", "e": "08:50"},
    {"i": 2,  "s": "09:00", "e": "09:50"},
    {"i": 3,  "s": "10:10", "e": "11:00"},
    {"i": 4,  "s": "11:10", "e": "12:00"},
    {"i": 5,  "s": "14:00", "e": "14:50"},
    {"i": 6,  "s": "15:00", "e": "15:50"},
    {"i": 7,  "s": "16:10", "e": "17:00"},
    {"i": 8,  "s": "17:10", "e": "18:00"},
    {"i": 9,  "s": "19:00", "e": "19:50"},
    {"i": 10, "s": "20:00", "e": "20:50"},
]
