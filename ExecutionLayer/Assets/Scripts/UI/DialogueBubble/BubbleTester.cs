using UnityEngine;
using UnityEngine.InputSystem;
public class DialogueBubbleTester : MonoBehaviour
{
    public DialogueBubbleUI bubble;

    private void Update()
    {
        if (Keyboard.current.digit1Key.wasPressedThisFrame)
        {
            bubble.Show("你好。");
        }

        if (Keyboard.current.digit2Key.wasPressedThisFrame)
        {
            bubble.Show("今天面包价格有点低，我想先买一点再看看明天会不会涨价。");
        }

        if (Keyboard.current.digit3Key.wasPressedThisFrame)
        {
            bubble.Show("我现在有点渴，但钱也不算很多，得先判断一下是先补水还是继续去集市交易。");
        }
    }
}