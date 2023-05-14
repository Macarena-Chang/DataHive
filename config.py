
import yaml
#config = dotenv_values(".env")

def load_config(file_path: str) -> dict:
    with open(file_path, "r") as config_file:
        return yaml.safe_load(config_file)
    
