import google.generativeai as genai
import os
from typing import List, Dict, Optional
import pytesseract
from PIL import Image
import cv2
import numpy as np
import io
import re

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

def enhance_image(image: np.ndarray) -> np.ndarray:
    """
    Enhance image quality for better OCR
    """
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Noise removal
    denoised = cv2.fastNlMeansDenoising(gray)

    # Thresholding
    thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    # Dilation
    kernel = np.ones((1, 1), np.uint8)
    dilated = cv2.dilate(thresh, kernel, iterations=1)

    return dilated

def extract_nutrition_info(text: str) -> Dict[str, str]:
    """
    Extract structured nutrition information from OCR text
    """
    info = {
        'serving_size': '',
        'calories': '',
        'ingredients': '',
        'allergens': '',
        'nutrients': []
    }

    lines = text.split('\n')
    current_section = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Identify sections
        lower_line = line.lower()
        if 'serving size' in lower_line:
            info['serving_size'] = re.sub(r'serving size[: ]*', '', line, flags=re.IGNORECASE)
        elif 'calories' in lower_line:
            info['calories'] = re.sub(r'calories[: ]*', '', line, flags=re.IGNORECASE)
        elif 'ingredients' in lower_line:
            current_section = 'ingredients'
        elif 'contains' in lower_line and ('allergen' in lower_line or any(allergen in lower_line for allergen in ['milk', 'soy', 'nuts', 'wheat'])):
            info['allergens'] = line
        elif current_section == 'ingredients':
            info['ingredients'] += ' ' + line
        elif re.match(r'^[\d.]+ *[g|mg|%]', line):
            info['nutrients'].append(line)

    return info

def process_nutrition_image(image: Image.Image) -> Optional[str]:
    """
    Process nutrition facts image and extract text with enhanced preprocessing
    """
    try:
        # Convert PIL Image to OpenCV format
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        # Image preprocessing pipeline
        processed_img = enhance_image(img_cv)

        # Configure OCR parameters for better accuracy
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(processed_img, config=custom_config)

        if not text.strip():
            return None

        # Extract structured information
        nutrition_info = extract_nutrition_info(text)

        # Format the information for analysis
        formatted_text = f"""
Nutrition Facts:
Serving Size: {nutrition_info['serving_size']}
Calories: {nutrition_info['calories']}

Ingredients: {nutrition_info['ingredients']}

Allergen Information: {nutrition_info['allergens']}

Nutrient Information:
{chr(10).join(nutrition_info['nutrients'])}
"""

        return formatted_text.strip()
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
As a nutrition and dietary safety expert, analyze this nutrition label for a person with the following profile:

USER PROFILE:
- Age: {user_profile['age']} years
- Health Conditions: {health_conditions}
- Allergies: {allergies}
- Dietary Restrictions: {dietary_restrictions}

NUTRITION INFORMATION:
{ingredients[0]}

Please provide a comprehensive analysis in the following format:

SAFETY ASSESSMENT:
[Provide an overall safety rating (Safe/Caution/Unsafe) and brief explanation]

DETAILED ANALYSIS:
1. Allergen Risk:
   - Known allergens present
   - Cross-contamination risks
   - Severity level for user's specific allergies

2. Dietary Compliance:
   - Compatibility with dietary restrictions
   - Any conflicting ingredients

3. Nutritional Impact:
   - Key nutrients and their relevance to user's health conditions
   - Portion size considerations
   - Caloric and macro-nutrient assessment

4. Health Considerations:
   - Specific impacts on user's health conditions
   - Potential interactions with medications (if any)
   - Long-term consumption considerations

RECOMMENDATIONS:
- Specific advice for safe consumption
- Suggested alternatives (if needed)
- Portion size recommendations

Please prioritize accuracy and be specific about any health risks or concerns.
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