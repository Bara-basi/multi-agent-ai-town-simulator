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
    public string agentId = "agent-1";

    [Header("位置字典（名称->坐标）")]
    public List<LocationPair> locationsSerialized = new();
    public List<LocationPath> locationPaths = new();

    private Dictionary<string, List<string>> locationGraph = new();
    private Dictionary<string, List<Vector2>> locations;

    private ClientWebSocket ws;
    private CancellationTokenSource cts;

    private readonly ConcurrentQueue<Action> mainThreadQueue = new();

    // 防止并发 SendAsync
    private readonly SemaphoreSlim sendLock = new(1, 1);
    private Coroutine reconnectCoroutine;
    [Header("Reconnect")]
    public float reconnectDelaySeconds = 2f;

    public MonoBehaviour navigatorBehaviour;
    private IAutoNavigator navigator;

    public PlayerHUD playerHUD;
    [Header("Animation Throttle")]
    public float animationDelaySeconds = 0.5f;

    private readonly List<string> inner_home_place = new() { "床","冰箱","储物柜","锅","茶桌"};
    private readonly List<string> inner_market_place = new() { "集市冰箱", "货架" };
    private readonly ConcurrentQueue<AnimationRequest> animationQueue = new();
    private Coroutine animationPumpCoroutine;
    private float lastAnimationPlayTime = float.NegativeInfinity;

    struct AnimationRequest
    {
        public string target;
        public int delta;
    }

    void Awake()
    {
        locationGraph = new Dictionary<string, List<string>>();
        locations = new Dictionary<string, List<Vector2>>();

        // 构建位置字典
        if (locationsSerialized != null)
        {
            foreach (var pair in locationsSerialized)
            {
                if (pair == null || string.IsNullOrEmpty(pair.key) || pair.value == null) continue;
                locations[pair.key] = new List<Vector2>(pair.value);
            }
        }

        // 构建邻接表
        if (locationPaths != null)
        {
            foreach (var p in locationPaths)
            {
                if (p == null || string.IsNullOrEmpty(p.from) || p.to == null) continue;
                locationGraph[p.from] = new List<string>(p.to);
            }
        }

        navigator = navigatorBehaviour as IAutoNavigator;
        if (navigator == null)
            Debug.LogError("navigatorBehaviour 未实现 IAutoNavigator 接口！");
    }

    async void Start()
    {
        // string json1 = "{\"type\":\"command\",\"cur_location\":\"家\",\"agent_id\" : \"" + agentId + "\",\"cmd\":\"go_to\",\"target\":\"收银台\",\"value\":\"0\"}"; 
        // string json2 = "{\"type\":\"command\",\"value\":\"0.5\",\"agent_id\" : \"" + agentId + "\",\"cmd\":\"pick_up\"}"; 
        // string animation_json1 = "{\"type\":\"animation\",\"target\":\"item\",\"agent_id\" : \"" + agentId + "\",\"value\":\"5\"}"; 
        await ConnectAndRun();
    }

    async Task ConnectAndRun()
    {
        // 防止重复连接造成资源泄漏
        try { cts?.Cancel(); } catch { }
        try { ws?.Dispose(); } catch { }

        cts = new CancellationTokenSource();
        ws = new ClientWebSocket();

        try
        {
           
            await ws.ConnectAsync(new Uri(serverUrl), cts.Token);

            // hello
            await SendJson(new OutMsgHello
            {
                type = "hello",
                agent_id = agentId,
                cap = new[] { "waiting" }
            });

            // 启动接收循环（后台线程）
            _ = Task.Run(ReceiveLoop);
        }
        catch (Exception e)
        {
            Debug.LogWarning("WS connect failed (backend offline?): " + e.Message);
            ScheduleReconnect();
        }
    }

    void Retry() => _ = ConnectAndRun();

    void ScheduleReconnect()
    {
        if (cts != null && cts.IsCancellationRequested) return;
        if (reconnectCoroutine != null) return;
        reconnectCoroutine = StartCoroutine(CoReconnect());
    }

    IEnumerator CoReconnect()
    {
        var wait = Mathf.Max(0.1f, reconnectDelaySeconds);
        yield return new WaitForSeconds(wait);
        reconnectCoroutine = null;
        if (this != null && isActiveAndEnabled)
            Retry();
    }

    async Task ReceiveLoop()
    {
        var buffer = new byte[8192];

        while (ws != null && ws.State == WebSocketState.Open && cts != null && !cts.IsCancellationRequested)
        {
            try
            {
                var sb = new StringBuilder();
                WebSocketReceiveResult result;

                do
                {
                    result = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), cts.Token);

                    if (result.MessageType == WebSocketMessageType.Close)
                    {
                        try
                        {
                            await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "bye", cts.Token);
                        }
                        catch { }
                        ScheduleReconnect();
                        return;
                    }

                    sb.Append(Encoding.UTF8.GetString(buffer, 0, result.Count));
                }
                while (!result.EndOfMessage);

                var json = sb.ToString();

                // HandleMessage 现在是同步方法：不 await，避免 CS1998 & 签名连锁爆炸
                HandleMessage(json);
            }
            catch (OperationCanceledException)
            {
                // 正常取消
                return;
            }
            catch (Exception e)
            {
                Debug.LogWarning("WS ReceiveLoop error: " + e.Message);
                ScheduleReconnect();
                return;
            }
        }

        ScheduleReconnect();
    }

    void HandleMessage(string json)
    {
        WSMsg msg = null;

        try
        {
            msg = JsonUtility.FromJson<WSMsg>(WSMsg.Fix(json));

        }
        catch (Exception e)
        {
            Debug.LogWarning("Json parse failed: " + e.Message + "\nraw: " + json);
            _ = SendJson(new OutMsg
            {
                type = "complete",
                cmd = null,
                agent_id = agentId,
                action_id = null,
                status = "error",
                error = "json parse failed"
            });
            return;
        }

        if (msg == null || string.IsNullOrEmpty(msg.type))
        {
            _ = SendJson(new OutMsg
            {
                type = "complete",
                cmd = null,
                agent_id = agentId,
                action_id = null,
                status = "error",
                error = "empty msg"
            });
            return;
        }

        if (msg.type == "hello_ack")
        {
            // no-op
            return;
        }

        if (msg.type == "ping")
        {
            _ = SendJson(new OutMsg { type = "pong" });
            return;
        }

        if (msg.type == "command" && msg.cmd == "go_to")
        {
   
            // ACK
            _ = SendJson(new OutMsg
            {
                type = "ack",
                agent_id = agentId,
                action_id = msg.action_id
            });

            // 主线程队列执行
            mainThreadQueue.Enqueue(() =>
            {
                if (msg.target == "家")
                    msg.target = inner_home_place[UnityEngine.Random.Range(0, inner_home_place.Count)];

                if (msg.target == "集市")
                    msg.target = inner_market_place[UnityEngine.Random.Range(0, inner_market_place.Count)];
                if (!TryResolveTarget(msg, out var target))
                {
                    _ = SendJson(new OutMsg
                    {
                        type = "complete",
                        cmd = msg.cmd,
                        agent_id = agentId,
                        action_id = msg.action_id,
                        status = "error",
                        error = "target not found"
                    });
                    return;
                }

                navigator?.AddCommand(msg.value, msg.cmd, target, onArrived: () =>
                {
                    _ = SendJson(new OutMsg
                    {
                        type = "complete",
                        cmd = msg.cmd,
                        agent_id = agentId,
                        action_id = msg.action_id,
                        status = "ok"
                    });
                });
            });

            return;
        }

        if (msg.type == "command" && msg.cmd != "go_to")
        {
            mainThreadQueue.Enqueue(() =>
            {
                navigator?.AddCommand(msg.value, msg.cmd, new List<Vector2>(), onArrived: () =>
                {
                    _ = SendJson(new OutMsg
                    {
                        type = "complete",
                        cmd = msg.cmd,
                        agent_id = agentId,
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

            _ = SendJson(new OutMsg
            {
                type = "complete",
                cmd = msg.cmd,
                agent_id = agentId,
                action_id = msg.action_id,
                status = "ok"
            });

            return;
        }

        _ = SendJson(new OutMsg
        {
            type = "complete",
            cmd = msg.cmd,
            agent_id = agentId,
            action_id = msg.action_id,
            status = "error",
            error = "unknown command"
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

            // 节流：保证任意两次播放开始时间至少间隔 animationDelaySeconds
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

            // 让出一帧，避免长队列在同一帧内吞掉过多时间
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

            // -1,-1 表示“跳过点”
            if (list[0].x == -1 && list[0].y == -1)
                continue;

            if (list.Count == 1) result.Add(list[0]);
            else result.Add(list[UnityEngine.Random.Range(0, list.Count)]);
        }

        if (result.Count == 0) return false;

        target = result;
        return true;
    }

    // ✅ 仍然是 async，但内部做了 sendLock 防并发 + try/catch 防火并忘丢异常
    async Task SendJson(object obj)
    {
        if (ws == null || ws.State != WebSocketState.Open || cts == null || cts.IsCancellationRequested) return;

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

        await sendLock.WaitAsync();
        try
        {
            await ws.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, cts.Token);
        }
        catch (OperationCanceledException)
        {
            // ignore
        }
        catch (Exception e)
        {
            Debug.LogWarning("SendAsync failed: " + e.Message + "\njson: " + json);
        }
        finally
        {
            sendLock.Release();
        }
    }

    void OnDestroy()
    {
        try { cts?.Cancel(); } catch { }
        if (reconnectCoroutine != null)
        {
            StopCoroutine(reconnectCoroutine);
            reconnectCoroutine = null;
        }

        try
        {
            if (ws != null)
            {
                if (ws.State == WebSocketState.Open)
                {
                    try
                    {
                        ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "destroy", CancellationToken.None).Wait(100);
                    }
                    catch { }
                }
                ws.Dispose();
            }
        }
        catch { }

        try { sendLock?.Dispose(); } catch { }
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
