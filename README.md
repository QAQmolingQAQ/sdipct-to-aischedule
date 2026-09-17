# sdipct-to-aischedule

山东石油化工学院 教务系统课表 → **小爱课程表** 一键导入工具。

自动启动独立浏览器登录教务系统，抓取个人课表 JSON，解析后通过小爱课程表云端接口推送，课表直接出现在手机小爱课程表 App 里。

- 支持 MIUI / HyperOS **系统自带小爱课程表** 与 **小爱课程表独立版 App**
- 自动识别实验课、同一课程不同周次的多个教室（按周拆分/合并）
- 自动设置开学日期与学校作息时间
- 支持用 F12 抓包的本地 JSON 离线导入

> 仅供学习辅助，导入结果请务必与教务系统核对，**一切以教务系统显示为准**。

## 环境

- Windows 10 / 11，装有 Edge 或 Chrome
- Python 3.9+

## 安装

```bash
pip install -r requirements.txt
```

## 准备小爱课程表调试数据（UserInfo）

1. 打开手机小爱课程表（独立版需先登录），点右下角**头像/设置**
2. 把页面滑到最底部，在“开始新学期”下方的**空白处连点 5 次**，进入 Debug 页
3. 点击“**点击获取 UserInfo**”，在弹窗中复制
4. 将复制内容保存为项目目录下的 `userinfo.json`（一整行 JSON）

> `userinfo.json` 含登录令牌，已在 `.gitignore` 中忽略，**切勿分享或提交**。

## 使用

### 方式一：自动抓取（推荐）

```bash
python main.py
```

1. 工具会打开一个**独立浏览器窗口**（独立配置，不影响日常浏览器）
2. 在窗口中登录学校教务系统，登录成功后工具自动继续
3. 自动打开个人课表页并抓取数据，预览课程
4. 回车确认后推送到小爱课程表
5. 手机上**退出小爱课程表重新进入**，右上角切换课表即可看到

登录态保存在 `browser_profile/`，下次运行一般无需重新登录。

### 方式二：用本地抓包 JSON

先用浏览器 F12 从教务系统拷出课表接口的 JSON，然后：

```bash
python main.py --file 你的课表.json
```

跳过浏览器，直接解析并推送。样例见 `sample_data/schedule_raw.json`。

## 配置

学校信息、学期代码、开学日期、作息时间等在 `config.py` 中修改：

- `TERM_CODE`：学年学期，`202601` = 2026–2027 学年第一学期
- `FIRST_DAY`：第 1 周周一日期
- `SECTIONS`：每节课起止时间

## 数据接口说明

- 登录入口：`https://jwxt.sdipct.edu.cn/`
- 课表页面：`/new/student/xsgrkb/main.page`
- 课表接口（POST）：`/new/student/xsgrkb/getCalendarWeekDatas`
  - 表单：`xnxqdm=202601&zc=&d1=...&d2=...`（依赖登录 Cookie）

## 项目结构

```
config.py            学校 / 学期 / 作息时间配置
cdp_browser.py       CDP 浏览器：启动、登录检测、网络抓包
schedule_parser.py   课表 JSON 解析（纯函数，含样例测试）
aischedule_push.py   小爱课程表云端推送
main.py              主流程入口
sample_data/         真实抓包样例与期望解析结果
```

## 常见问题

- **已存在同名课表**：先在小爱课程表 App 中删除同名课表，或改 `config.py` 的 `TABLE_NAME`
- **课表数量已达上限**：在 App 中删除不需要的课表
- **提示 course info has overlap（时间冲突）**：该节与已有课程时间重叠被跳过，终端会列出，请手动核对
- **抓到 0 门课**：该学期课表可能尚未发布，或接口结构有变，请用 `--file` 配合 `sample_data` 反馈

## 致谢

推送逻辑参考 [Ruid24/neu-jwxt-to-aischedule](https://github.com/Ruid24/neu-jwxt-to-aischedule) 与 [CreamPig233/neu_wisedu2wakeup](https://github.com/CreamPig233/neu_wisedu2wakeup)。
