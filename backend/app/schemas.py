from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class MessageOut(BaseModel):
    id: int; source: str; sender: str; subject: str; body: str
    priority_score: float; priority_label: str; created_at: datetime
    model_config = {"from_attributes": True}


class DraftCreate(BaseModel):
    message_id: int
    instruction: str = Field(min_length=1, max_length=2000)


class DraftOut(BaseModel):
    id: int; message_id: int; draft_text: str; status: str
    model_config = {"from_attributes": True}


class ReviseRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)


class ConfluenceConnect(BaseModel):
    base_url: str = Field(min_length=8, max_length=500)
    email: str = Field(min_length=3, max_length=255)
    api_token: str = Field(min_length=1, max_length=500)


class JiraConnect(ConfluenceConnect):
    pass


class JiraSearchRequest(BaseModel):
    query: str = Field(default="", max_length=2000)
    board_name: str = Field(default="", max_length=255)


class JiraCommentRequest(BaseModel):
    issue_key: str = Field(min_length=1, max_length=64)
    body: str = Field(min_length=1, max_length=10000)
    reply_to: str | None = Field(default=None, max_length=64)


class ConfluencePageRequest(BaseModel):
    url: str = Field(default="", max_length=1000)


class ConfluenceAskRequest(ConfluencePageRequest):
    question: str = Field(min_length=1, max_length=2000)
    focus: str = Field(default="everything", max_length=32)


class ConfluenceAnalyzeRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    focus: str = Field(default="everything", max_length=32)
    page: dict[str, str | None]


class VoiceTranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=30000)
    language: str = Field(min_length=2, max_length=20)


class AssistantQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10000)
    request_type: str = Field(default="workspace", min_length=1, max_length=32)


class AssistantQueryOut(BaseModel):
    id: int
    query: str
    answer: str
    request_type: str
    status: str
    created_at: datetime


class AssistantRequestOut(BaseModel):
    id: int
    request_text: str
    request_type: str
    response_text: Optional[str]
    status: str
    error_detail: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    model_config = {"from_attributes": True}
