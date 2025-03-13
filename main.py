import os
os.write(1,b'Something was executed.\n')


import streamlit as st
from utils import (
    init_genai, analyze_ingredients, validate_user_input,
    scan_barcode, get_product_info, format_nutrition_info
)
from PIL import Image
import numpy as np
import cv2
from auth import render_auth_ui, initialize_auth
import boto3



s3_client=boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION'),
    verify=True,
    use_ssl=True,
    config=boto3.session.Config(
        signature_version='s3v4',
        retries={'max_attempts':3},
    )
)

S3_BUCKET=os.getenv('S3_BUCKET')
S3_USERS_KEY = 'users/credentials.json'


def get_users_from_s3() -> dict:
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=S3_USERS_KEY)
        users_data = json.loads(response['Body'].read().decode('utf-8'))
        return users_data
    except s3_client.exceptions.NoSuchKey:
        return {}
    except Exception as e:
        st.error(f"An error occurred while fetching user data from S3: {str(e)}")
        return {}

def save_users_to_s3(users_data: dict) -> bool:
    try:
        users_json=json.dumps(users_data)
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=S3_USERS_KEY,
            Body=users_json
        )
        return True
    except Exception as e:
        st.error(f"An error occurred while saving to S3: {str(e)}")
        return False

def authenticate(username: str, password: str) -> bool:
    """
    Verify user credentials against S3 stored credentials.

    Args:
        username (str): The username to verify
        password (str): The plain text password to verify

    Returns:
        bool: True if credentials are valid, False otherwise
    """
    users = get_users_from_s3()
    hashed_password = hash_password(password)
    return username in users and users[username] == hashed_password

# Page configuration
st.set_page_config(
    page_title="NutriScan AI",
    page_icon="🥗",
    layout="wide"
)

# Load custom CSS
with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Initialize authentication
initialize_auth()

# Add logout button in sidebar if user is authenticated
if st.session_state.get('authenticated', False):
    with st.sidebar:
        st.write(f"👤 Logged in as: {st.session_state.get('username', '')}")
        if st.button("🚪 Logout"):
            # Clear only authentication-related state
            st.session_state['authenticated'] = False
            st.session_state['username'] = None
            st.session_state['step'] = 'welcome'  # Reset step to welcome
            st.rerun()

# Check authentication
if not st.session_state.get('authenticated', False):
    if render_auth_ui():
        st.rerun()
    st.stop()

# Initialize session state
if 'step' not in st.session_state:
    st.session_state.step = 'welcome'
if 'user_data' not in st.session_state:
    st.session_state.user_data = {}
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'current_product' not in st.session_state:
    st.session_state.current_product = None
if 'barcode_scanned' not in st.session_state:
    st.session_state.barcode_scanned = False

# Welcome Screen with distinct design
if st.session_state.step == 'welcome':
    # User greeting with personalization
    st.markdown(f"""
    <div class="welcome-container">
        <h1>Welcome, {st.session_state.get('username', 'User')}! 👋</h1>
        <p class="welcome-text">
            Let's start analyzing your food products for better dietary choices.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Quick Actions Section
    st.markdown("### 🚀 Quick Actions")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="action-card">
            <h3>📸 Scan Product</h3>
            <p>Use your camera to scan product barcodes for instant nutritional analysis</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="action-card">
            <h3>📋 Update Profile</h3>
            <p>Keep your dietary preferences and health information up to date</p>
        </div>
        """, unsafe_allow_html=True)

    # Get Started Button
    st.markdown("""
    <div style='text-align: center; margin: 2rem 0;'>
        <p class='welcome-subtitle'>Ready to analyze your first product?</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Get Started", key="welcome_button", use_container_width=True):
        st.session_state.step = 'personal_info'
        st.rerun()

    # Tips Section
    with st.expander("💡 Quick Tips"):
        st.markdown("""
        - Ensure product barcodes are clearly visible when scanning
        - Update your health profile regularly for more accurate recommendations
        - Save products you frequently consume for quick access
        """)

# Personal Information
elif st.session_state.step == 'personal_info':
    st.markdown("<h1>Tell Us About Yourself</h1>", unsafe_allow_html=True)

    with st.form("user_info_form"):
        name = st.text_input("Name", value=st.session_state.user_data.get('name', ''))
        age = st.number_input("Age", min_value=1, max_value=120, value=st.session_state.user_data.get('age', 25))
        height = st.number_input("Height (cm)", min_value=1.0, value=st.session_state.user_data.get('height', 170.0))
        weight = st.number_input("Weight (kg)", min_value=1.0, value=st.session_state.user_data.get('weight', 70.0))

        if st.form_submit_button("Continue"):
            user_data = {'name': name, 'age': age, 'height': height, 'weight': weight}
            valid, message = validate_user_input(user_data)

            if valid:
                st.session_state.user_data.update(user_data)
                st.session_state.step = 'health_info'
                st.rerun()
            else:
                st.error(message)

# Health Conditions and Dietary Preferences
elif st.session_state.step == 'health_info':
    st.header("Health & Dietary Information")

    with st.form("health_info_form"):
        health_conditions = st.text_area(
            "Health Conditions",
            value=st.session_state.user_data.get('health_conditions', ''),
            help="List any health conditions you have (separate with commas)"
        )

        allergies = st.text_area(
            "Allergies",
            value=st.session_state.user_data.get('allergies', ''),
            help="List any allergies you have (separate with commas)"
        )

        dietary_restrictions = st.multiselect(
            "Dietary Restrictions",
            options=['Vegetarian', 'Vegan', 'Gluten-Free', 'Dairy-Free', 'Halal', 'Kosher', 'None'],
            default=st.session_state.user_data.get('dietary_restrictions', ['None'])
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Back"):
                st.session_state.step = 'personal_info'
                st.rerun()
        with col2:
            if st.form_submit_button("Next"):
                st.session_state.user_data.update({
                    'health_conditions': health_conditions,
                    'allergies': allergies,
                    'dietary_restrictions': dietary_restrictions
                })
                st.session_state.step = 'barcode_scanning'
                st.rerun()

# Barcode Scanning
elif st.session_state.step == 'barcode_scanning':
    st.header("Scan Product Barcode")

    # Create tabs for different input methods
    tab1, tab2 = st.tabs(["📸 Use Camera", "📤 Upload Image"])

    with tab1:
        st.info("Use your device's camera to capture the barcode")
        camera_image = st.camera_input("Take a picture of the barcode")

        if camera_image is not None:
            # Display the captured image
            image = Image.open(camera_image)
            st.image(image, caption="Captured Barcode", use_container_width=True)

            try:
                # Convert PIL Image to OpenCV format
                img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                barcode = scan_barcode(img_cv)

                if barcode:
                    if not st.session_state.barcode_scanned:
                        with st.spinner("Retrieving product information..."):
                            product_info = get_product_info(barcode)
                            if product_info:
                                st.session_state.current_product = product_info
                                st.session_state.barcode_scanned = True
                                st.rerun()
                            else:
                                st.error("Could not find product information. Please try a different product.")

                    if st.session_state.barcode_scanned and st.session_state.current_product:
                        st.success("Product found! Please verify the details below:")
                        st.markdown(f"### {st.session_state.current_product['product_name']}")
                        st.markdown(f"**Serving Size:** {st.session_state.current_product['serving_size']}")
                        st.markdown(f"**Calories:** {st.session_state.current_product['calories']} kcal per 100g")

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Yes, this is correct"):
                                formatted_info = format_nutrition_info(st.session_state.current_product)
                                with st.spinner("Analyzing nutritional information..."):
                                    model = init_genai()
                                    analysis_result = analyze_ingredients(model, st.session_state.user_data, formatted_info)

                                    if analysis_result['success']:
                                        st.session_state.analysis_results = analysis_result['analysis']
                                        st.session_state.step = 'results'
                                        st.session_state.barcode_scanned = False
                                        st.session_state.current_product = None
                                        st.rerun()
                                    else:
                                        st.error(f"Analysis failed: {analysis_result['error']}")
                        with col2:
                            if st.button("❌ No, scan again"):
                                st.session_state.barcode_scanned = False
                                st.session_state.current_product = None
                                st.rerun()
                else:
                    st.error("Could not detect a barcode in the image. Please ensure the barcode is clearly visible.")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.info("Please try again with a clearer image or contact support if the problem persists.")

    with tab2:
        st.info("Upload a clear image of the product's barcode. Supported formats: PNG, JPG, JPEG")
        uploaded_file = st.file_uploader("Choose an image", type=["png", "jpg", "jpeg"])

        if uploaded_file is not None:
            # Display the uploaded image
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Barcode", use_container_width=True)

            try:
                # Convert PIL Image to OpenCV format
                img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                barcode = scan_barcode(img_cv)

                if barcode:
                    if not st.session_state.barcode_scanned:
                        with st.spinner("Retrieving product information..."):
                            product_info = get_product_info(barcode)
                            if product_info:
                                st.session_state.current_product = product_info
                                st.session_state.barcode_scanned = True
                                st.rerun()
                            else:
                                st.error("Could not find product information. Please try a different product.")

                    if st.session_state.barcode_scanned and st.session_state.current_product:
                        st.success("Product found! Please verify the details below:")
                        st.markdown(f"### {st.session_state.current_product['product_name']}")
                        st.markdown(f"**Serving Size:** {st.session_state.current_product['serving_size']}")
                        st.markdown(f"**Calories:** {st.session_state.current_product['calories']} kcal per 100g")

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Yes, this is correct", key="confirm_upload"):
                                formatted_info = format_nutrition_info(st.session_state.current_product)
                                with st.spinner("Analyzing nutritional information..."):
                                    model = init_genai()
                                    analysis_result = analyze_ingredients(model, st.session_state.user_data, formatted_info)

                                    if analysis_result['success']:
                                        st.session_state.analysis_results = analysis_result['analysis']
                                        st.session_state.step = 'results'
                                        st.session_state.barcode_scanned = False
                                        st.session_state.current_product = None
                                        st.rerun()
                                    else:
                                        st.error(f"Analysis failed: {analysis_result['error']}")
                        with col2:
                            if st.button("❌ No, scan again", key="reject_upload"):
                                st.session_state.barcode_scanned = False
                                st.session_state.current_product = None
                                st.rerun()
                else:
                    st.error("Could not detect a barcode in the image. Please ensure the barcode is clearly visible.")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.info("Please try again with a clearer image or contact support if the problem persists.")

    # Back button
    if not st.session_state.barcode_scanned:
        if st.button("Back"):
            st.session_state.step = 'health_info'
            st.rerun()

# Results
elif st.session_state.step == 'results':
    st.header("Analysis Results")

    if st.session_state.analysis_results:
        st.markdown(st.session_state.analysis_results)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Analyze Another Product"):
            st.session_state.step = 'barcode_scanning'
            st.session_state.analysis_results = None
            st.rerun()
    with col2:
        if st.button("Start Over"):
            st.session_state.clear()
            st.rerun()

# Footer
st.markdown("---")
st.markdown("Made with ❤️ for dietary safety")