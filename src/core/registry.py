import inspect
import importlib
import pkgutil
import logging
from typing import Any, Callable, Dict, List


from pydantic import validate_call


logger = logging.getLogger("Registry")


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: List[Dict[str, Any]] = []
        self._loaded_modules = set()  # Track module objects to reload them later

    def register(self, func: Callable):
        """Decorator to register a function as a tool."""

        # 1. Store the executable function (validated by Pydantic)
        validated_func = validate_call(func)
        self._tools[func.__name__] = validated_func

        # 2. Generate JSON Schema for Groq
        schema = self._generate_schema(func)
        self._schemas.append(schema)

        return validated_func

    def _generate_schema(self, func: Callable) -> Dict:
        """
        Reflects on the function to build a JSON schema for Groq/OpenAI.
        Parses Google/NumPy style docstrings to extract parameter descriptions.
        """
        sig = inspect.signature(func)
        docstring = func.__doc__ if func.__doc__ else ""

        # Parse docstring for param descriptions
        param_docs = {}
        if docstring:
            # Simple parsing for "Args:" or "Parameters:" sections
            lines = [line.strip() for line in docstring.split("\n")]
            current_param = None
            in_args = False

            for line in lines:
                if line.lower().startswith(("args:", "parameters:", "arguments:")):
                    in_args = True
                    continue

                if in_args:
                    if ":" in line:
                        # Likely "param_name: description"
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            current_param = parts[0].strip()
                            param_docs[current_param] = parts[1].strip()
                    elif current_param and line and not line.startswith("-"):
                        # Continuation of description
                        param_docs[current_param] += " " + line
                    elif not line:
                        # Empty line might end the section
                        pass

        parameters = {"type": "object", "properties": {}, "required": []}

        type_map = {str: "string", int: "integer", float: "number", bool: "boolean"}

        for param_name, param in sig.parameters.items():
            param_type = type_map.get(param.annotation, "string")

            # Get description from parsed docstring or default
            description = param_docs.get(param_name, f"Parameter: {param_name}")

            parameters["properties"][param_name] = {
                "type": param_type,
                "description": description,
            }
            if param.default == inspect.Parameter.empty:
                parameters["required"].append(param_name)

        return {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": docstring.split("Args:")[0].strip()
                if "Args:" in docstring
                else docstring.strip(),
                "parameters": parameters,
            },
        }

    def get_tool(self, name: str) -> Callable:
        return self._tools.get(name)

    def get_schemas(self) -> List[Dict]:
        return self._schemas

    def load_skills(self, package_name: str):
        """
        Dynamically import all modules in a package (directory).
        This executes the @tool decorators in those files, registering them.
        """
        try:
            # Import the package first
            package = importlib.import_module(package_name)

            # Walk through all modules in the package
            if hasattr(package, "__path__"):
                for _, name, _ in pkgutil.iter_modules(package.__path__):
                    full_name = f"{package_name}.{name}"
                    try:
                        mod = importlib.import_module(full_name)
                        self._loaded_modules.add(mod)
                        logger.info(f"Loaded skill module: {full_name}")
                    except Exception as e:
                        logger.error(f"Failed to load skill {full_name}: {e}")
            else:
                logger.warning(f"{package_name} is not a package.")

        except Exception as e:
            logger.error(f"Failed to load skills from {package_name}: {e}")

    def reload_all(self) -> str:
        """
        Reloads all previously loaded skill modules.
        This updates code and re-registers tools without restarting the bot.
        """
        try:
            # 1. Clear current registry
            self._tools.clear()
            self._schemas.clear()

            reloaded_count = 0

            # 2. Iterate and reload
            # We copy the set because reload() technically executes the module code again,
            # which might trigger imports. But here we just want to refresh what we have.
            modules_to_reload = list(self._loaded_modules)

            for mod in modules_to_reload:
                try:
                    importlib.reload(mod)
                    reloaded_count += 1
                    logger.info(f"Reloaded module: {mod.__name__}")
                except Exception as e:
                    logger.error(f"Failed to reload {mod.__name__}: {e}")

            return f"Successfully reloaded {reloaded_count} skill modules."

        except Exception as e:
            return f"Critical error during reload: {e}"


# Global Instance
registry = ToolRegistry()
tool = registry.register
