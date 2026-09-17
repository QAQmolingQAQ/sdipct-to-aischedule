# -*- coding: utf-8 -*-
"""乘方教务学期日期工具。

getCalendarWeekDatas 按周请求，请求参数 d1 为“被查询周的周一”，
响应/上下文里能得到某记录所属周次 zc。因此：

    第1周周一 = d1 - 7 * (zc - 1) 天

开学日的在线推导直接在 main.build_fetch_all_js 内完成（以本周一为锚点，
请求本周拿到 zc 后反推）；本模块保留离线/测试用的纯函数。
"""
import re
from datetime import date, timedelta


def week_monday_from_d1(d1, week):
    """根据“某周周一 d1”和该周次 week，反推第1周周一（date）。"""
    if not d1 or not week:
        return None
    m = re.match(r"\s*(\d{4})\D(\d{1,2})\D(\d{1,2})", str(d1))
    if not m:
        return None
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return d - timedelta(days=7 * (int(week) - 1))


def fmt(d):
    return d.strftime("%Y-%m-%d") if d else None
