import streamlit as st
import re
import yaml
from yaml.loader import SafeLoader
from yaml.dumper import SafeDumper

def save_config(config):
    """Save config to yaml file"""
    with open('config.yaml', 'w') as file:
        yaml.dump(config, file, Dumper=SafeDumper)

def load_config():
    """Load config from yaml file"""
    try:
        with open('config.yaml') as file:
            config = yaml.load(file, Loader=SafeLoader)
            return config
    except Exception:
        return {
            'cookie': {
                'expiry_days': 30,
                'key': "8f058fc8-1479-431f-a49b-1368cfefb8f5",
                'name': "groceryhelper_ai"
            },
            'credentials': {
                'usernames': {
                    'testuser': {
                        'email': 'test@example.com',
                        'name': 'Test User',
                        'password': 'Test123'
                    }
                }
            }
        }

def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength"""
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    return True, ""

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email))

def render_auth_ui():
    """Render authentication UI with signup and password reset"""
    config = load_config()

    # Branding Header with Minimalist Design
    st.markdown("""
        <div class="auth-header">
            <div class="brand-title">🥗 GroceryHelper AI</div>
            <div class="brand-subtitle">Smart Nutrition Analysis & Diet Management</div>
        </div>
    """, unsafe_allow_html=True)

    # Create authentication tabs
    auth_type = st.radio("", ["Login", "Sign Up", "Reset Password"], horizontal=True)

    if auth_type == "Login":
        # Simplified login interface
        st.markdown("##### Username")
        username = st.text_input("", key="login_username", placeholder="Enter username", label_visibility="collapsed")
        st.markdown("##### Password")
        password = st.text_input("", key="login_password", type="password", placeholder="Enter password", label_visibility="collapsed")

        col1, col2 = st.columns([2,1])
        with col2:
            if st.button("Login", use_container_width=True):
                if not username or not password:
                    st.error("Please fill in all fields")
                    return False

                users = config['credentials']['usernames']
                if username in users and users[username]['password'] == password:
                    st.session_state['authenticated'] = True
                    st.session_state['username'] = username
                    st.session_state['step'] = 'welcome'  # Set initial step to welcome
                    st.success("Login successful!")
                    return True
                else:
                    st.error("Invalid username or password")

    elif auth_type == "Sign Up":
        st.markdown("##### Create Your Account")

        st.markdown("##### Username")
        new_username = st.text_input("", key="signup_username", placeholder="Choose username (minimum 3 characters)", label_visibility="collapsed")

        st.markdown("##### Email")
        email = st.text_input("", key="signup_email", placeholder="Enter email address", label_visibility="collapsed")

        st.markdown("##### Password")
        new_password = st.text_input("", key="signup_password", type="password", placeholder="Choose password", help="Must be at least 6 characters with uppercase, lowercase, and numbers", label_visibility="collapsed")

        st.markdown("##### Confirm Password")
        confirm_password = st.text_input("", key="signup_confirm_password", type="password", placeholder="Confirm password", label_visibility="collapsed")

        if st.button("Create Account"):
            if not all([new_username, email, new_password, confirm_password]):
                st.error("Please fill in all fields")
                return False

            if len(new_username) < 3:
                st.error("Username must be at least 3 characters long")
                return False

            if not validate_email(email):
                st.error("Please enter a valid email address")
                return False

            is_valid_password, password_error = validate_password(new_password)
            if not is_valid_password:
                st.error(password_error)
                return False

            if new_password != confirm_password:
                st.error("Passwords do not match")
                return False

            if new_username in config['credentials']['usernames']:
                st.error("Username already exists")
                return False

            config['credentials']['usernames'][new_username] = {
                'password': new_password,
                'email': email,
                'name': new_username
            }
            save_config(config)
            st.success("Account created successfully! Please login.")
            st.balloons()

        # Show feature cards only on Sign Up tab
        st.markdown("""
            <div class="auth-image-grid">
                <div class="auth-feature-card">
                    <h3>🔍 Smart Scanning</h3>
                    <p>Instant barcode recognition for quick product information</p>
                </div>
                <div class="auth-feature-card">
                    <h3>🤖 AI Analysis</h3>
                    <p>Advanced dietary recommendations based on your preferences</p>
                </div>
                <div class="auth-feature-card">
                    <h3>🥗 Health Focus</h3>
                    <p>Personalized nutrition insights for better choices</p>
                </div>
            </div>
        """, unsafe_allow_html=True)

    else:  # Reset Password
        st.markdown("##### Reset Your Password")

        st.markdown("##### Username")
        username = st.text_input("", key="reset_username", placeholder="Enter username", label_visibility="collapsed")

        st.markdown("##### Email")
        email = st.text_input("", key="reset_email", placeholder="Enter email address", label_visibility="collapsed")

        if st.button("Reset Password"):
            if not username or not email:
                st.error("Please fill in all fields")
                return False

            users = config['credentials']['usernames']
            if username in users and users[username]['email'] == email:
                temp_password = "Temp123!"
                users[username]['password'] = temp_password
                save_config(config)
                st.success("Password reset successful!")
                st.info(f"Your temporary password is: {temp_password}")
            else:
                st.error("Invalid username or email")

    return False

def initialize_auth():
    """Initialize authentication system"""
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False