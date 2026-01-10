from src.core.registry import registry, tool
from src.config import OWNER_ID


@tool
def admin_reload_skills(user_id: str) -> str:
    """
    [ADMIN ONLY] Hot-reloads all skill modules.
    Use this when you have updated the code and want to apply changes without restarting.
    """
    if str(user_id).strip() != str(OWNER_ID).strip():
        return f"❌ ACCESS DENIED. User ID {user_id} does not match Owner ID."

    try:
        result = registry.reload_all()
        return f"✅ **System Reloaded**\n{result}"
    except Exception as e:
        return f"❌ Reload Failed: {e}"
