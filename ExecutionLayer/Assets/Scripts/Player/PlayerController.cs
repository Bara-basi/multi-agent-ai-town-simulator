/*
角色控制器：处理手动输入与自动寻路输入的整合，驱动动画与刚体运动,包含使用键盘WASD的手动输入
*/

using UnityEngine;
using UnityEngine.InputSystem;

[RequireComponent(typeof(Rigidbody2D))]
public class PlayerController : MonoBehaviour
{
    [SerializeField] private float speed;

    private Vector2 manualMove;              // WASD 读到的手动输入
    private Vector2 autoMove;                // 寻路系统注入的自动方向（单位向量或0）
    private bool hasAutoMove;                // 是否启用自动移动

    private Animator ani;
    private Rigidbody2D rBody;
    private Vector2 lastFacing = Vector2.down;
    public System.Action ManualControlStarted;

    private bool frozen = false;
    void Awake()
    {
        ani = GetComponent<Animator>();
        rBody = GetComponent<Rigidbody2D>();
        ani.SetInteger("move", 0);
    }

    // --- 新输入系统：PlayerInput 调用 ---
    void OnMove(InputValue value)
    {
        manualMove = value.Get<Vector2>();
        if (manualMove.sqrMagnitude > 0.0001f)
        {
            hasAutoMove = false;                
            ManualControlStarted?.Invoke();      
        }
    }

    /// <summary> 由寻路组件设置自动移动方向（长度可为0代表停止） </summary>
    public void SetAutoMove(Vector2 dir)
    {
        
        autoMove = dir;
        hasAutoMove = (dir.sqrMagnitude > 0.0001f);
    }

    /// <summary> 供寻路组件查询：当前是否有人为输入在接管 </summary>
    public bool IsManualControlling => manualMove.sqrMagnitude > 0.0001f;

    void Update()
    {
        // 选取本帧实际用于动画与运动的方向：手动优先，其次自动
        Vector2 used = IsManualControlling ? manualMove : (hasAutoMove ? autoMove : Vector2.zero);
        if (frozen)
        {
            ani.SetInteger("move", 0);
            return;
        }
        if (used.sqrMagnitude > 0.0001f)
        {
            ani.SetInteger("move", 1);
            if (Mathf.Abs(used.x) >= Mathf.Abs(used.y))
            {
                ani.SetFloat("Horizontal", Mathf.Sign(used.x));
                ani.SetFloat("Vertical", 0f);
                lastFacing = new Vector2(Mathf.Sign(used.x), 0f);
            }
            else
            {
                ani.SetFloat("Horizontal", 0f);
                ani.SetFloat("Vertical", Mathf.Sign(used.y));
                lastFacing = new Vector2(0f, Mathf.Sign(used.y));
            }
        }
        else
        {
            ani.SetFloat("Horizontal", lastFacing.x);
            ani.SetFloat("Vertical", lastFacing.y);
            ani.SetInteger("move", 0);
        }
    }

    public void SetFrozen(bool frozen)
    {
            this.frozen = frozen;
    }
    void FixedUpdate()
    {

        if (frozen) return;
      
        Vector2 used = IsManualControlling ? manualMove : (hasAutoMove ? autoMove : Vector2.zero);

        rBody.linearVelocity = used.normalized * speed;
    }
}
