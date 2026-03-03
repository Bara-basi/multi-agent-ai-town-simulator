using UnityEngine;

[RequireComponent(typeof(Animator))]
public class DoorAnimator:MonoBehaviour
{
    public string playerTag = "Player";
    Animator ani;
    void Awake()
    {
        ani = GetComponent<Animator>();
    }
    private void OnTriggerEnter2D(Collider2D collision)
    {
        if(collision.CompareTag(playerTag))
        {
            ani.SetBool("Open", true);
        }
    }
    private void OnTriggerExit2D(Collider2D collision)
    {
        if(collision.CompareTag(playerTag))
        {
            ani.SetBool("Open",false);
        }
    }
}
