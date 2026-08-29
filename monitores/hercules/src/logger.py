from datetime import datetime


def log(message: str) -> None:
    """Log simple por consola. No crea archivos."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}")
