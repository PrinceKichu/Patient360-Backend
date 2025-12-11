TEMPLATES = {
    'Greetings' : 'welcome_journey',
    'Diet': 'diet_plan_temp',
    'Exercise': 'exercise_plan_temp',
    'Routine': 'routine_plan_temp',
    'HealthSummary': 'summary',
    'summary1': 'summary1'
}

def get_template_name(plan_type: str) -> str:
    """Get the template name based on the plan type."""
    return TEMPLATES.get(plan_type, None)
