from fractions import Fraction
from itertools import product

# ================= 基础配置 =================

BASE = {
    "phy": 3,
    "mag": 2,
    "sta": 1,
}

AFFECTS = {
    "phy": ["gra", "spi"],
    "mag": ["spi"],
    "sta": ["gra"],
}

OBS = [
    {
        "attr": {"cor": 30, "spi": 30, "gra": 30},
        "display": {"phy": 15, "mag": 12, "sta": 5},
    },
    {
        "attr": {"cor": 40, "spi": 20, "gra": 35},
        "display": {"phy": 13, "mag": 9, "sta": 5},
    },
    {
        "attr": {"cor": 20, "spi": 40, "gra": 25},
        "display": {"phy": 14, "mag": 12, "sta": 5},
    },
    {
        "attr": {"cor": 15, "spi": 15, "gra": 10},
        "display": {"phy": 11, "mag": 7, "sta": 3},
    }
]

EPS = Fraction(5, 10)
CAP_GAME_MIN = Fraction(11)

# ================= 倾向候选 =================

def build_aff_cand():
    vals = set()
    for i in range(1, 21):
        vals.add(Fraction(i, 10))
    for i in range(1, 11):
        vals.add(Fraction(i, 15))
    for i in range(5, 11):
        vals.add(Fraction(i, 40))
    return sorted(v for v in vals if v > 0)

AFF_CAND = build_aff_cand()

# ================= 预计算 OBS（减少 Fraction 构造） =================

PRECOMP = {}

for def_name in BASE:
    base = Fraction(BASE[def_name])
    lst = []
    for obs in OBS:
        disp = Fraction(obs["display"][def_name])
        lo = disp - base - EPS
        hi = disp - base + EPS

        # attr 全部转成 Fraction
        attr_frac = {k: Fraction(v) for k, v in obs["attr"].items()}

        lst.append((lo, hi, attr_frac))
    PRECOMP[def_name] = lst

# ================= 核心推断（方案 B + 剪枝） =================

def infer(def_name):
    affects = AFFECTS[def_name]
    if not affects:
        return []

    results = []

    for fs in product(AFF_CAND, repeat=len(affects)):
        f_map = dict(zip(affects, fs))

        # ---------- 剪枝 1：cap=CAP_GAME_MIN 仍不可能 ----------
        dead = False
        for lo, hi, attr in PRECOMP[def_name]:
            total_min = sum(
                f_map[a] * min(CAP_GAME_MIN, attr[a])
                for a in affects
            )
            if total_min > hi:
                dead = True
                break
        if dead:
            continue
        # -------------------------------------------------------

        feasible_caps = []

        cap_ranges = {
            a: range(int(CAP_GAME_MIN), int(max(attr[a] for _, _, attr in PRECOMP[def_name])) + 1)
            for a in affects
        }

        for caps in product(*cap_ranges.values()):
            cap_map = dict(zip(affects, map(Fraction, caps)))

            ok = True
            for lo, hi, attr in PRECOMP[def_name]:
                total = sum(
                    f_map[a] * min(cap_map[a], attr[a])
                    for a in affects
                )
                if not (lo <= total <= hi):
                    ok = False
                    break

            if ok:
                feasible_caps.append(cap_map)

        if not feasible_caps:
            continue

        cap_proj = {}
        for a in affects:
            vals = [c[a] for c in feasible_caps]
            cap_proj[a] = (min(vals), max(vals))

        results.append({
            "f": f_map,
            "cap_proj": cap_proj,
            "feasible_caps": feasible_caps
        })

    return results

# ================= 输出（面积条形图） =================

def draw_area_bar(dist, label):
    max_len = 40
    print(f"\n{label} 面积分布:")
    for k in ["11~22", "22~33", ">=33"]:
        p = dist.get(k, 0.0)
        bar_len = int(p * max_len)
        bar = "#" * bar_len + "-" * (max_len - bar_len)
        print(f"    {k}: {p*100:6.2f}% {bar}")

# 翻译字典
TRANSLATION = {
    # 防御类型翻译
    "phy": "物理防御",
    "mag": "魔法防御", 
    "sta": "稳定性",
    # 属性翻译
    "gra": " 优雅 ",
    "spi": " 精神 ",
    "cor": " 勇气 ",
    # 其他翻译
    "cap": "属性上限",
}

def get_def_name_chinese(def_name):
    """获取防御类型的中文名"""
    return TRANSLATION.get(def_name, def_name)

def get_attr_chinese(attr):
    """获取属性的中文名"""
    return TRANSLATION.get(attr, attr)

def get_cap_label_chinese(def_name, attr):
    """获取cap标签的中文"""
    def_chinese = get_def_name_chinese(def_name)
    attr_chinese = get_attr_chinese(attr)
    cap_chinese = TRANSLATION.get("cap", "cap")
    return f"{def_chinese}中{attr_chinese}的{cap_chinese}"

def summarize(def_name, results):
    # 获取防御类型的中文名，如果没有翻译则使用原始名称
    def_name_chinese = get_def_name_chinese(def_name)
    print(f"\n[{def_name_chinese}]")

    if not results:
        print("  无可行解")
        return

    feasible_solutions_chinese = TRANSLATION.get("可行解数量", "可行解数量")
    print(f"  {feasible_solutions_chinese}: {len(results)}")

    affects = AFFECTS[def_name]

    for a in affects:
        # 获取属性的中文名，如果没有翻译则使用原始名称
        attr_chinese = get_attr_chinese(a)
        tendency_chinese = TRANSLATION.get("倾向", "倾向")
        vals = sorted(r["f"][a] for r in results)
        print(f"  {tendency_chinese} {attr_chinese}: {vals[0]} ~ {vals[-1]} [{float((vals[0]+vals[-1])/2):.3f}±({float((vals[-1]-vals[0])/2):.3f}|{float(100*((vals[-1]-vals[0])/(vals[0]+vals[-1]))):.1f}%)]")

        area = {"11~22": 0, "22~33": 0, ">=33": 0}
        total = 0

        for r in results:
            for cap_map in r["feasible_caps"]:
                v = cap_map[a]
                total += 1
                if v < 22:
                    area["11~22"] += 1
                elif v < 33:
                    area["22~33"] += 1
                else:
                    area[">=33"] += 1

        area = {k: area[k] / total for k in area}
        # 使用中文标签，如果没有翻译则使用原始名称
        cap_label_chinese = get_cap_label_chinese(def_name, a)
        draw_area_bar(area, cap_label_chinese)

# ================= 主程序 =================

if __name__ == "__main__":
    for d in ["phy", "mag", "sta"]:
        res = infer(d)
        summarize(d, res)