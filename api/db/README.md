# Database Layer

SQLModel-based database layer for BeCoMe API.

## Tables

| Table | Description |
|-------|-------------|
| `users` | User accounts with authentication data |
| `projects` | Decision-making projects with scale configuration |
| `project_members` | Many-to-many: users ↔ projects with roles |
| `invitations` | Unique invitation links for joining projects |
| `expert_opinions` | Fuzzy triangular numbers from experts (unique per user+project) |
| `calculation_results` | Cached BeCoMe calculation results |
| `password_reset_tokens` | Tokens for password reset via email |

## Entity Relationships

```
users (1:N) ──► projects (admin ownership)
      │
      ├─(N:M)─► project_members ◄─(N:M)─ projects
      │
      ├─(1:N)─► expert_opinions ◄─(N:1)─ projects
      │
      ├─(1:N)─► password_reset_tokens
      │
      └─(1:N)─► invitations (used_by) ◄─(N:1)─ projects

projects (1:1) ──► calculation_results
```

## Usage

### Creating Tables

```python
from api.db.engine import create_db_and_tables

create_db_and_tables()
```

Tables are created automatically on application startup via FastAPI lifespan.

### Session Dependency

```python
from fastapi import Depends
from sqlmodel import Session

from api.db.session import get_session

@app.get("/users/{user_id}")
def get_user(user_id: UUID, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    return user
```

### Model Examples

```python
from api.db.models import User, Project, ExpertOpinion, MemberRole

# Create user
user = User(
    email="expert@example.com",
    hashed_password="$2b$12$...",
    first_name="John",
    last_name="Doe",
)

# Create project
project = Project(
    name="Budget Allocation 2024",
    description="Annual budget distribution",
    admin_id=user.id,
    scale_min=0.0,
    scale_max=100.0,
    scale_unit="%",
)

# Add expert opinion (fuzzy triangular number)
opinion = ExpertOpinion(
    project_id=project.id,
    user_id=user.id,
    position="Financial Analyst",
    lower_bound=30.0,   # pessimistic
    peak=45.0,          # most likely
    upper_bound=60.0,   # optimistic
)
```

## Configuration

Database URL is configured via environment variable:

```bash
# SQLite (default, for development)
DATABASE_URL=sqlite:///./become.db

# PostgreSQL (production)
DATABASE_URL=postgresql://user:pass@localhost:5432/become
```

## File Structure

```
api/db/
├── __init__.py     # Package marker
├── engine.py       # Database engine and table creation
├── models.py       # SQLModel table definitions
├── session.py      # FastAPI session dependency
└── README.md       # This file
```
