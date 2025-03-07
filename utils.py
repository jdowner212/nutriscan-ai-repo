import google.generativeai as genai
import os
from typing import List, Dict
import pytesseract
from PIL import Image
import cv2
import numpy as np
import io

def init_genai():
    """Initialize the Gemini API client"""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not set. Please check your API key configuration.")

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-pro')
        # Test the model with a simple prompt to ensure it's working
        test_response = model.generate_content("Test connection")
        if not test_response:
            raise ValueError("Could not get a response from the API")
        return model
    except Exception as e:
        raise Exception(f"Failed to initialize Gemini API: {str(e)}")

def process_nutrition_image(image: Image.Image) -> str:
    """
    Process nutrition facts image and extract text
    """
    try:
        # Convert PIL Image to OpenCV format
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        # Image preprocessing
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

        # OCR
        text = pytesseract.image_to_string(thresh)

        if not text.strip():
            return None

        return text.strip()
    except Exception as e:
        raise Exception(f"Failed to process image: {str(e)}")

def analyze_ingredients(model, user_profile: Dict, ingredients: List[str]) -> Dict:
    """
    Analyze ingredients using Gemini API based on user profile
    """
    try:
        # Format health conditions and allergies for better readability
        health_conditions = user_profile.get('health_conditions', '').strip() or 'None reported'
        allergies = user_profile.get('allergies', '').strip() or 'None reported'
        dietary_restrictions = ', '.join(user_profile.get('dietary_restrictions', ['None']))

        prompt = f"""
As a dietary safety expert, analyze these ingredients and nutrition information for a person with the following profile:

USER PROFILE:
- Age: {user_profile['age']} years
- Health Conditions: {health_conditions}
- Allergies: {allergies}
- Dietary Restrictions: {dietary_restrictions}

NUTRITION INFORMATION:
{ingredients[0]}

Please provide a detailed analysis in the following format:

ANALYSIS SUMMARY:
[Overall safety assessment]

NUTRITIONAL ANALYSIS:
- Key Ingredients: [List main ingredients and their implications]
- Allergen Status: [Identify potential allergens]
- Dietary Compliance: [Check against dietary restrictions]
- Health Impact: [Consider health conditions]

RECOMMENDATIONS:
[Provide specific recommendations based on the user's profile]

Please be thorough and consider all health conditions, allergies, and dietary restrictions in your analysis.
"""

        response = model.generate_content(prompt)
        return {
            'success': True,
            'analysis': response.text
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Analysis failed: {str(e)}"
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