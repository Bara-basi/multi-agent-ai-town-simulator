using System;
using System.Collections;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

public interface IAutoNavigator
{
    void AddCommand(float cost_time, string cmd, List<Vector2> target, Action onArrived);
}

public interface IAutoHUDAnimation
{
    void AddAnimation(string type, float duration, int value);
}

[Serializable]
public class LocationPair
{
    public string key;
    public List<Vector2> value;
}

[Serializable]
public class LocationPath
{
    public string from;
    public List<string> to;
}

public class WsAgentClient : MonoBehaviour
{
    [Header("ws")]
    public string serverUrl = "ws://127.0.0.1:9876";
    public string agentId = "Agent-1";

    [Header("位置字典（名称->坐标）")]
    public List<LocationPair> locationsSerialized = new();
    public List<LocationPath> locationPaths = new();

    private Dictionary<string, List<string>> locationGraph = new();
    private Dictionary<string, List<Vector2>> locations;

    private readonly ConcurrentQueue<Action> mainThreadQueue = new();

    [Header("Reconnect")]
    public float reconnectDelaySeconds = 2f;

    public MonoBehaviour navigatorBehaviour;
    private IAutoNavigator navigator;

    public PlayerHUD playerHUD;
    [Header("Animation Throttle")]
    public float animationDelaySeconds = 0.5f;

    private readonly List<string> inner_home_place = new() { "床", "冰箱", "储物柜", "锅", "茶桌" };
    private readonly List<string> inner_market_place = new() { "集市冰箱", "货架" };
    private readonly ConcurrentQueue<AnimationRequest> animationQueue = new();
    private Coroutine animationPumpCoroutine;
    private float lastAnimationPlayTime = float.NegativeInfinity;

    private static readonly object SharedStateLock = new();
    private static readonly SemaphoreSlim sharedConnectLock = new(1, 1);
    private static readonly SemaphoreSlim sharedSendLock = new(1, 1);
    private static readonly Dictionary<string, WsAgentClient> routersByAgentId = new();

    private static ClientWebSocket sharedWs;
    private static CancellationTokenSource sharedCts;
    private static bool sharedReceiveLoopRunning;
    private static string sharedServerUrl;
    private static WsAgentClient reconnectHost;
    private static Coroutine sharedReconnectCoroutine;

    struct AnimationRequest
    {
        public string target;
        public int delta;
    }

    void Awake()
    {
        locationGraph = new Dictionary<string, List<string>>();
        locations = new Dictionary<string, List<Vector2>>();

        if (locationsSerialized != null)
        {
            foreach (var pair in locationsSerialized)
            {
                if (pair == null || string.IsNullOrEmpty(pair.key) || pair.value == null) continue;
                locations[pair.key] = new List<Vector2>(pair.value);
            }
        }

        if (locationPaths != null)
        {
            foreach (var p in locationPaths)
            {
                if (p == null || string.IsNullOrEmpty(p.from) || p.to == null) continue;
                locationGraph[p.from] = new List<string>(p.to);
            }
        }

        ResolveNavigator();

        RegisterSelf();
    }

    async void Start()
    {
        await EnsureConnectedAndBindSelf();
    }

    void RegisterSelf()
    {
        if (string.IsNullOrWhiteSpace(agentId))
        {
            Debug.LogWarning("WsAgentClient agentId 为空，无法注册路由。");
            return;
        }

        lock (SharedStateLock)
        {
            routersByAgentId[agentId] = this;
        }
    }

    void UnregisterSelf()
    {
        if (string.IsNullOrWhiteSpace(agentId)) return;

        lock (SharedStateLock)
        {
            if (routersByAgentId.TryGetValue(agentId, out var current) && current == this)
                routersByAgentId.Remove(agentId);
        }
    }

    void ResolveNavigator()
    {
        navigator = ResolveNavigatorFromBehaviour(navigatorBehaviour);
        if (navigator != null)
        {
            return;
        }

        navigator = ResolveNavigatorFromBehaviours(GetComponents<MonoBehaviour>());
        if (navigator == null)
        {
            navigator = ResolveNavigatorFromBehaviours(GetComponentsInChildren<MonoBehaviour>(true));
        }
        if (navigator == null)
        {
            navigator = ResolveNavigatorFromBehaviours(GetComponentsInParent<MonoBehaviour>(true));
        }

        if (navigator is MonoBehaviour navBehaviour)
        {
            navigatorBehaviour = navBehaviour;
        }
    }

    static IAutoNavigator ResolveNavigatorFromBehaviour(MonoBehaviour behaviour)
    {
        return behaviour as IAutoNavigator;
    }

    static IAutoNavigator ResolveNavigatorFromBehaviours(MonoBehaviour[] behaviours)
    {
        if (behaviours == null)
        {
            return null;
        }

        for (int i = 0; i < behaviours.Length; i++)
        {
            var b = behaviours[i];
            if (b is IAutoNavigator nav)
            {
                return nav;
            }
        }

        return null;
    }

    async Task EnsureConnectedAndBindSelf()
    {
        await EnsureSharedConnected(this);
        await SendHelloForSelf();
    }

    async Task SendHelloForSelf()
    {
        await SendJsonShared(new OutMsgHello
        {
            type = "hello",
            agent_id = agentId,
            cap = new[] { "waiting" }
        });
    }

    static bool IsSharedSocketOpen_NoLock()
    {
        return sharedWs != null
            && sharedCts != null
            && !sharedCts.IsCancellationRequested
            && sharedWs.State == WebSocketState.Open;
    }

    static async Task EnsureSharedConnected(WsAgentClient requester)
    {
        await sharedConnectLock.WaitAsync();
        try
        {
            lock (SharedStateLock)
            {
                if (IsSharedSocketOpen_NoLock()) return;
            }

            ClientWebSocket oldWs = null;
            CancellationTokenSource oldCts = null;

            lock (SharedStateLock)
            {
                oldWs = sharedWs;
                oldCts = sharedCts;

                sharedServerUrl = requester.serverUrl;
                sharedCts = new CancellationTokenSource();
                sharedWs = new ClientWebSocket();
                reconnectHost = requester;
            }

            try { oldCts?.Cancel(); } catch { }
            try { oldWs?.Dispose(); } catch { }

            try
            {
                await sharedWs.ConnectAsync(new Uri(sharedServerUrl), sharedCts.Token);

                lock (SharedStateLock)
                {
                    if (!sharedReceiveLoopRunning)
                    {
                        sharedReceiveLoopRunning = true;
                        _ = Task.Run(SharedReceiveLoop);
                    }
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning("WS connect failed (backend offline?): " + e.Message);
                ScheduleSharedReconnect();
            }
        }
        finally
        {
            sharedConnectLock.Release();
        }
    }

    static async Task SharedReceiveLoop()
    {
        var buffer = new byte[8192];

        while (true)
        {
            ClientWebSocket wsSnapshot;
            CancellationTokenSource ctsSnapshot;

            lock (SharedStateLock)
            {
                wsSnapshot = sharedWs;
                ctsSnapshot = sharedCts;
            }

            if (wsSnapshot == null || ctsSnapshot == null || ctsSnapshot.IsCancellationRequested || wsSnapshot.State != WebSocketState.Open)
            {
                break;
            }

            try
            {
                var sb = new StringBuilder();
                WebSocketReceiveResult result;

                do
                {
                    result = await wsSnapshot.ReceiveAsync(new ArraySegment<byte>(buffer), ctsSnapshot.Token);

                    if (result.MessageType == WebSocketMessageType.Close)
                    {
                        try
                        {
                            await wsSnapshot.CloseAsync(WebSocketCloseStatus.NormalClosure, "bye", ctsSnapshot.Token);
                        }
                        catch { }
                        ScheduleSharedReconnect();
                        lock (SharedStateLock)
                        {
                            sharedReceiveLoopRunning = false;
                        }
                        return;
                    }

                    sb.Append(Encoding.UTF8.GetString(buffer, 0, result.Count));
                }
                while (!result.EndOfMessage);

                DispatchIncoming(sb.ToString());
            }
            catch (OperationCanceledException)
            {
                lock (SharedStateLock)
                {
                    sharedReceiveLoopRunning = false;
                }
                return;
            }
            catch (Exception e)
            {
                Debug.LogWarning("WS ReceiveLoop error: " + e.Message);
                ScheduleSharedReconnect();
                lock (SharedStateLock)
                {
                    sharedReceiveLoopRunning = false;
                }
                return;
            }
        }

        lock (SharedStateLock)
        {
            sharedReceiveLoopRunning = false;
        }
    }

    static void DispatchIncoming(string json)
    {
        if (!TryParseIncoming(json, out var msg))
        {
            return;
        }

        if (TryHandleSharedMessage(msg)) return;
        if (TryHandleBroadcastMessage(msg)) return;

        if (!TryGetRouter(msg.agent_id, out var router))
        {
            SendRouterNotFound(msg);
            return;
        }

        router.HandleRoutedMessage(msg);
    }

    static bool TryParseIncoming(string json, out WSMsg msg)
    {
        msg = null;

        try
        {
            msg = JsonUtility.FromJson<WSMsg>(WSMsg.Fix(json));
        }
        catch (Exception e)
        {
            Debug.LogWarning("Json parse failed: " + e.Message + "\nraw: " + json);
            return false;
        }

        if (msg != null && !string.IsNullOrEmpty(msg.type))
        {
            return true;
        }

        Debug.LogWarning("WS message empty or missing type");
        return false;
    }

    static bool TryHandleSharedMessage(WSMsg msg)
    {
        switch (msg.type)
        {
            case "hello_ack":
                return true;
            case "ping":
                _ = SendJsonShared(new OutMsg { type = "pong" });
                return true;
            default:
                return false;
        }
    }

    static bool TryHandleBroadcastMessage(WSMsg msg)
    {
        if (msg.type != "information" || msg.target != "market" || !string.IsNullOrWhiteSpace(msg.agent_id))
        {
            return false;
        }

        foreach (var router in SnapshotRouters())
        {
            if (router == null) continue;
            router.mainThreadQueue.Enqueue(() =>
            {
                ShopAssistantDisplayUI.PushMarketInformationJson(msg.info);
            });
        }

        return true;
    }

    static WsAgentClient[] SnapshotRouters()
    {
        lock (SharedStateLock)
        {
            var routers = new WsAgentClient[routersByAgentId.Count];
            routersByAgentId.Values.CopyTo(routers, 0);
            return routers;
        }
    }

    static bool TryGetRouter(string routedAgentId, out WsAgentClient router)
    {
        router = null;
        if (string.IsNullOrEmpty(routedAgentId))
        {
            return false;
        }

        lock (SharedStateLock)
        {
            return routersByAgentId.TryGetValue(routedAgentId, out router);
        }
    }

    static void SendRouterNotFound(WSMsg msg)
    {
        Debug.LogWarning("No WsAgentClient router for agent_id=" + msg.agent_id);
        _ = SendJsonShared(new OutMsg
        {
            type = "complete",
            cmd = msg.cmd,
            agent_id = msg.agent_id,
            action_id = msg.action_id,
            status = "error",
            error = "agent router not found"
        });
    }

    void HandleRoutedMessage(WSMsg msg)
    {
        if (msg.type == "information" && msg.target == "market")
        {
            mainThreadQueue.Enqueue(() =>
            {
                ShopAssistantDisplayUI.PushMarketInformationJson(msg.info);
            });
            return;
        }

        if (msg.type == "command" && (msg.cmd == "round_start" || msg.cmd == "round_end"))
        {
            _ = SendJsonShared(new OutMsg
            {
                type = "ack",
                cmd = msg.cmd,
                agent_id = msg.agent_id,
                action_id = msg.action_id
            });

            mainThreadQueue.Enqueue(() =>
            {
                var ui = FindObjectOfType<ShopAssistantDisplayUI>();
                if (ui == null)
                {
                    _ = SendJsonShared(new OutMsg
                    {
                        type = "complete",
                        cmd = msg.cmd,
                        agent_id = msg.agent_id,
                        action_id = msg.action_id,
                        status = "error",
                        error = "ShopAssistantDisplayUI not found"
                    });
                    return;
                }

                if (msg.cmd == "round_start")
                {
                    ui.ShowRoundStartTransitionThenOpenInventory(Mathf.RoundToInt(msg.value), 1f);
                }
                else
                {
                    ui.ShowRoundEndTransition(Mathf.RoundToInt(msg.value));
                }

                _ = SendJsonShared(new OutMsg
                {
                    type = "complete",
                    cmd = msg.cmd,
                    agent_id = msg.agent_id,
                    action_id = msg.action_id,
                    status = "ok"
                });
            });

            return;
        }

        if (msg.type == "command" && msg.cmd == "go_to")
        {
            if (!EnsureNavigatorForCommand(msg))
            {
                return;
            }

            _ = SendJsonShared(new OutMsg
            {
                type = "ack",
                agent_id = msg.agent_id,
                action_id = msg.action_id
            });

            mainThreadQueue.Enqueue(() =>
            {
                if (msg.target == "家")
                    msg.target = inner_home_place[UnityEngine.Random.Range(0, inner_home_place.Count)];

                if (msg.target == "集市")
                    msg.target = inner_market_place[UnityEngine.Random.Range(0, inner_market_place.Count)];

                if (!TryResolveTarget(msg, out var target))
                {
                    _ = SendJsonShared(new OutMsg
                    {
                        type = "complete",
                        cmd = msg.cmd,
                        agent_id = msg.agent_id,
                        action_id = msg.action_id,
                        status = "error",
                        error = "target not found"
                    });
                    return;
                }

                navigator?.AddCommand(msg.value, msg.cmd, target, onArrived: () =>
                {
                    _ = SendJsonShared(new OutMsg
                    {
                        type = "complete",
                        cmd = msg.cmd,
                        agent_id = msg.agent_id,
                        action_id = msg.action_id,
                        status = "ok"
                    });
                });
            });

            return;
        }

        if (msg.type == "command" && msg.cmd != "go_to")
        {
            if (!EnsureNavigatorForCommand(msg))
            {
                return;
            }

            mainThreadQueue.Enqueue(() =>
            {
                navigator?.AddCommand(msg.value, msg.cmd, new List<Vector2>(), onArrived: () =>
                {
                    _ = SendJsonShared(new OutMsg
                    {
                        type = "complete",
                        cmd = msg.cmd,
                        agent_id = msg.agent_id,
                        action_id = msg.action_id,
                        status = "ok"
                    });
                });
            });

            return;
        }

        if (msg.type == "animation")
        {
            animationQueue.Enqueue(new AnimationRequest
            {
                target = msg.target,
                delta = (int)msg.value
            });
            mainThreadQueue.Enqueue(TryStartAnimationPump);

            _ = SendJsonShared(new OutMsg
            {
                type = "complete",
                cmd = msg.cmd,
                agent_id = msg.agent_id,
                action_id = msg.action_id,
                status = "ok"
            });

            return;
        }

        _ = SendJsonShared(new OutMsg
        {
            type = "complete",
            cmd = msg.cmd,
            agent_id = msg.agent_id,
            action_id = msg.action_id,
            status = "error",
            error = "unknown command"
        });
    }

    bool EnsureNavigatorForCommand(WSMsg msg)
    {
        if (navigator != null)
        {
            return true;
        }

        ResolveNavigator();
        if (navigator != null)
        {
            return true;
        }

        string actionId = msg != null ? msg.action_id : null;
        string cmd = msg != null ? msg.cmd : null;
        string routedAgentId = msg != null ? msg.agent_id : agentId;

        Debug.LogError($"WsAgentClient cannot execute command '{cmd}' because no IAutoNavigator was found. agentId={agentId}");
        _ = SendJsonShared(new OutMsg
        {
            type = "complete",
            cmd = cmd,
            agent_id = routedAgentId,
            action_id = actionId,
            status = "error",
            error = "navigator not found"
        });
        return false;
    }

    static void ScheduleSharedReconnect()
    {
        lock (SharedStateLock)
        {
            if (sharedCts != null && sharedCts.IsCancellationRequested) return;
            if (sharedReconnectCoroutine != null) return;

            reconnectHost = PickReconnectHost_NoLock();
            if (reconnectHost == null) return;

            sharedReconnectCoroutine = reconnectHost.StartCoroutine(reconnectHost.CoSharedReconnect());
        }
    }

    static WsAgentClient PickReconnectHost_NoLock()
    {
        foreach (var kv in routersByAgentId)
        {
            var candidate = kv.Value;
            if (candidate != null && candidate.isActiveAndEnabled)
                return candidate;
        }
        return null;
    }

    IEnumerator CoSharedReconnect()
    {
        var wait = Mathf.Max(0.1f, reconnectDelaySeconds);
        yield return new WaitForSeconds(wait);

        lock (SharedStateLock)
        {
            sharedReconnectCoroutine = null;
        }

        if (this != null && isActiveAndEnabled)
            _ = ReconnectAndRebindAll();
    }

    static async Task ReconnectAndRebindAll()
    {
        WsAgentClient[] clients;
        lock (SharedStateLock)
        {
            clients = new WsAgentClient[routersByAgentId.Count];
            routersByAgentId.Values.CopyTo(clients, 0);
        }

        WsAgentClient owner = null;
        for (int i = 0; i < clients.Length; i++)
        {
            var c = clients[i];
            if (c != null && c.isActiveAndEnabled)
            {
                owner = c;
                break;
            }
        }

        if (owner == null) return;

        await EnsureSharedConnected(owner);

        var seen = new HashSet<string>();
        for (int i = 0; i < clients.Length; i++)
        {
            var c = clients[i];
            if (c == null || !c.isActiveAndEnabled || string.IsNullOrWhiteSpace(c.agentId)) continue;
            if (!seen.Add(c.agentId)) continue;
            await c.SendHelloForSelf();
        }
    }

    static async Task SendJsonShared(object obj)
    {
        ClientWebSocket wsSnapshot;
        CancellationTokenSource ctsSnapshot;

        lock (SharedStateLock)
        {
            wsSnapshot = sharedWs;
            ctsSnapshot = sharedCts;
        }

        if (wsSnapshot == null || ctsSnapshot == null || ctsSnapshot.IsCancellationRequested || wsSnapshot.State != WebSocketState.Open)
            return;

        string json;
        try
        {
            json = JsonUtility.ToJson(obj);
        }
        catch (Exception e)
        {
            Debug.LogWarning("ToJson failed: " + e.Message);
            return;
        }

        var bytes = Encoding.UTF8.GetBytes(json);

        await sharedSendLock.WaitAsync();
        try
        {
            await wsSnapshot.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, ctsSnapshot.Token);
        }
        catch (OperationCanceledException)
        {
            // ignore
        }
        catch (Exception e)
        {
            Debug.LogWarning("SendAsync failed: " + e.Message + "\njson: " + json);
            if (!(obj is OutMsg outMsg) || outMsg.type != "pong")
            {
                ScheduleSharedReconnect();
            }
        }
        finally
        {
            sharedSendLock.Release();
        }
    }

    public static void SubmitShopStockUpdateJson(string infoJson)
    {
        WsAgentClient sender = null;
        lock (SharedStateLock)
        {
            foreach (var candidate in routersByAgentId.Values)
            {
                if (candidate != null && candidate.isActiveAndEnabled)
                {
                    sender = candidate;
                    break;
                }
            }
        }

        if (sender == null)
        {
            Debug.LogWarning("Shop stock update skipped: no active WsAgentClient router.");
            return;
        }

        _ = SendJsonShared(new OutMsgShopStockUpdate
        {
            type = "shop_stock_update",
            agent_id = sender.agentId,
            info = string.IsNullOrEmpty(infoJson) ? "{}" : infoJson
        });
    }

    void TryStartAnimationPump()
    {
        if (animationPumpCoroutine == null)
            animationPumpCoroutine = StartCoroutine(CoPlayAnimationsWithDelay());
    }

    IEnumerator CoPlayAnimationsWithDelay()
    {
        while (true)
        {
            if (!animationQueue.TryDequeue(out var request))
                break;

            if (animationDelaySeconds > 0f && !float.IsNegativeInfinity(lastAnimationPlayTime))
            {
                float elapsed = Time.time - lastAnimationPlayTime;
                float wait = animationDelaySeconds - elapsed;
                if (wait > 0f)
                    yield return new WaitForSeconds(wait);
            }

            if (playerHUD != null)
                playerHUD.PopStatus(request.target, request.delta);
            lastAnimationPlayTime = Time.time;

            yield return null;
        }

        animationPumpCoroutine = null;
    }

    void Update()
    {
        int processed = 0;
        const int MAX_PER_FRAME = 16;

        while (processed < MAX_PER_FRAME && mainThreadQueue.TryDequeue(out var action))
        {
            try { action?.Invoke(); }
            catch (Exception e) { Debug.LogWarning("Main thread action error: " + e.Message); }
            processed++;
        }
    }

    bool TryResolveTarget(WSMsg msg, out List<Vector2> target)
    {
        target = null;

        if (msg == null) return false;

        var start = msg.cur_location;
        var goal = msg.target;

        var path = FindPath(start, goal, locationGraph);
        if (path == null || path.Count == 0) return false;

        var result = new List<Vector2>();

        foreach (var name in path)
        {
            if (!locations.TryGetValue(name, out var list) || list == null || list.Count == 0)
                return false;

            if (list[0].x == -1 && list[0].y == -1)
                continue;

            if (list.Count == 1) result.Add(list[0]);
            else result.Add(list[UnityEngine.Random.Range(0, list.Count)]);
        }

        if (result.Count == 0) return false;

        target = result;
        return true;
    }

    void OnDestroy()
    {
        if (animationPumpCoroutine != null)
        {
            StopCoroutine(animationPumpCoroutine);
            animationPumpCoroutine = null;
        }

        UnregisterSelf();
        ShutdownSharedConnectionIfNoRouters();
    }

    static void ShutdownSharedConnectionIfNoRouters()
    {
        ClientWebSocket wsToClose = null;
        CancellationTokenSource ctsToCancel = null;

        lock (SharedStateLock)
        {
            if (routersByAgentId.Count > 0) return;

            if (sharedReconnectCoroutine != null && reconnectHost != null)
            {
                reconnectHost.StopCoroutine(sharedReconnectCoroutine);
                sharedReconnectCoroutine = null;
            }

            wsToClose = sharedWs;
            ctsToCancel = sharedCts;

            sharedWs = null;
            sharedCts = null;
            sharedReceiveLoopRunning = false;
            reconnectHost = null;
        }

        try { ctsToCancel?.Cancel(); } catch { }
        try
        {
            if (wsToClose != null)
            {
                if (wsToClose.State == WebSocketState.Open)
                {
                    try
                    {
                        wsToClose.CloseAsync(WebSocketCloseStatus.NormalClosure, "destroy", CancellationToken.None).Wait(100);
                    }
                    catch { }
                }
                wsToClose.Dispose();
            }
        }
        catch { }
    }

    [Serializable]
    public class WSMsg
    {
        public string type;
        public string cur_location;
        public string agent_id;
        public string action_id;
        public string cmd;
        public string target;
        public string info;
        public float value;

        public static string Fix(string s)
        {
            return s;
        }
    }

    [Serializable]
    class OutMsg
    {
        public string type;
        public string cmd;
        public string agent_id;
        public string action_id;
        public string status;
        public string error;
    }

    [Serializable]
    class OutMsgHello
    {
        public string type;
        public string agent_id;
        public string[] cap;
    }

    [Serializable]
    class OutMsgShopStockUpdate
    {
        public string type;
        public string agent_id;
        public string info;
    }

    List<string> FindPath(string start, string goal, Dictionary<string, List<string>> graph)
    {
        if (string.IsNullOrEmpty(start) || string.IsNullOrEmpty(goal) || graph == null)
            return null;

        if (start == goal) return new List<string> { start };

        var q = new Queue<string>();
        var prev = new Dictionary<string, string>();
        var vis = new HashSet<string>();

        q.Enqueue(start);
        vis.Add(start);

        while (q.Count > 0)
        {
            var u = q.Dequeue();

            if (!graph.TryGetValue(u, out var nbrs) || nbrs == null) continue;

            foreach (var v in nbrs)
            {
                if (!vis.Add(v)) continue;

                prev[v] = u;

                if (v == goal)
                {
                    var path = new List<string> { goal };
                    while (prev.ContainsKey(path[path.Count - 1]))
                        path.Add(prev[path[path.Count - 1]]);
                    path.Reverse();
                    return path;
                }

                q.Enqueue(v);
            }
        }

        return null;
    }
}


