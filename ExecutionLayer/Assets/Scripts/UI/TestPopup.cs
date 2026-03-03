using UnityEngine;

public class TestPopup : MonoBehaviour
{
    public PlayerHUD hud;

    void Update()
    {
        if (Input.GetKeyDown(KeyCode.Alpha1))
        {
            hud.PopStatus("money", -15);
        }
        if (Input.GetKeyDown(KeyCode.Alpha2))
        {
            hud.PopStatus("item", +1);
        }
        if (Input.GetKeyDown(KeyCode.Alpha3))
        {
            hud.PopStatus("fish", +1);
        }
        if (Input.GetKeyDown(KeyCode.Alpha4))
        {
            hud.PopStatus("food", +13);
        }
        if (Input.GetKeyDown(KeyCode.Alpha5))
        {
            hud.PopStatus("sanity", +1);
        }
        if (Input.GetKeyDown(KeyCode.Alpha6))
        {
            hud.PopStatus("water", +1);
        }
    }
}
