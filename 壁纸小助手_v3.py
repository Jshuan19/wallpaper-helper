# 壁纸小助手 · 第 3 版
# 作用：自动下载最近 8 天的必应壁纸，已有的跳过。可交给"计划任务"每天自动运行。

import json
import socket
import time
import urllib.request
from datetime import datetime
from pathlib import Path

# ① 找到脚本自己所在的文件夹，不管从哪里启动，都存到这里
BASE = Path(__file__).parent
folder = BASE / "壁纸"
folder.mkdir(exist_ok=True)
log = BASE / "运行记录.txt"

now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
lines = ["[" + now + "] 开始运行"]
new_count = 0

# ② 开机时网络可能还没连上：先敲门，不通就等 10 秒再敲，最多 6 次
for _ in range(6):
    try:
        socket.create_connection(("cn.bing.com", 443), timeout=3).close()
        break                       # 通了就走
    except OSError:
        time.sleep(10)              # 没通，等一会儿

try:
    # ② 问必应要最近 8 天的壁纸
    api = "https://cn.bing.com/HPImageArchive.aspx?format=js&idx=0&n=8&mkt=zh-CN"
    with urllib.request.urlopen(api, timeout=15) as r:
        data = json.load(r)

    # ③ 逐格处理，已有的跳过
    for item in data["images"]:
        date = item["startdate"]
        file = folder / (date + ".jpg")

        if file.exists():
            continue                      # 这张已经有了，跳过这一轮

        url = "https://cn.bing.com" + item["url"]
        with urllib.request.urlopen(url, timeout=30) as r:
            picture = r.read()
        file.write_bytes(picture)
        new_count += 1
        lines.append("  新增 " + file.name + "  " + item["title"])

    lines.append("  完成：新增 " + str(new_count) + " 张，共 " + str(len(data["images"])) + " 天数据")

except Exception as e:
    lines.append("  ✗ 出错：" + str(e))

# ④ 打印 + 追加写入运行记录
text = "\n".join(lines)
print(text)
with open(log, "a", encoding="utf-8") as f:
    f.write(text + "\n")
