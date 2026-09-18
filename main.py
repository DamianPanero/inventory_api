from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from typing import Annotated, AsyncGenerator
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from pwdlib import PasswordHash
from jose import jwt, JWTError
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase
from sqlalchemy.ext.asyncio import( async_sessionmaker, AsyncSession,create_async_engine)
from sqlalchemy import ForeignKey, select

#config
class Settings(BaseSettings):
    database_url:str
    secret_key:str
    algorithm:str
    access_token_expire_minutes:int
    model_config=SettingsConfigDict(env_file='.env')
settings=Settings()

#hash

password_hash=PasswordHash.recommended()

def hash_password(password:str)->str:
    return password_hash.hash(password)

def verify_password(plain:str,hashed:str)->bool:
    return password_hash.verify(plain,hashed)

#DB
engine=create_async_engine(settings.database_url, echo=True)

AsyncSessionLocal=async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

#models

class User(Base):
    __tablename__='users'
    id:Mapped[int]=mapped_column(primary_key=True, autoincrement=True)
    username:Mapped[str]=mapped_column(nullable=False,unique=True)
    hashed_password:Mapped[str]=mapped_column(nullable=False)
    products:Mapped[list["Product"]]=relationship(back_populates='owner', cascade='all, delete-orphan')

class Product(Base):
    __tablename__='products'
    id:Mapped[int]=mapped_column(primary_key=True, autoincrement=True)
    name:Mapped[str]=mapped_column(nullable=False)
    price:Mapped[float]=mapped_column(nullable=False)
    stock:Mapped[int]=mapped_column(nullable=False, default=0)
    owner_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    owner:Mapped[User]=relationship(back_populates='products')

#create tables

async def create_table():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@asynccontextmanager
async def lifespan(app:FastAPI):
    await create_table()
    yield

#pydantic models

class CreateUser(BaseModel):
    username:str
    password:str

class Token(BaseModel):
    access_token:str
    token_type:str

class TokenData(BaseModel):
    username:str | None=None

class CreateProduct(BaseModel):
    name:str
    price:float
    stock:int

class UpdateProduct(BaseModel):
    name:str | None=None
    price:float | None=None
    stock:int | None=None

class ProductResponse(BaseModel):
    id:int
    name:str
    price:float
    stock:int
    owner_id:int

#access token

def create_access_token(data:dict)->str:
    to_encode=data.copy()
    expire=datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp":expire})
    return jwt.encode(to_encode,settings.secret_key,algorithm=settings.algorithm)

#oauth scheme
oauth_scheme=OAuth2PasswordBearer(tokenUrl='login')
    
#dependencies

async def get_db()->AsyncGenerator[AsyncSession,None]:
    async with AsyncSessionLocal() as session:
        yield session

async def get_current_user(
        token:Annotated[str,Depends(oauth_scheme)],
        session:Annotated[AsyncSession,Depends(get_db)]
)->User:
    credentials_exception=HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Failed to validate credentials',
        headers={"WWW-Authenticate":"Bearer"}
    )
    try:
        payload=jwt.decode(token, settings.secret_key,algorithms=[settings.algorithm])
        username:str=payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data=TokenData(username=username)
    except JWTError:
        raise credentials_exception
    result=await session.execute(select(User).where(User.username==token_data.username))
    user=result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user
# reusable code
CurrentUser=Annotated[User,Depends(get_current_user)]
DBSession=Annotated[AsyncSession,Depends(get_db)]

#Instance of app
app=FastAPI(lifespan=lifespan)

#Auth endpoints
@app.post('/register', status_code=201)
async def register(data:CreateUser,session:DBSession):
    result=await session.execute(select(User).where(User.username==data.username))
    exist=result.scalar_one_or_none()
    if exist:
        raise HTTPException(
            status_code=400,
            detail='The user already exist'
        )
    user=User(username=data.username,hashed_password=hash_password(data.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return {"id":user.id,"username":user.username}

@app.post('/login', response_model=Token)
async def login(form_data:Annotated[OAuth2PasswordRequestForm,Depends()],session:DBSession):
    result=await session.execute(select(User).where(User.username==form_data.username))
    user=result.scalar_one_or_none()
    if not user or not verify_password(form_data.password,user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='The username or password are incorrect',
            headers={"WWW-Authenticate":"Bearer"}
        )
    token=create_access_token(data={"sub":user.username})
    return {"access_token":token,"token_type":"bearer"}

@app.get('/me')
async def get_me(current_user:CurrentUser):
    return {"id":current_user.id,"username":current_user.username}

#products endpoints

@app.get('/products', response_model=list[ProductResponse])
async def get_products(current_user:CurrentUser,session:DBSession):
    result=await session.execute(select(Product).where(Product.owner_id==current_user.id))
    products=result.scalars().all()
    if not products:
        raise HTTPException(
            status_code=404,
            detail="The products list is empty"
        )
    return products

@app.get('/products/{product_id}', response_model=ProductResponse)
async def get_product(product_id:int, current_user:CurrentUser, session:DBSession):
    result=await session.execute(select(Product).where(Product.id==product_id,Product.owner_id==current_user.id))
    product=result.scalar_one_or_none()
    if product is None:
        raise HTTPException(
            status_code=404,
            detail="The product was not found"
        )
    return product

@app.post('/products', status_code=201, response_model=ProductResponse)
async def create_product(data:CreateProduct, current_user:CurrentUser, session:DBSession):
    product=Product(
        name=data.name,
        price=data.price,
        stock=data.stock,
        owner_id=current_user.id
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product

@app.patch('/products/{product_id}', response_model=ProductResponse)
async def update_product(product_id:int, data:UpdateProduct, current_user:CurrentUser, session:DBSession):
    result=await session.execute(select(Product).where(Product.id==product_id,Product.owner_id==current_user.id))
    product=result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=404,
            detail="The product don't exist"
        )
    if data.name is not None:
        product.name=data.name
    if data.price is not None:
        product.price=data.price
    if data.stock is not None:
        product.stock=data.stock
    await session.commit()
    await session.refresh(product)
    return product

@app.delete('/products/{product_id}')
async def delete_product(product_id:int, current_user:CurrentUser, session:DBSession):
    result= await session.execute(select(Product).where(Product.id==product_id,Product.owner_id==current_user.id))
    product=result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=404,
            detail="The product don't exist"
        )
    await session.delete(product)
    await session.commit()
    return {"message":"The product was deleted"}

if __name__=="__main__":
    import uvicorn
    uvicorn.run(app, port=8000, reload=True)


    



        

