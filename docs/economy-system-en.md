# Economic System Design

## Overview

The economic system in this project is not just "random price movement." It is built around four interacting layers: **mean reversion + log-space noise + inventory replenishment + trading friction**. The goal is not to simulate a perfectly realistic market, but to create one that is:

- volatile enough to create trading opportunities
- stable enough not to drift out of control
- differentiated enough that item categories carry different risk profiles
- structured enough that survival goods and speculative goods support different play styles

## 1. Price Model: Mean Reversion + Log-Space Noise

The market price update is implemented in `MarketComponent.generate_price()`:

```python
lnP = lnP + kappa * (lnbase - lnP) + rng.normal(0.0, sigma, size=lnP.shape)
next_price = exp(lnP)
```

In mathematical form:

$$
\log P_{t+1} = \log P_t + \kappa (\log P^{*} - \log P_t) + \varepsilon_t
$$

$$
\varepsilon_t \sim \mathcal{N}(0, \sigma^2)
$$

where:

- $P_t$ is the current price
- $P^{*}$ is the intrinsic or base price `base_price`
- $\kappa$ controls mean reversion speed
- $\sigma$ controls volatility

This is, in essence, a discrete mean-reverting process defined in log-price space.

## 2. Why Model in Log Space

Modeling in log space has three direct advantages:

- prices remain strictly positive
- volatility is naturally relative rather than absolute
- low-priced and high-priced items can share the same dynamics

So the noise here is multiplicative in effect, not just a flat additive perturbation.

## 3. KAPPA: Why 0.11

The current configuration is:

```python
KAPPA = {
    "comsumable": 0.11,
    "valuable": 0.11,
}
```

$\kappa = 0.11$ means roughly 11% of the deviation from base value is pulled back each day. Ignoring noise, the deviation decays as:

$$
(1 - \kappa)^t = 0.89^t
$$

Its approximate half-life is:

$$
t_{\frac{1}{2}} \approx \frac{\ln 0.5}{\ln 0.89} \approx 6 \text{ days}
$$

That gives the system a useful balance:

- trends last long enough to be noticed and traded
- prices do not remain detached from fundamentals for too long

Both item categories share the same `KAPPA` because the category distinction is primarily expressed through volatility, not reversion speed.

## 4. SIGMA: Why Consumables and Valuables Differ So Much

The current configuration is:

```python
SIGMA = {
    "comsumable": 0.15,
    "valuable": 0.4,
}
```

### Consumables: $\sigma = 0.15$

This implies a typical daily relative fluctuation around:

$$
e^{0.15} \approx 1.16
$$

or about $\pm 16\%$.  
That is enough to make water, bread, and meat economically meaningful without destabilizing survival.

### Valuables: $\sigma = 0.4$

This implies a typical daily relative fluctuation around:

$$
e^{0.4} \approx 1.49
$$

or nearly $\pm 50\%$.  
That makes silver rings and gold behave much more like volatile assets than ordinary goods.

So in practice, `SIGMA` defines the market's risk layering:

- consumables are relatively stable
- valuables are speculative

## 5. Long-Run Stability: Why the Market Does Not Blow Up

The model is stable not because the random term is "small," but because the mean-reverting process itself has a stationary distribution.

The approximate steady-state variance of log-price around $\log P^{*}$ is:

$$
\mathrm{Var}(\log P) \approx \frac{\sigma^2}{1 - (1 - \kappa)^2}
$$

At $\kappa = 0.11$:

$$
1 - 0.89^2 = 0.2079
$$

This means:

- consumables have relatively mild long-run volatility
- valuables have significantly larger long-run volatility
- both remain bounded by the mean-reversion term

So the market keeps producing opportunities without drifting into numerical absurdity over long simulations.

## 6. Inventory Replenishment: A Second Constraint Beyond Price

The market replenishes inventory each day, but not instantly to full:

```python
self._stock[item_id] = min(default_quantity, current_stock + DEFAULT_MARKET_STOCK_INCREASE)
```

Current settings:

- default stock: `DEFAULT_MARKET_STOCK = 40`
- daily replenishment: `DEFAULT_MARKET_STOCK_INCREASE = 10`

This matters because:

- aggressive buying leaves short-term traces in the market
- the market cannot be permanently emptied by one action
- supply recovers gradually rather than resetting immediately

That gives the system both perturbability and recoverability.

## 7. Bid-Ask Spread as Trading Friction

If there were volatility but no friction, strategy would collapse into trivial arbitrage. That is why each item also has a `sellRatio`:

- water, bread: `0.85`
- meat: `0.8`
- valuables: close to or equal to `1`

This makes the design intention clear:

- consumables behave more like use goods
- valuables behave more like speculative assets

`sellRatio` and `SIGMA` together determine whether a category is better suited for survival consumption or capital accumulation.

## 8. Resulting Gameplay Structure: Two Survival Paths

These parameters naturally create two distinct play styles:

- low-risk path: use consumables for supply management and prioritize survival
- high-risk path: trade valuables in search of larger profits

This distinction is not explicitly written into the rules. It emerges from the market parameters themselves.

## 9. Why This System Is Effective

From an engineering perspective, the system uses only a few parameters, but each has a clear role:

- `base_price`: fundamental anchor
- `KAPPA`: reversion speed
- `SIGMA`: volatility scale
- `sellRatio`: trading friction
- `stock + restock`: supply constraint

That is enough to produce a micro-economy that is interpretable, tunable, and stable over long runs, while still being rich enough to support a portfolio-grade multi-agent trading scenario.
