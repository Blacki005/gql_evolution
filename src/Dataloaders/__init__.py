# from uoishelpers.dataloaders import createIdLoader, createFkeyLoader
# from functools import cache

from src.DBDefinitions import BaseModel
from src.DBDefinitions import (
    EventModel,
    EventInvitationModel,
    FragmentModel,
)

from uoishelpers.dataloaders.LoaderMapBase import LoaderMapBase
from uoishelpers.dataloaders.IDLoader import IDLoader
import src.DBDefinitions

class LoaderMap(LoaderMapBase[BaseModel]):
    """LoaderMap is a map of IDLoaders for all models in the BaseModel registry.
    It is used to create loaders for all models in the BaseModel registry.
    """
    BaseModel = BaseModel

    EventModel: IDLoader[src.DBDefinitions.EventModel] = None
    EventInvitationModel: IDLoader[src.DBDefinitions.EventInvitationModel] = None
    FragmentModel: IDLoader[src.DBDefinitions.FragmentModel] = None


    def __init__(self, session):
        super().__init__(session)

        self.EventModel = self.get(EventModel)
        self.EventInvitationModel = self.get(EventInvitationModel)
        self.FragmentModel = self.get(FragmentModel)

        # print(f"LoaderMap created with session: {session}")

def createLoadersContext(session):
    return {
        "loaders": LoaderMap(session)
    }
