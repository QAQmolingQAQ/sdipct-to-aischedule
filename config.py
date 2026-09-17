# 山东石油化工学院 教务系统配置（青果/强智风格 /new/ 系统）

# 教务系统首页（登录入口）
JWXT_URL = "https://jwxt.sdipct.edu.cn/"

# 登录成功后跳转的欢迎页（用于判断是否已登录）
WELCOME_URL = "https://jwxt.sdipct.edu.cn/new/welcome.page?ui=new"

# 个人课表页面（在浏览器中打开后会自动请求数据接口）
SCHEDULE_PAGE_URL = "https://jwxt.sdipct.edu.cn/new/student/xsgrkb/main.page"

# 课表数据接口（POST，学年学期 + 日期范围）
SCHEDULE_API = "https://jwxt.sdipct.edu.cn/new/student/xsgrkb/getCalendarWeekDatas"

# 课表接口 URL 关键字（用于在浏览器网络请求中自动识别）
SCHEDULE_URL_KEYWORD = "getCalendarWeekDatas"

# 学年学期代码（202601 = 2026-2027 学年第一学期）
TERM_CODE = "202601"

# 判断 JSON 是否为课表数据的字段特征（命中即认定）
SCHEDULE_JSON_HINTS = ["kcmc", "jxcdmc", "teaxms", "jcdm", "xnxqdm"]

# 课表名称（在小爱课程表中显示）
TABLE_NAME = "2026-2027学年第一学期"

# 开学日期（第1周周一），用于小爱课程表推算日期
FIRST_DAY = "2026-09-07"

# 总周数
TOTAL_WEEK = 20

# 作息时间表（依据学校实际上下课时间）
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
    {"i": 11, "s": "21:00", "e": "21:50"},
    {"i": 12, "s": "22:00", "e": "22:50"},
]
