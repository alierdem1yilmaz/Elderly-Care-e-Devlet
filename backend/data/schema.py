# Sahiplik: Kişi 2 (Backend İçerik & Takip)
# backend/data/benefits.json içeriğinin şekli. Kişi 1'in eligibility_agent'ı da
# dahil, bu veriyi tüketen herkese sabit bir sözleşme sağlamak için var —
# dosya bozuk/eksik alanla düzenlenirse state.load_benefits() net bir hata verir.

from pydantic import BaseModel, Field


class BenefitSource(BaseModel):
    title: str
    url: str


class BenefitCriteria(BaseModel):
    min_age: int | None = None
    income_limit_fraction_of_net_minimum_wage: float | None = None
    income_limit_description: str | None = None
    excludes: list[str] = Field(default_factory=list)
    requires_disability_report: bool | None = None
    disability_report_wording: str | None = None
    requires_care_assessment: bool | None = None
    min_disability_percentage: int | None = None
    citizenship: str | None = None
    municipality_dependent: bool | None = None


class BenefitProgram(BaseModel):
    id: str
    name: str
    legal_basis: str
    administered_by: str
    criteria: BenefitCriteria
    required_documents: list[str]
    steps: list[str]
    notes: str | None = None
    source: BenefitSource


class BenefitsFile(BaseModel):
    programs: list[BenefitProgram]

    model_config = {"extra": "ignore"}  # "_meta" gibi bilgilendirici alanları yok say
