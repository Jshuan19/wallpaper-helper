# 壁纸小助手 · 第 1 版
# 作用：运行一次，就下载一张今天的必应壁纸，存到「壁纸」文件夹

import json
import urllib.request          # Python 自带的"上网"工具，不用额外安装
from pathlib import Path

# ① 上网问必应：今天有什么好看的壁纸？
api = "https://cn.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=zh-CN"
with urllib.request.urlopen(api, timeout=15) as r:
    data = json.load(r)        # 把返回的内容整理成能读懂的"表格"

# ② 从"表格"里拿出壁纸地址和标题
item = data["images"][0]       # [0] 表示取第一张
url = "https://cn.bing.com" + item["url"]
title = item["title"]

# ③ 按地址把图片下载下来
with urllib.request.urlopen(url, timeout=30) as r:
    picture = r.read()         # read() 读出来的就是图片的原始数据

# ④ 存到「壁纸」文件夹
folder = Path("壁纸")
folder.mkdir(exist_ok=True)    # 文件夹已存在也不报错
file = folder / "我的壁纸.jpg"
file.write_bytes(picture)      # 把图片数据写成一个文件

# ⑤ 告诉你结果
print("ok！壁纸存到了：" + str(file))
print("壁纸主题：" + title)
