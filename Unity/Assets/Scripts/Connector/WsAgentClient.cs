using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;


public interface IAutoNavigator
{
    void AddCommand(float cost_time,string cmd,List<Vector2> target, Action onArrived);
}
public interface IAutoHUDAnimation
{
    void AddAnimation(string type,float duration,int value);
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
    private Dictionary<string,List<string>> locationGraph = new();
    private Dictionary<string, List<Vector2>> locations;
    private ClientWebSocket ws;
    private CancellationTokenSource cts;
    private readonly ConcurrentQueue<Action> mainThreadQueue = new();
    public MonoBehaviour navigatorBehaviour;
    private IAutoNavigator navigator;
    public PlayerHUD playerHUD;
    void Awake()
    {
        locationGraph = new Dictionary<string, List<string>>();
        locations = new Dictionary<string, List<Vector2>>();
        //构建邻接表
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
        navigator = navigatorBehaviour as IAutoNavigator;
        if (navigator == null)
            Debug.LogError("navigatorBehaviour 未实现 IAutoNavigator 接口！");
    }

    async void Start()
    {
        await ConnectAndRun();
        // StartCoroutine(test_call());

    }
    /// <summary>
    /// 测试调用的协程方法，用于定期发送JSON格式的命令消息
    /// </summary>
    /// <returns>返回一个WaitForSeconds枚举器，用于协程的等待操作</returns>
    private IEnumerator<UnityEngine.WaitForSeconds> test_call()
    {
        // 无限循环，持续发送测试消息
        while (true)
        {
           // 构建更新状态的JSON命令字符串
           string json = "{\"type\":\"command\",\"agent_id\" : \"" + agentId + "\",\"cmd\":\"update_state\",\"target\":\"item\",\"value\":\"10\"}";
           // 构建从家到收银台的移动JSON命令字符串
           string json1 = "{\"type\":\"command\",\"cur_location\":\"家\",\"agent_id\" : \"" + agentId + "\",\"cmd\":\"go_to\",\"target\":\"收银台\",\"value\":\"0\"}";
           // 构建从集市到河流的移动JSON命令字符串
           string json2 = "{\"type\":\"command\",\"value\":\"0.5\",\"agent_id\" : \"" + agentId + "\",\"cmd\":\"pick_up\"}";

           string animation_json1 = "{\"type\":\"animation\",\"target\":\"item\",\"agent_id\" : \"" + agentId + "\",\"value\":\"5\"}";
           
           
            // // 如果agentId为"agent-2"，则发送移动命令
            if (agentId == "agent-4")
            {
                // HandleMessage(json1); // 处理第一个移动命令
                HandleMessage(animation_json1);
            
                // HandleMessage(animation_json1); // 处理动画命令
            } 
       

            // 等待3秒后继续下一次循环
            yield return new WaitForSeconds(3);

        }
    }

    async Task ConnectAndRun()
    {
        cts = new CancellationTokenSource();
        ws = new ClientWebSocket();

        try
        {
            await ws.ConnectAsync(new Uri(serverUrl), cts.Token);

            // 发送 hello（使用可序列化 DTO，而非匿名对象）
            await SendJson(new OutMsgHello
            {
                type = "hello",
                agent_id = agentId,
                cap = new[] { "waiting" }
            });

            // 启动接收循环
            _ = Task.Run(ReceiveLoop);
        }
        catch (Exception e)
        {
            Debug.LogWarning("WS connect failed (backend offline?): " + e.Message);
        }
    }

    void Retry() => _ = ConnectAndRun();

    async Task ReceiveLoop()
    {
        var buffer = new byte[8192];
        while (ws != null && ws.State == WebSocketState.Open)
        {
            var sb = new StringBuilder();
            WebSocketReceiveResult result;
            do
            {
                result = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), cts.Token);
                if (result.MessageType == WebSocketMessageType.Close)
                {
                    await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "bye", cts.Token);
                    return;
                }
                sb.Append(Encoding.UTF8.GetString(buffer, 0, result.Count));
            } while (!result.EndOfMessage);

            var json = sb.ToString();
            HandleMessage(json);
        }
    }

    async Task HandleMessage(string json)
    {
        var msg = JsonUtility.FromJson<WSMsg>(WSMsg.Fix(json));
        

        if (msg.type == "hello_ack")
        {   
            // no-op
        }
        else if (msg.type == "ping")
        {
            _ = SendJson(new OutMsg { type = "pong" });
        }
        else if (msg.type == "command"  && msg.cmd == "go_to")
        {
            //print(msg.target);
            //print(msg.cur_location);
            // ACK
            _ = SendJson(new OutMsg
            {
                type = "ack",
                agent_id = agentId,
                action_id = msg.action_id
            });

            // 主线程排队：解析坐标 -> 下发给导航器 -> 完成后上报
            mainThreadQueue.Enqueue(() =>
            {
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
               
                navigator?.AddCommand(msg.value,msg.cmd,target, onArrived: () =>
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
        }else if (msg.type == "command" && (msg.cmd !="go_to"))
        {
            mainThreadQueue.Enqueue(() =>
            {
                //print("cost_time"+msg.time_cost);
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
        }else if (msg.type == "animation")
        {
            var target = msg.target;
            var delta = (int)msg.value;
            var agent = msg.agent_id;
            mainThreadQueue.Enqueue(() =>
            {
                print(agent);
                print(delta);
                print(target);
                if (playerHUD != null)
                    playerHUD.PopStatus(target, delta);
            });
            
            _ = SendJson(new OutMsg{
                type = "complete",
                cmd = msg.cmd,
                agent_id = agentId,
                action_id = msg.action_id,
                status = "ok"
            });
        }
        else
        {
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
    }

    void Update()
    {
        int processed = 0;
        const int MAX_PER_FRAME = 16;
        while (processed < MAX_PER_FRAME && mainThreadQueue.TryDequeue(out var action))
        {
            action?.Invoke();
            processed++;
        }
    }

    bool TryResolveTarget(WSMsg msg, out List<Vector2> target)
    {
       
        var path = FindPath(msg.cur_location, msg.target, locationGraph);
        //foreach(string p in path)
        //{
        //    print(p);
        //}
        if (path != null && path.Count > 0)
        {
            target = new List<Vector2>();
            foreach (var name in path)
            {
                if (!locations.TryGetValue(name, out var list) || list == null || list.Count == 0)
                    return false;
                if (list[0].x == -1 && list[0].y == -1)
                {
                    continue;
                }
                if (list.Count == 1)
                    target.Add(list[0]);
                else 
                    target.Add(list[UnityEngine.Random.Range(0, list.Count)]);
                
            }
            return target.Count > 0;
        }

        target = null;
        return false;
    }

    async Task SendJson(object obj) // 这里 obj 必须是 [Serializable] 的类/结构，字段而不是属性
    {
        if (ws == null || ws.State != WebSocketState.Open) return;
        var json = JsonUtility.ToJson(obj);
        var bytes = Encoding.UTF8.GetBytes(json);
        await ws.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, cts.Token);
    }

    void OnDestroy()
    {
        try { cts?.Cancel(); } catch { }
        try
        {
            if (ws != null)
            {
                if (ws.State == WebSocketState.Open)
                    ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "destroy", CancellationToken.None).Wait(100);
                ws.Dispose();
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
        public float value;

        public static string Fix(string s)
        {
            // 暂留逻辑，不做错误替换，直接返回
            return s;
        }
    }

    // ---- 发送用 DTO（JsonUtility 需要字段 & [Serializable]） ----
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
                    // 回溯路径：start -> ... -> goal
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
