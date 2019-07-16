import os
import pathlib
import subprocess


home = os.path.expanduser("~")
MAIN_DIR = os.path.join(home, ".datapod")
USER_INDEX = f"{MAIN_DIR}/user.index"
KEYS_DIR = os.path.join(MAIN_DIR, "keys")
USERDATA_PATH = os.path.join(MAIN_DIR, "userdata")
PARSED_DATA_PATH = os.path.join(USERDATA_PATH, "parsed")
RAW_DATA_PATH = os.path.join(USERDATA_PATH, "raw")



class Config:
   pass



#openssl rand -out .key 32
class DevelopmentConfig(Config):   
    DIR = os.path.dirname(os.path.abspath(__file__))
    GITHUB_OUTPUT_DIR = os.path.join(DIR, "account") 

 
config_object = DevelopmentConfig