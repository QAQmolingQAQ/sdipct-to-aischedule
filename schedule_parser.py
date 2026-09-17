# -*- coding: utf-8 -*-
"""教务系统课表 JSON 解析模块。

输入：教务系统“我的课表”接口返回的原始 JSON（含 data 数组的那条，即样例 2.json）。
输出：统一的课程列表 [
    {"name","position","teacher","weeks":[int],"day":int,"sections":[int]}, ...
]

说明：
- 每条记录代表一个固定时间槽（星期 xq + 起止节次 ps/pe）。
- zc 字段为该时间槽实际上课的周次（逗号分隔）。
- 当不同周在不同教室时，jxcdmc2 形如 “教室-周次,教室-周次”，据此按教室拆分。
- 最后将 同课程/同天/同节次/同教室/同老师 的记录合并周次。
"""
import re


def _parse_nums(value):
    """逗号分隔数字字符串 -> int 列表。"""
    if value is None:
        return []
    return [int(x) for x in str(value).split(",") if x.strip().isdigit()]


def _sections(ps, pe):
    """根据起止节次生成连续节次列表。"""
    try:
        start, end = int(ps), int(pe)
    except (TypeError, ValueError):
        return []
    if start <= 0 or end <= 0:
        return []
    return list(range(start, end + 1))


def _parse_room_weeks(jxcdmc2):
    """解析 jxcdmc2，返回 {教室: [周次,...]}；无法解析返回 None。

    形如 "4-409-1,4-409-2,..."，教室名自身可能含横杠，
    故用“最后一个 -数字”提取周次。
    """
    if not jxcdmc2:
        return None
    room_weeks = {}
    for part in str(jxcdmc2).split(","):
        m = re.match(r"^(.+)-(\d+)$", part.strip())
        if not m:
            continue
        room, week = m.group(1), int(m.group(2))
        room_weeks.setdefault(room, []).append(week)
    return room_weeks or None


def parse_schedule(raw):
    """解析原始 JSON（dict 或已解析的 data 列表）。"""
    # 兼容 {"code":0,"data":[...]} 或直接 [...]
    if isinstance(raw, dict):
        courses = raw.get("data", [])
    elif isinstance(raw, list):
        # 可能是 1.json 那种“按周展开”的列表
        courses = raw
    else:
        raise ValueError("不支持的课表数据格式")

    items = []
    for c in courses:
        # 跳过选课/考试等非课程条目（lx=xk 为选课安排；无节次信息的也跳过）
        if not isinstance(c, dict):
            continue
        if c.get("lx") == "xk":
            continue

        day = int(c["xq"]) if str(c.get("xq", "")).isdigit() else 0
        sections = _sections(c.get("ps"), c.get("pe"))
        weeks = _parse_nums(c.get("zc"))
        if not (1 <= day <= 7) or not sections or not weeks:
            continue

        name = c.get("kcmc", "") or ""
        teacher = c.get("teaxms", "") or ""
        room_weeks = _parse_room_weeks(c.get("jxcdmc2"))

        if room_weeks and len(room_weeks) > 1:
            # 多个教室：按教室拆分，仅保留该教室确实有课的周次
            for room, rw in room_weeks.items():
                valid = sorted(set(rw) & set(weeks))
                if valid:
                    items.append({
                        "name": name, "position": room, "teacher": teacher,
                        "weeks": valid, "day": day, "sections": sections,
                    })
        else:
            position = c.get("jxcdmc", "") or ""
            if room_weeks and len(room_weeks) == 1:
                position = next(iter(room_weeks.keys()))
            items.append({
                "name": name, "position": position, "teacher": teacher,
                "weeks": sorted(set(weeks)), "day": day, "sections": sections,
            })

    return _merge(_drop_summary(items))


def _teacher_tokens(teacher):
    """教师字段 -> 姓名集合（兼容中英文逗号）。"""
    return {t.strip() for t in str(teacher).replace("，", ",").split(",")
            if t.strip()}


def _drop_summary(items):
    """丢弃教务系统给出的“多周汇总”冗余条目。

    同一(课程/星期/节次/教室)下，若已存在单周记录，且某多周记录的周次与
    教师姓名都被这些单周记录完全覆盖，则该多周记录只是汇总行（例如
    “李晓玮,徐贺睿 / 周1,6,8,11,13,15”是“李晓玮 周1,6”与
    “徐贺睿 周8,11,13,15”的汇总），予以丢弃。单周记录才是真实授课安排。
    未被完全覆盖的多周记录仍然保留，避免误删真实数据。
    """
    groups = {}
    for it in items:
        key = (it["name"], it["day"], tuple(it["sections"]), it["position"])
        groups.setdefault(key, []).append(it)

    result = []
    for group in groups.values():
        singles = [it for it in group if len(it["weeks"]) == 1]
        if not singles:
            result.extend(group)
            continue
        single_weeks = set()
        single_teachers = set()
        for it in singles:
            single_weeks.update(it["weeks"])
            single_teachers.update(_teacher_tokens(it["teacher"]))
        for it in group:
            if len(it["weeks"]) == 1:
                result.append(it)
            elif not (set(it["weeks"]) <= single_weeks
                      and _teacher_tokens(it["teacher"]) <= single_teachers):
                result.append(it)
    return result


def _merge(items):
    """合并同课程/同天/同节次/同教室/同老师的周次。"""
    merged = {}
    order = []
    for it in items:
        key = (it["name"], it["day"], tuple(it["sections"]),
               it["position"], it["teacher"])
        if key not in merged:
            merged[key] = {
                "name": it["name"], "position": it["position"],
                "teacher": it["teacher"], "day": it["day"],
                "sections": list(it["sections"]), "weeks": set(it["weeks"]),
            }
            order.append(key)
        else:
            merged[key]["weeks"].update(it["weeks"])

    result = []
    for key in order:
        m = merged[key]
        result.append({
            "name": m["name"],
            "position": m["position"],
            "teacher": m["teacher"],
            "weeks": sorted(m["weeks"]),
            "day": m["day"],
            "sections": m["sections"],
        })
    result.sort(key=lambda x: (x["day"], x["sections"][0]))
    return result
