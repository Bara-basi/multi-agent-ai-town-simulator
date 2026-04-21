using UnityEngine;

public class MultiDisplayActivator : MonoBehaviour
{
    [SerializeField] [Range(0, 7)] private int extraDisplaysToActivate = 4;
    [SerializeField] [Range(0, 7)] private int ensureDisplayIndex = 5; // ensure Display6 is available

    private void Start()
    {
        int requestedMax = Mathf.Max(extraDisplaysToActivate, ensureDisplayIndex);
        int maxDisplayIndex = Mathf.Min(Display.displays.Length - 1, requestedMax);
        for (int i = 1; i <= maxDisplayIndex; i++)
        {
            Display.displays[i].Activate();
        }
    }
}
