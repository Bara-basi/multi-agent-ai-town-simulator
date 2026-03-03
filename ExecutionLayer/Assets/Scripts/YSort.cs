using UnityEngine;

[RequireComponent(typeof(SpriteRenderer))]
public class YSort:MonoBehaviour
{
    public int sortingOrderBase = 0;
    public int offset = 0;
    public float precision = 16f;
    public int addtionalY = 0;
    SpriteRenderer sr;
    private void Awake()
    {
        sr = GetComponent<SpriteRenderer>();
    }
    private void LateUpdate()
    {
        float y = sr.bounds.min.y;
        sr.sortingOrder = sortingOrderBase + offset + Mathf.RoundToInt(-y * precision)+addtionalY;
    }
}
