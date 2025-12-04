import yaml
from pathlib import Path


CONFIG_PATH = Path("config/users.yaml")


def _load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    # 默认占位配置
    return {
        "credentials": {
            "usernames": {
                "user_economy": {"email": "economy@school", "name": "经济学院", "password": "REPLACE_WITH_HASH"},
                "user_finance": {"email": "finance@school", "name": "金融学院", "password": "REPLACE_WITH_HASH"},
                "user_intl": {"email": "intl@school", "name": "国商学院", "password": "REPLACE_WITH_HASH"},
                "user_west": {"email": "west@school", "name": "西部学院", "password": "REPLACE_WITH_HASH"},
                "user_tax": {"email": "tax@school", "name": "财税学院", "password": "REPLACE_WITH_HASH"},
                "user_mgmt": {"email": "mgmt@school", "name": "经管学院", "password": "REPLACE_WITH_HASH"},
                "admin": {"email": "admin@school", "name": "管理员", "password": "REPLACE_WITH_HASH"},
            }
        },
        "cookie": {"name": "auth_cookie", "key": "random_key", "expiry_days": 1},
        "preauthorized": {"emails": []},
    }


def get_authenticator():
    import streamlit_authenticator as stauth
    config = _load_config()
    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )
    return authenticator


def get_user_info(username: str) -> dict:
    # 优先从配置读取中文名与学院代码
    cfg = _load_config()
    users = cfg.get("credentials", {}).get("usernames", {})
    info = users.get(username, {})
    display = info.get("name", username)
    # 推断学院代码
    if username == "admin":
        college = "admin"
        role = "admin"
    else:
        role = "user"
        college = info.get("college_code")
        if not college and username.startswith("user_"):
            college = username.split("_", 1)[1]
        college = college or "unknown"
    return {"display": display, "role": role, "college": college}
