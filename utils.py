import google.generativeai as genai
import os
from typing import List, Dict

def init_genai():
    """Initialize the Gemini API client"""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not set")

    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-pro')

def analyze_ingredients(model, user_profile: Dict, ingredients: List[str]) -> Dict:
    """
    Analyze ingredients using Gemini API based on user profile
    """
    try:
        prompt = f"""
        Analyze the following ingredients for dietary safety based on this user profile:

        User Profile:
        - Age: {user_profile['age']}
        - Health Conditions: {user_profile['health_conditions']}
        - Allergies: {user_profile['allergies']}
        - Dietary Restrictions: {user_profile['dietary_restrictions']}

        Ingredients to analyze:
        {', '.join(ingredients)}

        For each ingredient, provide:
        1. Safety status (Safe/Unsafe/Caution)
        2. Reason for the status
        3. Recommendations or alternatives if unsafe

        Format the response as a structured analysis.
        """

        response = model.generate_content(prompt)
        return {
            'success': True,
            'analysis': response.text
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def validate_user_input(data: Dict) -> tuple[bool, str]:
    """Validate user input data"""
    if not data.get('name'):
        return False, "Name is required"

    try:
        age = int(data.get('age', 0))
        if age <= 0 or age > 120:
            return False, "Please enter a valid age"
    except ValueError:
        return False, "Age must be a number"

    try:
        height = float(data.get('height', 0))
        weight = float(data.get('weight', 0))
        if height <= 0 or weight <= 0:
            return False, "Height and weight must be positive numbers"
    except ValueError:
        return False, "Height and weight must be numbers"

    return True, ""