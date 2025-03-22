import streamlit as st
import re
import yaml
from yaml.loader import SafeLoader
from yaml.dumper import SafeDumper
import os
import json

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

aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
aws_region = os.getenv('AWS_REGION', 'us-east-2')
s3_bucket = os.getenv('S3_BUCKET', 'nutriscan-ai-users-jane')


# Print debug info
print(f"DEBUG - AWS Access Key: {aws_access_key[:5]}... Secret Key: {'*' * 5} Region: {aws_region} Bucket: {s3_bucket}")

# Check for missing credentials
if not aws_access_key or not aws_secret_key:
    print("ERROR - AWS credentials are missing!")


S3_BUCKET = os.getenv('S3_BUCKET')
S3_USERS_KEY = 'users/credentials.json'
S3_PROFILES_KEY = 'users/profiles.json'

def get_users_from_s3() -> dict:
    """
    Retrieve user credential data from S3
    """
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=S3_USERS_KEY)
        users_data = json.loads(response['Body'].read().decode('utf-8'))
        return users_data
    except s3_client.exceptions.NoSuchKey:
        print(f"No credentials found in S3, will create new credentials file")
        return {}
    except Exception as e:
        print(f"An error occurred while fetching user data from S3: {str(e)}")
        return {}

def save_users_to_s3(users_data: dict) -> bool:
    """
    Save user credential data to S3
    """
    try:
        users_json = json.dumps(users_data)
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=S3_USERS_KEY,
            Body=users_json
        )
        print("User credentials successfully saved to S3")
        return True
    except Exception as e:
        print(f"An error occurred while saving to S3: {str(e)}")
        return False

def get_user_profiles_from_s3() -> dict:
    """
    Retrieve user profile data from S3
    """
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=S3_PROFILES_KEY)
        profiles_data = json.loads(response['Body'].read().decode('utf-8'))
        return profiles_data
    except s3_client.exceptions.NoSuchKey:
        st.info(f"No profiles found in S3, creating new profiles file")
        return {}
    except Exception as e:
        st.error(f"An error occurred while fetching profile data from S3: {str(e)}")
        return {}

def save_user_profiles_to_s3(profiles_data: dict) -> bool:
    """
    Save user profile data to S3
    """
    try:
        profiles_json = json.dumps(profiles_data)
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=S3_PROFILES_KEY,
            Body=profiles_json
        )
        return True
    except Exception as e:
        st.error(f"An error occurred while saving profiles to S3: {str(e)}")
        return False

# Helper functions to work with specific user profiles
def save_user_profile(username: str, profile_data: dict) -> bool:
    """
    Save a specific user's profile data
    """
    try:
        profiles = get_user_profiles_from_s3()
        # st.write(f"Debug - Current profiles: {profiles}")

        profiles[username] = profile_data
        # st.write(f"Debug - Saving profile for {username}: {profile_data}")

        result = save_user_profiles_to_s3(profiles)
        # st.write(f"Debug - Save result: {result}")

        return result

    except Exception as e:
        st.error(f"Failed to save user profile: {str(e)}")
        return False

def get_user_profile(username: str) -> dict:
    """
    Get a specific user's profile data
    """
    try:
        profiles = get_user_profiles_from_s3()
        return profiles.get(username, {})
    except Exception as e:
        st.error(f"Failed to get user profile: {str(e)}")
        return {}




def save_config(config):
    """Save config to yaml file"""
    with open('config.yaml', 'w') as file:
        yaml.dump(config, file, Dumper=SafeDumper)
    save_users_to_s3(config['credentials']['usernames'])


def load_config():
    """Load config from yaml file"""
    try:
        # First, try to load from local YAML file
        with open('config.yaml') as file:
            config = yaml.load(file, Loader=SafeLoader)
        
        # Try to get users from S3
        s3_users = get_users_from_s3()
        
        # If we have users in S3, merge them with local config
        if s3_users:
            # Update local config with S3 data
            config['credentials']['usernames'].update(s3_users)
            # Save the merged config back to local file
            with open('config.yaml', 'w') as file:
                yaml.dump(config, file, Dumper=SafeDumper)

        return config


    except Exception:
        st.warning(f"Error loading config, using default: {str(e)}")
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
        # Initialize S3 with default config
        save_users_to_s3(default_config['credentials']['usernames'])
        return default_config

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

# def sync_credentials_with_s3():
#     """Force sync local credentials with S3"""
#     try:
#         config = load_config()
#         # Upload current credentials to S3
#         success = save_users_to_s3(config['credentials']['usernames'])
#         if success:
#             st.success("Successfully synchronized credentials with S3")
#         else:
#             st.error("Failed to synchronize credentials with S3")
#     except Exception as e:
#         st.error(f"Error syncing credentials: {str(e)}")

def render_auth_ui():
    """Render authentication UI with signup and password reset"""
    config = load_config()

    # # Branding Header with Minimalist Design
    # st.markdown("""
    #     <div class="auth-header">
    #         <div class="brand-title">🛒 NutriScan AI</div>
    #         <div class="brand-subtitle">Smart Nutrition Analysis & Diet Management</div>
    #     </div>
    # """, unsafe_allow_html=True)

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
                    user_profile = get_user_profile(username)
                    # st.write(f"Debug - Loading user profile: {user_profile}")

                    st.session_state['authenticated'] = True
                    st.session_state['username'] = username
                    st.session_state['step'] = 'welcome'
                    
                    # Load saved profile data if available
                    user_profile = get_user_profile(username)
                    if user_profile:
                        st.session_state['user_data'] = user_profile
                    else:
                        st.session_state['user_data'] = {}
                        
                    st.success("Login successful!")

                    # email = config['credentials']['usernames'][username]['email']
                    # config['credentials']['usernames'][username] = {
                    #     'password': password,
                    #     'email': email,
                    #     'name': username
                    # }
                    # save_config(config)

                    return True

                ##
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

            # Initialize empty profile for the new user
            save_user_profile(new_username, {})

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

    # # Add a new admin section that can force sync
    # if st.checkbox("Admin Options"):
    #     st.caption("Use these options only if you're experiencing credential synchronization issues")
    #     if st.button("Force Sync Credentials with S3"):
    #         sync_credentials_with_s3()


    return False

def initialize_auth():
    """Initialize authentication system"""
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
