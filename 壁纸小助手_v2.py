# 壁纸小助手 · 第 2 版
# 作用：运行一次，下载最近 8 天的必应壁纸，按日期命名存到「壁纸」文件夹

import json
import urllib.request
from pathlib import Path

# ① 问必应要最近 8 天的壁纸（n=8 就是"要 8 天"）
api = "https://cn.bing.com/HPImageArchive.aspx?format=js&idx=0&n=8&mkt=zh-CN"
with urllib.request.urlopen(api, timeout=15) as r:
    data = json.load(r)

# ② 准备好「壁纸」文件夹
folder = Path("壁纸")
folder.mkdir(exist_ok=True)

# ③ 挨个打开每一格，把图下载下来
for item in data["images"]:
    date = item["startdate"]              # 日期，像 20261119
    url = "https://cn.bing.com" + item["url"]
    title = item["title"]

    with urllib.request.urlopen(url, timeout=30) as r:
        picture = r.read()

    file = folder / (date + ".jpg")       # 用日期当文件名，8 张不会互相覆盖
    file.write_bytes(picture)
    print("已保存：" + file.name + "  " + title)

# ④ 收尾报总数
print("全部完成，共 " + str(len(data["images"])) + " 张")
