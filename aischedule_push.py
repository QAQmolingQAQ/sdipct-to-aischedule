# -*- coding: utf-8 -*-
"""小爱课程表云端推送模块。

支持：
- MIUI/HyperOS 系统自带小爱课程表（UserInfo 含 userId/deviceId/authorization/userAgent）
- 小爱课程表独立版 App（含 appId/serviceToken）

推送流程（与官方 H5 一致）：
创建课表 -> 取配置 -> 改作息/开学日 -> 逐条添加课程。
接口移植自 Ruid24/neu-jwxt-to-aischedule，经实测可用。
"""
import base64
import hashlib

import requests

LESSON_COLORS = [
    '{"color":"#00A6F2","background":"#E5F4FF"}',
    '{"color":"#FC6B50","background":"#FDEBDE"}',
    '{"color":"#3CB3C8","background":"#DEFBF8"}',
    '{"color":"#7D7AEA","background":"#EDEDFF"}',
    '{"color":"#FF9900","background":"#FCEBCD"}',
    '{"color":"#EF5B75","background":"#FFEFF0"}',
    '{"color":"#5B8EFF","background":"#EAF1FF"}',
    '{"color":"#F067BB","background":"#FFEDF8"}',
    '{"color":"#29BBAA","background":"#E2F8F3"}',
    '{"color":"#CBA713","background":"#FFF8C8"}',
    '{"color":"#B967E3","background":"#F9EDFF"}',
    '{"color":"#6E8ADA","background":"#F3F2FD"}',
]


def _color_index(name):
    # 用 md5 取稳定的颜色，避免 Python hash 每次进程随机化
    h = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16)
    return h % len(LESSON_COLORS)


class PushError(RuntimeError):
    pass


class AiSchedulePusher:
    def __init__(self, userinfo: dict):
        self.info = userinfo
        self._resolve_auth()

    def _resolve_auth(self):
        info = self.info
        # MIUI 系统自带版
        if info.get("userId") and info.get("authorization") and info.get("userAgent"):
            self.user_id = info["userId"]
            if self.user_id == 0:
                raise PushError("userId 无效，请确认已登录小爱课程表")
            self.device_id = info["deviceId"]
            self.authorization = info["authorization"]
            self.user_agent = info["userAgent"]
            self.url_root = "https://i.xiaomixiaoai.com"
            self.source_name = "course-app-miui"
            self.kind = "MIUI系统自带小爱课程表"
            return
        # 独立版 App
        if info.get("serviceToken"):
            app_id = info.get("appId")
            token = info["serviceToken"]
            if not token:
                raise PushError("serviceToken 无效，请确认已登录")
            scope = base64.b64encode(
                json_dumps({"d": info["deviceId"]}).encode("utf-8")).decode("ascii")
            self.user_id = info.get("userId", 0)
            self.device_id = info["deviceId"]
            self.authorization = (
                f"AO-TOKEN-V1 dev_app_id:{app_id},scope_data:{scope},"
                f"access_token:{token}")
            self.user_agent = ""
            self.url_root = "https://i.ai.mi.com"
            self.source_name = "course-app-aiSchedule"
            self.kind = "小爱课程表独立版"
            return
        raise PushError("UserInfo 字段缺失，无法识别来源")

    def _headers(self, with_origin=False):
        h = {"content-type": "application/json",
             "access-control-allow-origin": "true"}
        if self.kind.startswith("MIUI"):
            h["user-agent"] = self.user_agent
            h["authorization"] = self.authorization
            if with_origin:
                h["accept"] = "application/json"
                h["origin"] = "https://i.xiaomixiaoai.com"
                h["referer"] = ("https://i.xiaomixiaoai.com/h5/"
                                "precache/ai-schedule/")
        else:
            h["accept"] = "application/json"
            h["authorization"] = self.authorization
        return h

    def create_table(self, name):
        r = requests.post(
            f"{self.url_root}/course-multi-auth/table",
            headers=self._headers(),
            json={"name": name, "current": 0, "sourceName": self.source_name},
            timeout=20).json()
        if r.get("code") != 0:
            desc = r.get("desc", "")
            if desc == "course table name exist":
                raise PushError(f"已存在同名课表，请先在 App 中删除：{name}")
            if desc == "table num over max size":
                raise PushError("课表数量已达上限，请在 App 中删除旧课表")
            raise PushError(f"创建课表失败：{r.get('code')} {desc}")
        ct_id = r["data"]
        if ct_id == "0":
            raise PushError(f"创建课表失败：{r.get('desc')}")
        return ct_id

    def configure_table(self, ct_id, name, sections, first_day, total_week,
                        morning_num=4, afternoon_num=4, night_num=2):
        r = requests.get(
            f"{self.url_root}/course-multi-auth/table"
            f"?ctId={ct_id}&sourceName={self.source_name}",
            headers={"content-type": "application/json",
                     "user-agent": self.user_agent,
                     "authorization": self.authorization},
            timeout=20).json()
        if r.get("code") != 0:
            raise PushError(f"获取课表配置失败：{r.get('desc')}")
        setting_id = r["data"]["setting"]["id"]

        extend = json_dumps({
            "startSemester": first_day,
            "degree": "本科/专科",
            "showNotInWeek": True,
            "bgSetting": {"name": "default", "opacity": 1},
        })
        r = requests.put(
            f"{self.url_root}/course-multi-auth/table",
            headers=self._headers(with_origin=True),
            json={
                "ctId": ct_id, "deviceId": self.device_id, "name": name,
                "sourceName": self.source_name, "userId": self.user_id,
                "setting": {
                    "afternoonNum": afternoon_num, "extend": extend,
                    "id": setting_id,
                    "isWeekend": 1, "morningNum": morning_num,
                    "nightNum": night_num,
                    "presentWeek": 1, "school": "{}",
                    "sections": json_dumps(sections), "speak": 1,
                    "startSemester": first_day, "totalWeek": total_week,
                    "weekStart": 7,
                },
            },
            timeout=20).json()
        if r.get("code") != 0:
            raise PushError(f"修改课表配置失败：{r.get('code')} {r.get('desc')}")

    def add_course(self, ct_id, course):
        body = {
            "ctId": ct_id,
            "course": {
                "name": course["name"],
                "position": course["position"],
                "teacher": course["teacher"],
                "extend": "",
                "weeks": ",".join(str(w) for w in course["weeks"]),
                "day": course["day"],
                "style": LESSON_COLORS[_color_index(course["name"])],
                "sections": ",".join(str(s) for s in course["sections"]),
            },
            "userId": self.user_id,
            "deviceId": self.device_id,
            "sourceName": self.source_name,
        }
        r = requests.post(
            f"{self.url_root}/course-multi-auth/courseInfo"
            f"?sourceName={self.source_name}",
            headers=self._headers(with_origin=True), json=body, timeout=20).json()
        return r

    def push_all(self, courses, name, sections, first_day, total_week=20,
                 morning_num=4, afternoon_num=4, night_num=2, log=print):
        log(f"识别来源：{self.kind}")
        ct_id = self.create_table(name)
        log(f"课表创建成功：{name} (id={ct_id})")
        self.configure_table(ct_id, name, sections, first_day, total_week,
                             morning_num, afternoon_num, night_num)
        log("作息时间与开学日期设置成功")

        ok, overlap, fail = 0, [], []
        for i, c in enumerate(courses, 1):
            r = self.add_course(ct_id, c)
            if r.get("code") == 0:
                ok += 1
                log(f"[{i}/{len(courses)}] 成功 {c['name']} 周{c['day']} "
                    f"第{c['sections'][0]}节")
            elif r.get("desc") == "course info has overlap":
                overlap.append(c)
                log(f"[{i}] 时间冲突跳过：{c['name']} 周{c['day']} "
                    f"第{','.join(map(str, c['sections']))}节")
            else:
                fail.append((c, r))
                log(f"[{i}] 失败：{r.get('code')} {r.get('desc')} {c['name']}")
        return {"ok": ok, "overlap": overlap, "fail": fail, "ctId": ct_id}


def json_dumps(obj):
    # 紧凑 JSON，分隔符与官方一致
    import json
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
