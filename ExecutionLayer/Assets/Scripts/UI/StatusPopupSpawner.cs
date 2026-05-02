using UnityEngine;
using System.Collections.Generic;

public class StatusPopupSpawner : MonoBehaviour
{
    [Header("Refs")]
    public RectTransform popStack;      // PlayerHUD 下的 PopStack
    public PopItem popItemPrefab;       // PopItem 预制体
    public StatusIconSet iconSet;       // 图标表 ScriptableObject

    [Header("Pool")]
    public int prewarmCount = 8;
    public int maxActive = 16;

    [Header("Style")]
    public Color positiveColor = new Color(0.2f, 0.9f, 0.3f);
    public Color negativeColor = new Color(0.95f, 0.2f, 0.2f);
    public float riseDistance = 6f;    // 上飘高度（与 PopItem 保持一致）

    private readonly Queue<PopItem> _pool = new Queue<PopItem>();
    private readonly List<PopItem> _active = new List<PopItem>(); // 0=最早（最上面）

    void Awake()
    {
        Prewarm();
    }

    void Prewarm()
    {
        if (!popItemPrefab || !popStack) return;
        for (int i = 0; i < prewarmCount; i++)
        {
            var inst = Instantiate(popItemPrefab, popStack);
            inst.gameObject.SetActive(false);
            _pool.Enqueue(inst);
        }
    }

    PopItem Get()
    {
        if (_pool.Count > 0) return _pool.Dequeue();

        if (_active.Count >= maxActive)
        {
            // 超量时强制回收最早的一条，避免爆 UI
            ForceRecycle(_active[0]);
            _active.RemoveAt(0);
            ReindexLanes();
        }
        return Instantiate(popItemPrefab, popStack);
    }

    void Recycle(PopItem item)
    {
        item.gameObject.SetActive(false);
        item.rt.anchoredPosition = Vector2.zero;
        item.rt.localScale = Vector3.one;
        _pool.Enqueue(item);
    }

    void ForceRecycle(PopItem item)
    {
        item.StopAllCoroutines();
        Recycle(item);
    }

    void ReindexLanes()
    {
        for (int i = 0; i < _active.Count; i++)
            _active[i].UpdateLane(i);   // i 号条目位于 i 号车道（0 在最上）
    }

    // —— 对外唯一 API ——
    public void PopStatus(string key, int delta, string overrideText = null)
    {
        var icon = iconSet ? iconSet.Get(key) : null;
   
        string sign = delta >= 0 ? "+" : "";
   
        string text = overrideText ?? $"{sign}{delta}";
       
        var color = delta >= 0 ? positiveColor : negativeColor;
     
        var item = Get();
        item.gameObject.SetActive(true);

        int lane = _active.Count;              // 新来的放在最下方
        item.laneIndex = lane;
        item.riseDistance = riseDistance;
        item.SetLane(lane ,snap: true);

        _active.Add(item);
        item.Play(icon, text, color, OnItemComplete);
    }

    void OnItemComplete(PopItem item)
    {
        int idx = _active.IndexOf(item);
        if (idx >= 0) _active.RemoveAt(idx);
        Recycle(item);
        ReindexLanes(); // 让下面的条目整体上移
    }
}
