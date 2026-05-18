import os

def get_env(name, required=True, default=None):
    value = os.getenv(name)

    if required and (value is None or value.strip() == ""):
        raise ValueError(f"❌ {name} env değişkeni eksik!")

    return value if value is not None else default


def get_env_int(name, required=True, default=None):
    value = get_env(name, required=required, default=default)

    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        raise ValueError(f"❌ {name} geçerli bir sayı değil: {value}")


# =======================
# ENV VARIABLES (RAILWAY)
# =======================

BOT_TOKEN = get_env("BOT_TOKEN")

REQUIRED_CHANNEL_ID = get_env_int("REQUIRED_CHANNEL_ID")

REQUIRED_CHANNEL_USERNAME = get_env("REQUIRED_CHANNEL_USERNAME", required=False, default="")

DOWNLOAD_DIR = get_env("DOWNLOAD_DIR", required=False, default="downloads")


# ADMIN IDS (Railway için güvenli parse)
admins = get_env("ADMIN_IDS", required=False, default="")

ADMIN_IDS = [
    int(x.strip())
    for x in admins.split(",")
    if x.strip().isdigit()
]
