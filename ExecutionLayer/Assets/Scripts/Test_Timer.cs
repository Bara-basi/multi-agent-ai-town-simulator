using UnityEngine;

public class Test_Timer:MonoBehaviour
{
    public PlayerHUD hud;
    private void Update()
    {
        if (Input.GetKeyDown(KeyCode.T))
        {
            hud.StartWork(3f);
        }
        if (Input.GetKeyDown(KeyCode.Y))
        {
            hud.StopWork();
        }
    }
}
