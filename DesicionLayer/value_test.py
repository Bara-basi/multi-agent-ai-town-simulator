# -*- coding: utf-8 -*-
# 模拟 + 可视化（价格轨迹 & 现金轨迹）
# 1) 目标函数：NPC通过倒卖基础生存物品的差价期望等于每日消耗期望
# 2) 均值回归 + 对数噪声市场
# 3) 设定交易规则价格大于buy_th卖出，小于sell_th买入
import numpy as np
import matplotlib.pyplot as plt

def simulate_with_trace(
    kappa=0.11,
    sigma=0.4,
    buy_limit=1,
    buy_th=0.7,
    sell_th=1.3,
    days=500,
    # seed=42,
):
    rng = np.random.default_rng()

    items = [
        # {"name": "water", "base": 5.0,  "sell_ratio": 0.85, "stock": 40},
        # {"name": "bread", "base": 7.0,  "sell_ratio": 0.85, "stock": 60},
        # {"name": "bbq",   "base": 15.0, "sell_ratio": 0.80, "stock": 40},
        {"name": "silver_ring", "base": 200.0,  "sell_ratio": 1, "stock": 10},
        {"name": "gold", "base": 1000.0,  "sell_ratio": 1, "stock": 10},
    ]

    lnbase = np.log([it["base"] for it in items])
    lnP = lnbase.copy()

    cash = 1000.0
    holdings = np.zeros(len(items), dtype=int)

    price_trace = []
    cash_trace = []

    for t in range(days):
        # 对数均值回归 + 噪声
        lnP = lnP + kappa * (lnbase - lnP) + rng.normal(0, sigma, size=len(items))
        P = np.exp(lnP)

        # 卖出
        for i, it in enumerate(items):
            if P[i] > sell_th * it["base"] and holdings[i] > 0:
                revenue = holdings[i] * P[i] * it["sell_ratio"]
                cash += revenue
                holdings[i] = 0

        # 买入
        for i, it in enumerate(items):
            if P[i] < buy_th * it["base"] and cash >=500:
                qty = min(buy_limit, it["stock"], int(cash // P[i]))
                if qty > 0:
                    cash -= qty * P[i]
                    holdings[i] += qty
        daily_cost = 5.0 + 15.0 * (8 / 35)
        cash -= daily_cost
        if cash<0:
            return np.array(price_trace), np.array(cash_trace)
        price_trace.append(P.copy())
        cash_trace.append(cash)

    return np.array(price_trace), np.array(cash_trace)


# ===== 运行模拟 =====
prices, cash = simulate_with_trace()

days = np.arange(len(cash))

# ===== 图1：价格轨迹（展示 water） =====
plt.figure()
plt.plot(days, prices[:, 0])
plt.title("Ring Price Over Time")
plt.xlabel("Day")
plt.ylabel("Price")
plt.show()

# ===== 图2：现金轨迹 =====
plt.figure()
plt.plot(days, cash)
plt.title("Cash Over Time")
plt.xlabel("Day")
plt.ylabel("Cash")
plt.show()