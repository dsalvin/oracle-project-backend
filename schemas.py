from pydantic import BaseModel

class TokenData(BaseModel):
    email: str | None = None

class UserCreate(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str 

class User(BaseModel):
    id: int
    email: str
    first_name: str 
    last_name: str 

    class Config:
        from_attributes = True # Changed from orm_mode

class Token(BaseModel):
    access_token: str
    token_type: str