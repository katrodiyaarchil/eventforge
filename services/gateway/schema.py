from pydantic import BaseModel, Field, EmailStr, SecretStr, ConfigDict

class UserRegisterRequest(BaseModel):
    first_name: str = Field(..., max_length=20)
    last_name: str = Field(..., max_length=20)
    email: EmailStr
    password: SecretStr = Field(..., min_length=8)

    model_config = ConfigDict(frozen=True, extra="forbid")


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(..., min_length=8)

    model_config = ConfigDict(frozen=True, extra="forbid")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = Field(default="bearer")
