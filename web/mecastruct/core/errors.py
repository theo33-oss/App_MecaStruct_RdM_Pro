"""Erreur commune aux moteurs de calcul."""


class MecaStructError(Exception):
    """Erreur de calcul MecaStruct, avec un identifiant identique à MATLAB (ex. 'MecaStruct:Beam:mechanism')."""

    def __init__(self, identifier: str, message: str):
        super().__init__(message)
        self.identifier = identifier
        self.message = message

    def __str__(self) -> str:
        return self.message
