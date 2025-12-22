#!/usr/bin/env python3
"""
Global Forest Watch API Registration Script

Automates the registration process for GFW API key.
This script is interactive and will guide you through:
1. Sign up (if needed)
2. Login to get access token
3. Create API key
4. Save to .env file

Usage:
    python scripts/register_gfw_api.py
"""

import requests
import json
import os
import sys
from pathlib import Path
from typing import Optional


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    """Print colored header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")


def get_input(prompt: str, default: Optional[str] = None) -> str:
    """Get user input with optional default"""
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    
    value = input(f"{Colors.OKBLUE}{prompt}{Colors.ENDC}").strip()
    return value if value else default


def get_password(prompt: str) -> str:
    """Get password input (hidden)"""
    import getpass
    return getpass.getpass(f"{Colors.OKBLUE}{prompt}: {Colors.ENDC}")


def sign_up(name: str, email: str) -> bool:
    """Sign up for GFW account"""
    print_info("Attempting to sign up...")
    
    try:
        response = requests.post(
            "https://data-api.globalforestwatch.org/auth/sign-up",
            json={"name": name, "email": email},
            timeout=10
        )
        
        if response.status_code == 200:
            print_success("Sign up successful! Check your email to verify your account and set password.")
            return True
        elif response.status_code == 422:
            data = response.json()
            print_error(f"Sign up failed: {data.get('detail', 'Unknown error')}")
            print_info("Account may already exist. Try logging in instead.")
            return False
        else:
            print_error(f"Sign up failed with status {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_error(f"Network error during sign up: {e}")
        return False


def get_access_token(email: str, password: str) -> Optional[str]:
    """Get access token by logging in"""
    print_info("Logging in to get access token...")
    
    try:
        response = requests.post(
            "https://data-api.globalforestwatch.org/auth/token",
            data={
                "grant_type": "password",
                "username": email,
                "password": password
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            # Access token is nested under 'data' key
            access_token = data.get("data", {}).get("access_token")
            if access_token:
                print_success("Successfully obtained access token!")
                return access_token
            else:
                print_error("Response missing access_token field")
                print_info(f"Response: {json.dumps(data, indent=2)[:500]}")
                return None
        else:
            print_error(f"Login failed with status {response.status_code}")
            if response.status_code == 401:
                print_error("Invalid email or password")
            return None
            
    except requests.exceptions.RequestException as e:
        print_error(f"Network error during login: {e}")
        return None


def create_api_key(
    access_token: str,
    alias: str,
    organization: str,
    email: str,
    domains: list
) -> Optional[str]:
    """Create API key"""
    print_info("Creating API key...")
    
    try:
        response = requests.post(
            "https://data-api.globalforestwatch.org/auth/apikey",
            json={
                "alias": alias,
                "organization": organization,
                "email": email,
                "domains": domains,
                "never_expires": False
            },
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            api_key = data.get("data", {}).get("api_key")
            expires_on = data.get("data", {}).get("expires_on", "Unknown")
            
            print_success("API key created successfully!")
            print_info(f"Expires: {expires_on}")
            return api_key
        else:
            print_error(f"API key creation failed with status {response.status_code}")
            print(response.text)
            return None
            
    except requests.exceptions.RequestException as e:
        print_error(f"Network error during API key creation: {e}")
        return None


def save_to_env(api_key: str) -> bool:
    """Save API key to .env file"""
    print_info("Saving API key to .env file...")
    
    # Find project root
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    env_example = project_root / ".env.example"
    
    # Create .env from .env.example if it doesn't exist
    if not env_file.exists() and env_example.exists():
        print_info("Creating .env file from .env.example...")
        env_file.write_text(env_example.read_text())
    
    # Read existing content
    if env_file.exists():
        content = env_file.read_text()
    else:
        content = ""
    
    # Check if GFW_API_KEY already exists
    if "GFW_API_KEY=" in content:
        # Replace existing key
        lines = content.split('\n')
        new_lines = []
        for line in lines:
            if line.startswith("GFW_API_KEY="):
                new_lines.append(f"GFW_API_KEY={api_key}")
            else:
                new_lines.append(line)
        content = '\n'.join(new_lines)
    else:
        # Add new key
        if not content.endswith('\n'):
            content += '\n'
        content += f"""
# =============================================================================
# Global Forest Watch API (EUDR Deforestation Checking)
# =============================================================================
# Free API - Register at: https://data-api.globalforestwatch.org
GFW_API_KEY={api_key}
"""
    
    # Write back
    env_file.write_text(content)
    print_success(f"API key saved to {env_file}")
    return True


def verify_api_key(api_key: str) -> bool:
    """Verify the API key works"""
    print_info("Verifying API key...")
    
    try:
        response = requests.get(
            "https://data-api.globalforestwatch.org/datasets",
            headers={"x-api-key": api_key},
            timeout=10
        )
        
        if response.status_code == 200:
            print_success("API key verified successfully! ✨")
            return True
        else:
            print_error(f"API key verification failed with status {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_error(f"Network error during verification: {e}")
        return False


def main():
    """Main registration flow"""
    print_header("Global Forest Watch API Registration")
    
    print("This script will help you register for a FREE Global Forest Watch API key.")
    print("The key is needed for EUDR deforestation compliance checking.\n")
    
    # Step 1: Check if already have credentials
    print_warning("Do you already have a GFW account?")
    has_account = get_input("(yes/no)", "no").lower() in ['y', 'yes']
    
    if not has_account:
        # Sign up flow
        print_header("Step 1: Sign Up")
        name = get_input("Your full name", "Voice Ledger Admin")
        email = get_input("Your email address")
        
        if not email:
            print_error("Email is required!")
            sys.exit(1)
        
        success = sign_up(name, email)
        if not success:
            print_error("Sign up failed. Please try logging in instead.")
            has_account = True
    
    # Login flow (always needed to get access token)
    print_header("Step 2: Login")
    email = get_input("Your email address")
    password = get_password("Your password")
    
    if not email or not password:
        print_error("Email and password are required!")
        sys.exit(1)
    
    access_token = get_access_token(email, password)
    if not access_token:
        print_error("Login failed. Please check your credentials and try again.")
        sys.exit(1)
    
    # Create API key
    print_header("Step 3: Create API Key")
    alias = get_input("Key alias (description)", "Voice-Ledger EUDR")
    organization = get_input("Organization name", "Voice-Ledger")
    
    print_info("\nDomain Configuration:")
    print("  Enter domains that will use this API key.")
    print("  Examples: voiceledger.com, *.voiceledger.com, localhost")
    print("  (Press Enter with empty value when done)\n")
    
    domains = ["localhost"]  # Always include localhost
    while True:
        domain = get_input("Domain (or Enter to finish)")
        if not domain:
            break
        domains.append(domain)
    
    if len(domains) > 1:
        print_info(f"Domains: {', '.join(domains)}")
    
    api_key = create_api_key(access_token, alias, organization, email, domains)
    if not api_key:
        print_error("Failed to create API key!")
        sys.exit(1)
    
    # Save to .env
    print_header("Step 4: Save Configuration")
    save_to_env(api_key)
    
    # Verify
    print_header("Step 5: Verification")
    verify_api_key(api_key)
    
    # Done!
    print_header("🎉 Setup Complete!")
    print(f"\n{Colors.OKGREEN}Your API key has been configured and verified!{Colors.ENDC}\n")
    print("Next steps:")
    print("  1. Test with: pytest tests/test_deforestation_checker.py -v")
    print("  2. Run workflow: pytest tests/test_eudr_workflow.py -v")
    print("  3. Check EUDR docs: docs/SETUP_GFW_API.md")
    print(f"\n{Colors.WARNING}Remember: Your API key expires in 1 year.{Colors.ENDC}")
    print("You'll receive email reminders before expiration.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nRegistration cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
