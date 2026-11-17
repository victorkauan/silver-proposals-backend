from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.db import Base


class Parent(Base):
    __tablename__ = "parent"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True)


class Child(Base):
    __tablename__ = "child"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("parent.id"))


def test_constraints_follow_naming_convention() -> None:
    parent = Base.metadata.tables["parent"]
    child = Base.metadata.tables["child"]

    assert parent.primary_key.name == "pk_parent"
    assert {c.name for c in parent.constraints} >= {"pk_parent", "uq_parent_code"}
    assert {fk.name for fk in child.foreign_key_constraints} == {"fk_child_parent_id_parent"}
