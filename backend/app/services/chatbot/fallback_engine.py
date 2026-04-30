def handle_logic_error(error_type: str) -> str:
    """Standardized recovery messages for technical glitches."""
    if error_type == "search_failure":
        return (
            "I had a small issue checking the vault. Let me try that again for you! 🙏"
        )

    return "I'm with you! Could you please give me a bit more detail about the property you want?"
