using System;
using UnityEngine;

[Serializable]
public sealed class ShopProductModel
{
    [SerializeField] private string productName;
    [SerializeField] private int currentStock;
    [SerializeField] private int purchaseQuantity;
    [SerializeField] private int todayPrice;
    [SerializeField] private int costPrice;
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

    public int CostPrice
    {
        get => costPrice;
        set => costPrice = Mathf.Max(0, value);
    }

    public bool PriceLocked
    {
        get => priceLocked;
        set => priceLocked = value;
    }

    public ShopProductModel(string productName, int costPrice, int purchaseQuantity, int todayPrice, int currentStock, bool priceLocked = false)
    {
        ProductName = productName;
        CostPrice = costPrice;
        PurchaseQuantity = purchaseQuantity;
        TodayPrice = todayPrice;
        CurrentStock = currentStock;
        PriceLocked = priceLocked;
    }
}
