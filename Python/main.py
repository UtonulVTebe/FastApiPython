import Services.UserServices as User
from fastapi import FastAPI

app = FastAPI()

@app.get("/Authorization")
def Authorization(login, password):
    return User.Authorization(login, password)