from datetime import datetime

def get_days_passed(timestamp_date: datetime) -> int:
    """Calculate the number of days passed since the given timestamp."""
    return (datetime.now() - timestamp_date).days