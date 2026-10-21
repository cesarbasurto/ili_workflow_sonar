import os


class Ili2DbConfiguration:
    def __init__(self):
        self.PROCESS_ID:str = ''
        self.ILI2DB_JAR_PATH:str = ''
        self.MODEL_DIR:str = ''
        self.MODEL_NAME:str = ''
        self.SCHEMA_NAME:str = ''
        self.XTF_PATH:str = ''
        self.USE_BASKETS:bool = True
        self.DISABLE_VALIDATION = False

class DbConfiguration:
    def __init__(self):
        self.DB_HOST: str = os.getenv("DB_HOST")
        self.DB_NAME: str = os.getenv("DB_NAME")
        self.DB_USER: str = os.getenv("DB_USER")
        self.DB_PASSWORD: str = os.getenv("DB_PASSWORD")
        self.DB_PORT: int = os.getenv("DB_PORT")
