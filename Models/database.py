## Create DataBase script

import Models
from sqlmodel import SQLModel, create_engine

def create_db():
    
    print("abs")

    SQLModel.metadata.create_all(Models.engine)

    print("created")

if __name__ == "__main__":
    create_db()

    input()