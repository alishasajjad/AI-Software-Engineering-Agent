import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task import Task
from app.schemas.task import TaskCreate


def create_task(db: Session, task_data: TaskCreate) -> Task:
    task = Task(
        title=task_data.title,
        description=task_data.description,
        repository_path=task_data.repository_path,
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return task


def get_tasks(db: Session) -> list[Task]:
    statement = select(Task).order_by(Task.created_at.desc())

    return list(db.scalars(statement).all())


def get_task(db: Session, task_id: uuid.UUID) -> Task | None:
    return db.get(Task, task_id)