from pydantic import BaseModel, ConfigDict, Field

class ItemBase(BaseModel):
    # API-level validation (W09): reject empty or overly long values with 422
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)

class ItemCreate(ItemBase):
    pass

class Item(ItemBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
