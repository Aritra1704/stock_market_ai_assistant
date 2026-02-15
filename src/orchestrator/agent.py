from src.services.assistant_service import AssistantService
from src.utils.time_utils import utc_now


class Agent:
    def __init__(self) -> None:
        self.assistant_service = AssistantService()

    def respond(self, query: str) -> dict:
        result = self.assistant_service.chat(query)
        result["timestamp"] = utc_now().isoformat()
        result["disclaimer"] = "For educational use only, not investment advice."
        return result
