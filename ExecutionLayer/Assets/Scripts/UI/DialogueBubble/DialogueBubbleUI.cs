using TMPro;
using UnityEngine;
using UnityEngine.UI;
using System.Collections;
using System.Collections.Generic;

public class DialogueBubbleUI : MonoBehaviour
{
    [Header("References")]
    public RectTransform bubbleBg;
    public TextMeshProUGUI bubbleText;
    public CanvasGroup canvasGroup;

    [Header("Size Settings")]
    public float minWidth = 260f;
    public float maxWidth = 260f;
    public float minHeight = 110f;
    public float paddingLeft = 26f;
    public float paddingRight = 26f;
    public float paddingTop = 20f;
    public float paddingBottom = 28f;
    public float minWidthForShortText = 170f;
    public float minHeightForShortText = 78f;
    public int shortTextCharThreshold = 10;

    [Header("Lifetime")]
    public float autoHideSeconds = 2.5f;

    [Header("Typewriter")]
    public float charactersPerSecond = 24f;

    [Header("Rendering Clarity")]
    public float minDynamicPixelsPerUnit = 16f;

    [Header("Tail Alignment")]
    public bool autoAlignTailForShortText = true;
    public float tailCompensationPerWidth = 0.45f;

    private Canvas worldCanvas;
    private CanvasScaler canvasScaler;
    private readonly Queue<string> messageQueue = new Queue<string>();
    private Coroutine queueCoroutine;
    private RectTransform rootRectTransform;
    private Vector2 baseAnchoredPosition;

    private void Awake()
    {
        worldCanvas = GetComponent<Canvas>();
        canvasScaler = GetComponent<CanvasScaler>();
        rootRectTransform = transform as RectTransform;

        if (rootRectTransform != null)
        {
            baseAnchoredPosition = rootRectTransform.anchoredPosition;
        }

        if (canvasGroup == null)
        {
            canvasGroup = GetComponent<CanvasGroup>();
        }

        ConfigureWorldSpaceCanvas();
        HideImmediate();
    }

    public void Show(string text)
    {
        if (string.IsNullOrEmpty(text))
        {
            return;
        }

        gameObject.SetActive(true);
        messageQueue.Enqueue(text);

        if (queueCoroutine == null)
        {
            queueCoroutine = StartCoroutine(ProcessMessageQueue());
        }
    }

    public void HideImmediate()
    {
        if (queueCoroutine != null)
        {
            StopCoroutine(queueCoroutine);
            queueCoroutine = null;
        }

        messageQueue.Clear();

        if (canvasGroup != null)
        {
            canvasGroup.alpha = 0f;
        }

        if (bubbleText != null)
        {
            bubbleText.text = string.Empty;
            bubbleText.maxVisibleCharacters = 0;
        }

        ApplyTailAlignmentOffset(maxWidth, 1f);
    }

    public void RefreshSize()
    {
        RefreshSizeForText(bubbleText != null ? bubbleText.text : string.Empty);
    }

    private IEnumerator ProcessMessageQueue()
    {
        while (messageQueue.Count > 0)
        {
            string message = messageQueue.Dequeue();
            yield return ShowSingleMessage(message);
        }

        queueCoroutine = null;
    }

    private IEnumerator ShowSingleMessage(string text)
    {
        if (bubbleText == null || bubbleBg == null)
        {
            yield break;
        }

        if (canvasGroup != null)
        {
            canvasGroup.alpha = 1f;
        }

        bubbleText.text = text;
        bubbleText.maxVisibleCharacters = 0;
        RefreshSizeForText(string.Empty);

        bubbleText.ForceMeshUpdate();
        int totalCharacters = bubbleText.textInfo.characterCount;

        if (totalCharacters > 0)
        {
            float visibleProgress = 0f;
            int lastVisible = -1;

            while (lastVisible < totalCharacters)
            {
                visibleProgress += Mathf.Max(1f, charactersPerSecond) * Time.deltaTime;
                int visibleCount = Mathf.Min(totalCharacters, Mathf.FloorToInt(visibleProgress));

                if (visibleCount != lastVisible)
                {
                    bubbleText.maxVisibleCharacters = visibleCount;

                    int safeCount = Mathf.Clamp(visibleCount, 0, text.Length);
                    string currentText = safeCount > 0 ? text.Substring(0, safeCount) : string.Empty;
                    RefreshSizeForText(currentText);

                    lastVisible = visibleCount;
                }

                yield return null;
            }
        }

        bubbleText.maxVisibleCharacters = int.MaxValue;
        RefreshSizeForText(text);

        float timer = autoHideSeconds;
        while (timer > 0f)
        {
            timer -= Time.deltaTime;
            yield return null;
        }

        if (canvasGroup != null)
        {
            canvasGroup.alpha = 0f;
        }
    }

    private void RefreshSizeForText(string textForMeasure)
    {
        if (bubbleText == null || bubbleBg == null) return;

        bubbleText.enableWordWrapping = true;
        bubbleText.rectTransform.SetSizeWithCurrentAnchors(RectTransform.Axis.Horizontal, maxWidth - paddingLeft - paddingRight);

        Vector2 textSize = bubbleText.GetPreferredValues(
            textForMeasure,
            maxWidth - paddingLeft - paddingRight,
            1000f
        );

        int visibleCharCount = string.IsNullOrWhiteSpace(textForMeasure)
            ? 0
            : textForMeasure.Replace(" ", string.Empty).Replace("\n", string.Empty).Replace("\r", string.Empty).Length;
        float transition = shortTextCharThreshold <= 0 ? 1f : Mathf.Clamp01((float)visibleCharCount / shortTextCharThreshold);

        float adaptiveMinWidth = Mathf.Lerp(minWidthForShortText, minWidth, transition);
        float adaptiveMinHeight = Mathf.Lerp(minHeightForShortText, minHeight, transition);

        float finalWidth = Mathf.Max(adaptiveMinWidth, textSize.x + paddingLeft + paddingRight);
        finalWidth = Mathf.Min(finalWidth, maxWidth);
        float finalHeight = Mathf.Max(adaptiveMinHeight, textSize.y + paddingTop + paddingBottom);

        bubbleBg.SetSizeWithCurrentAnchors(RectTransform.Axis.Horizontal, finalWidth);
        bubbleBg.SetSizeWithCurrentAnchors(RectTransform.Axis.Vertical, finalHeight);

        ApplyTailAlignmentOffset(finalWidth, transition);
    }

    private void ApplyTailAlignmentOffset(float currentWidth, float transition)
    {
        if (!autoAlignTailForShortText || rootRectTransform == null)
        {
            return;
        }

        float widthLoss = Mathf.Max(0f, maxWidth - currentWidth);
        float shortTextWeight = 1f - Mathf.Clamp01(transition);
        float offsetX = widthLoss * tailCompensationPerWidth * shortTextWeight;

        Vector2 anchored = baseAnchoredPosition;
        anchored.x += offsetX;
        rootRectTransform.anchoredPosition = anchored;
    }

    private void ConfigureWorldSpaceCanvas()
    {
        if (worldCanvas == null || worldCanvas.renderMode != RenderMode.WorldSpace)
        {
            return;
        }

        worldCanvas.overridePixelPerfect = true;
        worldCanvas.pixelPerfect = true;

        if (canvasScaler != null)
        {
            canvasScaler.dynamicPixelsPerUnit = Mathf.Max(canvasScaler.dynamicPixelsPerUnit, minDynamicPixelsPerUnit);
        }
    }
}
