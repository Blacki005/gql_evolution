import os

from functools import cache
from uoishelpers.feeders import ImportModels
from uoishelpers.dataloaders import readJsonFile

from src.DBDefinitions import (
    EventModel, 
    EventInvitationModel,
)

get_demodata = lambda :readJsonFile(jsonFileName="./systemdata.json")
async def initDB(asyncSessionMaker, filename="./systemdata.json"):

    dbModels = [
    ]
    
    isDemo = os.environ.get("DEMODATA", None) in ["True", "true", True]
    if isDemo:
        print("Demo mode", flush=True)
        dbModels = [
            EventModel, 
            EventInvitationModel,
        ]
        

    jsonData = readJsonFile(filename)
    await ImportModels(asyncSessionMaker, dbModels, jsonData)
    
    print("Data initialized", flush=True)