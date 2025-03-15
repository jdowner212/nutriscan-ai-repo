import google.generativeai as genai
import os
from typing import List, Dict, Optional, Tuple
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import requests
import json
from PIL import Image
import pytesseract
import re
import streamlit as st
from dotenv import load_dotenv
from auth import get_user_profiles_from_s3, save_user_profiles_to_s3

# Load environment variables from .env
load_dotenv('.env')

def create_custom_header():
    """Create a consistent header across all pages"""
    st.markdown("""
    <div class="main-header">
        <div class="brand-header">🛒 NutriScan AI</div>
    </div>
    <div class="header-divider"></div>
    """, unsafe_allow_html=True)


def init_genai():
    """Initialize the Gemini API client"""
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
    except:
        api_key = st.secrets["api"]["GOOGLE_API_KEY"]

    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not set. Please check your API key configuration.")

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
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

def scan_barcode(image: np.ndarray) -> Optional[str]:
    """
    Scan barcode from image and return the barcode number
    """
    try:
        # Convert image to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Decode barcodes
        barcodes = decode(gray)

        # Return the first barcode found
        if barcodes:
            barcode = barcodes[0].data.decode('utf-8')
            return barcode
        return None
    except Exception as e:
        raise Exception(f"Failed to scan barcode: {str(e)}")

def get_product_info(barcode: str) -> Optional[Dict]:
    """
    Retrieve product information from Open Food Facts API
    """
    print('DEBUG - Getting product info for barcode:', barcode)
    try:
        # Make API request to Open Food Facts
        url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
        response = requests.get(url)
        data = response.json()

        if data.get('status') != 1:
            return None

        product = data['product']

        # Extract relevant information
        nutrition_info = {
            'product_name': product.get('product_name', 'Unknown Product'),
            'serving_size': product.get('serving_size', 'Not specified'),
            'calories': product.get('nutriments', {}).get('energy-kcal_100g', 'Not specified'),
            'ingredients': product.get('ingredients_text', ''),
            'allergens': product.get('allergens_hierarchy', []),
            'nutrients': {
                'fat': product.get('nutriments', {}).get('fat_100g', 'Not specified'),
                'proteins': product.get('nutriments', {}).get('proteins_100g', 'Not specified'),
                'carbohydrates': product.get('nutriments', {}).get('carbohydrates_100g', 'Not specified'),
                'sugars': product.get('nutriments', {}).get('sugars_100g', 'Not specified'),
                'fiber': product.get('nutriments', {}).get('fiber_100g', 'Not specified'),
                'sodium': product.get('nutriments', {}).get('sodium_100g', 'Not specified')
            }
        }

        return nutrition_info
    except Exception as e:
        print('DEBUG - failed to retrieve product information')
        raise Exception(f"Failed to retrieve product information: {str(e)}")

def format_nutrition_info(info: Dict) -> str:
    """
    Format nutrition information for analysis
    """
    nutrients_text = "\n".join([
        f"{key.capitalize()}: {value}g per 100g"
        for key, value in info['nutrients'].items()
        if value != 'Not specified'
    ])

    allergens_text = ", ".join([
        allergen.replace('en:', '') for allergen in info['allergens']
    ]) or "None listed"

    formatted_text = f"""
Nutrition Facts for {info['product_name']}:
Serving Size: {info['serving_size']}
Calories: {info['calories']} kcal per 100g

Ingredients: {info['ingredients']}

Allergen Information: {allergens_text}

Nutrient Information per 100g:
{nutrients_text}
"""

    return formatted_text.strip()

def analyze_ingredients(model, user_profile: Dict, nutrition_info: str) -> Dict:
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
{nutrition_info}

Please provide a comprehensive analysis in the following format. Emphasize readability and clarity for the user, utilizing formatting tricks like bullet points and varied text styles:

SAFETY ASSESSMENT:
[Provide an overall safety rating (Safe/Caution/Unsafe) and brief explanation]

FURTHER ANALYSIS -- each should be brief with detail only if important as a warning to the user given their health profile:
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

Please prioritize accuracy and be specific about any health risks or concerns. If a food is safe but not extremely healthy (like chocolate), it is still considered safe.
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



# Add these functions to store and retrieve product history

def save_product_to_history(username, product_info, analysis_results):
    """Save analyzed product to user's history"""
    try:
        print(f"DEBUG - Saving product to history: {product_info.get('product_name')}")

        # Get current user's product history
        profiles = get_user_profiles_from_s3()
        user_profile = profiles.get(username, {})
        
        # Initialize product history if it doesn't exist
        if 'product_history' not in user_profile:
            user_profile['product_history'] = []

        # Get barcode for comparison
        barcode = product_info.get('barcode', '')
        print(f"DEBUG - Looking for existing product with barcode: {barcode}")
        
        # Track if we found and replaced an existing product
        replaced = False

        # Look for existing product with same barcode and replace it
        if barcode:
            for i, product in enumerate(user_profile['product_history']):
                if product.get('barcode') == barcode:
                    print(f"DEBUG - Found existing product at index {i}, replacing it")
                    
                    # Create new history entry
                    from datetime import datetime
                    product_entry = {
                        'product_id': product_info.get('id', ''),
                        'barcode': barcode,
                        'product_name': product_info.get('product_name', 'Unknown Product'),
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'analysis_summary': extract_analysis_summary(analysis_results),
                        'safety_rating': extract_safety_rating(analysis_results),
                        'full_analysis': analysis_results,
                        'nutrition_info': {
                            'serving_size': product_info.get('serving_size', 'Not specified'),
                            'calories': product_info.get('calories', 'Not specified'),
                            'nutrients': product_info.get('nutrients', {})
                        }
                    }
                    
                    # Replace the existing entry
                    user_profile['product_history'][i] = product_entry
                    replaced = True
                    break


        # If we didn't replace an existing entry, add as new
        if not replaced:
            print(f"DEBUG - No existing product found, adding as new entry")
            
            # Create new history entry
            from datetime import datetime
            product_entry = {
                'product_id': product_info.get('id', ''),
                'barcode': barcode,
                'product_name': product_info.get('product_name', 'Unknown Product'),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'analysis_summary': extract_analysis_summary(analysis_results),
                'safety_rating': extract_safety_rating(analysis_results),
                'full_analysis': analysis_results,
                'nutrition_info': {
                    'serving_size': product_info.get('serving_size', 'Not specified'),
                    'calories': product_info.get('calories', 'Not specified'),
                    'nutrients': product_info.get('nutrients', {})
                }
            }
            
            # Add to the beginning of history
            user_profile['product_history'].insert(0, product_entry)
            
            # Keep only the most recent 20 products
            if len(user_profile['product_history']) > 20:
                user_profile['product_history'] = user_profile['product_history'][:20]
        
        # Save updated profile
        profiles[username] = user_profile
        save_result = save_user_profiles_to_s3(profiles)
        print(f"DEBUG - Save result: {save_result}")
        
        return True
    except Exception as e:
        print(f"DEBUG - Error saving product to history: {str(e)}")
        st.error(f"Failed to save product to history: {str(e)}")
        return False


def get_product_history(username):
    """Get user's product scan history"""
    try:
        profiles = get_user_profiles_from_s3()
        user_profile = profiles.get(username, {})
        return user_profile.get('product_history', [])
    except Exception as e:
        st.error(f"Failed to retrieve product history: {str(e)}")
        return []


def get_product_from_history(username, barcode):
    """Check if product exists in history and return its data"""
    try:
        product_history = get_product_history(username)
        for product in product_history:
            # Check if barcode matches or product name matches
            if product.get('barcode') == barcode:
                return product
        return None
    except Exception as e:
        st.error(f"Error checking product history: {str(e)}")
        return None

def extract_safety_rating(analysis):
    """Extract safety rating from analysis text"""
    try:
        if "SAFETY ASSESSMENT:" in analysis:
            # safety_section = analysis.split("SAFETY ASSESSMENT:")[1].split("\n")[0].strip()
            safety_text = analysis.split("SAFETY ASSESSMENT:")[1]
            lines = safety_text.split("\n")
            print(f"Debug - First 3 lines after split: {lines[:3]}")
            # Check the next few lines for safety indicators
            lines = safety_text.split("\n")
            print(f"Debug - First 3 lines after split: {lines[:3]}")
            
            # Check the first few non-empty lines
            for line in lines[:3]:
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                    
                print(f"Debug - Checking line: '{line}'")
                # Look for rating keywords in this line
                if "Safe" in line or "safe" in line:
                    print(f"Debug - Found 'Safe' in: '{line}'")
                    return "Safe"
                elif "Caution" in line or "caution" in line or "Moderate" in line:
                    print(f"Debug - Found 'Caution' in: '{line}'")
                    return "Caution"
                elif "Unsafe" in line or "unsafe" in line or "Avoid" in line:
                    print(f"Debug - Found 'Unsafe' in: '{line}'")
                    return "Unsafe"
                
            # If we get here, no rating was found in the first few lines
            print(f"Debug - No rating found in first few lines")
        else:
            print(f"Debug - 'SAFETY ASSESSMENT:' not found in text")
        return "Unknown"
    except Exception as e:
        print(f"Debug - Error in extract_safety_rating: {str(e)}")
        return "Unknown"

def extract_analysis_summary(analysis):
    """Extract a brief summary from the full analysis"""
    try:
        if "SAFETY ASSESSMENT:" in analysis:
            # Get the first paragraph after SAFETY ASSESSMENT
            summary = analysis.split("SAFETY ASSESSMENT:")[1].split("\n\n")[0]
            return summary.strip()
        return "No summary available"
    except:
        return "No summary available"

# Update your barcode scanning step to check history first
def check_product_history_before_api(barcode, username):
    """Check if product exists in history before calling API"""
    print(f"Debug - Checking history for barcode: {barcode}, username: {username}")

    if not username:
        return None
        
    # Check history first
    historical_product = get_product_from_history(username, barcode)

    if historical_product:
        analysis = historical_product.get('full_analysis')

        return {
            'from_history': True,
            'product_info': {
                'product_name': historical_product['product_name'],
                'serving_size': historical_product['nutrition_info']['serving_size'],
                'calories': historical_product['nutrition_info']['calories'],
                'nutrients': historical_product['nutrition_info']['nutrients'],
                'barcode': historical_product['barcode'],
                'allergens': historical_product.get('allergens',[]), 
            },
            'analysis_results': analysis
        }
    
    return None


def get_barcode_next_steps(barcode):
    """Process a detected barcode - check history or fetch from API"""
    # First check history before making API call
    username = st.session_state.get('username')
    historical_data = check_product_history_before_api(barcode, username)
    
    # Set up the container to display only one UI section at a time
    with st.container():
        # Case 1: Product found in history
        if historical_data and historical_data.get('from_history'):
            st.session_state.scan_state = 'found_in_history'
            st.session_state.current_product = historical_data['product_info']
            st.session_state.barcode_scanned = True
            st.session_state.historical_data = historical_data
        
        # Case 2: New product from API
        else:
            with st.spinner("Retrieving product information..."):
                product_info = get_product_info(barcode)
                if product_info:
                    product_info['barcode'] = barcode
                    st.session_state.current_product = product_info
                    st.session_state.barcode_scanned = True
                    st.session_state.scan_state = 'showing_details'
                else:
                    st.error("Could not find product information. Please try a different product.")
                    st.session_state.scan_state = 'ready'
                    st.session_state.barcode_scanned = False



def display_product_verification(barcode, key_suffix=""):
    """Display the product verification UI"""
    st.subheader(st.session_state.current_product['product_name'])
    
    with st.expander("Nutrition Details", expanded=True):
        st.markdown(f"**Serving Size:** {st.session_state.current_product['serving_size']}")
        st.markdown(f"**Calories:** {st.session_state.current_product['calories']} kcal per 100g")
        
        # Add more nutrition info within the expander if available
        if 'nutrients' in st.session_state.current_product:
            st.markdown("**Nutrients per 100g:**")
            for key, value in st.session_state.current_product['nutrients'].items():
                if value != 'Not specified':
                    st.markdown(f"- {key.capitalize()}: {value}g")
    
    st.markdown("### Is this the correct product?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Yes, analyze this product", key=f"confirm{key_suffix}"):
            run_analyze(barcode)
                    
    with col2:
        if st.button("❌ No, scan again", key=f"reject{key_suffix}"):
            st.session_state.barcode_scanned = False
            st.session_state.current_product = None
            st.session_state.scan_state = 'ready'
            st.rerun()

def run_analyze(barcode):
    st.session_state.current_product['barcode'] = barcode
    formatted_info = format_nutrition_info(st.session_state.current_product)
    
    with st.spinner("Analyzing nutritional information..."):
        model = init_genai()
        analysis_result = analyze_ingredients(model, st.session_state.user_data, formatted_info)
        
        if analysis_result['success']:
            # Save results to history
            username = st.session_state.get('username')
            if username:
                save_product_to_history(
                    username, 
                    st.session_state.current_product, 
                    analysis_result['analysis']
                )

            st.session_state.analysis_results = analysis_result['analysis']
            st.session_state.analysis_success = analysis_result['success']
            st.session_state.step = 'results'
            st.session_state.barcode_scanned = False
            st.session_state.current_product = None
            st.rerun()
        else:
            st.error(f"Analysis failed: {analysis_result['error']}")
            # st.session_state.step = 'results'
            st.session_state.step = 'barcode_scanning'
            st.rerun()



def handle_barcode(barcode):
    get_barcode_next_steps(barcode)
    if st.session_state.barcode_scanned:
        # Display the appropriate UI based on scan state
        if st.session_state.scan_state == 'found_in_history':
            with st.container():
                st.info("This product has been analyzed before. What would you like to do?")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("View Previous Analysis"):
                        st.session_state.analysis_results = st.session_state.historical_data['analysis_results']
                        st.session_state.step = 'results'
                        st.session_state.from_history = True
                        st.rerun()
                with col2:
                    if st.button("Analyze Again"):
                        product_info = get_product_info(barcode)
                        # print('DEBUG: product_info:', product_info)
                        if product_info:
                            product_info['barcode'] = barcode
                            st.session_state.current_product = product_info
                            st.session_state.barcode_scanned = True
                            st.session_state.scan_state = 'showing_details'
                            st.session_state.run_analysis_for_barcode = barcode
                            st.rerun()
                        # run_analyze(barcode)
        
        elif st.session_state.scan_state == 'showing_details':
            with st.container():
                # Show product verification UI
                st.success("Product found! Please verify the details below:")
                display_product_verification(st.session_state.current_product.get('barcode', ''))