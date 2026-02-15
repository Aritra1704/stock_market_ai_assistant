
def validate_symbol(symbol: str) -> str:
    clean = symbol.strip().upper()
    if not clean.isalnum():
        raise ValueError("Symbol must be alphanumeric")
    return clean
