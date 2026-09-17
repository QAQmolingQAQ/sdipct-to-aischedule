# -*- coding: utf-8 -*-
"""山东石油化工学院 教务系统课表 -> 小爱课程表 一键导入工具。

启动后显示菜单：
    1. 自动获取课表并推送小爱课程表
    2. 仅获取课表（保存为 JSON，不推送）
    3. 推送之前自动获取的 JSON（last_raw.json）

流程（选项 1）：启动独立浏览器 -> 用户登录教务系统 -> 在页面内逐周请求
并汇总课表 JSON -> 解析预览 -> 读取小爱 UserInfo -> 推送到小爱课程表。

用法：
    python main.py                 # 显示菜单
    python main.py --file x.json   # 用本地 F12 抓包 JSON 直接解析推送（跳过菜单）
    python main.py --yes           # 推送前不再确认

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
from cdp_browser import find_browser, free_port, launch_browser, CDPClient


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
    client.eval(f'location.href="{config.SCHEDULE_PAGE_URL}"')
    time.sleep(3)

    # 在页面上下文（带登录 Cookie）逐周请求并汇总全学期课表。
    # 先请求第1周：响应/请求里的 d1 即第1周周一，由此自动得到开学日期，
    # 再以 7 天为步长推算后续各周的 d1/d2，循环到总周数。
    js = build_fetch_all_js()
    try:
        result = client.eval(js)
    except Exception as e:
        client.close()
        proc.terminate()
        print(f"请求课表接口失败：{e}")
        sys.exit(1)

    client.close()
    proc.terminate()

    if not result or not result.get("records"):
        print("未能获取到课表数据，请确认课表页已正常加载、该学期有课。")
        sys.exit(1)

    records = result["records"]
    first_day = result.get("firstMonday") or config.FIRST_DAY
    print(f"开学第1周周一：{first_day}")

    # 保存原始汇总数据备查（含开学日，供“推送上次获取的 JSON”复用）
    raw = {"code": 0, "data": records, "message": "merged",
           "firstMonday": first_day}
    raw_path = os.path.join(app_dir(), "last_raw.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    print(f"原始课表已保存：{raw_path}（共 {len(records)} 条原始记录）")

    # 作息时间以 config.SECTIONS 为权威（与教务上下课时间一致）
    sections = config.SECTIONS
    return raw, first_day, sections


def build_fetch_all_js():
    """生成在教务页面内执行的 JS：逐周请求并汇总，返回 records/firstMonday。

    乘方教务 getCalendarWeekDatas：
      POST xnxqdm=学期&zc=周次&d1=该周周一 00:00:00&d2=该周周日 00:00:00
    做法：
      1) 以“本周一”为锚点请求一次，从返回记录的 zc 字段得知本周是第几周，
         反推第1周周一 = 本周一 - 7*(本周周次-1)；
      2) 以第1周周一为基准，逐周 1..N 请求并去重汇总。
    """
    api = config.SCHEDULE_API
    term = config.TERM_CODE
    total = config.TOTAL_WEEK
    return f"""
(async()=>{{
    async function post(zc,d1,d2){{
        const body=new URLSearchParams({{xnxqdm:'{term}',zc:String(zc),
            d1:d1?d1+' 00:00:00':'',d2:d2?d2+' 00:00:00':''}});
        const r=await fetch('{api}',{{method:'POST',credentials:'include',
            headers:{{'content-type':'application/x-www-form-urlencoded; charset=UTF-8',
                     'x-requested-with':'XMLHttpRequest'}},
            body:body.toString()}});
        return await r.json().catch(()=>null);
    }}
    const collect=res=>Array.isArray(res&&res.data)?res.data:[];
    const addDays=(s,n)=>{{const p=s.split('-');
        const d=new Date(+p[0],+p[1]-1,+p[2]);d.setDate(d.getDate()+n);
        return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')
             +'-'+String(d.getDate()).padStart(2,'0');}};
    // 本周一
    const t=new Date(); const dow=(t.getDay()+6)%7; t.setDate(t.getDate()-dow);
    const fmt=d=>d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')
                  +'-'+String(d.getDate()).padStart(2,'0');
    const anchor=fmt(t);
    // 请求锚点周（d1=本周一），记录中的 zc 即真实周次
    let anchorWeek=0;
    const ar0=collect(await post('',anchor,addDays(anchor,6)));
    if(ar0.length){{
        const ws=ar0.map(x=>+String(x.zc).split(',')[0]).filter(x=>x>0);
        if(ws.length) anchorWeek=Math.min(...ws);
    }}
    let firstMonday=null;
    if(anchorWeek>0) firstMonday=addDays(anchor,-7*(anchorWeek-1));
    // 逐周汇总（有日期基准时按周请求；否则用 zc 空值请求整学期兜底）
    const all=[],seen=new Set();
    const push=arr=>arr.forEach(r=>{{
        const key=[r.kcmc,r.xq,r.ps,r.pe,r.zc,r.jxcdmc2||r.jxcdmc].join('|');
        if(!seen.has(key)){{seen.add(key);all.push(r);}}
    }});
    push(ar0);
    if(firstMonday){{
        for(let w=1;w<={total};w++){{
            const d1=addDays(firstMonday,7*(w-1));
            push(collect(await post(w,d1,addDays(d1,6))));
        }}
    }}else{{
        push(collect(await post('','','')));
    }}
    return {{records:all,firstMonday:firstMonday,anchorWeek:anchorWeek}};
}})()
"""



def normalize_raw(raw):
    """统一成解析器能吃的结构。

    getCalendarWeekDatas 常见返回：
      - {"code":0,"data":[...]}
      - 按周日历包装的对象，真正的课程列表在 data 内部某处
    解析器会递归按字段特征识别，这里直接透传。
    """
    return raw


def choose_mode():
    """启动后显示菜单并读取用户选择。"""
    print("请选择操作：")
    print("  1. 自动获取课表并推送小爱课程表")
    print("  2. 仅获取课表（保存为 JSON，不推送）")
    print("  3. 推送之前自动获取的 JSON（last_raw.json）")
    while True:
        c = input("输入 1 / 2 / 3：").strip()
        if c in ("1", "2", "3"):
            return c
        print("输入无效，请输入 1、2 或 3。")


def load_last_raw():
    """读取上次抓取的 last_raw.json，返回 (raw, first_day)。"""
    path = os.path.join(app_dir(), "last_raw.json")
    if not os.path.exists(path):
        print(f"未找到上次获取的数据：{path}")
        print("请先执行选项 1 或 2 获取课表。")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    first_day = raw.get("firstMonday") or config.FIRST_DAY
    return raw, first_day


def parse_and_preview(raw):
    """解析课表并预览、保存备份，返回课程列表。"""
    courses = parse_schedule(normalize_raw(raw))
    if not courses:
        print("未解析出任何课程，请检查原始数据或解析规则。")
        sys.exit(1)
    show_preview(courses)
    save_backup(courses)
    return courses


def confirm_and_push(courses, first_day, sections, assume_yes=False):
    """确认后推送到小爱课程表。"""
    if not assume_yes:
        ans = input("确认推送到小爱课程表？(回车继续 / q 取消): ").strip().lower()
        if ans == "q":
            return

    userinfo = load_userinfo()
    try:
        pusher = AiSchedulePusher(userinfo)
        result = pusher.push_all(
            courses, config.TABLE_NAME, sections,
            first_day, config.TOTAL_WEEK,
            morning_num=config.MORNING_NUM,
            afternoon_num=config.AFTERNOON_NUM,
            night_num=config.NIGHT_NUM)
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


def main():
    parser = argparse.ArgumentParser(description="教务课表 -> 小爱课程表")
    parser.add_argument("--file", help="使用本地抓包 JSON，跳过菜单直接解析并推送")
    parser.add_argument("--yes", action="store_true", help="解析后不询问直接推送")
    args = parser.parse_args()

    print("====== 山东石油化工学院 课表 -> 小爱课程表 导入工具 ======")
    print("提示：导入后请与教务系统核对，一切以教务系统显示为准。\n")

    # --file：直接用本地 JSON，跳过菜单
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            raw = json.load(f)
        first_day = config.FIRST_DAY
        if isinstance(raw, dict) and raw.get("firstMonday"):
            first_day = raw["firstMonday"]
        courses = parse_and_preview(raw)
        confirm_and_push(courses, first_day, config.SECTIONS, args.yes)
        return

    mode = choose_mode()
    print()

    if mode == "2":
        # 仅获取课表，不推送
        raw, first_day, sections = fetch_from_browser()
        parse_and_preview(raw)
        print("已获取并保存课表（未推送）。")
        return

    if mode == "3":
        # 推送之前自动获取的 JSON
        raw, first_day = load_last_raw()
        print(f"读取到上次获取的数据，开学第1周周一：{first_day}")
        sections = config.SECTIONS
        courses = parse_and_preview(raw)
        confirm_and_push(courses, first_day, sections, args.yes)
        return

    # mode == "1"：自动获取课表并推送
    raw, first_day, sections = fetch_from_browser()
    courses = parse_and_preview(raw)
    confirm_and_push(courses, first_day, sections, args.yes)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已取消。")
    except Exception:
        import traceback
        print("发生异常：\n" + traceback.format_exc())
        try:
            input("按回车键退出...")
        except EOFError:
            pass
        sys.exit(1)
