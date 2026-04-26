using System;
using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;
using UnityEngine.TextCore.LowLevel;
using UnityEngine.UI;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Runtime UI for ShopAssistant inventory. It accepts market information from backend
/// and renders products dynamically.
/// </summary>
public sealed class ShopAssistantDisplayUI : MonoBehaviour
{
    private const int FirstRoundIndex = 1;

    [Header("Display")]
    [SerializeField] [Range(0, 7)] private int targetDisplay = 5; // Display6 (0-based index)
    [SerializeField] private string displayCanvasNameHint = "Display6";
    [SerializeField] private int baseResolutionX = 1920;
    [SerializeField] private int baseResolutionY = 1080;

    [Header("Theme")]
    [SerializeField] private Color paperColor = new(0.97f, 0.94f, 0.84f, 0.96f);
    [SerializeField] private Color woodColor = new(0.83f, 0.64f, 0.13f, 1.0f); // #d3a421
    [SerializeField] private Color woodEdgeFade = new(0.93f, 0.80f, 0.46f, 0.95f);
    [SerializeField] private Color textColor = new(0.23f, 0.17f, 0.08f, 1.0f);

    [Header("Style Tunables")]
    [SerializeField] [Range(2f, 12f)] private float panelOutlineThickness = 6f;
    [SerializeField] [Range(1f, 12f)] private float frameBorderThickness = 5f;
    [SerializeField] [Range(0f, 14f)] private float frameBorderInset = 5f;
    [SerializeField] [Range(1f, 8f)] private float statusRowLineThickness = 2f;
    [SerializeField] [Range(0.75f, 0.95f)] private float plusButtonAnchorX = 0.92f;

    [Header("Mock Data")]
    [SerializeField] private int initialRound = 1;
    [SerializeField] private int initialMoney = 1000;
    [SerializeField] private string initialGameState = "回合进行中";

    [Header("Product Images")]
    [SerializeField] private List<ProductImageMapping> productImageMappings = new();
    [SerializeField] private string productImageMappingCsvResourcePath = "ShopAssistant/ProductImageMappings";

    [Header("Inventory Background")]
    [SerializeField] private string inventoryBackgroundResourcePath = "Art/UI/UI/ShopAssistantUI/背景";
    [SerializeField] private string inventoryBackgroundAssetPath = "Assets/Art/UI/UI/ShopAssistantUI/背景.png";
    [SerializeField] private string inventoryBackgroundSpriteName = "背景";

    [Header("Inventory Decorations")]
    [SerializeField] private string statusPanelResourcePath = "Art/UI/UI/ShopAssistantUI/状态面板";
    [SerializeField] private string statusPanelAssetPath = "Assets/Art/UI/UI/ShopAssistantUI/状态面板.png";
    [SerializeField] private string statusPanelSpriteName = "状态面板";
    [SerializeField] private string inventoryTitleResourcePath = "Art/UI/UI/ShopAssistantUI/商店库存标头";
    [SerializeField] private string inventoryTitleAssetPath = "Assets/Art/UI/UI/ShopAssistantUI/商店库存标头.png";
    [SerializeField] private string inventoryTitleSpriteName = "商店库存标头";
    [SerializeField] private string inventoryOpenButtonResourcePath = "Art/UI/UI/ShopAssistantUI/查看库存";
    [SerializeField] private string inventoryOpenButtonAssetPath = "Assets/Art/UI/UI/ShopAssistantUI/查看库存.png";
    [SerializeField] private string inventoryOpenButtonSpriteName = "查看库存";
    [SerializeField] private string inventoryStockButtonResourcePath = "Art/UI/UI/ShopAssistantUI/进货";
    [SerializeField] private string inventoryStockButtonAssetPath = "Assets/Art/UI/UI/ShopAssistantUI/进货.png";
    [SerializeField] private string inventoryStockButtonSpriteName = "进货按钮";
    [SerializeField] private string inventoryRightPanelResourcePath = "Art/UI/UI/ShopAssistantUI/右侧背景板";
    [SerializeField] private string inventoryRightPanelAssetPath = "Assets/Art/UI/UI/ShopAssistantUI/右侧背景板.png";
    [SerializeField] private string inventoryRightPanelSpriteName = "右侧背景板";
    [SerializeField] private string inventoryShopLogoResourcePath = "Art/UI/UI/ShopAssistantUI/商店图案";
    [SerializeField] private string inventoryShopLogoAssetPath = "Assets/Art/UI/UI/ShopAssistantUI/商店图案.png";
    [SerializeField] private string inventoryShopLogoSpriteName = "商店图案";
    [SerializeField] private string inventoryCoinFeatherResourcePath = "Art/UI/UI/ShopAssistantUI/金币和羽毛";
    [SerializeField] private string inventoryCoinFeatherAssetPath = "Assets/Art/UI/UI/ShopAssistantUI/金币和羽毛.png";
    [SerializeField] private string inventoryCoinSpriteName = "金币";
    [SerializeField] private string inventoryFeatherSpriteName = "羽毛";
    [SerializeField] private string inventoryHintPanelResourcePath = "Art/UI/UI/ShopAssistantUI/右下提示背景板";
    [SerializeField] private string inventoryHintPanelAssetPath = "Assets/Art/UI/UI/ShopAssistantUI/右下提示背景板.png";
    [SerializeField] private string inventoryHintPanelSpriteName = "右下提示背景板";
    [SerializeField] private string inventoryProductCellBgResourcePath = "Art/UI/UI/ShopAssistantUI/商品背景板";
    [SerializeField] private string inventoryProductCellBgAssetPath = "Assets/Art/UI/UI/ShopAssistantUI/商品背景板.png";
    [SerializeField] private string inventoryProductCellBgSpriteName = "商品背景板";
    [SerializeField] private string inventoryNameBannerResourcePath = "Art/UI/UI/ShopAssistantUI/文字背景框";
    [SerializeField] private string inventoryNameBannerAssetPath = "Assets/Art/UI/UI/ShopAssistantUI/文字背景框.png";
    [SerializeField] private string inventoryStepperButtonResourcePath = "Art/UI/UI/ShopAssistantUI/加减按钮";
    [SerializeField] private string inventoryStepperButtonAssetPath = "Assets/Art/UI/UI/ShopAssistantUI/加减按钮.png";
    [SerializeField] private string inventoryStepperMinusSpriteName = "减号";
    [SerializeField] private string inventoryStepperPlusSpriteName = "加号";
    [SerializeField] private string inventoryCloseButtonResourcePath = "Art/UI/UI/ShopAssistantUI/关闭按钮";
    [SerializeField] private string inventoryCloseButtonAssetPath = "Assets/Art/UI/UI/ShopAssistantUI/关闭按钮.png";
    [SerializeField] private string inventoryCloseButtonSpriteName = "关闭按钮";

    [Header("Round Transition")]
    [SerializeField] private string roundStartResourcePath = "Art/UI/UI/ShopAssistantUI/回合开始";
    [SerializeField] private string roundStartAssetPath = "Assets/Art/UI/UI/ShopAssistantUI/回合开始.png";
    [SerializeField] private string roundStartSpriteName = "回合开始";
    [SerializeField] private Key roundStartDebugKey = Key.B;
    [SerializeField] private string roundEndResourcePath = "Art/UI/UI/ShopAssistantUI/回合结束";
    [SerializeField] private string roundEndAssetPath = "Assets/Art/UI/UI/ShopAssistantUI/回合结束.png";
    [SerializeField] private string roundEndSpriteName = "回合结束";
    [SerializeField] private Key roundEndDebugKey = Key.E;
    [SerializeField] private float roundStartIntroSeconds = 0.32f;
    [SerializeField] private float roundStartHoldSeconds = 1.25f;
    [SerializeField] private float roundStartOutroSeconds = 0.28f;
    [SerializeField] private float roundEndCountSeconds = 0.62f;
    [SerializeField] private string roundStartAudioResourcePath = "Audio/ShopAssistant/round_start_notice";
    [SerializeField] private string roundEndAudioResourcePath = "Audio/ShopAssistant/round_end_notice";
    [SerializeField] [Range(0f, 1f)] private float roundTransitionAudioVolume = 1f;

    private TMP_FontAsset uiFont;
    private TMP_FontAsset runtimeDynamicChineseFont;
    private GameObject inventoryOverlayRoot;
    private GameObject roundStartOverlayRoot;
    private RectTransform roundStartPanel;
    private CanvasGroup roundStartCanvasGroup;
    private CanvasGroup roundStartTextCanvasGroup;
    private TextMeshProUGUI roundStartNumberText;
    private GameObject roundEndOverlayRoot;
    private RectTransform roundEndPanel;
    private RectTransform roundEndIncomeRow;
    private CanvasGroup roundEndCanvasGroup;
    private CanvasGroup roundEndTextCanvasGroup;
    private TextMeshProUGUI roundEndAmountText;
    private AudioSource roundTransitionAudioSource;
    private AudioClip roundStartAudioClip;
    private AudioClip roundEndAudioClip;
    private AudioClip fallbackRoundStartAudioClip;
    private AudioClip fallbackRoundEndAudioClip;
    private Coroutine roundStartRoutine;
    private Coroutine roundEndRoutine;
    private Coroutine openInventoryAfterRoundStartRoutine;
    private Button openInventoryButton;
    private Button stockInventoryButton;
    private TextMeshProUGUI roundText;
    private TextMeshProUGUI moneyText;
    private TextMeshProUGUI rightPanelMoneyText;
    private TextMeshProUGUI stateText;
    private RectTransform inventoryContentRoot;
    private readonly ShopAssistantPlayerModel playerModel = new();
    private readonly Dictionary<string, Sprite> productImageLookup = new();
    private readonly List<ShopProductModel> marketProducts = new();
    private readonly List<ShopUiStepper> inventorySteppers = new();
    private bool canEditStockPlan;
    private int currentRoundValue;
    private string currentGameStateValue;
    private static readonly Color StatusStaticTextColor = new(0.03f, 0.035f, 0.04f, 1f);
    private static readonly Color StatusDynamicTextColor = new(0.08f, 0.23f, 0.49f, 1f);
    private static readonly Color StatusSettlementTextColor = new(0.75f, 0.08f, 0.08f, 1f);
    private static string pendingMarketInformationJson;
    private static readonly string[] ProductNameBannerSpriteCycle =
    {
        "文字背景框_蓝",
        "文字背景框_褐",
        "文字背景框_棕",
        "文字背景框_紫",
        "文字背景框_橙"
    };

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Bootstrap()
    {
        if (FindObjectOfType<ShopAssistantDisplayUI>() != null)
        {
            return;
        }

        var root = new GameObject("UI_ShopAssistant_Display6");
        root.AddComponent<ShopAssistantDisplayUI>();
    }

    private void Awake()
    {
        uiFont = ResolveUiFont();
        BuildProductImageLookup();
        marketProducts.Clear();
        marketProducts.AddRange(BuildMockProducts());
        BuildUI();
        RefreshTopLeftStatus(initialRound, initialMoney, initialGameState);

        if (!string.IsNullOrWhiteSpace(pendingMarketInformationJson))
        {
            OnMarketInformationReceived(pendingMarketInformationJson);
            pendingMarketInformationJson = null;
        }
    }

    /// <summary>
    /// Entry for WsAgentClient information push.
    /// </summary>
    public static void PushMarketInformationJson(string infoJson)
    {
        var ui = FindObjectOfType<ShopAssistantDisplayUI>();
        if (ui == null)
        {
            pendingMarketInformationJson = infoJson;
            return;
        }

        ui.OnMarketInformationReceived(infoJson);
    }

    private void OnMarketInformationReceived(string infoJson)
    {
        if (string.IsNullOrWhiteSpace(infoJson))
        {
            return;
        }

        var products = ParseMarketInformation(infoJson);
        if (products.Count == 0)
        {
            Debug.LogWarning("[ShopAssistantUI] Market payload parsed, but no products found.");
            return;
        }

        marketProducts.Clear();
        marketProducts.AddRange(products);
        RebuildProductCells();
        Debug.Log($"[ShopAssistantUI] Loaded {products.Count} products from backend market information.");
    }

    private TMP_FontAsset ResolveUiFont()
    {
        var simhei = Resources.Load<TMP_FontAsset>("Fonts & Materials/SIMHEI SDF");
        runtimeDynamicChineseFont = TryCreateDynamicFromTmpSource(simhei);
        if (runtimeDynamicChineseFont == null)
        {
            runtimeDynamicChineseFont = TryCreateDynamicChineseFont();
        }

        // Always prefer dynamic font when available to avoid static SDF glyph gaps.
        if (runtimeDynamicChineseFont != null)
        {
            if (simhei != null)
            {
                if (runtimeDynamicChineseFont.fallbackFontAssetTable == null)
                {
                    runtimeDynamicChineseFont.fallbackFontAssetTable = new List<TMP_FontAsset>();
                }

                if (!runtimeDynamicChineseFont.fallbackFontAssetTable.Contains(simhei))
                {
                    runtimeDynamicChineseFont.fallbackFontAssetTable.Add(simhei);
                }
            }

            return runtimeDynamicChineseFont;
        }

        if (simhei != null)
        {
            // Secondary fallback chain for static SDF.
            if (simhei.fallbackFontAssetTable == null)
            {
                simhei.fallbackFontAssetTable = new List<TMP_FontAsset>();
            }
            return simhei;
        }

        return TMP_Settings.defaultFontAsset;
    }

    private TMP_FontAsset TryCreateDynamicFromTmpSource(TMP_FontAsset tmpFont)
    {
        if (tmpFont == null || tmpFont.sourceFontFile == null)
        {
            return null;
        }

        try
        {
            var tmp = TMP_FontAsset.CreateFontAsset(
                tmpFont.sourceFontFile,
                90,
                9,
                GlyphRenderMode.SDFAA,
                1024,
                1024,
                AtlasPopulationMode.Dynamic,
                true);
            if (tmp != null)
            {
                tmp.name = $"RuntimeTMP_{tmpFont.name}_Dynamic";
                return tmp;
            }
        }
        catch
        {
            // ignore and fallback
        }

        return null;
    }

    private void BuildProductImageLookup()
    {
        productImageLookup.Clear();

        LoadProductMappingsFromCsv(productImageMappingCsvResourcePath);

        if (productImageMappings == null)
        {
            return;
        }

        foreach (var item in productImageMappings)
        {
            RegisterProductImage(item);
        }
    }

    private void LoadProductMappingsFromCsv(string resourcePath)
    {
        if (string.IsNullOrWhiteSpace(resourcePath))
        {
            return;
        }

        var csvAsset = Resources.Load<TextAsset>(resourcePath.Trim());
        if (csvAsset == null)
        {
            Debug.LogWarning($"[ShopAssistantUI] Product mapping CSV not found: Resources/{resourcePath}");
            return;
        }

        var lines = csvAsset.text.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
        for (int i = 1; i < lines.Length; i++)
        {
            var cols = lines[i].Split(',');
            if (cols.Length < 2)
            {
                continue;
            }

            RegisterProductImage(new ProductImageMapping
            {
                productName = cols[0].Trim(),
                imagePath = cols[1].Trim(),
                spriteName = cols.Length > 2 ? cols[2].Trim() : string.Empty,
                sprite = null
            });
        }
    }

    private void RegisterProductImage(ProductImageMapping item)
    {
        if (string.IsNullOrWhiteSpace(item.productName))
        {
            return;
        }

        string key = item.productName.Trim();
        Sprite sprite = item.sprite;

        if (sprite == null && !string.IsNullOrWhiteSpace(item.imagePath))
        {
            string path = item.imagePath.Trim();
            const string pngExt = ".png";
            if (path.EndsWith(pngExt, StringComparison.OrdinalIgnoreCase))
            {
                path = path.Substring(0, path.Length - pngExt.Length);
            }
            sprite = ResolveSpriteFromResources(path, item.spriteName, key);
        }

        if (sprite != null)
        {
            productImageLookup[key] = sprite;
        }
    }

    private Sprite TryResolveProductSprite(string productName)
    {
        if (string.IsNullOrWhiteSpace(productName))
        {
            return null;
        }

        productImageLookup.TryGetValue(productName.Trim(), out var sprite);
        return sprite;
    }

    private static Sprite ResolveSpriteFromResources(string resourcePath, string spriteName, string productName)
    {
        var sprites = Resources.LoadAll<Sprite>(resourcePath);
        if (sprites == null || sprites.Length == 0)
        {
            return null;
        }

        if (!string.IsNullOrWhiteSpace(spriteName))
        {
            foreach (var s in sprites)
            {
                if (s != null && string.Equals(s.name, spriteName.Trim(), StringComparison.Ordinal))
                {
                    return s;
                }
            }
        }

        foreach (var s in sprites)
        {
            if (s != null && string.Equals(s.name, productName, StringComparison.Ordinal))
            {
                return s;
            }
        }

        return null;
    }

    private TMP_FontAsset TryCreateDynamicChineseFont()
    {
        string[] candidates =
        {
            "Microsoft YaHei UI",
            "Microsoft YaHei",
            "SimHei",
            "SimSun",
            "Arial Unicode MS"
        };

        foreach (var name in candidates)
        {
            try
            {
                var osFont = Font.CreateDynamicFontFromOSFont(name, 48);
                if (osFont == null)
                {
                    continue;
                }

                var tmp = TMP_FontAsset.CreateFontAsset(
                    osFont,
                    90,
                    9,
                    GlyphRenderMode.SDFAA,
                    1024,
                    1024,
                    AtlasPopulationMode.Dynamic,
                    true);

                if (tmp != null)
                {
                    tmp.name = $"RuntimeTMP_{name}";
                    return tmp;
                }
            }
            catch
            {
                // Try next candidate.
            }
        }

        return null;
    }

    private void BuildUI()
    {
        var hostCanvas = ResolveOrCreateHostCanvas();

        var uiRoot = new GameObject("ShopAssistantUIRoot", typeof(RectTransform));
        uiRoot.transform.SetParent(hostCanvas.transform, false);
        var uiRootRt = (RectTransform)uiRoot.transform;
        uiRootRt.anchorMin = Vector2.zero;
        uiRootRt.anchorMax = Vector2.one;
        uiRootRt.offsetMin = Vector2.zero;
        uiRootRt.offsetMax = Vector2.zero;

        BuildTopLeftStatusPanel(uiRoot.transform);
        BuildOpenInventoryButton(uiRoot.transform);
        BuildInventoryOverlay(uiRoot.transform);
        BuildRoundStartTransition(uiRoot.transform);
        BuildRoundEndTransition(uiRoot.transform);
    }

    private void Update()
    {
        var keyboard = Keyboard.current;
        if (keyboard != null && keyboard[roundStartDebugKey].wasPressedThisFrame)
        {
            Debug.Log($"[ShopAssistantUI] Debug key {roundStartDebugKey} pressed; showing round start transition and playing notice sound.");
            ShowRoundStartTransition(initialRound);
        }

        if (keyboard != null && keyboard[roundEndDebugKey].wasPressedThisFrame)
        {
            int debugAmount = UnityEngine.Random.Range(0, 10001);
            int debugDelta = UnityEngine.Random.value >= 0.5f ? debugAmount : -debugAmount;
            Debug.Log($"[ShopAssistantUI] Debug key {roundEndDebugKey} pressed; showing round end transition, today delta={debugDelta}.");
            ShowRoundEndTransition(debugDelta);
        }
    }

    private Canvas ResolveOrCreateHostCanvas()
    {
        var allCanvases = FindObjectsOfType<Canvas>(true);

        foreach (var existing in allCanvases)
        {
            if (existing != null && existing.targetDisplay == targetDisplay)
            {
                EnsureCanvasInputComponents(existing);
                return existing;
            }
        }

        foreach (var existing in allCanvases)
        {
            if (existing == null) continue;
            if (IsDisplay6NamedCanvas(existing.gameObject))
            {
                existing.targetDisplay = targetDisplay;
                EnsureCanvasInputComponents(existing);
                return existing;
            }
        }

        var displayObject = FindDisplay6NamedObject();
        if (displayObject != null)
        {
            var existing = displayObject.GetComponentInChildren<Canvas>(true);
            if (existing != null)
            {
                existing.targetDisplay = targetDisplay;
                EnsureCanvasInputComponents(existing);
                return existing;
            }

            var added = displayObject.AddComponent<Canvas>();
            added.renderMode = RenderMode.ScreenSpaceOverlay;
            added.targetDisplay = targetDisplay;
            added.sortingOrder = 300;
            added.pixelPerfect = true;
            EnsureCanvasInputComponents(added);
            return added;
        }

        var canvasGo = new GameObject("ShopAssistantCanvas_Display6", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
        canvasGo.transform.SetParent(transform, false);

        var canvas = canvasGo.GetComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.targetDisplay = targetDisplay;
        canvas.sortingOrder = 300;
        canvas.pixelPerfect = true;

        var scaler = canvasGo.GetComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(baseResolutionX, baseResolutionY);
        scaler.matchWidthOrHeight = 0.5f;
        return canvas;
    }

    private bool IsDisplay6NamedCanvas(GameObject go)
    {
        if (go == null) return false;
        if (NameMatchesDisplay6(go.name)) return true;
        var parent = go.transform.parent;
        return parent != null && NameMatchesDisplay6(parent.name);
    }

    private GameObject FindDisplay6NamedObject()
    {
        foreach (var t in FindObjectsOfType<Transform>(true))
        {
            if (t != null && NameMatchesDisplay6(t.name))
            {
                return t.gameObject;
            }
        }

        return null;
    }

    private bool NameMatchesDisplay6(string objectName)
    {
        if (string.IsNullOrEmpty(objectName))
        {
            return false;
        }

        var lowered = objectName.ToLowerInvariant();
        return lowered.Contains(displayCanvasNameHint.ToLowerInvariant()) || lowered.Contains("display 6");
    }

    private void EnsureCanvasInputComponents(Canvas canvas)
    {
        if (canvas == null) return;

        if (canvas.GetComponent<GraphicRaycaster>() == null)
        {
            canvas.gameObject.AddComponent<GraphicRaycaster>();
        }

        var scaler = canvas.GetComponent<CanvasScaler>();
        if (scaler == null)
        {
            scaler = canvas.gameObject.AddComponent<CanvasScaler>();
        }

        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(baseResolutionX, baseResolutionY);
        scaler.matchWidthOrHeight = 0.5f;
    }

    private void BuildTopLeftStatusPanel(Transform parent)
    {
        var panelGo = new GameObject("TopLeft_StatusPanel", typeof(RectTransform), typeof(Image));
        panelGo.transform.SetParent(parent, false);
        var panel = (RectTransform)panelGo.transform;
        panel.anchorMin = new Vector2(0f, 1f);
        panel.anchorMax = new Vector2(0f, 1f);
        panel.pivot = new Vector2(0f, 1f);
        panel.sizeDelta = new Vector2(430f, 236f);
        panel.anchoredPosition = new Vector2(30f, -28f);

        var panelImage = panelGo.GetComponent<Image>();
        var panelSprite = ResolveUiDecorationSprite(statusPanelResourcePath, statusPanelAssetPath, statusPanelSpriteName);
        if (panelSprite != null)
        {
            panelImage.sprite = panelSprite;
            panelImage.type = Image.Type.Simple;
            panelImage.preserveAspect = true;
            panelImage.color = Color.white;
        }
        else
        {
            panelImage.color = paperColor;
            Debug.LogWarning("[ShopAssistantUI] Status panel sprite missing, fallback color panel is used.");
        }
        panelImage.raycastTarget = false;

        var rowRound = CreateStatusTextArea("RowRound", panel, 0.635f, 0.855f);
        var rowMoney = CreateStatusTextArea("RowMoney", panel, 0.385f, 0.575f);
        var rowState = CreateStatusTextArea("RowState", panel, 0.125f, 0.315f);

        var roundPrefix = CreateStatusText("RoundPrefix", rowRound, "第", 35f, FontStyles.Bold, TextAlignmentOptions.Right, StatusStaticTextColor);
        SetAnchoredRect(roundPrefix.rectTransform, 0.01f, 0f, 0.12f, 1f);
        roundText = CreateStatusText("RoundValue", rowRound, "1", 35f, FontStyles.Bold, TextAlignmentOptions.Center, StatusDynamicTextColor);
        ApplyTextFaceDilate(roundText, 0.42f);
        SetAnchoredRect(roundText.rectTransform, 0.12f, 0f, 0.30f, 1f);
        var roundSuffix = CreateStatusText("RoundSuffix", rowRound, "回合", 35f, FontStyles.Bold, TextAlignmentOptions.Left, StatusStaticTextColor);
        SetAnchoredRect(roundSuffix.rectTransform, 0.30f, 0f, 0.53f, 1f);

        var moneyPrefix = CreateStatusText("MoneyPrefix", rowMoney, "当前金钱：", 27f, FontStyles.Bold, TextAlignmentOptions.Left, StatusStaticTextColor);
        SetAnchoredRect(moneyPrefix.rectTransform, 0f, 0f, 0.44f, 1f);
        moneyText = CreateStatusText("MoneyValue", rowMoney, "1000", 30f, FontStyles.Bold, TextAlignmentOptions.Left, StatusDynamicTextColor);
        ApplyTextFaceDilate(moneyText, 0.42f);
        SetAnchoredRect(moneyText.rectTransform, 0.44f, 0f, 1f, 1f);

        var statePrefix = CreateStatusText("StatePrefix", rowState, "游戏状态：", 27f, FontStyles.Bold, TextAlignmentOptions.Left, StatusStaticTextColor);
        SetAnchoredRect(statePrefix.rectTransform, 0f, 0f, 0.44f, 1f);
        stateText = CreateStatusText("StateValue", rowState, "回合进行中", 30f, FontStyles.Bold, TextAlignmentOptions.Left, StatusDynamicTextColor);
        ApplyTextFaceDilate(stateText, 0.42f);
        SetAnchoredRect(stateText.rectTransform, 0.44f, 0f, 1f, 1f);
    }

    private void BuildOpenInventoryButton(Transform parent)
    {
        openInventoryButton = CreateOpenInventorySpriteButton(parent);
        openInventoryButton.onClick.AddListener(() => SetInventoryVisible(true));
    }

    private Button CreateOpenInventorySpriteButton(Transform parent)
    {
        var buttonRoot = new GameObject("Btn_OpenInventory", typeof(RectTransform), typeof(Image), typeof(Button));
        buttonRoot.transform.SetParent(parent, false);

        var rt = (RectTransform)buttonRoot.transform;
        rt.anchorMin = new Vector2(1f, 0f);
        rt.anchorMax = new Vector2(1f, 0f);
        rt.pivot = new Vector2(1f, 0f);
        rt.sizeDelta = new Vector2(220f, 72f);
        rt.anchoredPosition = new Vector2(-36f, 30f);

        var buttonImage = buttonRoot.GetComponent<Image>();
        var buttonSprite = ResolveUiDecorationSprite(inventoryOpenButtonResourcePath, inventoryOpenButtonAssetPath, inventoryOpenButtonSpriteName);
        if (buttonSprite != null)
        {
            buttonImage.sprite = buttonSprite;
            buttonImage.type = Image.Type.Simple;
            buttonImage.preserveAspect = true;
            buttonImage.color = Color.white;
        }
        else
        {
            buttonImage.color = woodColor;
            Debug.LogWarning("[ShopAssistantUI] Inventory open button sprite missing, fallback color button is used.");
        }

        var button = buttonRoot.GetComponent<Button>();
        button.targetGraphic = buttonImage;
        var colors = button.colors;
        colors.normalColor = Color.white;
        colors.highlightedColor = Color.white;
        colors.pressedColor = new Color(0.92f, 0.92f, 0.92f, 1f);
        colors.disabledColor = new Color(1f, 1f, 1f, 0.6f);
        colors.colorMultiplier = 1f;
        colors.fadeDuration = 0.08f;
        button.colors = colors;
        return button;
    }

    private void BuildRoundStartTransition(Transform parent)
    {
        roundStartOverlayRoot = new GameObject("RoundStartTransitionOverlay", typeof(RectTransform), typeof(CanvasGroup), typeof(Image));
        roundStartOverlayRoot.transform.SetParent(parent, false);
        roundStartOverlayRoot.transform.SetAsLastSibling();

        var overlayRt = (RectTransform)roundStartOverlayRoot.transform;
        overlayRt.anchorMin = Vector2.zero;
        overlayRt.anchorMax = Vector2.one;
        overlayRt.offsetMin = Vector2.zero;
        overlayRt.offsetMax = Vector2.zero;

        roundStartCanvasGroup = roundStartOverlayRoot.GetComponent<CanvasGroup>();
        roundStartCanvasGroup.alpha = 0f;
        roundStartCanvasGroup.blocksRaycasts = false;
        roundStartCanvasGroup.interactable = false;

        roundTransitionAudioSource = roundStartOverlayRoot.AddComponent<AudioSource>();
        roundTransitionAudioSource.playOnAwake = false;
        roundTransitionAudioSource.loop = false;
        roundTransitionAudioSource.spatialBlend = 0f;
        roundTransitionAudioSource.ignoreListenerPause = true;
        roundTransitionAudioSource.volume = roundTransitionAudioVolume;
        roundStartAudioClip = LoadRoundTransitionAudio(roundStartAudioResourcePath);
        roundEndAudioClip = LoadRoundTransitionAudio(roundEndAudioResourcePath);
        fallbackRoundStartAudioClip = CreateRoundTransitionClip("Runtime_RoundStartNotice", new[] { 659.25f, 880f, 1174.66f }, 0.105f, 0.018f);
        fallbackRoundEndAudioClip = CreateRoundTransitionClip("Runtime_RoundEndNotice", new[] { 987.77f, 783.99f, 523.25f }, 0.12f, 0.018f);
        PreloadRoundTransitionAudio(roundStartAudioClip);
        PreloadRoundTransitionAudio(roundEndAudioClip);

        var overlayImage = roundStartOverlayRoot.GetComponent<Image>();
        overlayImage.color = new Color(0.02f, 0.025f, 0.035f, 0.28f);
        overlayImage.raycastTarget = false;

        var panelObj = new GameObject("RoundStartPanel", typeof(RectTransform), typeof(Image));
        panelObj.transform.SetParent(roundStartOverlayRoot.transform, false);
        roundStartPanel = (RectTransform)panelObj.transform;
        roundStartPanel.anchorMin = new Vector2(0.5f, 0.5f);
        roundStartPanel.anchorMax = new Vector2(0.5f, 0.5f);
        roundStartPanel.pivot = new Vector2(0.5f, 0.5f);
        roundStartPanel.sizeDelta = new Vector2(842f, 495f);
        roundStartPanel.anchoredPosition = Vector2.zero;

        var panelImage = panelObj.GetComponent<Image>();
        var panelSprite = ResolveUiDecorationSprite(roundStartResourcePath, roundStartAssetPath, roundStartSpriteName);
        if (panelSprite != null)
        {
            panelImage.sprite = panelSprite;
            panelImage.type = Image.Type.Simple;
            panelImage.preserveAspect = true;
            panelImage.color = Color.white;
        }
        else
        {
            panelImage.color = new Color(1f, 1f, 1f, 0.96f);
            Debug.LogWarning("[ShopAssistantUI] Round start sprite missing, fallback color panel is used.");
        }
        panelImage.raycastTarget = false;

        var textRoot = new GameObject("RoundStartTextRoot", typeof(RectTransform), typeof(CanvasGroup));
        textRoot.transform.SetParent(roundStartPanel, false);
        var textRootRt = (RectTransform)textRoot.transform;
        textRootRt.anchorMin = Vector2.zero;
        textRootRt.anchorMax = Vector2.one;
        textRootRt.offsetMin = Vector2.zero;
        textRootRt.offsetMax = Vector2.zero;
        roundStartTextCanvasGroup = textRoot.GetComponent<CanvasGroup>();
        roundStartTextCanvasGroup.alpha = 0f;
        roundStartTextCanvasGroup.blocksRaycasts = false;
        roundStartTextCanvasGroup.interactable = false;

        BuildRoundStartFirstLine(textRootRt);

        var secondLine = CreateRoundTransitionText("BusinessStart", textRootRt, "开始营业", 55f, TextAlignmentOptions.Center, StatusStaticTextColor, 0.06f);
        secondLine.characterSpacing = 5f;
        secondLine.rectTransform.anchorMin = new Vector2(0.25f, 0.155f);
        secondLine.rectTransform.anchorMax = new Vector2(0.75f, 0.305f);
        secondLine.rectTransform.offsetMin = Vector2.zero;
        secondLine.rectTransform.offsetMax = Vector2.zero;

        roundStartOverlayRoot.SetActive(false);
    }

    private void BuildRoundEndTransition(Transform parent)
    {
        roundEndOverlayRoot = new GameObject("RoundEndTransitionOverlay", typeof(RectTransform), typeof(CanvasGroup), typeof(Image));
        roundEndOverlayRoot.transform.SetParent(parent, false);
        roundEndOverlayRoot.transform.SetAsLastSibling();

        var overlayRt = (RectTransform)roundEndOverlayRoot.transform;
        overlayRt.anchorMin = Vector2.zero;
        overlayRt.anchorMax = Vector2.one;
        overlayRt.offsetMin = Vector2.zero;
        overlayRt.offsetMax = Vector2.zero;

        roundEndCanvasGroup = roundEndOverlayRoot.GetComponent<CanvasGroup>();
        roundEndCanvasGroup.alpha = 0f;
        roundEndCanvasGroup.blocksRaycasts = false;
        roundEndCanvasGroup.interactable = false;

        var overlayImage = roundEndOverlayRoot.GetComponent<Image>();
        overlayImage.color = new Color(0.02f, 0.025f, 0.035f, 0.28f);
        overlayImage.raycastTarget = false;

        var panelObj = new GameObject("RoundEndPanel", typeof(RectTransform), typeof(Image));
        panelObj.transform.SetParent(roundEndOverlayRoot.transform, false);
        roundEndPanel = (RectTransform)panelObj.transform;
        roundEndPanel.anchorMin = new Vector2(0.5f, 0.5f);
        roundEndPanel.anchorMax = new Vector2(0.5f, 0.5f);
        roundEndPanel.pivot = new Vector2(0.5f, 0.5f);
        roundEndPanel.sizeDelta = new Vector2(842f, 299f);
        roundEndPanel.anchoredPosition = Vector2.zero;

        var panelImage = panelObj.GetComponent<Image>();
        var panelSprite = ResolveUiDecorationSprite(roundEndResourcePath, roundEndAssetPath, roundEndSpriteName);
        if (panelSprite != null)
        {
            panelImage.sprite = panelSprite;
            panelImage.type = Image.Type.Simple;
            panelImage.preserveAspect = true;
            panelImage.color = Color.white;
        }
        else
        {
            panelImage.color = new Color(1f, 1f, 1f, 0.96f);
            Debug.LogWarning("[ShopAssistantUI] Round end sprite missing, fallback color panel is used.");
        }
        panelImage.raycastTarget = false;

        var textRoot = new GameObject("RoundEndTextRoot", typeof(RectTransform), typeof(CanvasGroup));
        textRoot.transform.SetParent(roundEndPanel, false);
        var textRootRt = (RectTransform)textRoot.transform;
        textRootRt.anchorMin = Vector2.zero;
        textRootRt.anchorMax = Vector2.one;
        textRootRt.offsetMin = Vector2.zero;
        textRootRt.offsetMax = Vector2.zero;
        roundEndTextCanvasGroup = textRoot.GetComponent<CanvasGroup>();
        roundEndTextCanvasGroup.alpha = 0f;
        roundEndTextCanvasGroup.blocksRaycasts = false;
        roundEndTextCanvasGroup.interactable = false;

        BuildRoundEndIncomeRow(textRootRt);

        roundEndOverlayRoot.SetActive(false);
    }

    private void BuildRoundEndIncomeRow(RectTransform parent)
    {
        var row = new GameObject("RoundEndIncomeRow", typeof(RectTransform));
        row.transform.SetParent(parent, false);
        roundEndIncomeRow = (RectTransform)row.transform;
        roundEndIncomeRow.anchorMin = new Vector2(0.5f, 0.5f);
        roundEndIncomeRow.anchorMax = new Vector2(0.5f, 0.5f);
        roundEndIncomeRow.pivot = new Vector2(0.5f, 0.5f);
        roundEndIncomeRow.sizeDelta = new Vector2(560f, 78f);
        roundEndIncomeRow.anchoredPosition = new Vector2(34f, -72f);

        var label = CreateRoundTransitionText("TodayLabel", roundEndIncomeRow, "今日", 48f, TextAlignmentOptions.Center, Color.black, 0.045f);
        SetFixedRowItem(label.rectTransform, -170f, 130f, 72f);

        var coinObj = new GameObject("CoinIcon", typeof(RectTransform), typeof(Image));
        coinObj.transform.SetParent(roundEndIncomeRow, false);
        var coinRt = (RectTransform)coinObj.transform;
        SetLeftRowItem(coinRt, -78f, 58f, 58f);

        var coinImage = coinObj.GetComponent<Image>();
        var coinSprite = ResolveUiDecorationSprite(inventoryCoinFeatherResourcePath, inventoryCoinFeatherAssetPath, inventoryCoinSpriteName);
        coinImage.sprite = coinSprite;
        coinImage.type = Image.Type.Simple;
        coinImage.preserveAspect = true;
        coinImage.color = coinSprite != null ? Color.white : new Color(1f, 1f, 1f, 0f);
        coinImage.raycastTarget = false;

        roundEndAmountText = CreateRoundTransitionText("TodayAmount", roundEndIncomeRow, "+0", 52f, TextAlignmentOptions.Left, new Color(0.08f, 0.50f, 0.16f, 1f), 0.06f);
        roundEndAmountText.enableAutoSizing = true;
        roundEndAmountText.fontSizeMin = 42f;
        roundEndAmountText.fontSizeMax = 52f;
        SetLeftRowItem(roundEndAmountText.rectTransform, -4f, 260f, 72f);
    }

    private AudioClip LoadRoundTransitionAudio(string resourcePath)
    {
        if (string.IsNullOrWhiteSpace(resourcePath))
        {
            return null;
        }

        var clip = Resources.Load<AudioClip>(resourcePath.Trim());
        if (clip == null)
        {
            Debug.LogWarning($"[ShopAssistantUI] Round transition audio not found: Resources/{resourcePath}");
            clip = resourcePath.IndexOf("end", StringComparison.OrdinalIgnoreCase) >= 0
                ? CreateRoundTransitionClip("Runtime_RoundEndNotice", new[] { 987.77f, 783.99f, 523.25f }, 0.12f, 0.018f)
                : CreateRoundTransitionClip("Runtime_RoundStartNotice", new[] { 659.25f, 880f, 1174.66f }, 0.105f, 0.018f);
        }

        return clip;
    }

    private static AudioClip CreateRoundTransitionClip(string name, float[] frequencies, float noteSeconds, float gapSeconds)
    {
        const int sampleRate = 44100;
        int noteSamples = Mathf.Max(1, Mathf.RoundToInt(sampleRate * noteSeconds));
        int gapSamples = Mathf.Max(0, Mathf.RoundToInt(sampleRate * gapSeconds));
        int totalSamples = frequencies.Length * (noteSamples + gapSamples);
        var data = new float[totalSamples];
        int writeIndex = 0;

        for (int noteIndex = 0; noteIndex < frequencies.Length; noteIndex++)
        {
            float frequency = frequencies[noteIndex];
            for (int i = 0; i < noteSamples; i++)
            {
                float t = i / (float)sampleRate;
                float env = RoundTransitionEnvelope(t, noteSeconds);
                float sample =
                    Mathf.Sin(2f * Mathf.PI * frequency * t) * 0.68f +
                    Mathf.Sin(2f * Mathf.PI * frequency * 2f * t) * 0.18f +
                    Mathf.Sin(2f * Mathf.PI * frequency * 3f * t) * 0.07f;
                data[writeIndex++] = sample * env * 0.55f;
            }

            writeIndex += gapSamples;
        }

        var clip = AudioClip.Create(name, totalSamples, 1, sampleRate, false);
        clip.SetData(data, 0);
        return clip;
    }

    private static float RoundTransitionEnvelope(float time, float duration)
    {
        const float attack = 0.01f;
        const float release = 0.08f;
        if (time < attack)
        {
            return Mathf.Clamp01(time / attack);
        }

        if (time > duration - release)
        {
            return Mathf.Clamp01((duration - time) / release);
        }

        return 1f;
    }

    private static void PreloadRoundTransitionAudio(AudioClip clip)
    {
        if (clip != null && clip.loadState == AudioDataLoadState.Unloaded)
        {
            clip.LoadAudioData();
        }
    }

    private void BuildRoundStartFirstLine(RectTransform parent)
    {
        var row = new GameObject("RoundStartLine", typeof(RectTransform));
        row.transform.SetParent(parent, false);
        var rowRt = (RectTransform)row.transform;
        rowRt.anchorMin = new Vector2(0.5f, 0.5f);
        rowRt.anchorMax = new Vector2(0.5f, 0.5f);
        rowRt.pivot = new Vector2(0.5f, 0.5f);
        rowRt.sizeDelta = new Vector2(360f, 86f);
        rowRt.anchoredPosition = new Vector2(0f, -24f);

        var prefix = CreateRoundTransitionText("RoundPrefix", rowRt, "第", 64f, TextAlignmentOptions.Center, StatusStaticTextColor, 0.06f);
        SetFixedRowItem(prefix.rectTransform, -118f, 54f, 86f);

        roundStartNumberText = CreateRoundTransitionText("RoundNumber", rowRt, "128", 76f, TextAlignmentOptions.Center, StatusDynamicTextColor, 0.08f);
        roundStartNumberText.enableAutoSizing = true;
        roundStartNumberText.fontSizeMin = 58f;
        roundStartNumberText.fontSizeMax = 76f;
        SetFixedRowItem(roundStartNumberText.rectTransform, -24f, 132f, 86f);

        var suffix = CreateRoundTransitionText("RoundSuffix", rowRt, "回合", 64f, TextAlignmentOptions.Center, StatusStaticTextColor, 0.06f);
        SetFixedRowItem(suffix.rectTransform, 106f, 122f, 86f);
    }

    private TextMeshProUGUI CreateRoundTransitionText(
        string name,
        Transform parent,
        string content,
        float fontSize,
        TextAlignmentOptions align,
        Color color,
        float faceDilate)
    {
        var text = CreateTMPText(name, parent, content, fontSize, FontStyles.Bold, align);
        text.color = color;
        text.textWrappingMode = TextWrappingModes.NoWrap;
        text.overflowMode = TextOverflowModes.Overflow;
        text.margin = Vector4.zero;
        ApplyTextFaceDilate(text, faceDilate);
        return text;
    }

    private static void AddFixedLayout(GameObject go, float preferredWidth)
    {
        var element = go.AddComponent<LayoutElement>();
        element.minWidth = preferredWidth;
        element.preferredWidth = preferredWidth;
        element.flexibleWidth = 0f;
    }

    private static void SetFixedRowItem(RectTransform rt, float x, float width, float height)
    {
        rt.anchorMin = new Vector2(0.5f, 0.5f);
        rt.anchorMax = new Vector2(0.5f, 0.5f);
        rt.pivot = new Vector2(0.5f, 0.5f);
        rt.sizeDelta = new Vector2(width, height);
        rt.anchoredPosition = new Vector2(x, 0f);
    }

    private static void SetLeftRowItem(RectTransform rt, float x, float width, float height)
    {
        rt.anchorMin = new Vector2(0.5f, 0.5f);
        rt.anchorMax = new Vector2(0.5f, 0.5f);
        rt.pivot = new Vector2(0f, 0.5f);
        rt.sizeDelta = new Vector2(width, height);
        rt.anchoredPosition = new Vector2(x, 0f);
    }

    public void ShowRoundStartTransition(int round)
    {
        if (roundStartOverlayRoot == null)
        {
            return;
        }

        if (roundStartRoutine != null)
        {
            StopCoroutine(roundStartRoutine);
        }

        if (roundEndRoutine != null)
        {
            StopCoroutine(roundEndRoutine);
            roundEndRoutine = null;
        }
        if (roundEndOverlayRoot != null)
        {
            roundEndOverlayRoot.SetActive(false);
        }

        roundStartRoutine = StartCoroutine(PlayRoundStartTransition(Mathf.Clamp(round, 0, 999)));
    }

    public void ShowRoundStartTransitionThenOpenInventory(int round, float extraDelaySeconds = 1f)
    {
        BeginStockPlanningRound(round);
        ShowRoundStartTransition(round);

        if (openInventoryAfterRoundStartRoutine != null)
        {
            StopCoroutine(openInventoryAfterRoundStartRoutine);
        }

        openInventoryAfterRoundStartRoutine = StartCoroutine(OpenInventoryAfterRoundStart(extraDelaySeconds));
    }

    private IEnumerator OpenInventoryAfterRoundStart(float extraDelaySeconds)
    {
        float waitSeconds =
            Mathf.Max(0f, roundStartIntroSeconds) +
            Mathf.Max(0f, roundStartHoldSeconds) +
            Mathf.Max(0f, roundStartOutroSeconds) +
            Mathf.Max(0f, extraDelaySeconds);

        yield return new WaitForSecondsRealtime(waitSeconds);
        OpenInventory();
        openInventoryAfterRoundStartRoutine = null;
    }

    private void BeginStockPlanningRound(int round)
    {
        if (Mathf.Max(FirstRoundIndex, round) == FirstRoundIndex)
        {
            foreach (var product in marketProducts)
            {
                product.PurchaseQuantity = 0;
            }
        }

        canEditStockPlan = true;
        RebuildProductCells();
        RefreshStockControlsInteractable();
    }

    public void ShowRoundEndTransition(int todayMoneyDelta)
    {
        if (roundEndOverlayRoot == null)
        {
            return;
        }

        playerModel.TodayIncome = Mathf.Clamp(todayMoneyDelta, -10000, 10000);

        if (roundEndRoutine != null)
        {
            StopCoroutine(roundEndRoutine);
        }

        if (roundStartRoutine != null)
        {
            StopCoroutine(roundStartRoutine);
            roundStartRoutine = null;
        }
        if (roundStartOverlayRoot != null)
        {
            roundStartOverlayRoot.SetActive(false);
        }

        roundEndRoutine = StartCoroutine(PlayRoundEndTransition(playerModel.TodayIncome));
    }

    public void PlayRoundEndNoticeSound()
    {
        PlayRoundTransitionSound(roundEndAudioClip, fallbackRoundEndAudioClip);
    }

    private IEnumerator PlayRoundStartTransition(int round)
    {
        roundStartOverlayRoot.SetActive(true);
        roundStartOverlayRoot.transform.SetAsLastSibling();
        PlayRoundTransitionSound(roundStartAudioClip, fallbackRoundStartAudioClip);

        if (roundStartNumberText != null)
        {
            roundStartNumberText.text = round.ToString();
        }

        if (roundStartCanvasGroup != null)
        {
            roundStartCanvasGroup.alpha = 0f;
        }

        if (roundStartTextCanvasGroup != null)
        {
            roundStartTextCanvasGroup.alpha = 0f;
        }

        Vector2 startPos = new Vector2(0f, 46f);
        Vector2 restPos = Vector2.zero;
        roundStartPanel.anchoredPosition = startPos;
        roundStartPanel.localScale = Vector3.one * 0.92f;

        float intro = Mathf.Max(0.01f, roundStartIntroSeconds);
        float elapsed = 0f;
        while (elapsed < intro)
        {
            elapsed += Time.unscaledDeltaTime;
            float t = Mathf.Clamp01(elapsed / intro);
            float eased = EaseOutBack(t);
            roundStartCanvasGroup.alpha = Mathf.SmoothStep(0f, 1f, t);
            roundStartTextCanvasGroup.alpha = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.28f, 1f, t));
            roundStartPanel.anchoredPosition = Vector2.LerpUnclamped(startPos, restPos, eased);
            roundStartPanel.localScale = Vector3.one * Mathf.LerpUnclamped(0.92f, 1f, eased);
            yield return null;
        }

        roundStartCanvasGroup.alpha = 1f;
        roundStartTextCanvasGroup.alpha = 1f;
        roundStartPanel.anchoredPosition = restPos;
        roundStartPanel.localScale = Vector3.one;

        float holdUntil = Time.unscaledTime + Mathf.Max(0f, roundStartHoldSeconds);
        while (Time.unscaledTime < holdUntil)
        {
            yield return null;
        }

        float outro = Mathf.Max(0.01f, roundStartOutroSeconds);
        elapsed = 0f;
        while (elapsed < outro)
        {
            elapsed += Time.unscaledDeltaTime;
            float t = Mathf.Clamp01(elapsed / outro);
            float eased = t * t;
            roundStartCanvasGroup.alpha = 1f - t;
            roundStartPanel.anchoredPosition = Vector2.Lerp(restPos, new Vector2(0f, -28f), eased);
            roundStartPanel.localScale = Vector3.one * Mathf.Lerp(1f, 0.985f, t);
            yield return null;
        }

        roundStartCanvasGroup.alpha = 0f;
        roundStartOverlayRoot.SetActive(false);
        roundStartRoutine = null;
    }

    private IEnumerator PlayRoundEndTransition(int todayMoneyDelta)
    {
        roundEndOverlayRoot.SetActive(true);
        roundEndOverlayRoot.transform.SetAsLastSibling();

        int amount = Mathf.Abs(todayMoneyDelta);
        bool isIncrease = todayMoneyDelta >= 0;
        Color amountColor = isIncrease ? new Color(0.08f, 0.50f, 0.16f, 1f) : new Color(0.74f, 0.08f, 0.08f, 1f);
        UpdateRoundEndAmountText(isIncrease, 0, amountColor);

        if (roundEndCanvasGroup != null)
        {
            roundEndCanvasGroup.alpha = 0f;
        }

        if (roundEndTextCanvasGroup != null)
        {
            roundEndTextCanvasGroup.alpha = 0f;
        }

        Vector2 startPos = new Vector2(0f, 46f);
        Vector2 restPos = Vector2.zero;
        roundEndPanel.anchoredPosition = startPos;
        roundEndPanel.localScale = Vector3.one * 0.92f;
        if (roundEndIncomeRow != null)
        {
            roundEndIncomeRow.localScale = Vector3.one;
        }

        float intro = Mathf.Max(0.01f, roundStartIntroSeconds);
        float elapsed = 0f;
        while (elapsed < intro)
        {
            elapsed += Time.unscaledDeltaTime;
            float t = Mathf.Clamp01(elapsed / intro);
            float eased = EaseOutBack(t);
            roundEndCanvasGroup.alpha = Mathf.SmoothStep(0f, 1f, t);
            roundEndTextCanvasGroup.alpha = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.28f, 1f, t));
            roundEndPanel.anchoredPosition = Vector2.LerpUnclamped(startPos, restPos, eased);
            roundEndPanel.localScale = Vector3.one * Mathf.LerpUnclamped(0.92f, 1f, eased);
            yield return null;
        }

        roundEndCanvasGroup.alpha = 1f;
        roundEndTextCanvasGroup.alpha = 1f;
        roundEndPanel.anchoredPosition = restPos;
        roundEndPanel.localScale = Vector3.one;

        float countDuration = Mathf.Max(0.01f, roundEndCountSeconds);
        elapsed = 0f;
        while (elapsed < countDuration)
        {
            elapsed += Time.unscaledDeltaTime;
            float t = Mathf.Clamp01(elapsed / countDuration);
            int displayedAmount = Mathf.RoundToInt(Mathf.Lerp(0f, amount, Mathf.SmoothStep(0f, 1f, t)));
            UpdateRoundEndAmountText(isIncrease, displayedAmount, amountColor);
            yield return null;
        }

        UpdateRoundEndAmountText(isIncrease, amount, amountColor);

        const float emphasizeSeconds = 0.22f;
        elapsed = 0f;
        while (elapsed < emphasizeSeconds)
        {
            elapsed += Time.unscaledDeltaTime;
            float t = Mathf.Clamp01(elapsed / emphasizeSeconds);
            float pulse = Mathf.Sin(t * Mathf.PI);
            if (roundEndIncomeRow != null)
            {
                roundEndIncomeRow.localScale = Vector3.one * Mathf.Lerp(1f, 1.12f, pulse);
            }
            yield return null;
        }

        if (roundEndIncomeRow != null)
        {
            roundEndIncomeRow.localScale = Vector3.one;
        }

        float holdUntil = Time.unscaledTime + Mathf.Max(0f, roundStartHoldSeconds);
        while (Time.unscaledTime < holdUntil)
        {
            yield return null;
        }

        float outro = Mathf.Max(0.01f, roundStartOutroSeconds);
        elapsed = 0f;
        while (elapsed < outro)
        {
            elapsed += Time.unscaledDeltaTime;
            float t = Mathf.Clamp01(elapsed / outro);
            float eased = t * t;
            roundEndCanvasGroup.alpha = 1f - t;
            roundEndPanel.anchoredPosition = Vector2.Lerp(restPos, new Vector2(0f, -28f), eased);
            roundEndPanel.localScale = Vector3.one * Mathf.Lerp(1f, 0.985f, t);
            yield return null;
        }

        roundEndCanvasGroup.alpha = 0f;
        roundEndOverlayRoot.SetActive(false);
        roundEndRoutine = null;
    }

    private void UpdateRoundEndAmountText(bool isIncrease, int amount, Color amountColor)
    {
        if (roundEndAmountText == null)
        {
            return;
        }

        roundEndAmountText.color = amountColor;
        roundEndAmountText.text = $"{(isIncrease ? "+" : "-")}{Mathf.Clamp(amount, 0, 10000)}";
    }

    private void PlayRoundTransitionSound(AudioClip clip, AudioClip fallbackClip)
    {
        if (clip == null || roundTransitionAudioSource == null)
        {
            Debug.LogWarning($"[ShopAssistantUI] Round transition audio skipped. clip={(clip == null ? "null" : clip.name)}, source={(roundTransitionAudioSource == null ? "null" : "ok")}");
            if (roundTransitionAudioSource != null && fallbackClip != null)
            {
                roundTransitionAudioSource.volume = roundTransitionAudioVolume;
                roundTransitionAudioSource.PlayOneShot(fallbackClip, 1f);
                Debug.Log($"[ShopAssistantUI] Round transition fallback audio played: {fallbackClip.name}, volume={roundTransitionAudioVolume}");
            }
            return;
        }

        if (clip.loadState == AudioDataLoadState.Unloaded)
        {
            clip.LoadAudioData();
        }

        if (clip.loadState == AudioDataLoadState.Loading)
        {
            StartCoroutine(PlayRoundTransitionSoundWhenLoaded(clip, fallbackClip));
            return;
        }

        if (clip.loadState != AudioDataLoadState.Loaded)
        {
            Debug.LogWarning($"[ShopAssistantUI] Round transition audio not ready: {clip.name}, loadState={clip.loadState}");
            if (fallbackClip != null)
            {
                roundTransitionAudioSource.volume = roundTransitionAudioVolume;
                roundTransitionAudioSource.PlayOneShot(fallbackClip, 1f);
                Debug.Log($"[ShopAssistantUI] Round transition fallback audio played: {fallbackClip.name}, volume={roundTransitionAudioVolume}");
            }
            return;
        }

        roundTransitionAudioSource.volume = roundTransitionAudioVolume;
        roundTransitionAudioSource.PlayOneShot(clip, 1f);
        Debug.Log($"[ShopAssistantUI] Round transition audio played: {clip.name}, volume={roundTransitionAudioVolume}, listeners={FindObjectsOfType<AudioListener>(true).Length}");
    }

    private IEnumerator PlayRoundTransitionSoundWhenLoaded(AudioClip clip, AudioClip fallbackClip)
    {
        float deadline = Time.realtimeSinceStartup + 0.25f;
        while (clip != null && clip.loadState == AudioDataLoadState.Loading && Time.realtimeSinceStartup < deadline)
        {
            yield return null;
        }

        if (clip != null && clip.loadState == AudioDataLoadState.Loaded && roundTransitionAudioSource != null)
        {
            roundTransitionAudioSource.volume = roundTransitionAudioVolume;
            roundTransitionAudioSource.PlayOneShot(clip, 1f);
        }
        else if (fallbackClip != null && roundTransitionAudioSource != null)
        {
            roundTransitionAudioSource.volume = roundTransitionAudioVolume;
            roundTransitionAudioSource.PlayOneShot(fallbackClip, 1f);
            Debug.Log($"[ShopAssistantUI] Round transition fallback audio played after load timeout: {fallbackClip.name}, volume={roundTransitionAudioVolume}");
        }
    }

    private static float EaseOutBack(float t)
    {
        const float c1 = 1.70158f;
        const float c3 = c1 + 1f;
        float p = t - 1f;
        return 1f + c3 * p * p * p + c1 * p * p;
    }

    private void BuildInventoryOverlay(Transform parent)
    {
        inventoryOverlayRoot = new GameObject("InventoryOverlay", typeof(RectTransform), typeof(CanvasGroup), typeof(Image));
        inventoryOverlayRoot.transform.SetParent(parent, false);

        var overlayRt = (RectTransform)inventoryOverlayRoot.transform;
        overlayRt.anchorMin = Vector2.zero;
        overlayRt.anchorMax = Vector2.one;
        overlayRt.offsetMin = Vector2.zero;
        overlayRt.offsetMax = Vector2.zero;

        var overlayBg = inventoryOverlayRoot.GetComponent<Image>();
        overlayBg.color = new Color(0.17f, 0.12f, 0.04f, 0.45f);

        // Match the background sprite aspect (1360x998) to avoid content overflowing visible paper area.
        var window = CreatePanel("InventoryWindow", inventoryOverlayRoot.transform, paperColor, woodColor, new Vector2(1505, 1055), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), Vector2.zero);
        ApplyInventoryWindowBackground(window);

        CreateInventoryTitleSprite(window);

        var closeButton = CreateInventoryCloseSpriteButton(window);
        closeButton.onClick.AddListener(() => SetInventoryVisible(false));

        CreateInventoryRightPanelSprite(window);

        var scrollRoot = new GameObject("GoodsScroll", typeof(RectTransform), typeof(Image), typeof(Mask), typeof(ScrollRect));
        scrollRoot.transform.SetParent(window, false);
        var scrollRt = (RectTransform)scrollRoot.transform;
        scrollRt.anchorMin = new Vector2(0.04f, 0.16f);
        scrollRt.anchorMax = new Vector2(0.78f, 0.86f);
        scrollRt.offsetMin = Vector2.zero;
        scrollRt.offsetMax = Vector2.zero;

        var scrollImage = scrollRoot.GetComponent<Image>();
        scrollImage.color = new Color(1f, 1f, 1f, 0.22f);
        scrollRoot.GetComponent<Mask>().showMaskGraphic = false;

        var viewport = new GameObject("Viewport", typeof(RectTransform), typeof(Image), typeof(Mask));
        viewport.transform.SetParent(scrollRoot.transform, false);
        var viewportRt = (RectTransform)viewport.transform;
        viewportRt.anchorMin = Vector2.zero;
        viewportRt.anchorMax = Vector2.one;
        viewportRt.offsetMin = new Vector2(8f, 8f);
        viewportRt.offsetMax = new Vector2(-8f, -8f);
        var viewportImage = viewport.GetComponent<Image>();
        viewportImage.color = new Color(1f, 1f, 1f, 0.02f);
        viewport.GetComponent<Mask>().showMaskGraphic = false;

        var content = new GameObject("Content", typeof(RectTransform), typeof(GridLayoutGroup), typeof(ContentSizeFitter));
        content.transform.SetParent(viewport.transform, false);
        var contentRt = (RectTransform)content.transform;
        inventoryContentRoot = contentRt;
        contentRt.anchorMin = new Vector2(0f, 1f);
        contentRt.anchorMax = new Vector2(1f, 1f);
        contentRt.pivot = new Vector2(0.5f, 1f);
        contentRt.anchoredPosition = Vector2.zero;
        contentRt.sizeDelta = new Vector2(0f, 1200f);

        var grid = content.GetComponent<GridLayoutGroup>();
        grid.cellSize = new Vector2(210f, 336f);
        grid.spacing = new Vector2(14f, 14f);
        grid.padding = new RectOffset(14, 14, 14, 14);
        grid.startAxis = GridLayoutGroup.Axis.Horizontal;
        grid.startCorner = GridLayoutGroup.Corner.UpperLeft;
        grid.childAlignment = TextAnchor.UpperLeft;
        grid.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
        grid.constraintCount = 4;

        var autoColumns = content.AddComponent<InventoryGridAutoColumns>();
        autoColumns.Bind(grid, viewportRt, 4, 4);

        var fitter = content.GetComponent<ContentSizeFitter>();
        fitter.horizontalFit = ContentSizeFitter.FitMode.Unconstrained;
        fitter.verticalFit = ContentSizeFitter.FitMode.PreferredSize;

        var scrollRect = scrollRoot.GetComponent<ScrollRect>();
        scrollRect.viewport = viewportRt;
        scrollRect.content = contentRt;
        scrollRect.horizontal = false;
        scrollRect.vertical = true;
        scrollRect.movementType = ScrollRect.MovementType.Clamped;
        scrollRect.scrollSensitivity = 28f;

        RebuildProductCells();

        stockInventoryButton = CreateInventoryStockSpriteButton(window);
        stockInventoryButton.onClick.AddListener(SubmitStockPlan);
        RefreshStockControlsInteractable();

        SetInventoryVisible(false);
    }

    private RectTransform CreatePanel(
        string name,
        Transform parent,
        Color fill,
        Color border,
        Vector2 size,
        Vector2 anchorMin,
        Vector2 anchorMax,
        Vector2 anchoredPos)
    {
        var go = new GameObject(name, typeof(RectTransform), typeof(Image), typeof(Outline), typeof(Shadow));
        go.transform.SetParent(parent, false);
        var rt = (RectTransform)go.transform;
        rt.anchorMin = anchorMin;
        rt.anchorMax = anchorMax;
        rt.pivot = new Vector2(0.5f, 0.5f);
        rt.sizeDelta = size;
        rt.anchoredPosition = anchoredPos;

        var image = go.GetComponent<Image>();
        image.color = fill;

        var outline = go.GetComponent<Outline>();
        outline.effectColor = border;
        outline.effectDistance = new Vector2(panelOutlineThickness, -panelOutlineThickness);

        var shadow = go.GetComponent<Shadow>();
        shadow.effectColor = new Color(0f, 0f, 0f, 0.2f);
        shadow.effectDistance = new Vector2(panelOutlineThickness + 2f, -(panelOutlineThickness + 2f));

        return rt;
    }

    private GameObject CreateButtonLikePanel(
        string name,
        Transform parent,
        Vector2 size,
        Vector2 anchorMin,
        Vector2 anchorMax,
        Vector2 anchoredPos,
        string label,
        float fontSize)
    {
        var root = new GameObject(name, typeof(RectTransform), typeof(Image), typeof(Outline), typeof(Shadow), typeof(Button));
        root.transform.SetParent(parent, false);
        var rt = (RectTransform)root.transform;
        rt.anchorMin = anchorMin;
        rt.anchorMax = anchorMax;
        rt.pivot = new Vector2(0.5f, 0.5f);
        rt.sizeDelta = size;
        rt.anchoredPosition = anchoredPos;

        root.GetComponent<Image>().color = woodColor;

        var outline = root.GetComponent<Outline>();
        outline.effectColor = new Color(0.48f, 0.34f, 0.08f, 0.95f);
        outline.effectDistance = new Vector2(3f, -3f);

        var shadow = root.GetComponent<Shadow>();
        shadow.effectColor = new Color(0f, 0f, 0f, 0.2f);
        shadow.effectDistance = new Vector2(5f, -5f);

        var fadedEdge = new GameObject("FadedEdge", typeof(RectTransform), typeof(Image));
        fadedEdge.transform.SetParent(root.transform, false);
        var edgeRt = (RectTransform)fadedEdge.transform;
        edgeRt.anchorMin = Vector2.zero;
        edgeRt.anchorMax = Vector2.one;
        edgeRt.offsetMin = new Vector2(6f, 6f);
        edgeRt.offsetMax = new Vector2(-6f, -6f);
        fadedEdge.GetComponent<Image>().color = woodEdgeFade;

        var center = new GameObject("Center", typeof(RectTransform), typeof(Image));
        center.transform.SetParent(root.transform, false);
        var centerRt = (RectTransform)center.transform;
        centerRt.anchorMin = Vector2.zero;
        centerRt.anchorMax = Vector2.one;
        centerRt.offsetMin = new Vector2(14f, 12f);
        centerRt.offsetMax = new Vector2(-14f, -12f);
        center.GetComponent<Image>().color = woodColor;

        var txt = CreateTMPText("Label", root.transform, label, fontSize, FontStyles.Bold, TextAlignmentOptions.Center);
        var textRt = (RectTransform)txt.transform;
        textRt.anchorMin = Vector2.zero;
        textRt.anchorMax = Vector2.one;
        textRt.offsetMin = Vector2.zero;
        textRt.offsetMax = Vector2.zero;

        var button = root.GetComponent<Button>();
        button.targetGraphic = root.GetComponent<Image>();

        var colors = button.colors;
        colors.normalColor = Color.white;
        colors.highlightedColor = Color.white;
        colors.pressedColor = new Color(0.92f, 0.92f, 0.92f, 1f);
        colors.disabledColor = new Color(1f, 1f, 1f, 0.6f);
        colors.colorMultiplier = 1f;
        colors.fadeDuration = 0.08f;
        button.colors = colors;

        return root;
    }

    private void RebuildProductCells()
    {
        if (inventoryContentRoot == null)
        {
            return;
        }

        inventorySteppers.Clear();
        for (int i = inventoryContentRoot.childCount - 1; i >= 0; i--)
        {
            var child = inventoryContentRoot.GetChild(i);
            if (child != null)
            {
                Destroy(child.gameObject);
            }
        }

        if (marketProducts.Count == 0)
        {
            marketProducts.AddRange(BuildMockProducts());
        }

        for (int i = 0; i < marketProducts.Count; i++)
        {
            CreateProductCell(inventoryContentRoot, marketProducts[i], i);
        }
    }

    private List<ShopProductModel> ParseMarketInformation(string infoJson)
    {
        try
        {
            var payload = JsonUtility.FromJson<MarketInformationPayload>(infoJson);
            if (payload == null || payload.items == null || payload.items.Length == 0)
            {
                return new List<ShopProductModel>();
            }

            var result = new List<ShopProductModel>(payload.items.Length);
            foreach (var item in payload.items)
            {
                if (item == null || string.IsNullOrWhiteSpace(item.name))
                {
                    continue;
                }

                int cachedPurchaseQuantity = 0;
                foreach (var existing in marketProducts)
                {
                    if (existing != null && string.Equals(existing.ProductName, item.name.Trim(), StringComparison.Ordinal))
                    {
                        cachedPurchaseQuantity = existing.PurchaseQuantity;
                        break;
                    }
                }

                result.Add(new ShopProductModel(
                    item.name.Trim(),
                    RoundToInt(item.purchasePrice),
                    cachedPurchaseQuantity,
                    RoundToInt(item.basePrice),
                    RoundToInt(item.quantity),
                    item.priceLocked));
            }

            return result;
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[ShopAssistantUI] Failed to parse market info json: {e.Message}");
            return new List<ShopProductModel>();
        }
    }

    private static int RoundToInt(float value)
    {
        return Mathf.Max(0, Mathf.RoundToInt(value));
    }

    private void CreateProductCell(Transform content, ShopProductModel data, int cellIndex)
    {
        data.TodayPrice = Mathf.Min(data.TodayPrice, MaxProductTodayPrice(data));

        var cell = CreatePanel(
            $"Cell_{data.ProductName}",
            content,
            new Color(1f, 1f, 1f, 0.45f),
            woodColor,
            new Vector2(210f, 320f),
            new Vector2(0.5f, 0.5f),
            new Vector2(0.5f, 0.5f),
            Vector2.zero
        );
        var cellSprite = ResolveUiDecorationSprite(inventoryProductCellBgResourcePath, inventoryProductCellBgAssetPath, inventoryProductCellBgSpriteName);
        var cellImage = cell.GetComponent<Image>();
        if (cellSprite != null)
        {
            cellImage.sprite = cellSprite;
            cellImage.type = Image.Type.Simple;
            cellImage.preserveAspect = false;
            cellImage.color = Color.white;
        }

        var cellOutline = cell.GetComponent<Outline>();
        if (cellOutline != null)
        {
            cellOutline.enabled = false;
        }

        var cellShadow = cell.GetComponent<Shadow>();
        if (cellShadow != null)
        {
            cellShadow.enabled = false;
        }

        var iconBg = new GameObject("IconBG", typeof(RectTransform), typeof(Image));
        iconBg.transform.SetParent(cell, false);
        var iconRt = (RectTransform)iconBg.transform;
        iconRt.anchorMin = new Vector2(0.08f, 1f);
        iconRt.anchorMax = new Vector2(0.92f, 1f);
        iconRt.pivot = new Vector2(0.5f, 1f);
        iconRt.sizeDelta = new Vector2(0f, 76f);
        iconRt.anchoredPosition = new Vector2(0f, -14f);
        iconBg.GetComponent<Image>().color = new Color(1f, 1f, 1f, 0f);

        var iconImageObj = new GameObject("IconImage", typeof(RectTransform), typeof(Image));
        iconImageObj.transform.SetParent(iconBg.transform, false);
        var iconImageRt = (RectTransform)iconImageObj.transform;
        iconImageRt.anchorMin = new Vector2(0f, 0f);
        iconImageRt.anchorMax = new Vector2(1f, 1f);
        iconImageRt.offsetMin = new Vector2(4f, 4f);
        iconImageRt.offsetMax = new Vector2(-4f, -4f);
        var iconImage = iconImageObj.GetComponent<Image>();
        iconImage.preserveAspect = true;

        var sprite = TryResolveProductSprite(data.ProductName);
        if (sprite != null)
        {
            iconImage.sprite = sprite;
            iconImage.color = Color.white;
        }
        else
        {
            iconImage.color = new Color(1f, 1f, 1f, 0f);
            var iconText = CreateTMPText("IconText", iconBg.transform, "图片占位", 18, FontStyles.Italic, TextAlignmentOptions.Center);
            StretchText(iconText, 0f);
        }

        var nameBannerObj = new GameObject("NameBanner", typeof(RectTransform), typeof(Image));
        nameBannerObj.transform.SetParent(cell, false);
        var nameBannerRt = (RectTransform)nameBannerObj.transform;
        nameBannerRt.anchorMin = new Vector2(0.07f, 1f);
        nameBannerRt.anchorMax = new Vector2(0.93f, 1f);
        nameBannerRt.pivot = new Vector2(0.5f, 1f);
        nameBannerRt.sizeDelta = new Vector2(0f, 34f);
        nameBannerRt.anchoredPosition = new Vector2(0f, -95f);
        var nameBannerImage = nameBannerObj.GetComponent<Image>();
        var nameBannerSprite = ResolveProductNameBannerSprite(cellIndex);
        nameBannerImage.sprite = nameBannerSprite;
        nameBannerImage.type = Image.Type.Simple;
        nameBannerImage.preserveAspect = false;
        nameBannerImage.color = nameBannerSprite != null ? Color.white : new Color(1f, 1f, 1f, 0f);
        nameBannerImage.raycastTarget = false;

        var nameText = CreateTMPText("Name", nameBannerObj.transform, data.ProductName, 26, FontStyles.Bold, TextAlignmentOptions.Center);
        nameText.color = Color.white;
        var nameRt = (RectTransform)nameText.transform;
        nameRt.anchorMin = Vector2.zero;
        nameRt.anchorMax = Vector2.one;
        nameRt.offsetMin = Vector2.zero;
        nameRt.offsetMax = Vector2.zero;

        var buyPrice = CreateTMPText("BuyPrice", cell, $"进货价：{data.CostPrice}", 22, FontStyles.Bold, TextAlignmentOptions.Left);
        var buyRt = (RectTransform)buyPrice.transform;
        buyRt.anchorMin = new Vector2(0.08f, 1f);
        buyRt.anchorMax = new Vector2(0.92f, 1f);
        buyRt.pivot = new Vector2(0.5f, 1f);
        buyRt.sizeDelta = new Vector2(0f, 26f);
        buyRt.anchoredPosition = new Vector2(0f, -136f);

        CreateProductCellDivider(cell, -164f);
        var currentStock = CreateTMPText("CurrentStock", cell, $"当前储量：{data.CurrentStock}", 22, FontStyles.Bold, TextAlignmentOptions.Left);
        var stockRt = (RectTransform)currentStock.transform;
        stockRt.anchorMin = new Vector2(0.08f, 1f);
        stockRt.anchorMax = new Vector2(0.92f, 1f);
        stockRt.pivot = new Vector2(0.5f, 1f);
        stockRt.sizeDelta = new Vector2(0f, 24f);
        stockRt.anchoredPosition = new Vector2(0f, -186f);

        CreateProductCellDivider(cell, -210f);

        CreateStepperRow(
            cell,
            "进货\n数量",
            0,
            -218f,
            data.PurchaseQuantity,
            value =>
            {
                data.PurchaseQuantity = value;
                RefreshMoneyDisplays();
                RefreshStockControlsInteractable();
            },
            () => CanAffordAdditionalPurchase(data));

        CreateStepperRow(
            cell,
            "出售\n价格",
            1,
            -264f,
            data.TodayPrice,
            value => data.TodayPrice = value,
            null,
            MaxProductTodayPrice(data),
            !data.PriceLocked);
    }

    private void CreateStepperRow(
        RectTransform parent,
        string label,
        int rowId,
        float topOffset,
        int initialValue,
        Action<int> onValueChanged = null,
        Func<bool> canIncrease = null,
        int maxValue = int.MaxValue,
        bool canEditThisStepper = true)
    {
        var row = new GameObject($"StepperRow_{rowId}", typeof(RectTransform));
        row.transform.SetParent(parent, false);
        var rowRt = (RectTransform)row.transform;
        rowRt.anchorMin = new Vector2(0.06f, 1f);
        rowRt.anchorMax = new Vector2(0.94f, 1f);
        rowRt.pivot = new Vector2(0.5f, 1f);
        rowRt.sizeDelta = new Vector2(0f, 38f);
        rowRt.anchoredPosition = new Vector2(0f, topOffset);

        var lbl = CreateTMPText("Label", row.transform, $"{label}:", 20, FontStyles.Bold, TextAlignmentOptions.Left);
        var lblRt = (RectTransform)lbl.transform;
        lblRt.anchorMin = new Vector2(0f, 0f);
        lblRt.anchorMax = new Vector2(0.42f, 1f);
        lblRt.offsetMin = Vector2.zero;
        lblRt.offsetMax = Vector2.zero;

        var minus = CreateMiniButton(row.transform, "-", new Vector2(0.43f, 0.5f));
        var plus = CreateMiniButton(row.transform, "+", new Vector2(plusButtonAnchorX, 0.5f));

        var valueText = CreateTMPText("Value", row.transform, initialValue.ToString(), 22, FontStyles.Bold, TextAlignmentOptions.Center);
        var valueRt = (RectTransform)valueText.transform;
        valueRt.anchorMin = new Vector2(0.54f, 0f);
        valueRt.anchorMax = new Vector2(0.82f, 1f);
        valueRt.offsetMin = Vector2.zero;
        valueRt.offsetMax = Vector2.zero;
        valueText.enableAutoSizing = true;
        valueText.fontSizeMin = 16f;
        valueText.fontSizeMax = 22f;
        valueText.enableWordWrapping = false;
        valueText.overflowMode = TextOverflowModes.Overflow;

        var stepper = row.AddComponent<ShopUiStepper>();
        stepper.Bind(minus, plus, valueText, initialValue, onValueChanged, canIncrease, maxValue, canEditThisStepper);
        stepper.SetInteractable(canEditStockPlan);
        inventorySteppers.Add(stepper);
    }

    private Button CreateMiniButton(Transform parent, string sign, Vector2 anchor)
    {
        var btn = new GameObject($"Btn_{sign}", typeof(RectTransform), typeof(Image), typeof(Button));
        btn.transform.SetParent(parent, false);

        var rt = (RectTransform)btn.transform;
        rt.anchorMin = anchor;
        rt.anchorMax = anchor;
        rt.pivot = new Vector2(0.5f, 0.5f);
        rt.sizeDelta = new Vector2(30f, 30f);

        var img = btn.GetComponent<Image>();
        var spriteName = sign == "+" ? inventoryStepperPlusSpriteName : inventoryStepperMinusSpriteName;
        var btnSprite = ResolveUiDecorationSprite(inventoryStepperButtonResourcePath, inventoryStepperButtonAssetPath, spriteName);
        if (btnSprite != null)
        {
            img.sprite = btnSprite;
            img.type = Image.Type.Simple;
            img.preserveAspect = true;
            img.color = Color.white;
        }
        else
        {
            img.color = woodEdgeFade;
        }

        if (btnSprite == null)
        {
            var text = CreateTMPText("Sign", btn.transform, sign, 24, FontStyles.Bold, TextAlignmentOptions.Center);
            StretchText(text, 0f);
        }

        var button = btn.GetComponent<Button>();
        button.targetGraphic = img;
        var colors = button.colors;
        colors.normalColor = Color.white;
        colors.highlightedColor = Color.white;
        colors.pressedColor = new Color(0.78f, 0.78f, 0.78f, 1f);
        colors.disabledColor = new Color(0.78f, 0.78f, 0.78f, 1f);
        colors.colorMultiplier = 1f;
        colors.fadeDuration = 0.08f;
        button.colors = colors;
        return button;
    }

    private Sprite ResolveProductNameBannerSprite(int index)
    {
        if (ProductNameBannerSpriteCycle.Length == 0)
        {
            return null;
        }

        int spriteIndex = Mathf.Abs(index) % ProductNameBannerSpriteCycle.Length;
        return ResolveUiDecorationSprite(inventoryNameBannerResourcePath, inventoryNameBannerAssetPath, ProductNameBannerSpriteCycle[spriteIndex]);
    }

    private void CreateProductCellDivider(RectTransform parent, float topOffset)
    {
        var divider = new GameObject("CellDivider", typeof(RectTransform), typeof(Image));
        divider.transform.SetParent(parent, false);
        var rt = (RectTransform)divider.transform;
        rt.anchorMin = new Vector2(0.14f, 1f);
        rt.anchorMax = new Vector2(0.86f, 1f);
        rt.pivot = new Vector2(0.5f, 1f);
        rt.sizeDelta = new Vector2(0f, 1f);
        rt.anchoredPosition = new Vector2(0f, topOffset);

        var image = divider.GetComponent<Image>();
        image.color = new Color(0.42f, 0.30f, 0.15f, 0.22f);
        image.raycastTarget = false;
    }

    private TextMeshProUGUI CreateTMPText(string name, Transform parent, string content, float fontSize, FontStyles style, TextAlignmentOptions align)
    {
        var go = new GameObject(name, typeof(RectTransform), typeof(TextMeshProUGUI));
        go.transform.SetParent(parent, false);
        var txt = go.GetComponent<TextMeshProUGUI>();
        txt.text = content;
        txt.fontSize = fontSize;
        txt.fontStyle = style;
        txt.alignment = align;
        txt.color = textColor;
        txt.raycastTarget = false;
        if (uiFont != null)
        {
            txt.font = uiFont;
        }
        return txt;
    }

    private List<ShopProductModel> BuildMockProducts()
    {
        return new List<ShopProductModel>
        {
            new("瓶装水", 4, 40, 5, 40),
            new("面包", 5, 60, 7, 60),
            new("烤肉", 13, 30, 15, 30),
            new("银戒指", 150, 10, 200, 10),
            new("黄金", 950, 10, 1000, 10),
        };
    }

    private void SetInventoryVisible(bool visible)
    {
        if (inventoryOverlayRoot != null)
        {
            inventoryOverlayRoot.SetActive(visible);
        }

        if (openInventoryButton != null)
        {
            openInventoryButton.gameObject.SetActive(!visible);
        }
    }

    public void OpenInventory()
    {
        SetInventoryVisible(true);
        RefreshStockControlsInteractable();
    }

    private void SubmitStockPlan()
    {
        if (!canEditStockPlan)
        {
            return;
        }

        int plannedCost = CalculatePlannedPurchaseCost();
        if (plannedCost > playerModel.CurrentMoney)
        {
            RefreshMoneyDisplays();
            RefreshStockControlsInteractable();
            Debug.LogWarning("[ShopAssistantUI] Stock plan rejected: not enough money.");
            return;
        }

        foreach (var product in marketProducts)
        {
            product.CurrentStock += product.PurchaseQuantity;
        }
        playerModel.CurrentMoney -= plannedCost;

        canEditStockPlan = false;
        RebuildProductCells();
        RefreshTopLeftStatus(currentRoundValue, playerModel.CurrentMoney, currentGameStateValue);
        RefreshStockControlsInteractable();

        string payload = BuildStockPlanUpdateJson();
        WsAgentClient.SubmitShopStockUpdateJson(payload);
        Debug.Log($"[ShopAssistantUI] Stock plan submitted: {payload}");
    }

    private void RefreshStockControlsInteractable()
    {
        bool canSubmit = canEditStockPlan && CalculatePreviewMoney() >= 0;
        if (stockInventoryButton != null)
        {
            stockInventoryButton.interactable = canSubmit;
            if (stockInventoryButton.targetGraphic != null)
            {
                stockInventoryButton.targetGraphic.color = canEditStockPlan ? Color.white : new Color(1f, 1f, 1f, 0f);
            }
        }

        foreach (var stepper in inventorySteppers)
        {
            if (stepper != null)
            {
                stepper.SetInteractable(canEditStockPlan);
            }
        }
    }

    private int CalculatePreviewMoney()
    {
        return playerModel.CurrentMoney - CalculatePlannedPurchaseCost();
    }

    private int CalculatePlannedPurchaseCost()
    {
        int total = 0;
        foreach (var product in marketProducts)
        {
            total += Mathf.Max(0, product.CostPrice) * Mathf.Max(0, product.PurchaseQuantity);
        }
        return total;
    }

    private bool CanAffordAdditionalPurchase(ShopProductModel product)
    {
        if (product == null)
        {
            return false;
        }

        int extraCost = Mathf.Max(0, product.CostPrice);
        return extraCost <= 0 || CalculatePreviewMoney() >= extraCost;
    }

    private static int MaxProductTodayPrice(ShopProductModel product)
    {
        if (product == null)
        {
            return 0;
        }

        return Mathf.Max(0, product.CostPrice * 2);
    }

    private void RefreshMoneyDisplays()
    {
        int displayMoney = canEditStockPlan ? CalculatePreviewMoney() : playerModel.CurrentMoney;
        if (moneyText != null)
        {
            moneyText.text = displayMoney.ToString();
        }
        if (rightPanelMoneyText != null)
        {
            rightPanelMoneyText.text = $"资金：{displayMoney}";
        }
    }

    private string BuildStockPlanUpdateJson()
    {
        var payload = new ShopStockUpdatePayload
        {
            currentMoney = playerModel.CurrentMoney,
            todayIncome = playerModel.TodayIncome,
            items = new ShopStockUpdateItem[marketProducts.Count]
        };

        for (int i = 0; i < marketProducts.Count; i++)
        {
            var product = marketProducts[i];
            payload.items[i] = new ShopStockUpdateItem
            {
                name = product.ProductName,
                currentStock = product.CurrentStock,
                purchaseQuantity = product.PurchaseQuantity,
                todayPrice = product.TodayPrice,
                costPrice = product.CostPrice
            };
        }

        return JsonUtility.ToJson(payload);
    }

    private void RefreshTopLeftStatus(int round, int money, string state)
    {
        int clampedRound = Mathf.Clamp(round, 0, 999);
        string stateValue = string.IsNullOrWhiteSpace(state) ? "回合进行中" : state.Trim();
        currentRoundValue = clampedRound;
        currentGameStateValue = stateValue;
        playerModel.CurrentMoney = money;

        if (roundText != null) roundText.text = clampedRound.ToString();
        RefreshMoneyDisplays();
        if (stateText != null)
        {
            stateText.text = stateValue;
            stateText.color = stateValue.IndexOf("结算", StringComparison.Ordinal) >= 0
                ? StatusSettlementTextColor
                : StatusDynamicTextColor;
        }
    }

    private RectTransform CreateStatusTextArea(string name, RectTransform parent, float yMin, float yMax)
    {
        var row = new GameObject(name, typeof(RectTransform));
        row.transform.SetParent(parent, false);
        var rt = (RectTransform)row.transform;
        rt.anchorMin = new Vector2(0.265f, yMin);
        rt.anchorMax = new Vector2(0.955f, yMax);
        rt.offsetMin = Vector2.zero;
        rt.offsetMax = Vector2.zero;
        return rt;
    }

    private TextMeshProUGUI CreateStatusText(string name, RectTransform parent, string content, float fontSize, FontStyles style, TextAlignmentOptions align, Color color)
    {
        var text = CreateTMPText(name, parent, content, fontSize, style, align);
        text.color = color;
        text.enableWordWrapping = false;
        text.overflowMode = TextOverflowModes.Overflow;
        text.margin = Vector4.zero;
        ApplyTextFaceDilate(text, 0.30f);
        return text;
    }

    private static void ApplyTextFaceDilate(TextMeshProUGUI text, float dilate)
    {
        if (text == null || text.fontMaterial == null)
        {
            return;
        }

        var material = new Material(text.fontMaterial)
        {
            name = $"{text.fontMaterial.name}_Thick"
        };

        if (material.HasProperty(ShaderUtilities.ID_FaceDilate))
        {
            material.SetFloat(ShaderUtilities.ID_FaceDilate, dilate);
        }

        text.fontMaterial = material;
    }

    private static void SetAnchoredRect(RectTransform rt, float xMin, float yMin, float xMax, float yMax)
    {
        rt.anchorMin = new Vector2(xMin, yMin);
        rt.anchorMax = new Vector2(xMax, yMax);
        rt.offsetMin = Vector2.zero;
        rt.offsetMax = Vector2.zero;
    }

    private RectTransform CreateStatusRow(string name, Transform parent, float height)
    {
        var row = new GameObject(name, typeof(RectTransform), typeof(Image), typeof(Outline), typeof(LayoutElement));
        row.transform.SetParent(parent, false);
        var rt = (RectTransform)row.transform;
        rt.sizeDelta = new Vector2(0f, height);

        var element = row.GetComponent<LayoutElement>();
        element.preferredHeight = height;
        element.minHeight = height;

        row.GetComponent<Image>().color = new Color(1f, 1f, 1f, 0.28f);
        var line = row.GetComponent<Outline>();
        line.effectColor = new Color(0.55f, 0.39f, 0.12f, 1f);
        line.effectDistance = new Vector2(statusRowLineThickness, -statusRowLineThickness);
        return rt;
    }

    private void StretchText(TextMeshProUGUI text, float horizontalPadding = 10f)
    {
        if (text == null) return;
        var rt = (RectTransform)text.transform;
        rt.anchorMin = Vector2.zero;
        rt.anchorMax = Vector2.one;
        rt.offsetMin = new Vector2(horizontalPadding, 0f);
        rt.offsetMax = new Vector2(-horizontalPadding, 0f);
    }

    private void AddFrameBorder(RectTransform parent, float inset, Color borderColor, float thickness)
    {
        var border = new GameObject("FrameBorder", typeof(RectTransform));
        border.transform.SetParent(parent, false);
        border.transform.SetAsFirstSibling();

        var rt = (RectTransform)border.transform;
        rt.anchorMin = Vector2.zero;
        rt.anchorMax = Vector2.one;
        rt.offsetMin = new Vector2(inset, inset);
        rt.offsetMax = new Vector2(-inset, -inset);

        CreateBorderLine("Top", rt, new Vector2(0f, 1f), new Vector2(1f, 1f), new Vector2(0f, -thickness), new Vector2(0f, 0f), borderColor);
        CreateBorderLine("Bottom", rt, new Vector2(0f, 0f), new Vector2(1f, 0f), new Vector2(0f, 0f), new Vector2(0f, thickness), borderColor);
        CreateBorderLine("Left", rt, new Vector2(0f, 0f), new Vector2(0f, 1f), new Vector2(0f, 0f), new Vector2(thickness, 0f), borderColor);
        CreateBorderLine("Right", rt, new Vector2(1f, 0f), new Vector2(1f, 1f), new Vector2(-thickness, 0f), new Vector2(0f, 0f), borderColor);
    }

    private void CreateBorderLine(
        string name,
        RectTransform parent,
        Vector2 anchorMin,
        Vector2 anchorMax,
        Vector2 offsetMin,
        Vector2 offsetMax,
        Color color)
    {
        var line = new GameObject(name, typeof(RectTransform), typeof(Image));
        line.transform.SetParent(parent, false);

        var rt = (RectTransform)line.transform;
        rt.anchorMin = anchorMin;
        rt.anchorMax = anchorMax;
        rt.offsetMin = offsetMin;
        rt.offsetMax = offsetMax;

        var image = line.GetComponent<Image>();
        image.color = color;
        image.raycastTarget = false;
    }

    private void ApplyInventoryWindowBackground(RectTransform window)
    {
        if (window == null)
        {
            return;
        }

        var windowImage = window.GetComponent<Image>();
        if (windowImage == null)
        {
            return;
        }

        var bgSprite = ResolveInventoryBackgroundSprite();
        if (bgSprite == null)
        {
            windowImage.color = paperColor;
            return;
        }

        windowImage.sprite = bgSprite;
        windowImage.type = Image.Type.Simple;
        windowImage.preserveAspect = true;
        windowImage.color = Color.white;

        var outline = window.GetComponent<Outline>();
        if (outline != null)
        {
            outline.enabled = false;
        }

        var shadow = window.GetComponent<Shadow>();
        if (shadow != null)
        {
            shadow.enabled = false;
        }
    }

    private Sprite ResolveInventoryBackgroundSprite()
    {
        return ResolveUiDecorationSprite(inventoryBackgroundResourcePath, inventoryBackgroundAssetPath, inventoryBackgroundSpriteName);
    }

    private void CreateInventoryTitleSprite(RectTransform window)
    {
        var titleSprite = ResolveUiDecorationSprite(inventoryTitleResourcePath, inventoryTitleAssetPath, inventoryTitleSpriteName);
        if (titleSprite == null)
        {
            Debug.LogWarning("[ShopAssistantUI] Inventory title sprite missing, title image will be hidden.");
        }

        var titleObj = new GameObject("TitleSprite", typeof(RectTransform), typeof(Image));
        titleObj.transform.SetParent(window, false);

        var titleRt = (RectTransform)titleObj.transform;
        titleRt.anchorMin = new Vector2(0.5f, 1f);
        titleRt.anchorMax = new Vector2(0.5f, 1f);
        titleRt.pivot = new Vector2(0.5f, 1f);
        titleRt.sizeDelta = new Vector2(520f, 88f);
        titleRt.anchoredPosition = new Vector2(0f, -20f);

        var titleImage = titleObj.GetComponent<Image>();
        titleImage.sprite = titleSprite;
        titleImage.type = Image.Type.Simple;
        titleImage.preserveAspect = true;
        titleImage.color = titleSprite != null ? Color.white : new Color(1f, 1f, 1f, 0f);
        titleImage.raycastTarget = false;
    }

    private Button CreateInventoryStockSpriteButton(RectTransform window)
    {
        var buttonRoot = new GameObject("Btn_StockIn", typeof(RectTransform), typeof(Image), typeof(Button));
        buttonRoot.transform.SetParent(window, false);

        var rt = (RectTransform)buttonRoot.transform;
        rt.anchorMin = new Vector2(0.5f, 0f);
        rt.anchorMax = new Vector2(0.5f, 0f);
        rt.pivot = new Vector2(0.5f, 0f);
        rt.sizeDelta = new Vector2(392f, 96f);
        rt.anchoredPosition = new Vector2(0f, 20f);

        var buttonImage = buttonRoot.GetComponent<Image>();
        var buttonSprite = ResolveUiDecorationSprite(inventoryStockButtonResourcePath, inventoryStockButtonAssetPath, inventoryStockButtonSpriteName);
        if (buttonSprite != null)
        {
            buttonImage.sprite = buttonSprite;
            buttonImage.type = Image.Type.Simple;
            buttonImage.preserveAspect = true;
            buttonImage.color = Color.white;
        }
        else
        {
            buttonImage.color = woodColor;
            Debug.LogWarning("[ShopAssistantUI] Inventory stock button sprite missing, fallback color button is used.");
        }

        var button = buttonRoot.GetComponent<Button>();
        button.targetGraphic = buttonImage;
        var colors = button.colors;
        colors.normalColor = Color.white;
        colors.highlightedColor = Color.white;
        colors.pressedColor = new Color(0.92f, 0.92f, 0.92f, 1f);
        colors.disabledColor = new Color(1f, 1f, 1f, 0.6f);
        colors.colorMultiplier = 1f;
        colors.fadeDuration = 0.08f;
        button.colors = colors;
        return button;
    }

    private Button CreateInventoryCloseSpriteButton(RectTransform window)
    {
        var buttonRoot = new GameObject("Btn_CloseInventory", typeof(RectTransform), typeof(Image), typeof(Button));
        buttonRoot.transform.SetParent(window, false);

        var rt = (RectTransform)buttonRoot.transform;
        rt.anchorMin = new Vector2(1f, 1f);
        rt.anchorMax = new Vector2(1f, 1f);
        rt.pivot = new Vector2(0.5f, 0.5f);
        rt.sizeDelta = new Vector2(72f, 72f);
        rt.anchoredPosition = new Vector2(-48f, -44f);

        var buttonImage = buttonRoot.GetComponent<Image>();
        var buttonSprite = ResolveUiDecorationSprite(inventoryCloseButtonResourcePath, inventoryCloseButtonAssetPath, inventoryCloseButtonSpriteName);
        if (buttonSprite != null)
        {
            buttonImage.sprite = buttonSprite;
            buttonImage.type = Image.Type.Simple;
            buttonImage.preserveAspect = true;
            buttonImage.color = Color.white;
        }
        else
        {
            buttonImage.color = woodColor;
            Debug.LogWarning("[ShopAssistantUI] Inventory close button sprite missing, fallback color button is used.");
        }

        var button = buttonRoot.GetComponent<Button>();
        button.targetGraphic = buttonImage;
        var colors = button.colors;
        colors.normalColor = Color.white;
        colors.highlightedColor = Color.white;
        colors.pressedColor = new Color(0.92f, 0.92f, 0.92f, 1f);
        colors.disabledColor = new Color(1f, 1f, 1f, 0.6f);
        colors.colorMultiplier = 1f;
        colors.fadeDuration = 0.08f;
        button.colors = colors;
        return button;
    }

    private void CreateInventoryRightPanelSprite(RectTransform window)
    {
        var panelSprite = ResolveUiDecorationSprite(inventoryRightPanelResourcePath, inventoryRightPanelAssetPath, inventoryRightPanelSpriteName);
        if (panelSprite == null)
        {
            Debug.LogWarning("[ShopAssistantUI] Inventory right panel sprite missing, right panel image will be hidden.");
        }

        var panelObj = new GameObject("RightInfoPanel", typeof(RectTransform), typeof(Image));
        panelObj.transform.SetParent(window, false);

        var panelRt = (RectTransform)panelObj.transform;
        panelRt.anchorMin = new Vector2(0.745f, 0.11f);
        panelRt.anchorMax = new Vector2(0.955f, 0.865f);
        panelRt.offsetMin = Vector2.zero;
        panelRt.offsetMax = Vector2.zero;

        var panelImage = panelObj.GetComponent<Image>();
        panelImage.sprite = panelSprite;
        panelImage.type = Image.Type.Simple;
        // Keep height controlled by anchors; preserveAspect shrinks visible height unexpectedly here.
        panelImage.preserveAspect = false;
        panelImage.color = panelSprite != null ? Color.white : new Color(1f, 1f, 1f, 0f);
        panelImage.raycastTarget = false;

        BuildRightInfoPanelContent(panelRt);
    }

    private void BuildRightInfoPanelContent(RectTransform panelRt)
    {
        if (panelRt == null)
        {
            return;
        }

        var content = new GameObject("Content", typeof(RectTransform));
        content.transform.SetParent(panelRt, false);
        var contentRt = (RectTransform)content.transform;
        contentRt.anchorMin = Vector2.zero;
        contentRt.anchorMax = Vector2.one;
        contentRt.offsetMin = new Vector2(12f, 18f);
        contentRt.offsetMax = new Vector2(-16f, -18f);

        var logoSprite = ResolveUiDecorationSprite(inventoryShopLogoResourcePath, inventoryShopLogoAssetPath, inventoryShopLogoSpriteName);
        var logoObj = new GameObject("Logo", typeof(RectTransform), typeof(Image));
        logoObj.transform.SetParent(contentRt, false);
        var logoRt = (RectTransform)logoObj.transform;
        logoRt.anchorMin = new Vector2(0.10f, 0.73f);
        logoRt.anchorMax = new Vector2(0.90f, 0.96f);
        logoRt.offsetMin = Vector2.zero;
        logoRt.offsetMax = Vector2.zero;
        var logoImage = logoObj.GetComponent<Image>();
        logoImage.sprite = logoSprite;
        logoImage.type = Image.Type.Simple;
        logoImage.preserveAspect = true;
        logoImage.color = logoSprite != null ? Color.white : new Color(1f, 1f, 1f, 0f);
        logoImage.raycastTarget = false;

        var header = CreateTMPText("InfoHeader", contentRt, "-◆商店信息◆-", 26, FontStyles.Bold, TextAlignmentOptions.Center);
        var headerRt = (RectTransform)header.transform;
        headerRt.anchorMin = new Vector2(0.02f, 0.63f);
        headerRt.anchorMax = new Vector2(0.98f, 0.70f);
        headerRt.offsetMin = Vector2.zero;
        headerRt.offsetMax = Vector2.zero;
        header.enableWordWrapping = false;

        var ownerText = CreateTMPText("OwnerText", contentRt, "店主：Barabasi", 23, FontStyles.Bold, TextAlignmentOptions.Left);
        var ownerRt = (RectTransform)ownerText.transform;
        ownerRt.anchorMin = new Vector2(0.08f, 0.57f);
        ownerRt.anchorMax = new Vector2(0.94f, 0.62f);
        ownerRt.offsetMin = Vector2.zero;
        ownerRt.offsetMax = Vector2.zero;
        ownerText.enableWordWrapping = false;

        CreateRightPanelDivider(contentRt, 0.545f);

        var moneyRow = new GameObject("MoneyRow", typeof(RectTransform));
        moneyRow.transform.SetParent(contentRt, false);
        var moneyRt = (RectTransform)moneyRow.transform;
        moneyRt.anchorMin = new Vector2(0.08f, 0.485f);
        moneyRt.anchorMax = new Vector2(0.94f, 0.535f);
        moneyRt.offsetMin = Vector2.zero;
        moneyRt.offsetMax = Vector2.zero;

        rightPanelMoneyText = CreateTMPText("MoneyText", moneyRt, $"资金：{playerModel.CurrentMoney}", 23, FontStyles.Bold, TextAlignmentOptions.Left);
        var moneyTextRt = (RectTransform)rightPanelMoneyText.transform;
        moneyTextRt.anchorMin = new Vector2(0f, 0f);
        moneyTextRt.anchorMax = new Vector2(0.80f, 1f);
        moneyTextRt.offsetMin = Vector2.zero;
        moneyTextRt.offsetMax = Vector2.zero;
        rightPanelMoneyText.enableWordWrapping = false;

        var coinSprite = ResolveUiDecorationSprite(inventoryCoinFeatherResourcePath, inventoryCoinFeatherAssetPath, inventoryCoinSpriteName);
        var coinObj = new GameObject("CoinIcon", typeof(RectTransform), typeof(Image));
        coinObj.transform.SetParent(moneyRt, false);
        var coinRt = (RectTransform)coinObj.transform;
        coinRt.anchorMin = new Vector2(0.84f, 0.15f);
        coinRt.anchorMax = new Vector2(0.99f, 0.85f);
        coinRt.offsetMin = Vector2.zero;
        coinRt.offsetMax = Vector2.zero;
        var coinImage = coinObj.GetComponent<Image>();
        coinImage.sprite = coinSprite;
        coinImage.type = Image.Type.Simple;
        coinImage.preserveAspect = true;
        coinImage.color = coinSprite != null ? Color.white : new Color(1f, 1f, 1f, 0f);
        coinImage.raycastTarget = false;

        CreateRightPanelDivider(contentRt, 0.465f);

        var openingLabel = CreateTMPText("OpeningLabel", contentRt, "营业时间：", 23, FontStyles.Bold, TextAlignmentOptions.Left);
        var openingLabelRt = (RectTransform)openingLabel.transform;
        openingLabelRt.anchorMin = new Vector2(0.08f, 0.41f);
        openingLabelRt.anchorMax = new Vector2(0.94f, 0.46f);
        openingLabelRt.offsetMin = Vector2.zero;
        openingLabelRt.offsetMax = Vector2.zero;
        openingLabel.enableWordWrapping = false;

        var openingTime = CreateTMPText("OpeningTime", contentRt, "08:00 - 22:00", 23, FontStyles.Bold, TextAlignmentOptions.Left);
        var openingTimeRt = (RectTransform)openingTime.transform;
        openingTimeRt.anchorMin = new Vector2(0.08f, 0.36f);
        openingTimeRt.anchorMax = new Vector2(0.94f, 0.41f);
        openingTimeRt.offsetMin = Vector2.zero;
        openingTimeRt.offsetMax = Vector2.zero;
        openingTime.enableWordWrapping = false;

        CreateRightPanelDivider(contentRt, 0.34f);

        var hintSprite = ResolveUiDecorationSprite(inventoryHintPanelResourcePath, inventoryHintPanelAssetPath, inventoryHintPanelSpriteName);
        var hintObj = new GameObject("HintPanel", typeof(RectTransform), typeof(Image));
        hintObj.transform.SetParent(contentRt, false);
        var hintRt = (RectTransform)hintObj.transform;
        hintRt.anchorMin = new Vector2(0.06f, 0.02f);
        hintRt.anchorMax = new Vector2(0.94f, 0.02f);
        hintRt.pivot = new Vector2(0.5f, 0f);
        hintRt.sizeDelta = new Vector2(0f, 10f);
        var hintAspect = hintObj.AddComponent<AspectRatioFitter>();
        hintAspect.aspectMode = AspectRatioFitter.AspectMode.WidthControlsHeight;
        hintAspect.aspectRatio = 947f / 847f; // Match sprite rect ratio from meta.
        var hintImage = hintObj.GetComponent<Image>();
        hintImage.sprite = hintSprite;
        hintImage.type = Image.Type.Simple;
        hintImage.preserveAspect = true;
        hintImage.color = hintSprite != null ? Color.white : new Color(1f, 1f, 1f, 0f);
        hintImage.raycastTarget = false;

    }

    private void CreateRightPanelDivider(RectTransform parent, float yAnchor)
    {
        var divider = new GameObject("Divider", typeof(RectTransform), typeof(Image));
        divider.transform.SetParent(parent, false);
        var dividerRt = (RectTransform)divider.transform;
        dividerRt.anchorMin = new Vector2(0.14f, yAnchor);
        dividerRt.anchorMax = new Vector2(0.86f, yAnchor);
        dividerRt.sizeDelta = new Vector2(0f, 1f);
        dividerRt.anchoredPosition = Vector2.zero;

        var dividerImage = divider.GetComponent<Image>();
        dividerImage.color = new Color(0.42f, 0.30f, 0.15f, 0.22f);
        dividerImage.raycastTarget = false;
    }

    private Sprite ResolveUiDecorationSprite(string resourcePath, string assetPath, string spriteName)
    {
        if (!string.IsNullOrWhiteSpace(resourcePath))
        {
            var primaryName = string.IsNullOrWhiteSpace(spriteName) ? string.Empty : spriteName.Trim();
            if (!string.IsNullOrEmpty(primaryName))
            {
                var sprite = ResolveSpriteFromResources(resourcePath.Trim(), primaryName, primaryName);
                if (sprite != null)
                {
                    return sprite;
                }
            }
            else
            {
                var sprites = Resources.LoadAll<Sprite>(resourcePath.Trim());
                if (sprites != null && sprites.Length > 0)
                {
                    return sprites[0];
                }
            }
        }

#if UNITY_EDITOR
        if (!string.IsNullOrWhiteSpace(assetPath))
        {
            var assets = AssetDatabase.LoadAllAssetsAtPath(assetPath.Trim());
            foreach (var asset in assets)
            {
                var s = asset as Sprite;
                if (s == null)
                {
                    continue;
                }

                if (string.IsNullOrWhiteSpace(spriteName))
                {
                    return s;
                }

                var trimmed = spriteName.Trim();
                if (string.Equals(s.name, trimmed, StringComparison.Ordinal))
                {
                    return s;
                }
            }
        }
#endif

        Debug.LogWarning($"[ShopAssistantUI] UI sprite not found: {assetPath} ({spriteName})");
        return null;
    }

    [Serializable]
    private sealed class MarketInformationPayload
    {
        public MarketItem[] items;
    }

    [Serializable]
    private sealed class MarketItem
    {
        public string name;
        public float purchasePrice;
        public float basePrice;
        public float quantity;
        public bool priceLocked;
    }

    [Serializable]
    private sealed class ShopStockUpdatePayload
    {
        public int currentMoney;
        public int todayIncome;
        public ShopStockUpdateItem[] items;
    }

    [Serializable]
    private sealed class ShopStockUpdateItem
    {
        public string name;
        public int currentStock;
        public int purchaseQuantity;
        public int todayPrice;
        public int costPrice;
    }

    [Serializable]
    private struct ProductImageMapping
    {
        public string productName;
        [Tooltip("Resources relative path without extension, e.g. UI/Item/base_goods")]
        public string imagePath;
        [Tooltip("Sub-sprite name in atlas, e.g. 面包")]
        public string spriteName;
        [Tooltip("Direct sprite assignment; if set, it overrides imagePath/spriteName")]
        public Sprite sprite;
    }

}

public sealed class InventoryGridAutoColumns : MonoBehaviour
{
    private GridLayoutGroup grid;
    private RectTransform viewport;
    private int minColumns;
    private int maxColumns;
    private float lastWidth = -1f;

    public void Bind(GridLayoutGroup targetGrid, RectTransform targetViewport, int min, int max)
    {
        grid = targetGrid;
        viewport = targetViewport;
        minColumns = Mathf.Max(1, min);
        maxColumns = Mathf.Max(minColumns, max);
        Refresh();
    }

    private void Update()
    {
        Refresh();
    }

    private void Refresh()
    {
        if (grid == null || viewport == null)
        {
            return;
        }

        float width = viewport.rect.width;
        if (Mathf.Abs(width - lastWidth) < 0.2f || width <= 0f)
        {
            return;
        }

        lastWidth = width;

        float cellWidth = grid.cellSize.x;
        float spacing = grid.spacing.x;
        float available = width - grid.padding.left - grid.padding.right + spacing;
        int columns = Mathf.FloorToInt(available / (cellWidth + spacing));
        columns = Mathf.Clamp(columns, minColumns, maxColumns);
        grid.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
        grid.constraintCount = columns;
    }
}

public sealed class ShopUiStepper : MonoBehaviour
{
    private Button minusButton;
    private Button plusButton;
    private ShopUiPressRepeater minusRepeater;
    private ShopUiPressRepeater plusRepeater;
    private TextMeshProUGUI valueText;
    private Action<int> onValueChanged;
    private Func<bool> canIncrease;
    private int maxValue = int.MaxValue;
    private bool baseInteractable = true;
    private bool editAllowed = true;
    private int value;

    public void Bind(
        Button minus,
        Button plus,
        TextMeshProUGUI valueLabel,
        int initialValue,
        Action<int> valueChanged = null,
        Func<bool> canIncreaseValue = null,
        int maxAllowedValue = int.MaxValue,
        bool canEdit = true)
    {
        minusButton = minus;
        plusButton = plus;
        valueText = valueLabel;
        onValueChanged = valueChanged;
        canIncrease = canIncreaseValue;
        maxValue = Mathf.Max(0, maxAllowedValue);
        editAllowed = canEdit;
        value = Mathf.Clamp(initialValue, 0, maxValue);
        UpdateLabel();

        if (minusButton != null)
        {
            minusRepeater = minusButton.GetComponent<ShopUiPressRepeater>();
            if (minusRepeater == null)
            {
                minusRepeater = minusButton.gameObject.AddComponent<ShopUiPressRepeater>();
            }
            minusRepeater.Bind(Decrease);
        }

        if (plusButton != null)
        {
            plusRepeater = plusButton.GetComponent<ShopUiPressRepeater>();
            if (plusRepeater == null)
            {
                plusRepeater = plusButton.gameObject.AddComponent<ShopUiPressRepeater>();
            }
            plusRepeater.Bind(Increase);
        }

        RefreshButtons();
    }

    private void OnDestroy()
    {
        if (minusRepeater != null)
        {
            minusRepeater.Unbind();
        }

        if (plusRepeater != null)
        {
            plusRepeater.Unbind();
        }
    }

    private void Decrease()
    {
        if (!baseInteractable || value <= 0)
        {
            RefreshButtons();
            return;
        }

        value = Mathf.Max(0, value - 1);
        UpdateLabel();
    }

    private void Increase()
    {
        if (!baseInteractable || value >= maxValue || (canIncrease != null && !canIncrease.Invoke()))
        {
            RefreshButtons();
            return;
        }

        value = Mathf.Min(maxValue, value + 1);
        UpdateLabel();
    }

    private void UpdateLabel()
    {
        if (valueText != null)
        {
            valueText.text = value.ToString();
        }
        onValueChanged?.Invoke(value);
        RefreshButtons();
    }

    public void SetInteractable(bool interactable)
    {
        baseInteractable = interactable && editAllowed;
        RefreshButtons();
    }

    private void RefreshButtons()
    {
        SetButtonVisual(minusButton, baseInteractable && value > 0);
        SetButtonVisual(plusButton, baseInteractable && value < maxValue && (canIncrease == null || canIncrease.Invoke()));
    }

    private static void SetButtonVisual(Button button, bool interactable)
    {
        if (button == null)
        {
            return;
        }

        button.interactable = interactable;
        if (button.targetGraphic != null)
        {
            button.targetGraphic.color = interactable ? Color.white : new Color(0.78f, 0.78f, 0.78f, 1f);
        }
    }
}

public sealed class ShopUiPressRepeater : MonoBehaviour, IPointerDownHandler, IPointerUpHandler, IPointerExitHandler, IPointerClickHandler
{
    [SerializeField] private float holdDelaySeconds = 0.35f;
    [SerializeField] private float fastModeHoldSeconds = 1.5f;
    [SerializeField] private float repeatIntervalSeconds = 0.06f;
    [SerializeField] private int fastRepeatStepCount = 5;

    private Action onStep;
    private bool isHolding;
    private bool hasRepeated;
    private float holdElapsed;
    private float repeatElapsed;

    public void Bind(Action onStepAction)
    {
        onStep = onStepAction;
    }

    public void Unbind()
    {
        onStep = null;
        isHolding = false;
        hasRepeated = false;
        holdElapsed = 0f;
        repeatElapsed = 0f;
    }

    public void OnPointerDown(PointerEventData eventData)
    {
        isHolding = true;
        hasRepeated = false;
        holdElapsed = 0f;
        repeatElapsed = 0f;
    }

    public void OnPointerUp(PointerEventData eventData)
    {
        isHolding = false;
    }

    public void OnPointerExit(PointerEventData eventData)
    {
        isHolding = false;
    }

    public void OnPointerClick(PointerEventData eventData)
    {
        // Keep single-click as exactly one step; suppress extra click when hold-repeat already triggered.
        if (!hasRepeated)
        {
            onStep?.Invoke();
        }
    }

    private void Update()
    {
        if (!isHolding || onStep == null)
        {
            return;
        }

        holdElapsed += Time.unscaledDeltaTime;
        if (holdElapsed < holdDelaySeconds)
        {
            return;
        }

        hasRepeated = true;
        repeatElapsed += Time.unscaledDeltaTime;
        while (repeatElapsed >= repeatIntervalSeconds)
        {
            repeatElapsed -= repeatIntervalSeconds;
            int stepCount = holdElapsed >= fastModeHoldSeconds ? Mathf.Max(1, fastRepeatStepCount) : 1;
            for (int i = 0; i < stepCount; i++)
            {
                onStep.Invoke();
            }
        }
    }
}
