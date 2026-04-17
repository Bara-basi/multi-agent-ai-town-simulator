using UnityEngine;

public class MultiDisplayActivator : MonoBehaviour
{
    [SerializeField] [Range(0, 7)] private int extraDisplaysToActivate = 4;

    private void Start()
    {
        int maxDisplayIndex = Mathf.Min(Display.displays.Length - 1, extraDisplaysToActivate);
        for (int i = 1; i <= maxDisplayIndex; i++)
        {
            Display.displays[i].Activate();
        }
    }
}
