using System;
using UnityEngine;

[Serializable]
public sealed class AgentModel
{
    [SerializeField] private int hungerValue;
    [SerializeField] private int fatigueValue;
    [SerializeField] private int waterValue;
    [SerializeField] private int money;
    [SerializeField] private string agentName;
    [SerializeField] private string agentCode;

    public int HungerValue
    {
        get => hungerValue;
        set => hungerValue = Mathf.Clamp(value, 0, 100);
    }

    public int FatigueValue
    {
        get => fatigueValue;
        set => fatigueValue = Mathf.Clamp(value, 0, 100);
    }

    public int WaterValue
    {
        get => waterValue;
        set => waterValue = Mathf.Clamp(value, 0, 100);
    }

    public int Money
    {
        get => money;
        set => money = Mathf.Max(0, value);
    }

    public string AgentName
    {
        get => agentName;
        set => agentName = string.IsNullOrWhiteSpace(value) ? string.Empty : value.Trim();
    }

    public string AgentCode
    {
        get => agentCode;
        set => agentCode = string.IsNullOrWhiteSpace(value) ? string.Empty : value.Trim();
    }

    public AgentModel(
        string agentCode,
        string agentName,
        int hungerValue = 80,
        int fatigueValue = 80,
        int waterValue = 80,
        int money = 1000)
    {
        AgentCode = agentCode;
        AgentName = agentName;
        HungerValue = hungerValue;
        FatigueValue = fatigueValue;
        WaterValue = waterValue;
        Money = money;
    }

    public void UpdateRuntimeValues(int hungerValue, int fatigueValue, int waterValue, int money)
    {
        HungerValue = hungerValue;
        FatigueValue = fatigueValue;
        WaterValue = waterValue;
        Money = money;
    }
}
