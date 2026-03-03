using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System.Collections;

public class PopItem : MonoBehaviour
{
    [Header("Refs")]
    public Image icon;
    public TMP_Text label;
    public CanvasGroup cg;
    public RectTransform rt;

    [Header("Anim")]
    public float riseDistance = 6f;      // 自身动画上飘高度
    public float duration = 2.4f;         // 总时长
    public AnimationCurve moveCurve = AnimationCurve.EaseInOut(0, 0, 1, 1);
    public AnimationCurve fadeCurve = AnimationCurve.Linear(0, 1, 1, 0);
    public AnimationCurve scaleCurve = AnimationCurve.EaseInOut(0, 1.1f, 1, 1f);

    [Header("Lane")]
    public int laneIndex = 0;             // 0 在最上方

    private System.Action<PopItem> _onComplete;
    private bool _playing;
    private Vector2 _laneBase;            // 由 lane 决定的基础位置
    private Vector2 visual;
    private float _t;                     // 动画计时

    void Reset()
    {
        rt = GetComponent<RectTransform>();
        cg = GetComponent<CanvasGroup>();
        icon = transform.Find("Icon")?.GetComponent<Image>();
        label = transform.Find("Label")?.GetComponent<TMP_Text>();

    }

    public void SetLane(int lane, bool snap = false)
    {
        laneIndex = lane;
        var newBase = new Vector2(0f, 0f);

        if (snap || rt == null)
        {
            _laneBase = newBase;

        }
        else
        {
            // 平滑换道：保持视觉位置不跳变
            visual = rt.anchoredPosition;
            float p = Mathf.Clamp01(_t / Mathf.Max(0.0001f, duration));
            float moveT = moveCurve.Evaluate(p);
            Vector2 animRise = new Vector2(0f, riseDistance * moveT);
            _laneBase = visual - animRise;
        }
    }

    public void UpdateLane(int newLaneIndex)
    {
        SetLane(newLaneIndex, snap: false);
    }

    public void Play(Sprite s, string text, Color textColor, System.Action<PopItem> onComplete)
    {
        if (rt == null) rt = GetComponent<RectTransform>();
        if (cg == null) cg = GetComponent<CanvasGroup>();

        _onComplete = onComplete;
        _playing = true;

        if (icon) icon.sprite = s;
        if (label)
        {
            label.text = text;
            label.color = textColor;
        }

        StopAllCoroutines();
        StartCoroutine(CoPlay());
    }

    IEnumerator CoPlay()
    {
        cg.alpha = 1f;
        _t = 0f;

        while (_t < duration)
        {
            _t += Time.deltaTime;
            float p = Mathf.Clamp01(_t / duration);

            float moveT = moveCurve.Evaluate(p);
            var animRise = new Vector2(0f, riseDistance * moveT);

            cg.alpha = fadeCurve.Evaluate(p);
            rt.localScale = Vector3.one * scaleCurve.Evaluate(p);
            rt.anchoredPosition = _laneBase + animRise;

            yield return null;
        }

        _playing = false;
        _onComplete?.Invoke(this);
    }

    public bool IsPlaying() => _playing;
}
