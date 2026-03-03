using UnityEngine;

[CreateAssetMenu(fileName = "StatusIconSet", menuName = "AI Town/Status Icon Set")]
public class StatusIconSet : ScriptableObject
{
    [System.Serializable]
    public class Entry
    {
        public string key;  
        public Sprite icon;
    }
    public Entry[] entries;

    public Sprite Get(string k)
    {
        if (string.IsNullOrEmpty(k) || entries == null) return null;
        for (int i = 0; i < entries.Length; i++)
            if (entries[i].key == k) return entries[i].icon;
        return null;
    }
}
