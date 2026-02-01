import tkinter as tk
from tkinter import ttk
import pandas as pd
from fractions import Fraction

# ================== Excel 读取 ==================
FILE = "armor.xlsx"

helmet_df = pd.read_excel(FILE, sheet_name="helmet")
body_df   = pd.read_excel(FILE, sheet_name="body armor")
boots_df  = pd.read_excel(FILE, sheet_name="boots")
for df in (helmet_df, body_df, boots_df):
    df.columns = (
        df.columns
        .astype(str)
        .str.strip()      # 去前后空格
        .str.lower()      # 全部转小写
    )
# 字符串列防御
for df in (helmet_df, body_df, boots_df):
    df["name"] = df["name"].astype(str)
    df["drop"] = df["drop"].astype(str)

# ================== Fraction 工具 ==================
def F(x):
    if pd.isna(x) or str(x).strip() == "":
        return Fraction(0)
    return Fraction(str(x))
def fmt(x):
    return f"{float(x):.3f}".rstrip("0").rstrip(".")
# ================== 上限解析 ==================
def parse_limits(s):
    """
    "cor:15;gra:10" -> {"cor":15,"gra":10}
    """
    if pd.isna(s) or str(s).strip() == "":
        return {}
    result = {}
    for part in str(s).split(";"):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        result[k.strip()] = Fraction(str(v.strip()))
    return result

def apply_limit(value, limits, key):
    if key in limits:
        return min(value, limits[key])
    return value  # 未写 = 无上限

# ================== 核心计算（新版） ==================
def calc(row, C, S, G):
    C, S, G = F(C), F(S), F(G)

    base_phy = F(row.base_phy)
    base_mag = F(row.base_mag)
    base_sta = F(row.base_sta)

    # ---- 最低穿戴限制 ----
    if (
        C < F(row.min_cor) or
        S < F(row.min_spi) or
        G < F(row.min_gra)
    ):
        return base_phy, base_mag, base_sta, 0, 0, 0

    # ---- 每种防御的属性上限 ----
    lim_phy = parse_limits(row.max_phy)
    lim_mag = parse_limits(row.max_mag)
    lim_sta = parse_limits(row.max_sta)

    # ---- 物理 ----
    C_phy = apply_limit(C, lim_phy, "cor")
    S_phy = apply_limit(S, lim_phy, "spi")
    G_phy = apply_limit(G, lim_phy, "gra")

    add_phy = (
        F(row.phy_cor) * C_phy +
        F(row.phy_spi) * S_phy +
        F(row.phy_gra) * G_phy
    )
    phy = base_phy + add_phy

    # ---- 魔法 ----
    C_mag = apply_limit(C, lim_mag, "cor")
    S_mag = apply_limit(S, lim_mag, "spi")
    G_mag = apply_limit(G, lim_mag, "gra")

    add_mag = (
        F(row.mag_cor) * C_mag +
        F(row.mag_spi) * S_mag +
        F(row.mag_gra) * G_mag
    )
    mag = base_mag + add_mag

    # ---- 稳定 ----
    C_sta = apply_limit(C, lim_sta, "cor")
    S_sta = apply_limit(S, lim_sta, "spi")
    G_sta = apply_limit(G, lim_sta, "gra")

    add_sta = (
        F(row.sta_cor) * C_sta +
        F(row.sta_spi) * S_sta +
        F(row.sta_gra) * G_sta
    )
    sta = base_sta + add_sta

    return phy, mag, sta, add_phy, add_mag, add_sta

# ================== 等价压缩 ==================
def compress(df, C, S, G):
    groups = {}
    for _, r in df.iterrows():
        p, m, s, ap, am, ast = calc(r, C, S, G)
        key = (p, m, s)   
        if key not in groups:
            groups[key] = {"rows": [], "data": (p, m, s, ap, am, ast)}
        groups[key]["rows"].append(r)
    return list(groups.values())

# ================== 搜索前三档 ==================
def find_top(C, S, G, w1, w2, w3):

    H = compress(helmet_df, C, S, G)
    B = compress(body_df,   C, S, G)
    Sg = compress(boots_df, C, S, G)

    results = []

    for h in H:
        hp, hm, hs, _, _, _ = h["data"]
        for b in B:
            bp, bm, bs, _, _, _ = b["data"]
            for s in Sg:
                sp, sm, ss, _, _, _ = s["data"]

                phy = hp + bp + sp
                mag = hm + bm + sm
                sta = hs + bs + ss

                score = float(w1*phy + w2*mag + w3*sta)
                results.append((score, h, b, s, (phy, mag, sta)))

    results.sort(key=lambda x: x[0], reverse=True)

    tiers, cur = [], None
    for r in results:
        if cur is None or abs(r[0] - cur) > 1e-6:
            if len(tiers) == 3:
                break
            tiers.append([])
            cur = r[0]
        tiers[-1].append(r)

    return tiers

# ================== GUI ==================
root = tk.Tk()
root.title("装备选择器")
root.geometry("960x720")

# ---- 输入 ----
tk.Label(root, text="勇气").grid(row=0, column=0)
tk.Label(root, text="精神").grid(row=1, column=0)
tk.Label(root, text="优雅").grid(row=2, column=0)

C = tk.Entry(root); C.grid(row=0, column=1)
S = tk.Entry(root); S.grid(row=1, column=1)
G = tk.Entry(root); G.grid(row=2, column=1)

# ---- 权重 ----
presets = {
    "平均": (1,1,1),
    "物理优先": (1.3,1,0.7),
    "魔法优先": (1,1.3,0.7),
    "忽视稳定": (1,1,0.7)
}

combo = ttk.Combobox(root, values=list(presets.keys())+["自定义"], state="readonly")
combo.grid(row=0, column=3)
combo.set("平均")

w1 = tk.DoubleVar(value=1)
w2 = tk.DoubleVar(value=1)
w3 = tk.DoubleVar(value=1)

def preset_changed(e):
    name = combo.get()
    if name in presets:
        a,b,c = presets[name]
        w1.set(a); w2.set(b); w3.set(c)

def check_custom(*_):
    if (w1.get(), w2.get(), w3.get()) not in presets.values():
        combo.set("自定义")

combo.bind("<<ComboboxSelected>>", preset_changed)

for i,(txt,var) in enumerate([("物理权重",w1),("魔法权重",w2),("稳定权重",w3)]):
    tk.Label(root,text=txt).grid(row=1+i,column=2)
    tk.Entry(root,textvariable=var,width=6).grid(row=1+i,column=3)
    var.trace_add("write", check_custom)

# ---- 输出框 ----
output = tk.Text(root, width=120, height=34, wrap="word")
output.grid(row=5, column=0, columnspan=5, pady=10)

# 样式
output.tag_configure("tier",  font=("Arial",13,"bold"), foreground="#003366")
output.tag_configure("part",  font=("Arial",12,"bold underline"), foreground="#1f618d")
output.tag_configure("drop",  font=("Arial",10,"italic"), foreground="#7f8c8d")
output.tag_configure("score", font=("Consolas",10,"bold"), foreground="#7d3c98")
output.tag_configure("sum",   font=("Arial",11,"bold"), foreground="#145a32")

output.config(state="disabled")

def insert_part(title, g):
    p, m, s, ap, am, ast = g["data"]
    namestr = " / ".join(str(r["name"]) for r in g["rows"])
    drops = " / ".join(sorted({str(r["drop"]) for r in g["rows"]}))

    output.insert("end", title, "part")
    output.insert("end", ": ")
    output.insert("end", f"{namestr}\n")

    output.insert("end", "  来源", "drop")
    output.insert("end", ": ")
    output.insert("end", f"{drops}\n", "drop")

    output.insert(
        "end",
        f"  物理(+{fmt(ap)}){fmt(p)}  "
        f"魔法(+{fmt(am)}){fmt(m)}  "
        f"稳定(+{fmt(ast)}){fmt(s)}\n"
    )


def run():
    tiers = find_top(C.get(), S.get(), G.get(), w1.get(), w2.get(), w3.get())

    output.config(state="normal")
    output.delete("1.0","end")

    for i, tier in enumerate(tiers, 1):
        output.insert("end", f"\n======= 第 {i} 档（并列 {len(tier)} 套） =======\n", "tier")
        for score, h, b, s, (tp, tm, ts) in tier:
            output.insert("end", f"\n评分: {score:.2f}\n", "score")
            insert_part("头盔", h)
            insert_part("胸甲", b)
            insert_part("鞋子", s)
            output.insert(
                "end",
                f"合计 → 物理 {float(tp):.1f}  魔法 {float(tm):.1f}  "
                f"稳定 {float(ts):.1f}  总和 {float(tp+tm+ts):.1f}\n",
                "sum"
            )

    output.config(state="disabled")

tk.Button(root, text="计算最优组合", command=run, width=22, height=2)\
  .grid(row=4, column=0, columnspan=4)

root.mainloop()
