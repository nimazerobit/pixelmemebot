import json
from pathlib import Path

# Paths
CONFIG_PATH = Path("config/config.json")
TEXTS_PATH = Path("config/texts.json")

# Initial
CFG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
TEXTS = json.loads(TEXTS_PATH.read_text(encoding="utf-8"))

def reload_config():
    global CFG
    new_cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    CFG.clear()
    CFG.update(new_cfg)
    return CFG

def reload_texts():
    global TEXTS
    new_texts = json.loads(TEXTS_PATH.read_text(encoding="utf-8"))
    TEXTS.clear()
    TEXTS.update(new_texts)
    return TEXTS