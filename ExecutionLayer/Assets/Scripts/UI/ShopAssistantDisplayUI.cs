using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.TextCore.LowLevel;
using UnityEngine.UI;

/// <summary>
/// Runtime UI for ShopAssistant inventory. It accepts market information from backend
/// and renders products dynamically.
/// </summary>
public sealed class ShopAssistantDisplayUI : MonoBehaviour
{
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
    [SerializeField] [Range(0.75f, 0.95f)] private float plusButtonAnchorX = 0.90f;

    [Header("Mock Data")]
    [SerializeField] private int initialRound = 1;
    [SerializeField] private int initialMoney = 1000;
    [SerializeField] private string initialGameState = "回合进行中";

    [Header("Product Images")]
    [SerializeField] private List<ProductImageMapping> productImageMappings = new();
    [SerializeField] private string productImageMappingCsvResourcePath = "ShopAssistant/ProductImageMappings";

    private TMP_FontAsset uiFont;
    private TMP_FontAsset runtimeDynamicChineseFont;
    private GameObject inventoryOverlayRoot;
    private Button openInventoryButton;
    private TextMeshProUGUI roundText;
    private TextMeshProUGUI moneyText;
    private TextMeshProUGUI stateText;
    private RectTransform inventoryContentRoot;
    private readonly Dictionary<string, Sprite> productImageLookup = new();
    private readonly List<ProductMockData> marketProducts = new();
    private static string pendingMarketInformationJson;

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
        var panel = CreatePanel("TopLeft_StatusPanel", parent, paperColor, woodColor, new Vector2(430f, 205f), new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(30f, -28f));
        panel.pivot = new Vector2(0f, 1f);
        AddFrameBorder(panel, frameBorderInset, new Color(0.55f, 0.39f, 0.12f, 1f), frameBorderThickness);

        var layout = panel.gameObject.AddComponent<VerticalLayoutGroup>();
        layout.padding = new RectOffset(14, 14, 14, 14);
        layout.spacing = 5f;
        layout.childControlWidth = true;
        layout.childControlHeight = true;
        layout.childForceExpandWidth = true;
        layout.childForceExpandHeight = false;

        var rowRound = CreateStatusRow("RowRound", panel, 80f);
        var rowMoney = CreateStatusRow("RowMoney", panel, 42f);
        var rowState = CreateStatusRow("RowState", panel, 42f);

        roundText = CreateTMPText("Round", rowRound, "第 1 回合", 50, FontStyles.Bold, TextAlignmentOptions.Left);
        moneyText = CreateTMPText("Money", rowMoney, "当前金钱: 1000", 28, FontStyles.Normal, TextAlignmentOptions.Left);
        stateText = CreateTMPText("State", rowState, "游戏状态: 回合进行中", 28, FontStyles.Normal, TextAlignmentOptions.Left);

        StretchText(roundText);
        StretchText(moneyText);
        StretchText(stateText);
    }

    private void BuildOpenInventoryButton(Transform parent)
    {
        var buttonRoot = CreateButtonLikePanel(
            "Btn_OpenInventory",
            parent,
            new Vector2(220f, 72f),
            new Vector2(1f, 0f),
            new Vector2(1f, 0f),
            new Vector2(-36f, 30f),
            "查看库存",
            34f
        );

        ((RectTransform)buttonRoot.transform).pivot = new Vector2(1f, 0f);

        openInventoryButton = buttonRoot.GetComponent<Button>();
        openInventoryButton.onClick.AddListener(() => SetInventoryVisible(true));
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

        var window = CreatePanel("InventoryWindow", inventoryOverlayRoot.transform, paperColor, woodColor, new Vector2(1520f, 860f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), Vector2.zero);
        AddFrameBorder(window, frameBorderInset + 1f, new Color(0.55f, 0.39f, 0.12f, 1f), frameBorderThickness + 1f);

        var title = CreateTMPText("Title", window, "商店库存", 54, FontStyles.Bold, TextAlignmentOptions.Center);
        var titleRt = (RectTransform)title.transform;
        titleRt.anchorMin = new Vector2(0f, 1f);
        titleRt.anchorMax = new Vector2(1f, 1f);
        titleRt.offsetMin = new Vector2(20f, -90f);
        titleRt.offsetMax = new Vector2(-20f, -20f);

        var closeButton = CreateButtonLikePanel(
            "Btn_CloseInventory",
            window,
            new Vector2(72f, 72f),
            new Vector2(1f, 1f),
            new Vector2(1f, 1f),
            new Vector2(-20f, -20f),
            "X",
            38f
        );
        closeButton.GetComponent<Button>().onClick.AddListener(() => SetInventoryVisible(false));

        var scrollRoot = new GameObject("GoodsScroll", typeof(RectTransform), typeof(Image), typeof(Mask), typeof(ScrollRect));
        scrollRoot.transform.SetParent(window, false);
        var scrollRt = (RectTransform)scrollRoot.transform;
        scrollRt.anchorMin = new Vector2(0.03f, 0.16f);
        scrollRt.anchorMax = new Vector2(0.97f, 0.86f);
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
        grid.cellSize = new Vector2(210f, 266f);
        grid.spacing = new Vector2(14f, 14f);
        grid.padding = new RectOffset(14, 14, 14, 14);
        grid.startAxis = GridLayoutGroup.Axis.Horizontal;
        grid.startCorner = GridLayoutGroup.Corner.UpperLeft;
        grid.childAlignment = TextAnchor.UpperLeft;
        grid.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
        grid.constraintCount = 5;

        var autoColumns = content.AddComponent<InventoryGridAutoColumns>();
        autoColumns.Bind(grid, viewportRt, 4, 7);

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

        var stockButton = CreateButtonLikePanel(
            "Btn_StockIn",
            window,
            new Vector2(360f, 82f),
            new Vector2(0.5f, 0f),
            new Vector2(0.5f, 0f),
            new Vector2(0f, 28f),
            "进货！",
            42f
        );
        stockButton.GetComponent<Button>().onClick.AddListener(() =>
        {
            // Placeholder only: no data sync or gameplay effect.
            Debug.Log("[ShopAssistantUI] 进货按钮点击（占位逻辑）");
        });

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

        foreach (var product in marketProducts)
        {
            CreateProductCell(inventoryContentRoot, product);
        }
    }

    private List<ProductMockData> ParseMarketInformation(string infoJson)
    {
        try
        {
            var payload = JsonUtility.FromJson<MarketInformationPayload>(infoJson);
            if (payload == null || payload.items == null || payload.items.Length == 0)
            {
                return new List<ProductMockData>();
            }

            var result = new List<ProductMockData>(payload.items.Length);
            foreach (var item in payload.items)
            {
                if (item == null || string.IsNullOrWhiteSpace(item.name))
                {
                    continue;
                }

                result.Add(new ProductMockData(
                    item.name.Trim(),
                    RoundToInt(item.purchasePrice),
                    RoundToInt(item.quantity),
                    RoundToInt(item.basePrice)));
            }

            return result;
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[ShopAssistantUI] Failed to parse market info json: {e.Message}");
            return new List<ProductMockData>();
        }
    }

    private static int RoundToInt(float value)
    {
        return Mathf.Max(0, Mathf.RoundToInt(value));
    }

    private void CreateProductCell(Transform content, ProductMockData data)
    {
        var cell = CreatePanel(
            $"Cell_{data.productName}",
            content,
            new Color(1f, 1f, 1f, 0.45f),
            woodColor,
            new Vector2(210f, 248f),
            new Vector2(0.5f, 0.5f),
            new Vector2(0.5f, 0.5f),
            Vector2.zero
        );
        cell.GetComponent<Outline>().effectDistance = new Vector2(2f, -2f);
        AddFrameBorder(cell, Mathf.Max(1f, frameBorderInset - 3f), new Color(0.55f, 0.39f, 0.12f, 0.95f), Mathf.Max(2f, frameBorderThickness - 1f));

        var iconBg = new GameObject("IconBG", typeof(RectTransform), typeof(Image));
        iconBg.transform.SetParent(cell, false);
        var iconRt = (RectTransform)iconBg.transform;
        iconRt.anchorMin = new Vector2(0.08f, 1f);
        iconRt.anchorMax = new Vector2(0.92f, 1f);
        iconRt.pivot = new Vector2(0.5f, 1f);
        iconRt.sizeDelta = new Vector2(0f, 76f);
        iconRt.anchoredPosition = new Vector2(0f, -14f);
        iconBg.GetComponent<Image>().color = new Color(0.93f, 0.92f, 0.85f, 0.95f);

        var iconImageObj = new GameObject("IconImage", typeof(RectTransform), typeof(Image));
        iconImageObj.transform.SetParent(iconBg.transform, false);
        var iconImageRt = (RectTransform)iconImageObj.transform;
        iconImageRt.anchorMin = new Vector2(0f, 0f);
        iconImageRt.anchorMax = new Vector2(1f, 1f);
        iconImageRt.offsetMin = new Vector2(4f, 4f);
        iconImageRt.offsetMax = new Vector2(-4f, -4f);
        var iconImage = iconImageObj.GetComponent<Image>();
        iconImage.preserveAspect = true;

        var sprite = TryResolveProductSprite(data.productName);
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

        var nameText = CreateTMPText("Name", cell, data.productName, 26, FontStyles.Bold, TextAlignmentOptions.Center);
        var nameRt = (RectTransform)nameText.transform;
        nameRt.anchorMin = new Vector2(0.05f, 1f);
        nameRt.anchorMax = new Vector2(0.95f, 1f);
        nameRt.pivot = new Vector2(0.5f, 1f);
        nameRt.sizeDelta = new Vector2(0f, 30f);
        nameRt.anchoredPosition = new Vector2(0f, -96f);

        var buyPrice = CreateTMPText("BuyPrice", cell, $"进货价: {data.buyPrice}", 22, FontStyles.Normal, TextAlignmentOptions.Left);
        var buyRt = (RectTransform)buyPrice.transform;
        buyRt.anchorMin = new Vector2(0.08f, 1f);
        buyRt.anchorMax = new Vector2(0.92f, 1f);
        buyRt.pivot = new Vector2(0.5f, 1f);
        buyRt.sizeDelta = new Vector2(0f, 26f);
        buyRt.anchoredPosition = new Vector2(0f, -128f);

        CreateStepperRow(cell, "进货\n数量", 0, -158f, data.buyCount);
        CreateStepperRow(cell, "出售\n价格", 1, -204f, data.sellPrice);
    }

    private void CreateStepperRow(RectTransform parent, string label, int rowId, float topOffset, int initialValue)
    {
        var row = new GameObject($"StepperRow_{rowId}", typeof(RectTransform));
        row.transform.SetParent(parent, false);
        var rowRt = (RectTransform)row.transform;
        rowRt.anchorMin = new Vector2(0.06f, 1f);
        rowRt.anchorMax = new Vector2(0.94f, 1f);
        rowRt.pivot = new Vector2(0.5f, 1f);
        rowRt.sizeDelta = new Vector2(0f, 38f);
        rowRt.anchoredPosition = new Vector2(0f, topOffset);

        var lbl = CreateTMPText("Label", row.transform, $"{label}:", 20, FontStyles.Normal, TextAlignmentOptions.Left);
        var lblRt = (RectTransform)lbl.transform;
        lblRt.anchorMin = new Vector2(0f, 0f);
        lblRt.anchorMax = new Vector2(0.42f, 1f);
        lblRt.offsetMin = Vector2.zero;
        lblRt.offsetMax = Vector2.zero;

        var minus = CreateMiniButton(row.transform, "-", new Vector2(0.45f, 0.5f));
        var plus = CreateMiniButton(row.transform, "+", new Vector2(plusButtonAnchorX, 0.5f));

        var valueText = CreateTMPText("Value", row.transform, initialValue.ToString(), 22, FontStyles.Bold, TextAlignmentOptions.Center);
        var valueRt = (RectTransform)valueText.transform;
        valueRt.anchorMin = new Vector2(0.58f, 0f);
        valueRt.anchorMax = new Vector2(0.86f, 1f);
        valueRt.offsetMin = Vector2.zero;
        valueRt.offsetMax = Vector2.zero;

        var stepper = row.AddComponent<ShopUiStepper>();
        stepper.Bind(minus, plus, valueText, initialValue);
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
        img.color = woodEdgeFade;

        var text = CreateTMPText("Sign", btn.transform, sign, 24, FontStyles.Bold, TextAlignmentOptions.Center);
        StretchText(text, 0f);

        var button = btn.GetComponent<Button>();
        button.targetGraphic = img;
        return button;
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

    private List<ProductMockData> BuildMockProducts()
    {
        return new List<ProductMockData>
        {
            new("瓶装水", 4, 40, 5),
            new("面包", 5, 60, 7),
            new("烤肉", 13, 30, 15),
            new("银戒指", 150, 10, 200),
            new("黄金", 950, 10, 1000),
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

    private void RefreshTopLeftStatus(int round, int money, string state)
    {
        if (roundText != null) roundText.text = $"第 {round} 回合";
        if (moneyText != null) moneyText.text = $"当前金钱: {money}";
        if (stateText != null) stateText.text = $"游戏状态: {state}";
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

    [Serializable]
    private struct ProductMockData
    {
        public string productName;
        public int buyPrice;
        public int buyCount;
        public int sellPrice;

        public ProductMockData(string productName, int buyPrice, int buyCount, int sellPrice)
        {
            this.productName = productName;
            this.buyPrice = buyPrice;
            this.buyCount = buyCount;
            this.sellPrice = sellPrice;
        }
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
    private TextMeshProUGUI valueText;
    private int value;

    public void Bind(Button minus, Button plus, TextMeshProUGUI valueLabel, int initialValue)
    {
        minusButton = minus;
        plusButton = plus;
        valueText = valueLabel;
        value = Mathf.Max(0, initialValue);
        UpdateLabel();

        if (minusButton != null)
        {
            minusButton.onClick.AddListener(Decrease);
        }

        if (plusButton != null)
        {
            plusButton.onClick.AddListener(Increase);
        }
    }

    private void OnDestroy()
    {
        if (minusButton != null)
        {
            minusButton.onClick.RemoveListener(Decrease);
        }

        if (plusButton != null)
        {
            plusButton.onClick.RemoveListener(Increase);
        }
    }

    private void Decrease()
    {
        value = Mathf.Max(0, value - 1);
        UpdateLabel();
    }

    private void Increase()
    {
        value += 1;
        UpdateLabel();
    }

    private void UpdateLabel()
    {
        if (valueText != null)
        {
            valueText.text = value.ToString();
        }
    }
}


