using System;
using UnityEngine;

[Serializable]
public sealed class ShopAssistantPlayerModel
{
    [SerializeField] private int currentMoney;
    [SerializeField] private int todayIncome;

    public int CurrentMoney
    {
        get => currentMoney;
        set => currentMoney = value;
    }

    public int TodayIncome
    {
        get => todayIncome;
        set => todayIncome = value;
    }

    public ShopAssistantPlayerModel(int currentMoney = 0, int todayIncome = 0)
    {
        CurrentMoney = currentMoney;
        TodayIncome = todayIncome;
    }
}
