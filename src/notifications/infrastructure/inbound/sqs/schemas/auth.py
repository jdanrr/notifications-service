"""Esquema del detail de UserRegistered (source kenko.auth).

Solo declara los campos que Notifications consume. El resto se ignora.
"""

from pydantic import BaseModel, ConfigDict, Field

from notifications.infrastructure.inbound.sqs.schemas.common import EventMetadata


class Person(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    first_name: str = Field(alias="firstName")


class Contact(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: str | None = None
    email_verified: bool = Field(default=False, alias="emailVerified")


class UserRegisteredData(BaseModel):
    person: Person
    contact: Contact


class UserRegisteredDetail(BaseModel):
    metadata: EventMetadata
    data: UserRegisteredData
