using System;
using UnityEngine;

[Serializable]
public sealed class ShopProductModel
{
    [SerializeField] private string productName;
    [SerializeField] private int currentStock;
    [SerializeField] private int purchaseQuantity;
    [SerializeField] private int todayPrice;
    [SerializeField] private int yesterdayPrice;
    [SerializeField] private int basePrice;
    [SerializeField] private int costPrice;
    [SerializeField] private int defaultStock;
    [SerializeField] private bool priceLocked;

    public string ProductName
    {
        get => productName;
        set => productName = string.IsNullOrWhiteSpace(value) ? string.Empty : value.Trim();
    }

    public int CurrentStock
    {
        get => currentStock;
        set => currentStock = Mathf.Max(0, value);
    }

    public int PurchaseQuantity
    {
        get => purchaseQuantity;
        set => purchaseQuantity = Mathf.Max(0, value);
    }

    public int TodayPrice
    {
        get => todayPrice;
        set => todayPrice = Mathf.Max(0, value);
    }

    public int YesterdayPrice
    {
        get => yesterdayPrice;
        set => yesterdayPrice = Mathf.Max(0, value);
    }

    public int BasePrice
    {
        get => basePrice;
        set => basePrice = Mathf.Max(0, value);
    }

    public int CostPrice
    {
        get => costPrice;
        set => costPrice = Mathf.Max(0, value);
    }

    public int DefaultStock
    {
        get => defaultStock;
        set => defaultStock = Mathf.Max(0, value);
    }

    public bool PriceLocked
    {
        get => priceLocked;
        set => priceLocked = value;
    }

    public ShopProductModel(string productName, int costPrice, int purchaseQuantity, int todayPrice, int currentStock, bool priceLocked = false, int defaultStock = 0, int yesterdayPrice = 0, int basePrice = 0)
    {
        ProductName = productName;
        CostPrice = costPrice;
        PurchaseQuantity = purchaseQuantity;
        TodayPrice = todayPrice;
        CurrentStock = currentStock;
        PriceLocked = priceLocked;
        DefaultStock = defaultStock > 0 ? defaultStock : currentStock;
        YesterdayPrice = yesterdayPrice > 0 ? yesterdayPrice : todayPrice;
        BasePrice = basePrice > 0 ? basePrice : todayPrice;
    }
}
