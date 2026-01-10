import logging
import sys


# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

COLORS = {
    "DEBUG": "\033[35m",  # Magenta
    "INFO": "\033[34m",  # Blue
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",  # Red
    "CRITICAL": "\033[41m",  # Red Background
}

ICONS = {
    "DEBUG": "🐛",
    "INFO": "ℹ️ ",
    "WARNING": "⚠️ ",
    "ERROR": "❌",
    "CRITICAL": "🚨",
}


class AestheticFormatter(logging.Formatter):
    def __init__(self):
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        # 1. Timestamp (Dimmed)
        timestamp = self.formatTime(record, "%H:%M:%S")
        ts_str = f"{DIM}{timestamp}{RESET}"

        # 2. Level (Colored + Icon)
        color = COLORS.get(record.levelname, RESET)
        icon = ICONS.get(record.levelname, "")
        # Pad level name to 8 chars for alignment
        level_str = f"{color}{icon} {record.levelname:<8}{RESET}"

        # 3. Logger Name (Bold + Cyan-ish)
        # Truncate if too long, or pad to align
        name = record.name
        if len(name) > 15:
            name = name[:12] + "..."
        name_str = f"{BOLD}\033[36m{name:<15}{RESET}"

        # 4. Message
        # Highlight specific keywords if needed (simple implementation)
        msg = record.getMessage()
        if "Tool Call" in msg:
            msg = f"\033[92m{msg}{RESET}"  # Light green for tools
        elif "Thought" in msg:
            msg = f"\033[95m{msg}{RESET}"  # Light purple for thoughts
        elif "User" in msg:
            msg = msg.replace("User", f"{BOLD}User{RESET}")

        return f"{ts_str} | {level_str} | {name_str} | {msg}"


def setup_rich_logging(level: int = logging.INFO):
    """
    Replaces the default logging handler with a rich, aesthetic one.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    if root_logger.handlers:
        root_logger.handlers.clear()

    # Create Console Handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(AestheticFormatter())

    root_logger.addHandler(handler)

    # Silence some noisy libraries if needed
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Test log
    # logging.info("Aesthetic Logger initialized.")
