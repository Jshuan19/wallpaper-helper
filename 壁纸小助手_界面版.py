# 壁纸小助手 · 界面版
# 浅色扁平风格：白色卡片 + 圆角按钮 + 层级字号

import ctypes
import json
import os
import random
import re
import sys
import threading
import urllib.request
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog

# ---------------- 配色：中性底 + 单一深色主色，把颜色让给壁纸本身 ----------------
BG = "#F5F5F6"
CARD = "#FFFFFF"
BORDER = "#E4E4E7"
DIVIDER = "#EFEFF1"
TEXT = "#18181B"
TEXT_SUB = "#71717A"
INK = "#18181B"
INK_HOVER = "#27272A"
INK_PRESS = "#000000"
SOFT = "#F4F4F5"
SOFT_HOVER = "#E9E9EB"
TEAL = "#0F766E"

FONT_TITLE = ("Microsoft YaHei UI", 20, "bold")
FONT_SUB = ("Microsoft YaHei UI", 9)
FONT_LABEL = ("Microsoft YaHei UI", 10)
FONT_BODY = ("Microsoft YaHei UI", 10)
FONT_SECTION = ("Microsoft YaHei UI", 9, "bold")
FONT_BTN = ("Microsoft YaHei UI", 10, "bold")
FONT_BTN_S = ("Microsoft YaHei UI", 10)
FONT_MONO = ("Consolas", 9)

BASE = Path(__file__).parent
CONFIG_FILE = BASE / "设置.json"
LOG_FILE = BASE / "运行记录.txt"

DEFAULT_FOLDER = BASE / "壁纸"
FOLDER = DEFAULT_FOLDER

SIZES = {
    "1920 × 1080（1080P）": "_1920x1080.jpg",
    "3840 × 2160（4K）": "_UHD.jpg",
    "1366 × 768": "_1366x768.jpg",
    "1280 × 720（720P）": "_1280x720.jpg",
}

FREQS = {
    "只手动": 0,
    "每10分钟": 10,
    "每 30 分钟": 30,
    "每 1 小时": 60,
    "每 6 小时": 360,
    "每天一次": 1440,
}

COUNT_OPTIONS = ["1", "2", "3", "4", "5", "6", "7", "8","10"]

# ---------------- 系统接口 ----------------
user32 = ctypes.windll.user32
user32.SystemParametersInfoW.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
user32.SystemParametersInfoW.restype = ctypes.c_int
SPI_SETDESKWALLPAPER = 20
SPIF_UPDATEINIFILE_SENDCHANGE = 3


def set_wallpaper(path):
    return user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, str(path), SPIF_UPDATEINIFILE_SENDCHANGE) == 1


def latest_image():
    files = list(FOLDER.glob("*.jpg"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def detect_screen():
    try:
        return ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
    except Exception:
        return 1920, 1080


def size_wh(label):
    """从「1920 × 1080（1080P）」里取出 1920 和 1080，供不限档位的来源用"""
    nums = re.findall(r"\d+", label)
    if len(nums) < 2:
        return 1920, 1080
    return int(nums[0]), int(nums[1])


def grab_bing(count, size_label, out):
    """必应每日精选：只有四种固定尺寸，最多回溯 8 天"""
    FOLDER.mkdir(parents=True, exist_ok=True)
    suffix = SIZES[size_label]

    api = "https://cn.bing.com/HPImageArchive.aspx?format=js&idx=0&n=%d&mkt=zh-CN" % count
    with urllib.request.urlopen(api, timeout=15) as r:
        data = json.load(r)

    tag = suffix.strip("_").replace(".jpg", "")
    new_count = 0

    for item in data["images"][:count]:
        name = item["startdate"] + "_" + tag + ".jpg"
        file = FOLDER / name
        if file.exists():
            continue
        url = "https://cn.bing.com" + item["urlbase"] + suffix
        with urllib.request.urlopen(url, timeout=60) as r:
            picture = r.read()
        file.write_bytes(picture)
        new_count += 1
        out("新增 " + name + "   " + item["title"])

    out("完成：新增 %d 张（本次取 %d 天数据）" % (new_count, len(data["images"])))
    return new_count


def grab_picsum(count, size_label, out):
    """Picsum 摄影：随机摄影作品，按所选尺寸裁切，要多少有多少"""
    FOLDER.mkdir(parents=True, exist_ok=True)
    w, h = size_wh(size_label)

    new_count = 0
    seen = set()
    tries = 0

    while new_count < count and tries < count + 3:
        tries += 1
        page = random.randint(1, 60)
        api = "https://picsum.photos/v2/list?page=%d&limit=%d" % (page, max(3, count))
        with urllib.request.urlopen(api, timeout=20) as r:
            items = json.load(r)
        if not items:
            break

        for item in items:
            if new_count >= count:
                break
            pid = str(item["id"])
            if pid in seen:
                continue
            seen.add(pid)

            name = "picsum_%s_%dx%d.jpg" % (pid, w, h)
            file = FOLDER / name
            if file.exists():
                continue

            url = "https://picsum.photos/id/%s/%d/%d" % (pid, w, h)
            with urllib.request.urlopen(url, timeout=90) as r:
                picture = r.read()
            file.write_bytes(picture)
            new_count += 1
            out("新增 " + name + "   摄影：" + str(item.get("author", "未知")))

    out("完成：新增 %d 张（来源 Picsum 摄影）" % new_count)
    return new_count


# 360 壁纸：4K 专区，接口用 start/count 翻页，原图 3840×2160
W360_CID = 36
W360_VARIANTS = {
    (1600, 900): "img_1600_900",
    (1440, 900): "img_1440_900",
    (1366, 768): "img_1366_768",
    (1280, 800): "img_1280_800",
    (1024, 768): "img_1024_768",
}


def pick_360_url(item, w, h):
    """有刚好对得上的小尺寸就用它，否则取原图"""
    field = W360_VARIANTS.get((w, h))
    if field and item.get(field):
        return item[field]
    return item["url"]


def grab_360(count, size_label, out):
    """360 壁纸：随机翻页取图，免得每次点都抓到同一批"""
    FOLDER.mkdir(parents=True, exist_ok=True)
    w, h = size_wh(size_label)

    new_count = 0
    seen = set()
    tries = 0

    while new_count < count and tries < count + 3:
        tries += 1
        start = random.randint(0, 800)
        api = ("http://wallpaper.apc.360.cn/index.php?c=WallPaper&a=getAppsByCategory"
               "&cid=%d&start=%d&count=%d&from=360chrome" % (W360_CID, start, max(3, count)))
        with urllib.request.urlopen(api, timeout=20) as r:
            data = json.load(r)
        items = data.get("data") or []
        if not items:
            break

        for item in items:
            if new_count >= count:
                break
            wid = str(item.get("id"))
            if wid in seen:
                continue
            seen.add(wid)

            name = "360_%s.jpg" % wid
            file = FOLDER / name
            if file.exists():
                continue

            url = pick_360_url(item, w, h)
            with urllib.request.urlopen(url, timeout=90) as r:
                picture = r.read()
            file.write_bytes(picture)
            new_count += 1
            out("新增 " + name + "   " + str(item.get("resolution", "")))

    out("完成：新增 %d 张（来源 360 壁纸）" % new_count)
    return new_count


# 来源名 → 抓取函数。以后加新来源，写一个函数、在这里加一行即可
SOURCES = {
    "必应每日精选": grab_bing,
    "360 壁纸（4K）": grab_360,
    "Picsum 摄影": grab_picsum,
}


def grab(source, count, size_label, out):
    """按用户选的来源，把活交给对应的抓取函数"""
    fn = SOURCES.get(source)
    if fn is None:
        raise ValueError("不认识的来源：" + str(source))
    return fn(count, size_label, out)


def load_config():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config():
    cfg = {
        "source": source_var.get(),
        "folder": str(FOLDER),
        "size": size_var.get(),
        "count": count_var.get(),
        "freq": freq_var.get(),
        "auto_wallpaper": bool(auto_wall_var.get()),
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


if "--test" in sys.argv:
    grab("必应每日精选", 2, "1280 × 720（720P）", print)
    sys.exit()

if "--test-picsum" in sys.argv:
    grab("Picsum 摄影", 2, "1280 × 720（720P）", print)
    sys.exit()

if "--test-360" in sys.argv:
    grab("360 壁纸（4K）", 2, "1920 × 1080（1080P）", print)
    sys.exit()

if "--test-wallpaper" in sys.argv:
    import winreg
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop")
    old, _ = winreg.QueryValueEx(key, "WallPaper")
    print("原壁纸:", old)
    target = latest_image()
    print("目标图:", target)
    print("调用结果:", set_wallpaper(target))
    k2 = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop")
    now, _ = winreg.QueryValueEx(k2, "WallPaper")
    print("注册表现在:", now)
    set_wallpaper(Path(old))
    print("已恢复原壁纸")
    sys.exit()


# ---------------- 圆角绘制 ----------------
def round_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kwargs)


class RoundButton(tk.Canvas):
    """自绘圆角按钮（tkinter 没有原生圆角）：带悬停、按下两种反馈"""

    def __init__(self, master, text, command, fill, hover, fg="#FFFFFF",
                 width=200, height=46, radius=10, font=FONT_BTN, bg=BG,
                 outline=None, press=None):
        super().__init__(master, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.command = command
        self.fill = fill
        self.hover = hover
        self.press = press or hover

        self.shape = round_rect(self, 1, 1, width - 1, height - 1, radius,
                                fill=fill, outline=outline or "", width=1)
        self.label = self.create_text(width / 2, height / 2, text=text,
                                      fill=fg, font=font)

        self.bind("<Enter>", lambda e: self.itemconfig(self.shape, fill=self.hover))
        self.bind("<Leave>", lambda e: self.itemconfig(self.shape, fill=self.fill))
        self.bind("<Button-1>", lambda e: self.itemconfig(self.shape, fill=self.press))
        self.bind("<ButtonRelease-1>", self._on_release)

    def _on_release(self, event):
        inside = 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        self.itemconfig(self.shape, fill=self.hover if inside else self.fill)
        if inside:
            self.command()

    def set_text(self, text):
        self.itemconfig(self.label, text=text)

    def set_style(self, fill, hover, fg=None, outline=None):
        """切换整组配色，自动运行按钮的开关状态用它"""
        self.fill = fill
        self.hover = hover
        self.press = hover
        self.itemconfig(self.shape, fill=fill, outline=outline or "")
        if fg:
            self.itemconfig(self.label, fill=fg)


# ---------------- 窗口 ----------------
root = tk.Tk()
root.title("壁纸小助手")
root.configure(bg=BG)
root.resizable(False, False)

PAD = 28          # 统一外边距，保证左右内容边缘对齐
GAP = 12          # 按钮之间的固定间隙
W, H = 700, 800
sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
H = min(H, sh - 120)                 # 小屏幕上别超出可视区
root.geometry("%dx%d+%d+%d" % (W, H, (sw - W) // 2, max(30, (sh - H) // 2 - 20)))

BTN_W = (W - PAD * 2 - GAP) // 2     # 一行两个按钮，等宽撑满

style = ttk.Style()
style.theme_use("clam")
style.configure("TCombobox",
                fieldbackground=CARD, background=CARD, foreground=TEXT,
                bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                arrowcolor=TEXT_SUB, padding=6)
style.map("TCombobox",
          fieldbackground=[("readonly", CARD)],
          selectbackground=[("readonly", CARD)],
          selectforeground=[("readonly", TEXT)],
          bordercolor=[("focus", INK), ("hover", "#C7C7CC")])
style.configure("TEntry",
                fieldbackground=CARD, foreground=TEXT,
                bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=6)
style.map("TEntry", bordercolor=[("focus", INK)])

root.option_add("*TCombobox*Listbox.background", CARD)
root.option_add("*TCombobox*Listbox.foreground", TEXT)
root.option_add("*TCombobox*Listbox.selectBackground", INK)
root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
root.option_add("*TCombobox*Listbox.font", FONT_BODY)

# ---------------- 标题 ----------------
header = tk.Frame(root, bg=BG)
header.pack(fill="x", padx=PAD, pady=(22, 16))

tk.Label(header, text="壁纸小助手", bg=BG, fg=TEXT,
         font=FONT_TITLE, anchor="w").pack(fill="x")
tk.Label(header, text="三个来源 · 按尺寸抓取 · 一键换桌面",
         bg=BG, fg=TEXT_SUB, font=FONT_SUB, anchor="w").pack(fill="x", pady=(4, 0))

# ---------------- 设置卡片 ----------------
card = tk.Frame(root, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
card.pack(fill="x", padx=PAD, pady=(0, GAP))

inner = tk.Frame(card, bg=CARD)
inner.pack(fill="x", padx=20, pady=(14, 14))
inner.columnconfigure(0, minsize=64)
inner.columnconfigure(1, weight=1)


def section(text, r):
    tk.Label(inner, text=text, bg=CARD, fg=TEXT_SUB, font=FONT_SECTION,
             anchor="w").grid(row=r, column=0, columnspan=4, sticky="w", pady=(4, 0))


def lab(text, r, c):
    tk.Label(inner, text=text, bg=CARD, fg=TEXT_SUB, font=FONT_LABEL,
             anchor="w").grid(row=r, column=c, sticky="w", pady=7)


def divider(r):
    tk.Frame(inner, bg=DIVIDER, height=1).grid(row=r, column=0, columnspan=4,
                                               sticky="ew", pady=12)


section("抓 取", 0)

lab("壁纸来源", 1, 0)
source_var = tk.StringVar(value="必应每日精选")
source_box = ttk.Combobox(inner, textvariable=source_var, values=list(SOURCES.keys()),
                          state="readonly", width=19, font=FONT_BODY)
source_box.grid(row=1, column=1, sticky="w", padx=(12, 20), pady=7)
tk.Label(inner, text="切换后自动记住", bg=CARD, fg=TEXT_SUB,
         font=FONT_SUB, anchor="w").grid(row=1, column=2, columnspan=2, sticky="w",
                                         padx=(4, 0), pady=7)

lab("屏幕尺寸", 2, 0)
size_var = tk.StringVar()
size_box = ttk.Combobox(inner, textvariable=size_var, values=list(SIZES.keys()),
                        state="readonly", width=19, font=FONT_BODY)
size_box.grid(row=2, column=1, sticky="w", padx=(12, 20), pady=7)

count_group = tk.Frame(inner, bg=CARD)
count_group.grid(row=2, column=2, columnspan=2, sticky="e", pady=7)
tk.Label(count_group, text="张数", bg=CARD, fg=TEXT_SUB,
         font=FONT_LABEL, anchor="w").pack(side="left", padx=(0, 10))
count_var = tk.StringVar(value="8")
count_box = ttk.Combobox(count_group, textvariable=count_var, values=COUNT_OPTIONS,
                         state="readonly", width=4, font=FONT_BODY)
count_box.pack(side="left")

divider(3)

section("自动化与保存", 4)

lab("运行频率", 5, 0)
freq_var = tk.StringVar(value="只手动")
freq_box = ttk.Combobox(inner, textvariable=freq_var, values=list(FREQS.keys()),
                        state="readonly", width=19, font=FONT_BODY)
freq_box.grid(row=5, column=1, sticky="w", padx=(12, 20), pady=7)

auto_wall_var = tk.BooleanVar(value=False)
chk = tk.Checkbutton(inner, text="抓完自动设为桌面", variable=auto_wall_var,
                     bg=CARD, fg=TEXT, activebackground=CARD, activeforeground=TEXT,
                     selectcolor=CARD, font=FONT_BODY, bd=0, highlightthickness=0,
                     anchor="w", cursor="hand2", command=lambda: save_config())
chk.grid(row=5, column=2, columnspan=2, sticky="w", padx=(12, 0), pady=7)

lab("保存位置", 6, 0)
path_var = tk.StringVar(value=str(FOLDER))
path_entry = ttk.Entry(inner, textvariable=path_var, font=FONT_SUB)
path_entry.grid(row=6, column=1, columnspan=2, sticky="we", padx=(12, 10), pady=7)

browse = RoundButton(inner, "浏览", lambda: choose_folder(),
                     fill=CARD, hover=SOFT, fg=TEXT, outline=BORDER,
                     width=62, height=32, radius=8, font=FONT_BTN_S, bg=CARD)
browse.grid(row=6, column=3, sticky="e", pady=7)

# ---------------- 主按钮：一个深色主操作 + 一个描边次操作 ----------------
btn_row = tk.Frame(root, bg=BG)
btn_row.pack(fill="x", padx=PAD, pady=(0, 10))

grab_btn = RoundButton(btn_row, "立即抓取一次", lambda: run_grab(),
                       fill=INK, hover=INK_HOVER, press=INK_PRESS,
                       width=BTN_W, height=46)
grab_btn.pack(side="left", padx=(0, GAP))

auto_btn = RoundButton(btn_row, "开始自动运行", lambda: toggle_auto(),
                       fill=CARD, hover=SOFT, fg=TEXT, outline=BORDER,
                       width=BTN_W, height=46)
auto_btn.pack(side="left")

btn_row2 = tk.Frame(root, bg=BG)
btn_row2.pack(fill="x", padx=PAD, pady=(0, GAP))

wall_btn = RoundButton(btn_row2, "把最新一张设为桌面", lambda: apply_wallpaper(),
                       fill=CARD, hover=SOFT, fg=TEXT, outline=BORDER,
                       width=BTN_W, height=38, radius=9, font=FONT_BTN_S)
wall_btn.pack(side="left", padx=(0, GAP))

open_btn = RoundButton(btn_row2, "打开壁纸文件夹", lambda: open_folder(),
                       fill=CARD, hover=SOFT, fg=TEXT, outline=BORDER,
                       width=BTN_W, height=38, radius=9, font=FONT_BTN_S)
open_btn.pack(side="left")

# ---------------- 状态行 ----------------
status_row = tk.Frame(root, bg=BG)
status_row.pack(fill="x", padx=PAD, pady=(0, 10))

tk.Label(status_row, text="●", bg=BG, fg=TEAL,
         font=("Microsoft YaHei UI", 8)).pack(side="left")
status = tk.Label(status_row, text="就绪", bg=BG, fg=TEXT_SUB, font=FONT_SUB,
                  anchor="w", justify="left")
status.pack(side="left", fill="x", expand=True, padx=(6, 0))

# ---------------- 日志卡片 ----------------
log_card = tk.Frame(root, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
log_card.pack(fill="both", expand=True, padx=PAD, pady=(0, PAD))

log_head = tk.Frame(log_card, bg=CARD)
log_head.pack(fill="x", padx=16, pady=(12, 8))
tk.Label(log_head, text="运行日志", bg=CARD, fg=TEXT,
         font=FONT_SECTION, anchor="w").pack(side="left")

clear_lbl = tk.Label(log_head, text="清空", bg=CARD, fg=TEXT_SUB,
                     font=FONT_SUB, cursor="hand2")
clear_lbl.pack(side="right")

tk.Frame(log_card, bg=DIVIDER, height=1).pack(fill="x", padx=16)

box = tk.Text(log_card, height=7, state="disabled", font=FONT_MONO,
              bg=CARD, fg=TEXT_SUB, bd=0, highlightthickness=0,
              wrap="word", padx=16, pady=10, spacing1=3, spacing3=3,
              insertbackground=TEXT)
box.pack(fill="both", expand=True)


def clear_log():
    box.config(state="normal")
    box.delete("1.0", "end")
    box.config(state="disabled")


clear_lbl.bind("<Button-1>", lambda e: clear_log())
clear_lbl.bind("<Enter>", lambda e: clear_lbl.config(fg=TEXT))
clear_lbl.bind("<Leave>", lambda e: clear_lbl.config(fg=TEXT_SUB))


def log(msg):
    item = "[" + datetime.now().strftime("%H:%M:%S") + "] " + msg
    box.config(state="normal")
    box.insert("end", item + "\n")
    box.see("end")
    box.config(state="disabled")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write("[" + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "] " + msg + "\n")


def ui_log(msg):
    root.after(0, lambda m=msg: log(m))


# ---------------- 功能 ----------------
def choose_folder():
    p = filedialog.askdirectory(initialdir=str(FOLDER), title="选择壁纸保存位置")
    if not p:
        return
    path_var.set(p)
    apply_folder()


def apply_folder():
    global FOLDER
    target = Path(path_var.get().strip())
    try:
        target.mkdir(parents=True, exist_ok=True)
        FOLDER = target
        save_config()
        log("保存位置已切换到：" + str(target))
        status.config(text="保存位置：" + str(target))
    except Exception as e:
        log("✗ 无法使用该路径：" + str(e))
        path_var.set(str(FOLDER))


def open_folder():
    try:
        FOLDER.mkdir(parents=True, exist_ok=True)
        os.startfile(str(FOLDER))
    except Exception as e:
        log("✗ 打不开文件夹：" + str(e))


def apply_wallpaper():
    img = latest_image()
    if img is None:
        log("文件夹里还没有壁纸，先点「立即抓取一次」")
        return
    if set_wallpaper(img):
        log("已把 " + img.name + " 设为桌面壁纸")
        status.config(text="桌面壁纸：" + img.name)
    else:
        log("✗ 设置桌面壁纸失败（系统拒绝了请求）")


def run_grab():
    source = source_var.get()
    count = int(count_var.get())
    size_label = size_var.get()
    save_config()

    def worker():
        log("开始抓取 %d 张｜来源：%s｜尺寸：%s" % (count, source, size_label))
        try:
            grab(source, count, size_label, ui_log)
            if auto_wall_var.get():
                img = latest_image()
                if img is not None:
                    ok = set_wallpaper(img)
                    ui_log(("已设为桌面：" if ok else "✗ 设桌面失败：") + img.name)
        except Exception as e:
            ui_log("✗ 出错：" + str(e))

    threading.Thread(target=worker, daemon=True).start()


auto_job = None


def auto_tick():
    global auto_job
    run_grab()
    minutes = FREQS[freq_var.get()]
    if minutes > 0:
        auto_job = root.after(minutes * 60 * 1000, auto_tick)
        nxt = datetime.now().timestamp() + minutes * 60
        status.config(text="下次自动运行：" + datetime.fromtimestamp(nxt).strftime("%H:%M"))


def toggle_auto():
    global auto_job
    minutes = FREQS[freq_var.get()]

    if minutes == 0:
        log("当前频率是「只手动」，请先选一个频率再点自动运行")
        return

    if auto_job is None:
        auto_btn.set_text("停止自动运行")
        auto_btn.set_style(INK, INK_HOVER, "#FFFFFF", None)
        auto_tick()
    else:
        root.after_cancel(auto_job)
        auto_job = None
        auto_btn.set_text("开始自动运行")
        auto_btn.set_style(CARD, SOFT, TEXT, BORDER)
        status.config(text="已停止自动运行")


# ---------------- 启动时恢复设置 ----------------
w, h = detect_screen()
cfg = load_config()

if cfg.get("folder"):
    try:
        p = Path(cfg["folder"])
        p.mkdir(parents=True, exist_ok=True)
        FOLDER = p
    except Exception:
        FOLDER = DEFAULT_FOLDER
FOLDER.mkdir(parents=True, exist_ok=True)
path_var.set(str(FOLDER))

if cfg.get("source") in SOURCES:
    source_var.set(cfg["source"])
if cfg.get("size") in SIZES:
    size_var.set(cfg["size"])
else:
    if w >= 3000:
        size_var.set("3840 × 2160（4K）")
    elif w >= 1900:
        size_var.set("1920 × 1080（1080P）")
    elif w >= 1300:
        size_var.set("1366 × 768")
    else:
        size_var.set("1280 × 720（720P）")

if cfg.get("count") in COUNT_OPTIONS:
    count_var.set(cfg["count"])
if cfg.get("freq") in FREQS:
    freq_var.set(cfg["freq"])
if "auto_wallpaper" in cfg:
    auto_wall_var.set(bool(cfg["auto_wallpaper"]))

status.config(text="就绪｜屏幕 %d × %d" % (w, h))

# 日志区空状态提示：只写进界面，不写进运行记录.txt
box.config(state="normal")
box.insert("end", "选好来源与尺寸后，点「立即抓取一次」开始抓图。\n")
box.config(state="disabled")

root.mainloop()
