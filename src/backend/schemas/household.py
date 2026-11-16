from pydantic import BaseModel, Field, ConfigDict


class HouseholdCreate(BaseModel):
    household_name: str = Field(
        min_length=2,
        max_length=150
    )


class HouseholdResponse(BaseModel):
    id: int
    household_name: str

    model_config = ConfigDict(from_attributes=True)