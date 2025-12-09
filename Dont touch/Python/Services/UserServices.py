import sqlite3

def Authorization(login, password):
    if (login and password):
        return {"Response": "Succefull"}
    return {"Response": "NoSucefful"}