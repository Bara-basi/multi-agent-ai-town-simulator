using UnityEngine;
using UnityEngine.InputSystem;

public class TestPopup : MonoBehaviour
{
    public PlayerHUD hud;

    void Update()
    {
        if (Keyboard.current.digit1Key.wasPressedThisFrame)
        {
            hud.PopStatus("money", -15);
        }

        if (Keyboard.current.digit2Key.wasPressedThisFrame)
        {
            hud.PopStatus("item", +1);
        }

        if (Keyboard.current.digit3Key.wasPressedThisFrame)
        {
            hud.PopStatus("fish", +1);
        }

        if (Keyboard.current.digit4Key.wasPressedThisFrame)
        {
            hud.PopStatus("hunger", +13);
        }

        if (Keyboard.current.digit5Key.wasPressedThisFrame)
        {
            hud.PopStatus("fatigue", +1);
        }

        if (Keyboard.current.digit6Key.wasPressedThisFrame)
        {
            hud.PopStatus("thirst", +1);
        }
    }
}