# 壁纸小助手 · 界面版
# 浅色扁平风格：白色卡片 + 圆角按钮 + 层级字号

import ctypes
import json
import os
import sys
import threading
import urllib.request
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog

# ---------------- 配色 ----------------
BG = "#F4F6FA"
CARD = "#FFFFFF"
BORDER = "#E3E7EE"
TEXT = "#1F2430"
TEXT_SUB = "#7A8194"
PRIMARY = "#7C3AED"
PRIMARY_HOVER = "#6D28D9"
GREEN = "#047857"
GREEN_HOVER = "#036249"
DANGER = "#B91C1C"
DANGER_HOVER = "#991B1B"
SOFT = "#EDF1F8"
SOFT_HOVER = "#DEE6F4"
SOFT_FG = "#3B4A66"

FONT_TITLE = ("Microsoft YaHei UI", 18, "bold")
FONT_SUB = ("Microsoft YaHei UI", 9)
FONT_LABEL = ("Microsoft YaHei UI", 10)
FONT_BODY = ("Microsoft YaHei UI", 10)
FONT_BTN = ("Microsoft YaHei UI", 11, "bold")
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


def grab(count, suffix, out):
    """抓 count 张指定尺寸的壁纸"""
    FOLDER.mkdir(parents=True, exist_ok=True)

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


def load_config():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config():
    cfg = {
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
    grab(2, "_1280x720.jpg", print)
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
    """自绘圆角按钮（tkinter 没有原生圆角）"""

    def __init__(self, master, text, command, fill, hover, fg="#FFFFFF",
                 width=200, height=46, radius=12, font=FONT_BTN, bg=BG):
        super().__init__(master, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.command = command
        self.fill = fill
        self.hover = hover

        self.shape = round_rect(self, 1, 1, width - 1, height - 1, radius,
                                fill=fill, outline="")
        self.label = self.create_text(width / 2, height / 2, text=text,
                                      fill=fg, font=font)

        self.bind("<Enter>", lambda e: self.itemconfig(self.shape, fill=self.hover))
        self.bind("<Leave>", lambda e: self.itemconfig(self.shape, fill=self.fill))
        self.bind("<Button-1>", lambda e: self.command())

    def set_text(self, text):
        self.itemconfig(self.label, text=text)

    def set_color(self, fill, hover):
        self.fill = fill
        self.hover = hover
        self.itemconfig(self.shape, fill=fill)


# ---------------- 窗口 ----------------
root = tk.Tk()
root.title("壁纸小助手")
root.configure(bg=BG)
root.resizable(False, False)

W, H = 700, 700
sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
root.geometry("%dx%d+%d+%d" % (W, H, (sw - W) // 2, max(30, (sh - H) // 2 - 20)))

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
          bordercolor=[("focus", PRIMARY), ("hover", "#C9D2E3")])
style.configure("TEntry",
                fieldbackground=CARD, foreground=TEXT,
                bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=6)
style.map("TEntry", bordercolor=[("focus", PRIMARY)])

root.option_add("*TCombobox*Listbox.background", CARD)
root.option_add("*TCombobox*Listbox.foreground", TEXT)
root.option_add("*TCombobox*Listbox.selectBackground", PRIMARY)
root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
root.option_add("*TCombobox*Listbox.font", FONT_BODY)

# ---------------- 标题 ----------------
header = tk.Frame(root, bg=BG)
header.pack(fill="x", padx=24, pady=(18, 14))

tk.Label(header, text="壁纸小助手", bg=BG, fg=TEXT,
         font=FONT_TITLE, anchor="w").pack(fill="x")
tk.Label(header, text="必应每日精选 · 自动抓取 · 一键换桌面",
         bg=BG, fg=TEXT_SUB, font=FONT_SUB, anchor="w").pack(fill="x", pady=(2, 0))

# ---------------- 设置卡片 ----------------
card = tk.Frame(root, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
card.pack(fill="x", padx=24, pady=(0, 12))

inner = tk.Frame(card, bg=CARD)
inner.pack(fill="x", padx=18, pady=14)
inner.columnconfigure(1, weight=1)


def lab(text, r, c):
    tk.Label(inner, text=text, bg=CARD, fg=TEXT_SUB, font=FONT_LABEL,
             anchor="w").grid(row=r, column=c, sticky="w", pady=6)


lab("屏幕尺寸", 0, 0)
size_var = tk.StringVar()
size_box = ttk.Combobox(inner, textvariable=size_var, values=list(SIZES.keys()),
                        state="readonly", width=18, font=FONT_BODY)
size_box.grid(row=0, column=1, sticky="w", padx=(12, 20), pady=6)

lab("一次抓几张", 0, 2)
count_var = tk.StringVar(value="8")
count_box = ttk.Combobox(inner, textvariable=count_var, values=COUNT_OPTIONS,
                         state="readonly", width=4, font=FONT_BODY)
count_box.grid(row=0, column=3, sticky="w", padx=(12, 0), pady=6)

lab("运行频率", 1, 0)
freq_var = tk.StringVar(value="只手动")
freq_box = ttk.Combobox(inner, textvariable=freq_var, values=list(FREQS.keys()),
                        state="readonly", width=18, font=FONT_BODY)
freq_box.grid(row=1, column=1, sticky="w", padx=(12, 20), pady=6)

auto_wall_var = tk.BooleanVar(value=False)
chk = tk.Checkbutton(inner, text="抓完自动设为桌面", variable=auto_wall_var,
                     bg=CARD, fg=TEXT, activebackground=CARD, activeforeground=TEXT,
                     selectcolor=CARD, font=FONT_BODY, bd=0, highlightthickness=0,
                     anchor="w", cursor="hand2", command=lambda: save_config())
chk.grid(row=1, column=2, columnspan=2, sticky="w", padx=(12, 0), pady=6)

lab("保存位置", 2, 0)
path_var = tk.StringVar(value=str(FOLDER))
path_entry = ttk.Entry(inner, textvariable=path_var, font=FONT_SUB)
path_entry.grid(row=2, column=1, columnspan=2, sticky="we", padx=(12, 10), pady=6)

browse = RoundButton(inner, "浏览", lambda: choose_folder(),
                     fill=SOFT, hover=SOFT_HOVER, fg=SOFT_FG,
                     width=62, height=32, radius=8, font=FONT_BTN_S, bg=CARD)
browse.grid(row=2, column=3, sticky="e", pady=6)

# ---------------- 主按钮 ----------------
btn_row = tk.Frame(root, bg=BG)
btn_row.pack(fill="x", padx=24, pady=(0, 10))

grab_btn = RoundButton(btn_row, "立即抓取一次", lambda: run_grab(),
                       fill=PRIMARY, hover=PRIMARY_HOVER, width=270, height=48)
grab_btn.pack(side="left", padx=(0, 12))

auto_btn = RoundButton(btn_row, "开始自动运行", lambda: toggle_auto(),
                       fill=GREEN, hover=GREEN_HOVER, width=270, height=48)
auto_btn.pack(side="left")

btn_row2 = tk.Frame(root, bg=BG)
btn_row2.pack(fill="x", padx=24, pady=(0, 12))

wall_btn = RoundButton(btn_row2, "把最新一张设为桌面", lambda: apply_wallpaper(),
                       fill=SOFT, hover=SOFT_HOVER, fg=SOFT_FG,
                       width=270, height=38, radius=10, font=FONT_BTN_S)
wall_btn.pack(side="left", padx=(0, 12))

open_btn = RoundButton(btn_row2, "打开壁纸文件夹", lambda: open_folder(),
                       fill=SOFT, hover=SOFT_HOVER, fg=SOFT_FG,
                       width=270, height=38, radius=10, font=FONT_BTN_S)
open_btn.pack(side="left")

status = tk.Label(root, text="就绪", bg=BG, fg=TEXT_SUB, font=FONT_SUB, anchor="w")
status.pack(fill="x", padx=26, pady=(0, 8))

# ---------------- 日志卡片 ----------------
log_card = tk.Frame(root, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
log_card.pack(fill="both", expand=True, padx=24, pady=(0, 20))

log_head = tk.Frame(log_card, bg=CARD)
log_head.pack(fill="x", padx=16, pady=(10, 4))
tk.Label(log_head, text="运行日志", bg=CARD, fg=TEXT_SUB,
         font=("Microsoft YaHei UI", 9, "bold"), anchor="w").pack(side="left")

box = tk.Text(log_card, height=7, state="disabled", font=FONT_MONO,
              bg=CARD, fg="#4A5568", bd=0, highlightthickness=0,
              wrap="word", padx=16, pady=2, spacing1=2, spacing3=2)
box.pack(fill="both", expand=True, padx=(0, 8), pady=(0, 10))


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
    count = int(count_var.get())
    suffix = SIZES[size_var.get()]
    save_config()

    def worker():
        log("开始抓取 " + count_var.get() + " 张，尺寸 " + size_var.get())
        try:
            grab(count, suffix, ui_log)
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
        auto_btn.set_color(DANGER, DANGER_HOVER)
        auto_tick()
    else:
        root.after_cancel(auto_job)
        auto_job = None
        auto_btn.set_text("开始自动运行")
        auto_btn.set_color(GREEN, GREEN_HOVER)
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

status.config(text="已检测屏幕 %d × %d · 壁纸保存在：%s" % (w, h, FOLDER))

root.mainloop()
