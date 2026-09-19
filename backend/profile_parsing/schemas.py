from typing import List, Union

from pydantic import BaseModel, Field, model_validator


class PersonalInfo(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""


class EducationEntry(BaseModel):
    degree: str = ""
    field: str = ""
    institution: str = ""
    graduation_year: str = ""


class ExperienceEntry(BaseModel):
    company: str = ""
    role: str = ""
    duration: str = ""
    responsibilities: List[str] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    name: str = ""
    description: str = ""
    technologies: List[str] = Field(default_factory=list)


class UserProfile(BaseModel):
    """Canonical candidate profile shared by backend agents.

    ``education`` accepts the legacy string form as well as the structured
    entries produced by the profile parser. The default remains an empty list
    so an absent education value is never invented.
    """

    name: str = ""
    email: str = ""
    phone: str = ""
    education: Union[List[EducationEntry], str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    experience: List[ExperienceEntry] = Field(default_factory=list)
    projects: List[ProjectEntry] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    location: str = ""
    target_role: str = ""

    def __getitem__(self, field_name: str):
        """Preserve read-only dict-style access for existing state consumers."""
        return getattr(self, field_name)

    @model_validator(mode="before")
    @classmethod
    def default_missing_values(cls, value):
        """Treat omitted or null profile values as empty values."""
        if not isinstance(value, dict):
            return value
        if any(key in value for key in ("candidate_skills", "job_title", "top_k")):
            raise ValueError("Payload is a skill match request, not a user profile.")

        normalized = dict(value)
        for field_name in ("name", "email", "phone", "location", "target_role"):
            if field_name in normalized and normalized[field_name] is None:
                normalized[field_name] = ""
        for field_name in ("skills", "experience", "projects", "certifications", "interests"):
            if field_name in normalized and normalized[field_name] is None:
                normalized[field_name] = []
        if "education" in normalized and normalized["education"] is None:
            normalized["education"] = []
        return normalized


class ResumeProfile(BaseModel):
    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    education: List[EducationEntry] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    experience: List[ExperienceEntry] = Field(default_factory=list)
    projects: List[ProjectEntry] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)


EMPTY_PROFILE = ResumeProfile().model_dump()
