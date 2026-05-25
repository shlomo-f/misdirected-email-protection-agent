from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class Persona(BaseModel):
    email: str
    inferred_names: List[str] = Field(
        default=[],
        description=(
            "A list of names inferred from the email address or content. "
            "Include professional names, nicknames, or aliases found in the text."
        )
    )
    company: List[str] = Field(
        default=[],
        description=(
            "A list of companies or organizations associated with the person. "
            "Include official legal names, trading names, parent companies, "
            "or colloquial abbreviations/nicknames found in the content."
        )
    )
    job_title: Optional[str] = Field(description="His job title, what is his function in the company")
    relationship_to_sender: Optional[str] = Field(description="How does this person relate to the sender? e.g., 'Client', 'Vendor', 'Internal Colleague'")
    known_topics: List[str] = Field(default_factory=list, description="List of projects, topics, or themes discussed with this person.")
    last_updated: str
    last_talked: Optional[str] = Field(description="When did they had their last conversation.")


class SecurityVerdict(BaseModel):
    status: Literal["SAFE", "WARN"] = Field(
        description="SAFE if the email aligns with the persona. WARN if there is a plausible chance it is misdirected."
    )
    risk_score: int = Field(
        description="A score from 0 to 100. 0 means perfectly normal. 100 means obvious and highly probable misdirection.",
        ge=0, le=100
    )
    reasoning: str = Field(
        description="A concise, polite explanation to display to the user in the UI popup. Explain WHY it looks wrong."
    )
    flagged_context: List[str] = Field(
        default_factory=list,
        description="Specific terms, names, or topics in the draft that do not match the recipient's known persona."
    )
    suggested_recipient: Optional[str] = Field(
        default=None,
        description="The email address of the correct intended recipient if a mix-up is identified from the alternative candidates list. Leave None if no better match is found."
    )
    suggestion_reason: Optional[str] = Field(
        default=None,
        description="A very brief explanation of why this alternative contact is a better match (e.g., 'Matches TechStars project context')."
    )