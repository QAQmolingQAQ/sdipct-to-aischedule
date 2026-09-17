# -*- coding: utf-8 -*-
"""山东石油化工学院 教务系统课表 -> 小爱课程表 一键导入工具。

流程：
启动独立浏览器 -> 用户登录教务系统 -> 自动捕获课表 JSON ->
解析预览 -> 读取小爱 UserInfo -> 推送到小爱课程表。

用法：
    python main.py                 # 完整流程（浏览器抓取 + 推送）
    python main.py --file x.json   # 用本地 F12 抓包 JSON 直接解析推送（不走浏览器）

仅提供学习辅助，导入结果请以教务系统为准。
"""
import argparse
import json
import os
import sys
import time

import config
from schedule_parser import parse_schedule
from aischedule_push import AiSchedulePusher, PushError
from cdp_browser import (find_browser, free_port, launch_browser, CDPClient)


def app_dir():
    return os.path.dirname(os.path.abspath(__file__))


def load_userinfo():
    """从 userinfo.json 读取小爱调试数据。"""
    path = os.path.join(app_dir(), "userinfo.json")
    if not os.path.exists(path):
        print("未找到 userinfo.json。")
        print("获取方法：小爱课程表 -> 右下角头像(设置) -> 滑到最底部 ->")
        print("在“开始新学期”下方空白处连点5次进入 Debug 页 ->")
        print("点击“获取 UserInfo” -> 复制，保存为项目下的 userinfo.json")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def show_preview(courses):
    day_name = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    print(f"\n共解析出 {len(courses)} 条课程安排：")
    for d in range(1, 8):
        day_courses = [c for c in courses if c["day"] == d]
        if not day_courses:
            continue
        print(f"【{day_name[d]}】")
        for c in day_courses:
            secs = (f"{c['sections'][0]}-{c['sections'][-1]}"
                    if len(c['sections']) > 1 else str(c['sections'][0]))
            print(f"  第{secs}节 {c['name']} | {c['teacher']} | "
                  f"{c['position']} | 第{','.join(map(str, c['weeks']))}周")
    print()


def save_backup(courses):
    path = os.path.join(app_dir(), f"schedule_{config.TERM_CODE}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(courses, f, ensure_ascii=False, indent=2)
    print(f"已保存课表备份：{path}")


def fetch_from_browser():
    browser = find_browser()
    if not browser:
        print("未找到 Edge 或 Chrome，请安装后重试。")
        sys.exit(1)

    port = free_port()
    profile = os.path.join(app_dir(), "browser_profile")
    print(f"正在启动浏览器（{os.path.basename(browser)}）...")
    proc = launch_browser(browser, profile, port, config.JWXT_URL)

    try:
        print("正在连接调试端口...")
        client = CDPClient(port)
    except Exception as e:
        proc.terminate()
        print(f"无法连接浏览器调试端口：{e}")
        sys.exit(1)

    print("请在打开的浏览器窗口中登录教务系统（账号密码或扫码）...")
    # 等待登录：URL 跳转到 welcome
    deadline = time.time() + 300
    logged = False
    while time.time() < deadline:
        try:
            url = client.current_url()
        except Exception:
            url = ""
        if "welcome" in url or "/new/" in url:
            logged = True
            break
        time.sleep(2)
    if not logged:
        print("等待登录超时，请重试。")
        proc.terminate()
        sys.exit(1)
    print("登录成功，正在打开个人课表页并抓取数据...")

    # 打开课表页，开始监听接口（先开监听再导航，避免漏掉请求）
    # 通过 JS 跳转
    client.eval(f'location.href="{config.SCHEDULE_PAGE_URL}"')
    time.sleep(2)
    # 若页面需要选择学期，再触发一次按周数据请求（多数系统进入即请求）
    try:
        raw = client.capture_schedule(
            config.SCHEDULE_URL_KEYWORD, config.SCHEDULE_JSON_HINTS, timeout=45)
    except TimeoutError:
        # 兜底：直接在页面上下文里 fetch 接口（带登录 Cookie）
        print("未监听到响应，尝试在页面内直接请求接口...")
        expr = f"""
        (async()=>{{
            const r = await fetch("{config.SCHEDULE_API}", {{
                method:'POST',
                headers:{{'content-type':'application/x-www-form-urlencoded; charset=UTF-8','x-requested-with':'XMLHttpRequest'}},
                body:'xnxqdm={config.TERM_CODE}&zc=&d1=&d2=',
                credentials:'include'
            }});
            return await r.text();
        }})()
        """
        body = client.eval(expr)
        raw = json.loads(body) if body else None

    client.close()
    proc.terminate()
    if raw is None:
        print("未能获取到课表数据。")
        sys.exit(1)

    # 保存原始数据备查
    raw_path = os.path.join(app_dir(), "last_raw.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    print(f"原始课表已保存：{raw_path}")
    return raw


def normalize_raw(raw):
    """统一成解析器能吃的结构。

    getCalendarWeekDatas 常见返回：
      - {"code":0,"data":[...]}
      - 按周日历包装的对象，真正的课程列表在 data 内部某处
    解析器会递归按字段特征识别，这里直接透传。
    """
    return raw


def main():
    parser = argparse.ArgumentParser(description="教务课表 -> 小爱课程表")
    parser.add_argument("--file", help="使用本地抓包 JSON，跳过浏览器抓取")
    parser.add_argument("--yes", action="store_true", help="解析后不询问直接推送")
    args = parser.parse_args()

    print("====== 山东石油化工学院 课表 -> 小爱课程表 导入工具 ======")
    print("提示：导入后请与教务系统核对，一切以教务系统显示为准。\n")

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            raw = json.load(f)
    else:
        raw = fetch_from_browser()

    raw = normalize_raw(raw)
    courses = parse_schedule(raw)
    if not courses:
        print("未解析出任何课程，请检查原始数据或解析规则。")
        sys.exit(1)

    show_preview(courses)
    save_backup(courses)

    if not args.yes:
        ans = input("确认推送到小爱课程表？(回车继续 / q 取消): ").strip().lower()
        if ans == "q":
            return

    userinfo = load_userinfo()
    try:
        pusher = AiSchedulePusher(userinfo)
        result = pusher.push_all(
            courses, config.TABLE_NAME, config.SECTIONS,
            config.FIRST_DAY, config.TOTAL_WEEK)
    except PushError as e:
        print(f"推送失败：{e}")
        sys.exit(1)

    print(f"\n完成：成功 {result['ok']} 门，冲突 {len(result['overlap'])} 门，"
          f"失败 {len(result['fail'])} 门。")
    if result["overlap"]:
        print("冲突课程（请手动核对）：")
        for c in result["overlap"]:
            print(f"  {c['name']} 周{c['day']} 第{c['sections']}节 "
                  f"{c['weeks']}周 {c['position']}")
    print("请退出小爱课程表重新进入，右上角切换课表即可查看。")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        print("发生异常：\n" + traceback.format_exc())
        input("按回车键退出...")
        sys.exit(1)
