import streamlit as st
from utils import init_genai, analyze_ingredients, validate_user_input

# Page configuration
st.set_page_config(
    page_title="Dietary Safety Checker",
    page_icon="🥗",
    layout="wide"
)

# Load custom CSS
with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Initialize session state
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'user_data' not in st.session_state:
    st.session_state.user_data = {}
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None

# Initialize Gemini API
try:
    model = init_genai()
except ValueError as e:
    st.error(f"Error initializing Gemini API: {str(e)}")
    st.stop()

# App title
st.title("🥗 Dietary Safety Checker")

# Step 1: Basic Information
if st.session_state.step == 1:
    st.header("Step 1: Personal Information")
    
    with st.form("user_info_form"):
        name = st.text_input("Name", value=st.session_state.user_data.get('name', ''))
        age = st.number_input("Age", min_value=1, max_value=120, value=st.session_state.user_data.get('age', 25))
        height = st.number_input("Height (cm)", min_value=1.0, value=st.session_state.user_data.get('height', 170.0))
        weight = st.number_input("Weight (kg)", min_value=1.0, value=st.session_state.user_data.get('weight', 70.0))
        
        if st.form_submit_button("Next"):
            user_data = {'name': name, 'age': age, 'height': height, 'weight': weight}
            valid, message = validate_user_input(user_data)
            
            if valid:
                st.session_state.user_data.update(user_data)
                st.session_state.step = 2
                st.experimental_rerun()
            else:
                st.error(message)

# Step 2: Health Conditions and Dietary Preferences
elif st.session_state.step == 2:
    st.header("Step 2: Health & Dietary Information")
    
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
                st.session_state.step = 1
                st.experimental_rerun()
        with col2:
            if st.form_submit_button("Next"):
                st.session_state.user_data.update({
                    'health_conditions': health_conditions,
                    'allergies': allergies,
                    'dietary_restrictions': dietary_restrictions
                })
                st.session_state.step = 3
                st.experimental_rerun()

# Step 3: Ingredient Analysis
elif st.session_state.step == 3:
    st.header("Step 3: Ingredient Analysis")
    
    with st.form("ingredient_form"):
        ingredients = st.text_area(
            "Enter ingredients to analyze",
            help="Enter each ingredient on a new line",
            height=150
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Back"):
                st.session_state.step = 2
                st.experimental_rerun()
        with col2:
            if st.form_submit_button("Analyze"):
                if not ingredients.strip():
                    st.error("Please enter at least one ingredient")
                else:
                    ingredient_list = [i.strip() for i in ingredients.split('\n') if i.strip()]
                    
                    with st.spinner("Analyzing ingredients..."):
                        analysis_result = analyze_ingredients(model, st.session_state.user_data, ingredient_list)
                        
                        if analysis_result['success']:
                            st.session_state.analysis_results = analysis_result['analysis']
                            st.session_state.step = 4
                            st.experimental_rerun()
                        else:
                            st.error(f"Analysis failed: {analysis_result['error']}")

# Step 4: Results
elif st.session_state.step == 4:
    st.header("Analysis Results")
    
    if st.session_state.analysis_results:
        st.markdown(st.session_state.analysis_results)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Analyze More Ingredients"):
            st.session_state.step = 3
            st.session_state.analysis_results = None
            st.experimental_rerun()
    with col2:
        if st.button("Start Over"):
            st.session_state.clear()
            st.experimental_rerun()

# Footer
st.markdown("---")
st.markdown("Made with ❤️ for dietary safety")
