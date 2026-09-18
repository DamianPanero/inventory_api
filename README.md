# Inventory API — FastAPI + PostgreSQL + JWT + Docker

REST API for product inventory management with user authentication. Each user can only manage their own products.

## Tech Stack

- Python 3.11
- FastAPI (async)
- SQLAlchemy 2.0 (async ORM)
- PostgreSQL
- JWT Authentication (python-jose + pwdlib)
- Docker + Docker Compose

## Features

- User registration and login with JWT authentication
- Password hashing with Argon2
- Each user manages only their own products
- Full CRUD for products
- Async endpoints with PostgreSQL

## Endpoints

### Auth
| Method | Route | Description | Auth required |
|--------|-------|-------------|---------------|
| POST | `/register` | Register a new user | No |
| POST | `/login` | Login and get JWT token | No |
| GET | `/me` | Get current user info | Yes |

### Products
| Method | Route | Description | Auth required |
|--------|-------|-------------|---------------|
| GET | `/products` | List all your products | Yes |
| GET | `/products/{id}` | Get a product by ID | Yes |
| POST | `/products` | Create a new product | Yes |
| PATCH | `/products/{id}` | Update a product | Yes |
| DELETE | `/products/{id}` | Delete a product | Yes |

## Getting Started

### With Docker (recommended)

```bash
git clone https://github.com/DamianPanero/inventario_api
cd inventario_api
```

Create a `.env` file:
```env
DATABASE_URL=postgresql+asyncpg://usuario:password@db:5432/inventario_db
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

```bash
docker-compose up --build
```

API available at `http://localhost:8000`  
Interactive docs at `http://localhost:8000/docs`

### Without Docker

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## Project Structure
├── main.py
├── .env
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .gitignore