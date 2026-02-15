from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.models.notification import DeviceRegistration, NotificationPayload
from src.notifications.service import NotificationService
from src.orchestrator.agent import Agent
from src.services.assistant_service import AssistantService


router = APIRouter(prefix="/api")
assistant_service = AssistantService()
agent = Agent()
notification_service = NotificationService()


class ChatRequest(BaseModel):
    query: str


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/portfolio/summary")
def portfolio_summary() -> dict:
    return assistant_service.portfolio_brief()


@router.get("/stocks/{symbol}/analysis")
def stock_analysis(symbol: str) -> dict:
    try:
        return assistant_service.analyze_stock(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/chat")
def chat(payload: ChatRequest) -> dict:
    return agent.respond(payload.query)


@router.post("/notifications/register")
def register_device(payload: DeviceRegistration) -> dict:
    return notification_service.register_device(payload)


class SendNotificationRequest(BaseModel):
    user_id: str
    title: str
    body: str
    data: dict[str, str] = {}


@router.post("/notifications/send")
def send_notification(payload: SendNotificationRequest) -> dict:
    message = NotificationPayload(title=payload.title, body=payload.body, data=payload.data)
    return notification_service.send_to_user(payload.user_id, message)
