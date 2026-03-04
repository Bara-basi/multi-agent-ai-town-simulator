/*
驱动角色自动寻路的组件
*/

using System;
using System.Collections;
using System.Collections.Generic;
using Unity.Cinemachine;
using UnityEngine;
using UnityEngine.Tilemaps;

[Serializable]
public class ActionPair
{
    public string cmd;
    public Vector2 target;
    public Action actionCallBack;
    public float cost;
}

public class AutoMove : MonoBehaviour, IAutoNavigator,IPortalTraveller
{
    [Header("References")]
    public Camera cam;
    public CinemachineCamera vcam;
    public Grid grid;
    public Tilemap obstacleTilemap;
    public PlayerHUD hud;

    [SerializeField] 
    private float speed = 10f;
    private float suspendTimer = 0f;
    private float res_time = 0f;

    private Vector2 autoMove = Vector2.zero;
    private readonly Queue<ActionPair> actionList = new();
    private Action currentCallback;

    private Animator ani;
    private Rigidbody2D rb;
    private Vector2 lastFacing = Vector2.down;
    private bool frozen = false;
    private bool isTeleporting = false; 
    private float frozenUntil = 0f;
    private string curCmd = "";
    private bool idleMoving = false;
    private Vector3Int idleTargetCell;
    private float nextIdleMoveAt = 0f;
   
    [Header("Idle Wander")]
    public bool enableIdleWander = true;
    public float idleMoveIntervalMin = 2f;
    public float idleMoveIntervalMax = 5f;


    [Header("Path Following")]
    public float arriveCellEpsilon = 0.2f;
    public float repathIfBlockedAfterSec = 0.5f;
    public float hardStuckAfterSec = 2f;
    public int hardStuckSnapRadius = 2;
    private readonly List<Vector3Int> pathCells = new();
    private int pathIndex = 0;
    private float stuckTimer = 0f;
    private float hardStuckTimer = 0f;
    private Vector3 lastPos;
    private Vector3Int currentGoalCell;
    private bool hasGoal = false;

    [Header("Obstacle Physics Check")]
    public Collider2D playerCollider;
    public LayerMask obstacleMask;
    [Range(0f, 0.2f)]
    public float extraClearance = 0.02f;

    

    void Awake()
    {
        ani = GetComponent<Animator>();
        rb = GetComponent<Rigidbody2D>();
        if (!cam) cam = Camera.main;
        if (ani) ani.SetInteger("move", 0);
        lastPos = transform.position;
        ScheduleNextIdleMove();
    }

    void FixedUpdate()
    {
        if (frozen)
        {
            if (rb != null) rb.linearVelocity = Vector2.zero;
            return;
        }
        rb.linearVelocity = autoMove * speed;
    }

    void Update()
    {

        if (frozen && Time.time >= frozenUntil && !isTeleporting)
            frozen = false;

        if (frozen)
        {
            if (ani) ani.SetInteger("move", 0);
            autoMove = Vector2.zero;
            if (rb != null) rb.linearVelocity = Vector2.zero;
            return;
        }
        if (suspendTimer > 0f)
        {
            suspendTimer -= Time.deltaTime;
            CancelAuto();
            return;
        }
        // 驱动动画
        if (autoMove.sqrMagnitude > 0.0001f)
        {
            if (ani)
            {
                ani.SetInteger("move", 1);
                if (Mathf.Abs(autoMove.x) >= Mathf.Abs(autoMove.y))
                {
                    ani.SetFloat("Horizontal", Mathf.Sign(autoMove.x));
                    ani.SetFloat("Vertical", 0f);
                    lastFacing = new Vector2(Mathf.Sign(autoMove.x), 0f);
                }
                else
                {
                    ani.SetFloat("Horizontal", 0f);
                    ani.SetFloat("Vertical", Mathf.Sign(autoMove.y));
                    lastFacing = new Vector2(0f, Mathf.Sign(autoMove.y));
                }
            }
        }
        else
        {
            if (ani)
            {
                ani.SetFloat("Horizontal", lastFacing.x);
                ani.SetFloat("Vertical", lastFacing.y);
                ani.SetInteger("move", 0);
            }
        }

        // 若空闲且有新命令，取队头开始寻路
        if (curCmd == "" && actionList.Count > 0)
        {
            StopIdleWander();
            var pair = actionList.Dequeue();
            currentCallback = pair.actionCallBack;
            curCmd = pair.cmd;
            if (curCmd == "go_to")
            {
                var startCell = grid.WorldToCell(transform.position);
                var targetCell = grid.WorldToCell((Vector3)pair.target);
                if (!IsWalkable(targetCell))
                {
                    if (!FindNearestWalkable(ref targetCell, 8))
                    {
                        CancelAuto();
                        CompleteCurrent();
                        return;
                    }
                }

                hasGoal = true;
                currentGoalCell = targetCell;

                var path = AStar(startCell, targetCell);
                if (path != null && path.Count > 0)
                {
                    pathCells.Clear();
                    pathCells.AddRange(path);
                    pathIndex = 0;
                    stuckTimer = 0f;
                    lastPos = transform.position;
                    NextStep();
                }
                else
                {
                    CancelAuto();
                    CompleteCurrent();
                }
            }else if(curCmd == "waiting")
            {
                //等待或者工作中
                print("waiting");
                res_time = pair.cost;
                hud.StartWork(res_time);
                
            }else if(pair.cmd == "sleeping")
            {
                print("sleeping");
                res_time = pair.cost;
                //播放睡觉动画
                ani.SetInteger("sleep", 1);

            }
            else if (pair.cmd == "pick_up")
            {
                print("pick up something");
                ani.SetTrigger("pick_up");
                res_time = pair.cost;

            }
            else if (pair.cmd == "fishing")
            {
                
            }
            else
            {
                
                CancelAuto();
                CompleteCurrent();
                print("error:no such command");
            }

        }
        if (curCmd == "" && actionList.Count == 0 && enableIdleWander)
        {
            HandleIdleWander();
        }
        else if (!idleMoving)
        {
            autoMove = Vector2.zero;
        }

        if(curCmd == "go_to")
        {
            //向着某处走动
            if (pathCells.Count > 0)
            {
                var targetWorld = grid.GetCellCenterWorld(pathCells[pathIndex]);
                targetWorld.z = 0f;
                Vector2 dir = (Vector2)(targetWorld - transform.position);

                float snapDist = Mathf.Max(arriveCellEpsilon, speed * Time.fixedDeltaTime * 1.1f);
                if (dir.magnitude <= snapDist)
                {
                    if (rb != null) rb.position = targetWorld;
                    else transform.position = targetWorld;
                    pathIndex++;
                    if (pathIndex >= pathCells.Count)
                    {
                        // 到达终点
                        frozen = true;
                        frozenUntil = Time.time + 3;
                        CancelAuto();
                        CompleteCurrent();
                        return;
                    }
                    else
                    {
                        NextStep();
                    }
                }
                else
                {
                    autoMove = dir.normalized;
                }

                float moved = (transform.position - lastPos).sqrMagnitude;
                lastPos = transform.position;
                if (moved < 0.0001f)
                {
                    stuckTimer += Time.deltaTime;
                    hardStuckTimer += Time.deltaTime;
                    if (stuckTimer > repathIfBlockedAfterSec)
                    {
                        RepathFromHere();
                        stuckTimer = 0f;
                    }
                    if (hardStuckTimer > hardStuckAfterSec)
                    {
                        var curCell = grid.WorldToCell(transform.position);
                        if (FindNearestWalkable(ref curCell, hardStuckSnapRadius))
                        {
                            var snap = grid.GetCellCenterWorld(curCell);
                            snap.z = 0f;
                            if (rb != null) rb.position = snap;
                            else transform.position = snap;
                            RepathFromHere();
                        }
                        else
                        {
                            CancelAuto();
                            CompleteCurrent();
                            return;
                        }
                        hardStuckTimer = 0f;
                    }
                }
                else
                {
                    stuckTimer = 0f;
                    hardStuckTimer = 0f;
                }
            }
            else
            {
                CancelAuto();
                CompleteCurrent();
            }
        }else if(curCmd == "waiting")
        {
            //原地等待或等待工作完成
            res_time -= Time.deltaTime;
            if(res_time <= 0)
            {
                hud.StopWork();
                CompleteCurrent();
            }

        }else if (curCmd == "sleeping")
        {
            //睡觉动画
            res_time -= Time.deltaTime;
            if (res_time <= 0)
            {
                print("stop");
                ani.SetInteger("sleep", 0);
                CompleteCurrent();
            }
        }else if (curCmd == "pick_up")
        {
            //捡东西
            res_time -= Time.deltaTime;
            if (res_time <= 0)
            {
                print("stop");
                CompleteCurrent();
            }
        }


    }

    public void AddCommand(float cost_time,string cmd, List<Vector2> target, Action onArrived)
    {
        //Vector3Int startCell = grid.WorldToCell(transform.position);
        //Vector2 temp_target = new Vector2(startCell.x+10f, startCell.y+10f);
        
        for (int i = 0; i < target.Count - 1; i++)
        {
            actionList.Enqueue(new ActionPair { cost =  cost_time,cmd= cmd,target = target[i], actionCallBack = null});
        }
        if(target.Count > 0)
        {
            actionList.Enqueue(new ActionPair { cost = cost_time, cmd = cmd, target = target[^1], actionCallBack = onArrived });
        }
        else
        {
            actionList.Enqueue(new ActionPair { cost = cost_time, cmd = cmd, target = Vector2.zero, actionCallBack = onArrived });
        }
    }
    public void Suspend(float seconds)
    {
        //短暂屏蔽自动寻路
        CancelAuto();
        //传送必定完成某次移动，返回成功响应
        CompleteCurrent();
        suspendTimer = Mathf.Max(suspendTimer, seconds);
    }
    //public void SetFrozen(bool frozen)
    //{
    //    this.frozen = frozen;
    //}
    public void CancelAuto()
    {
        pathCells.Clear();
        pathIndex = 0;
        autoMove = Vector2.zero;
        if (rb != null) rb.linearVelocity = Vector2.zero;
        idleMoving = false;
        stuckTimer = 0f;
        hardStuckTimer = 0f;
        hasGoal = false;
    }

    void CompleteCurrent()
    {
        var cb = currentCallback;
        currentCallback = null;
        curCmd = "";
        cb?.Invoke();
    }

    void RepathFromHere()
    {
        if (!hasGoal) return;

        var startCell = grid.WorldToCell(transform.position);
        var goalCell = currentGoalCell;
        if (!IsWalkable(goalCell))
        {
            if (!FindNearestWalkable(ref goalCell, 8)) return;
            currentGoalCell = goalCell;
        }

        var path = AStar(startCell, goalCell);
        if (path != null && path.Count > 0)
        {
            pathCells.Clear();
            pathCells.AddRange(path);
            pathIndex = 0;
            NextStep();
        }
    }

    void NextStep()
    {
        if (pathCells.Count == 0)
        {
            autoMove = Vector2.zero;
            return;
        }
        var targetWorld = grid.GetCellCenterWorld(pathCells[pathIndex]);
        Vector2 dir = (Vector2)(targetWorld - transform.position);
        autoMove = dir.normalized;
    }

    void HandleIdleWander()
    {
        if (idleMoving)
        {
            var targetWorld = grid.GetCellCenterWorld(idleTargetCell);
            targetWorld.z = 0f;
            Vector2 dir = (Vector2)(targetWorld - transform.position);
            float snapDist = Mathf.Max(arriveCellEpsilon, speed * Time.fixedDeltaTime * 1.1f);

            if (dir.magnitude <= snapDist)
            {
                if (rb != null) rb.position = targetWorld;
                else transform.position = targetWorld;
                idleMoving = false;
                autoMove = Vector2.zero;
                ScheduleNextIdleMove();
            }
            else
            {
                autoMove = dir.normalized;
            }
            return;
        }

        if (Time.time < nextIdleMoveAt)
        {
            autoMove = Vector2.zero;
            return;
        }

        TryStartIdleMove();
    }

    void TryStartIdleMove()
    {
        var currentCell = grid.WorldToCell(transform.position);
        var dirs = new[] { Vector3Int.up, Vector3Int.down, Vector3Int.left, Vector3Int.right };
        var walkableNeighbors = new List<Vector3Int>(4);

        foreach (var d in dirs)
        {
            var cell = currentCell + d;
            if (IsWalkable(cell))
                walkableNeighbors.Add(cell);
        }

        if (walkableNeighbors.Count == 0)
        {
            autoMove = Vector2.zero;
            ScheduleNextIdleMove();
            return;
        }

        idleTargetCell = walkableNeighbors[UnityEngine.Random.Range(0, walkableNeighbors.Count)];
        idleMoving = true;
    }

    void StopIdleWander()
    {
        idleMoving = false;
        autoMove = Vector2.zero;
    }

    void ScheduleNextIdleMove()
    {
        float min = Mathf.Max(0f, idleMoveIntervalMin);
        float max = Mathf.Max(min, idleMoveIntervalMax);
        nextIdleMoveAt = Time.time + UnityEngine.Random.Range(min, max);
    }

    bool IsWalkable(Vector3Int cell)
    {
        var center = grid.GetCellCenterWorld(cell);

        Vector2 probeSize;
        if (playerCollider != null)
        {
            var sz = playerCollider.bounds.size;
            probeSize = new Vector2(
                Mathf.Max(0.01f, sz.x + 2f * extraClearance),
                Mathf.Max(0.01f, sz.y + 2f * extraClearance)
            );
        }
        else
        {
            probeSize = new Vector2(
                Mathf.Max(0.01f, Mathf.Abs(grid.cellSize.x) + 2f * extraClearance),
                Mathf.Max(0.01f, Mathf.Abs(grid.cellSize.y) + 2f * extraClearance)
            );
        }

        if (obstacleTilemap && obstacleTilemap.HasTile(cell)) return false;
        if (Physics2D.OverlapBox(center, probeSize, 0f, obstacleMask) != null) return false;
        return true;
    }

    bool FindNearestWalkable(ref Vector3Int cell, int maxRadius)
    {
        if (IsWalkable(cell)) return true;

        var q = new Queue<Vector3Int>();
        var visited = new HashSet<Vector3Int> { cell };
        q.Enqueue(cell);

        Vector3Int[] dirs = { Vector3Int.up, Vector3Int.down, Vector3Int.left, Vector3Int.right };

        while (q.Count > 0)
        {
            var cur = q.Dequeue();
            foreach (var d in dirs)
            {
                var n = cur + d;
                if (!visited.Add(n)) continue;

                int r = Mathf.Abs(n.x - cell.x) + Mathf.Abs(n.y - cell.y);
                if (r > maxRadius) continue;

                if (IsWalkable(n))
                {
                    cell = n;
                    return true;
                }
                q.Enqueue(n);
            }
        }
        return false;
    }

    List<Vector3Int> AStar(Vector3Int start, Vector3Int goal)
    {
        var open = new List<Vector3Int> { start };
        var came = new Dictionary<Vector3Int, Vector3Int>();
        var g = new Dictionary<Vector3Int, int> { [start] = 0 };
        var f = new Dictionary<Vector3Int, int> { [start] = Heu(start, goal) };

        Vector3Int[] dirs = { Vector3Int.up, Vector3Int.down, Vector3Int.left, Vector3Int.right };

        while (open.Count > 0)
        {
            int best = 0;
            for (int i = 1; i < open.Count; i++)
                if (f[open[i]] < f[open[best]]) best = i;

            var cur = open[best];
            if (cur == goal) return Reconstruct(came, cur);
            open.RemoveAt(best);

            foreach (var d in dirs)
            {
                var nx = cur + d;
                if (!IsWalkable(nx)) continue;

                int candG = g[cur] + 1;
                if (!g.ContainsKey(nx) || candG < g[nx])
                {
                    g[nx] = candG;
                    f[nx] = candG + Heu(nx, goal);
                    came[nx] = cur;
                    if (!open.Contains(nx)) open.Add(nx);
                }
            }
        }
        return null;
    }

    int Heu(Vector3Int a, Vector3Int b)
        => Mathf.Abs(a.x - b.x) + Mathf.Abs(a.y - b.y);

    List<Vector3Int> Reconstruct(Dictionary<Vector3Int, Vector3Int> came, Vector3Int cur)
    {
        var list = new List<Vector3Int> { cur };
        while (came.ContainsKey(cur)) { cur = came[cur]; list.Add(cur); }
        list.Reverse();
        return list;
    }

    public void PortalRequestTeleport(Transform portal, Vector3 targetPosition,
                                      float preWait, float postWait
                                      )
    {
        if (isTeleporting) return;  // 防止重复触发
        isTeleporting = true;
        StopIdleWander();
        autoMove = Vector2.zero;
        if (rb) rb.linearVelocity = Vector2.zero;
        StartCoroutine(TeleportAfterDelay(targetPosition, preWait, postWait, vcam));
    }

    private IEnumerator TeleportAfterDelay(Vector3 targetPosition, float preWait, float postWait, CinemachineCamera vcam)
    {
        //延迟传送
        bool shouldCompleteGoTo = (curCmd == "go_to");
        var preTeleportPos = transform.position;

        if (rb) rb.linearVelocity = Vector2.zero;
        frozen = true;

        if (preWait > 0f)
            yield return new WaitForSeconds(preWait);

        CancelAuto();
        idleMoving = false;

        targetPosition.z = transform.position.z;
        if (rb != null)
        {
            rb.position = targetPosition;
            transform.position = targetPosition;
            rb.linearVelocity = Vector2.zero;
        }
        else
        {
            transform.position = targetPosition;
        }
        Physics2D.SyncTransforms();
        lastPos = transform.position;
        if (vcam != null)
        {
            var warpTarget = vcam.Follow != null ? vcam.Follow : transform;
            vcam.OnTargetObjectWarped(warpTarget, transform.position - preTeleportPos);
            vcam.PreviousStateIsValid = false;
        }
        if (cam != null)
        {
            var p = cam.transform.position;
            cam.transform.position = new Vector3(transform.position.x, transform.position.y, p.z);
        }

        // 传送点通常是当前 go_to 的阶段终点，传送后直接进入后续动作
        if (shouldCompleteGoTo)
        {
            CompleteCurrent();
        }

        frozenUntil = Time.time + postWait;
        if (postWait > 0f)
            yield return new WaitForSeconds(postWait);

        isTeleporting = false;
        if (Time.time >= frozenUntil)
            frozen = false;
        

    }
}
