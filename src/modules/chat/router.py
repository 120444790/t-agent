from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.agents.supervisor_agent import chat
from src.core.exceptions import BizException


router = APIRouter(prefix="/api/v1", tags=["聊天"])


class ChatIn(BaseModel):
    session_id: str = Field(..., description="会话ID，同一个用户不同会话请传不同值")
    message: str = Field(..., min_length=1, description="用户消息")


class ChatOut(BaseModel):
    code: int = 200
    message: str = "ok"
    data: str


@router.post("/chat", response_model=ChatOut)
async def chat_endpoint(body: ChatIn):
    """
    聊天接口（目前先不强制鉴权，Day 5 再挂 JWT）
    thread_id = 临时用户:session_id
    """
    # 暂时用固定用户，Day 5 换成真实登录用户
    user_id = "demo_user"

    try:
        reply = await chat(
            user_id=user_id,
            session_id=body.session_id,
            message=body.message,
        )
        return ChatOut(data=reply)
    except Exception as e:
        raise BizException(message=f"聊天失败: {str(e)}", code=500)