
using UnityEngine;
using UnityEngine.UI;
using System.Collections;



public class PlayerHUD : MonoBehaviour
{
    [Header("Refs")]
    public CanvasGroup canvasGroup;       
    public Animator workIndicatorAnimator;     
    public StatusPopupSpawner statusPopup;

    [Header("Working Indicator")]
    public bool hideHudWhenIdle = false;   
    public float showFadeTime = 0.12f;
    public float hideFadeTime = 0.12f;

    private Coroutine _timerCo;

    public void PopStatus(string key, int delta, string overrideText = null)
    {
        if (statusPopup != null)
            statusPopup.PopStatus(key, delta, overrideText);
    }

    void Reset()
    {
        canvasGroup = GetComponent<CanvasGroup>();
    }

    void Awake()
    {
        if (hideHudWhenIdle && canvasGroup != null)
        {
            canvasGroup.alpha = 0f;
        }
        if (workIndicatorAnimator != null)
        {
            workIndicatorAnimator.SetBool("Working", false);
        }

    }


    public void StartWork(float durationSec = 0f)
    {
        if (workIndicatorAnimator != null)
            workIndicatorAnimator.SetBool("Working", true);

        if (hideHudWhenIdle && canvasGroup != null)
            FadeCanvas(1f, showFadeTime);

        // 停止旧计时器
        if (_timerCo != null)
            StopCoroutine(_timerCo);

        // 有时长就启动计时器
        if (durationSec > 0f)
            _timerCo = StartCoroutine(CoWorkTimer(durationSec));
        else
            _timerCo = null; // 无时长则不计时
    }


    public void StopWork()
    {
        if (workIndicatorAnimator != null)
            workIndicatorAnimator.SetBool("Working", false);

        if (_timerCo != null)
        {
            StopCoroutine(_timerCo);
            _timerCo = null;
        }


        if (hideHudWhenIdle && canvasGroup != null)
            FadeCanvas(0f, hideFadeTime);
    }

    private IEnumerator CoWorkTimer(float duration)
    {
        float t = 0f;
        while (t < duration)
        {
            t += Time.deltaTime;
            yield return null;
        }
        StopWork();
    }

    private void FadeCanvas(float target, float time)
    {
        if (gameObject.activeInHierarchy)
            StartCoroutine(CoFadeCanvas(target, time));
    }

    private IEnumerator CoFadeCanvas(float target, float time)
    {
        if (canvasGroup == null)
            yield break;

        float start = canvasGroup.alpha;
        float t = 0f;
        while (t < time)
        {
            t += Time.deltaTime;
            canvasGroup.alpha = Mathf.Lerp(start, target, t / time);
            yield return null;
        }
        canvasGroup.alpha = target;
    }

}
