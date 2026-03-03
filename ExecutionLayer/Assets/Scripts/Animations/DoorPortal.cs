using System.Collections;
using System.Collections.Generic;
using Unity.Cinemachine;
using UnityEngine;



public interface IPortalTraveller
{
    void PortalRequestTeleport(Transform portal,Vector3 targetPosition,float preWait,float postWait);
}
public class DoorPortal:MonoBehaviour
{
    [Tooltip("玩家被传送到这里！")]
    public Transform targetPosition;

    public float preTeleportWait = 2f;
    public float suspendTime = 0.2f;

    private void OnTriggerEnter2D(Collider2D player)
    {

        
        if (!player.CompareTag("Player")) return;

        if (player.TryGetComponent<IPortalTraveller>(out var traveller))
        {
            traveller.PortalRequestTeleport(transform, targetPosition.position,
                                            preTeleportWait, suspendTime);
        }
        //StartCoroutine(TeleportAfterDelay(player.transform));
    }

}
