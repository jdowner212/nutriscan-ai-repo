import os
os.write(1,b'Something was executed.\n')


import streamlit as st
from utils import *
from PIL import Image
import numpy as np
import cv2
from auth import *

# TEMPORARY CODE TO CLEAR PRODUCT HISTORY - REMOVE AFTER RUNNING ONCE

# def clear_all_product_history():
#     try:
#         # Get all profiles
#         profiles = get_user_profiles_from_s3()
        
#         # Clear product history for all users
#         for username in profiles:
#             if 'product_history' in profiles[username]:
#                 profiles[username]['product_history'] = []
        
#         # Save updated profiles
#         save_result = save_user_profiles_to_s3(profiles)
        
#         return save_result
#     except Exception as e:
#         print(f"DEBUG - Failed to clear product history: {str(e)}")
#         return False

# # Execute the function once when app starts
# if 'history_cleared' not in st.session_state:
#     result = clear_all_product_history()
#     st.session_state.history_cleared = True
#     print(f"DEBUG - Product history clearing result: {result}")


    ##############################


def is_profile_complete():
    """Check if user has completed their profile"""
    required_fields = ['name', 'age', 'height', 'weight', 'dietary_restrictions']
    if 'user_data' not in st.session_state:
        return False
        
    user_data = st.session_state.user_data
    return all(field in user_data and user_data[field] for field in required_fields)


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
    page_icon="🛒",
    layout="wide"
)

# Load custom CSS
with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Initialize authentication
initialize_auth()



if 'run_analysis_for_barcode' in st.session_state:
    barcode = st.session_state.run_analysis_for_barcode
    # Remove the flag to prevent re-running
    del st.session_state.run_analysis_for_barcode
    # Run the analysis
    run_analyze(barcode)



# Check authentication
if not st.session_state.get('authenticated', False):
    # Only show the centered header for login page
    st.markdown("""
        <div class="auth-header">
            <div class="brand-title">🛒 NutriScan AI</div>
            <div class="brand-subtitle">Smart Nutrition Analysis & Diet Management</div>
        </div>
    """, unsafe_allow_html=True)
    
    if render_auth_ui():
        st.rerun()
    st.stop()

create_custom_header()
    
# Add logout button in sidebar if user is authenticated
with st.sidebar:
    st.write(f"👤 Logged in as: {st.session_state.get('username', '')}")
    st.markdown('<div class="danger-button">', unsafe_allow_html=True)
    if st.button("Logout", use_container_width=True):
        # Clear only authentication-related state
        st.session_state['authenticated'] = False
        st.session_state['username'] = None
        st.session_state['step'] = 'welcome' 
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)




if 'flow_type' not in st.session_state:
    st.session_state.flow_type = 'normal'  # or 'onboarding'



# Initialize session state
if 'step' not in st.session_state:
    st.session_state.step = 'welcome'
if 'user_data' not in st.session_state:
    st.session_state.user_data = {}
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'analysis_success' not in st.session_state:
    st.session_state.analysis_success = None
if 'current_product' not in st.session_state:
    st.session_state.current_product = None
if 'barcode_scanned' not in st.session_state:
    st.session_state.barcode_scanned = False
if 'from_history' not in st.session_state:
    st.session_state.from_history = False
if 'scan_state' not in st.session_state:
    st.session_state.scan_state = 'ready'

# Welcome Screen with distinct design
if st.session_state.step == 'welcome':
    # User greeting with personalization
    st.markdown(f"""
    <div class="welcome-container">
        <h1>Welcome, {st.session_state.get('username', 'User')}!</h1>
        <p class="welcome-text">
            Let's analyze your food products for better dietary choices.
        </p>
    </div>
    """, unsafe_allow_html=True)


    # Quick Actions Section
    st.markdown("### Quick Actions")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="action-button">', unsafe_allow_html=True)
        if st.button("📸 Scan Product", key="scan_product_btn", use_container_width=True):
            # Your existing scan button logic
            if is_profile_complete():
                st.session_state.step = 'barcode_scanning'
                st.rerun()
            else:
                st.session_state.flow_type = 'onboarding'
                st.session_state.step = 'personal_info'
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="action-button">', unsafe_allow_html=True)
        if st.button("📋 Update Profile", key="update_profile_btn", use_container_width=True):
            st.session_state.flow_type = 'profile_update'
            st.session_state.step = 'personal_info'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    username = st.session_state.get('username')
    if username:
        product_history = get_product_history(username)
        # st.markdown(f"product_history: {product_history}")

        if product_history:
            st.markdown("### Your Product History")
            
            # Create tabs for different ways to view history
            history_tab1, history_tab2 = st.tabs(["Recent Products", "By Safety Rating"])
            
            with history_tab1:
                # Display recent products in a grid
                col1, col2 = st.columns(2)
                
                for i, product in enumerate(product_history[:8]):  # Show only 8 most recent
                    with col1 if i % 2 == 0 else col2:
                        with st.container():
                            # Determine color based on safety rating
                            color = "#4CAF50" if product['safety_rating'] == "Safe" else \
                                   "#FF9800" if product['safety_rating'] == "Caution" else \
                                   "#F44336" if product['safety_rating'] == "Unsafe" else "#9E9E9E"
                            
                            st.markdown(f"""
                            <div style="padding: 10px; margin-bottom: 10px; border-left: 5px solid {color}; background-color: #f9f9f9;">
                                <div style="font-weight: bold; font-size: 16px;">{product['product_name']}</div>
                                <div style="color: #666; font-size: 12px; margin-bottom: 5px;">Analyzed on {product['timestamp']}</div>
                                <div style="margin-top: 5px;">
                                    <span style="background-color: {color}; color: white; padding: 2px 6px; border-radius: 10px; font-size: 12px;">
                                        {product['safety_rating']}
                                    </span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            if st.button(f"View Details", key=f"history_{i}"):
                                st.session_state.analysis_results = product['full_analysis']
                                st.session_state.from_history = True
                                st.session_state.step = 'results'
                                st.rerun()
            
            with history_tab2:
                # Group products by safety rating
                safe_products = [p for p in product_history if p['safety_rating'] == "Safe"]
                caution_products = [p for p in product_history if p['safety_rating'] == "Caution"]
                unsafe_products = [p for p in product_history if p['safety_rating'] == "Unsafe"]
                
                # Create expanders for each category
                if unsafe_products:
                    with st.expander("⚠️ Unsafe Products", expanded=True):
                        for i, product in enumerate(unsafe_products):
                            st.markdown(f"**{product['product_name']}** - {product['timestamp']}")
                            st.markdown(f"_{product['analysis_summary']}_")
                            if st.button(f"View Details", key=f"unsafe_{i}"):
                                st.session_state.analysis_results = product['full_analysis']
                                st.session_state.from_history = True
                                st.session_state.step = 'results'
                                st.rerun()
                            st.divider()
                
                if caution_products:
                    with st.expander("⚠️ Use with Caution", expanded=False):
                        for i, product in enumerate(caution_products):
                            st.markdown(f"**{product['product_name']}** - {product['timestamp']}")
                            st.markdown(f"_{product['analysis_summary']}_")
                            if st.button(f"View Details", key=f"caution_{i}"):
                                st.session_state.analysis_results = product['full_analysis']
                                st.session_state.from_history = True
                                st.session_state.step = 'results'
                                st.rerun()
                            st.divider()
                
                if safe_products:
                    with st.expander("✅ Safe Products", expanded=False):
                        for i, product in enumerate(safe_products):
                            st.markdown(f"**{product['product_name']}** - {product['timestamp']}")
                            st.markdown(f"_{product['analysis_summary']}_")
                            if st.button(f"View Details", key=f"safe_{i}"):
                                st.session_state.analysis_results = product['full_analysis']
                                st.session_state.from_history = True
                                st.session_state.step = 'results'
                                st.rerun()
                            st.divider()


    # Tips Section
    with st.expander("💡 Quick Tips"):
        st.markdown("""
        - Ensure product barcodes are clearly visible when scanning
        - Update your health profile regularly for more accurate recommendations
        - Save products you frequently consume for quick access
        """)


elif st.session_state.step == 'personal_info':
    st.markdown("<h1>Tell Us About Yourself</h1>", unsafe_allow_html=True)

    # Add return to home button at the top
    if st.button("Return to Home", key="personal_info_home_btn"):
        st.session_state.step = 'welcome'
        st.rerun()

    with st.form("user_info_form"):
        name = st.text_input("Name", value=st.session_state.user_data.get('name', ''))
        age = st.number_input("Age", min_value=1, max_value=120, value=st.session_state.user_data.get('age', 25))
        height = st.number_input("Height (cm)", min_value=1.0, value=st.session_state.user_data.get('height', 170.0))
        weight = st.number_input("Weight (kg)", min_value=1.0, value=st.session_state.user_data.get('weight', 70.0))

        # Use columns for form buttons to place them side by side
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Cancel"):
                st.session_state.step = 'welcome'
                st.rerun()

        with col2:
            continue_text = "Continue" if st.session_state.flow_type == 'onboarding' else "Next"
            if st.form_submit_button(continue_text):
                user_data = {'name': name, 'age': age, 'height': height, 'weight': weight}
                valid, message = validate_user_input(user_data)

                if valid:
                    st.session_state.user_data.update(user_data)  # Add this line
                    # Save user data
                    if st.session_state.get('username'):
                        save_user_profile(st.session_state['username'], st.session_state.user_data)
                    st.session_state.step = 'health_info'
                    st.rerun()
                else:
                    st.error(message)

# 2. Health Information Step
elif st.session_state.step == 'health_info':
    st.header("Health & Dietary Information")

    # Add return to home button at the top
    if st.button("Return to Home", key="health_info_home_btn"):
        st.session_state.step = 'welcome'
        st.rerun()

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

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.form_submit_button("Cancel"):
                st.session_state.step = 'welcome'
                st.rerun()

        with col2:
            if st.form_submit_button("Back"):
                st.session_state.step = 'personal_info'
                st.rerun()
        with col3:
            next_button_text = "Save & Continue" if st.session_state.flow_type == 'onboarding' else "Save Profile"
            if st.form_submit_button(next_button_text):
                st.session_state.user_data.update({
                    'health_conditions': health_conditions,
                    'allergies': allergies,
                    'dietary_restrictions': dietary_restrictions
                })

                # Save the complete user profile
                if st.session_state.get('username'):
                    save_user_profile(st.session_state['username'], st.session_state.user_data)
                # Different navigation based on flow type
                if st.session_state.flow_type == 'onboarding':
                    st.session_state.step = 'barcode_scanning'
                else:
                    st.session_state.step = 'welcome'
                    st.success("Profile updated successfully!")

                    
                st.rerun()

# 3. Barcode Scanning Step
elif st.session_state.step == 'barcode_scanning':
    st.header("Scan Product Barcode")

    # Add return to home button at the top
    if st.button("Return to Home", key="barcode_home_btn"):
        st.session_state.step = 'welcome'
        st.rerun()

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
                # print(f"DEBUG - Detected barcode: {barcode}, type: {type(barcode)}")

                if barcode:
                    handle_barcode(barcode)

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
                    handle_barcode(barcode)
                else:
                    st.error("Could not detect a barcode in the image. Please ensure the barcode is clearly visible.")

            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.info("Please try again with a clearer image or contact support if the problem persists.")


    # Back button at the bottom (existing)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back to Health Info"):
            st.session_state.step = 'health_info'
            st.rerun()
    with col2:
        if st.button("Cancel Scanning"):
            st.session_state.step = 'welcome'
            st.rerun()


# Results
elif st.session_state.step == 'results':
    st.header("Analysis Results")

    if st.session_state.analysis_results:
        # Show a badge if viewing from history
        if st.session_state.get('from_history', False):
            st.info("You are viewing a previously analyzed product from your history")
        st.markdown(st.session_state.analysis_results)

    if st.session_state.get('from_history', False):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Home"):

                # Preserve authentication and user data
                authenticated = st.session_state.get('authenticated', False)
                username = st.session_state.get('username', None)
                user_data = st.session_state.get('user_data', {})
                # Clear state but preserve important data
                st.session_state.clear()
                # Restore important state
                st.session_state['authenticated'] = authenticated
                st.session_state['username'] = username
                st.session_state['user_data'] = user_data
                st.session_state['step'] = 'welcome'

                st.rerun()

        with col2:
            if st.button("Analyze New Product"):

                # Preserve authentication and user data
                authenticated = st.session_state.get('authenticated', False)
                username = st.session_state.get('username', None)
                user_data = st.session_state.get('user_data', {})
                # Clear state but preserve important data
                st.session_state.clear()
                # Restore important state
                st.session_state['authenticated'] = authenticated
                st.session_state['username'] = username
                st.session_state['user_data'] = user_data
                st.session_state['step'] = 'barcode_scanning'
                
                st.rerun()

    else:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Analyze Another Product"):

                # Preserve authentication and user data
                authenticated = st.session_state.get('authenticated', False)
                username = st.session_state.get('username', None)
                user_data = st.session_state.get('user_data', {})
                # Clear state but preserve important data
                st.session_state.clear()
                # Restore important state
                st.session_state['authenticated'] = authenticated
                st.session_state['username'] = username
                st.session_state['user_data'] = user_data
                st.session_state['step'] = 'barcode_scanning'
                
                st.rerun()
        with col2:
            if st.button("Return to Home"):
                # Preserve authentication and user data
                authenticated = st.session_state.get('authenticated', False)
                username = st.session_state.get('username', None)
                user_data = st.session_state.get('user_data', {})
                # Clear only analysis-related state
                st.session_state.clear()
                # Restore important state
                st.session_state['authenticated'] = authenticated
                st.session_state['username'] = username
                st.session_state['user_data'] = user_data
                st.session_state['step'] = 'welcome'
                
                st.rerun()

# Footer
st.markdown("---")
st.markdown("Made with ❤️ for dietary safety")
