from pydantic import BaseModel, Field


class HouseholdUpdate(BaseModel):
    household_name: str = Field(
        min_length=1,
        max_length=150
    )