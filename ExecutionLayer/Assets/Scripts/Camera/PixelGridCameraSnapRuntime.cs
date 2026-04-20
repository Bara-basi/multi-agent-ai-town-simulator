using UnityEngine;
using UnityEngine.Rendering;

public sealed class PixelGridCameraSnapRuntime : MonoBehaviour
{
    private static PixelGridCameraSnapRuntime instance;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
    private static void Bootstrap()
    {
        if (instance != null)
        {
            return;
        }

        GameObject go = new GameObject(nameof(PixelGridCameraSnapRuntime));
        DontDestroyOnLoad(go);
        instance = go.AddComponent<PixelGridCameraSnapRuntime>();
    }

    private void OnEnable()
    {
        RenderPipelineManager.beginCameraRendering += OnBeginCameraRendering;
        Camera.onPreCull += OnPreCull;
    }

    private void OnDisable()
    {
        RenderPipelineManager.beginCameraRendering -= OnBeginCameraRendering;
        Camera.onPreCull -= OnPreCull;
    }

    private static void OnBeginCameraRendering(ScriptableRenderContext _, Camera cam)
    {
        SnapCameraToPixelGrid(cam);
    }

    private static void OnPreCull(Camera cam)
    {
        SnapCameraToPixelGrid(cam);
    }

    private static void SnapCameraToPixelGrid(Camera cam)
    {
        if (!Application.isPlaying || cam == null || !cam.enabled || !cam.orthographic)
        {
            return;
        }

        if (cam.cameraType != CameraType.Game || cam.pixelHeight <= 0)
        {
            return;
        }

        float unitsPerPixel = (cam.orthographicSize * 2f) / cam.pixelHeight;
        if (unitsPerPixel <= 0f)
        {
            return;
        }

        Transform tr = cam.transform;
        Vector3 p = tr.position;
        float snappedX = Mathf.Round(p.x / unitsPerPixel) * unitsPerPixel;
        float snappedY = Mathf.Round(p.y / unitsPerPixel) * unitsPerPixel;

        if (!Mathf.Approximately(p.x, snappedX) || !Mathf.Approximately(p.y, snappedY))
        {
            tr.position = new Vector3(snappedX, snappedY, p.z);
        }
    }
}
