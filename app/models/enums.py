"""Lookup tables for model fields."""

# Position code (stored in the database) -> display name (returned by the API)
POSITIONS: dict[str, str] = {
    "GK": "Goalkeeper",
    "CB": "Center-Back",
    "LB": "Left-Back",
    "RB": "Right-Back",
    "CDM": "Defensive Midfielder",
    "CM": "Center Midfielder",
    "CAM": "Attacking Midfielder",
    "LM": "Left Midfielder",
    "RM": "Right Midfielder",
    "ST": "Striker",
    "CF": "Center-Forward",
    "LW": "Left Winger",
    "RW": "Right Winger",
}
