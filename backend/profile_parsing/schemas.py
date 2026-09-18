from typing import List, Optional

from pydantic import BaseModel, Field


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


class ResumeProfile(BaseModel):
    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    education: List[EducationEntry] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    experience: List[ExperienceEntry] = Field(default_factory=list)
    projects: List[ProjectEntry] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)


EMPTY_PROFILE = ResumeProfile().model_dump()
