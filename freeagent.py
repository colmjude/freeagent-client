import requests
from dotenv import load_dotenv
import os
import csv
import json
import time
from datetime import date
from pathlib import Path
import base64
import mimetypes

# auth code maker url
# https://api.freeagent.com/v2/approve_app?response_type=code&
# client_id=6jOCaYCRb7Vg8tEGEm43Jg&redirect_uri=http%3A%2F%2Flocalhost%3A5000
# returned
# http://localhost:5000/?code=1f8vTjlYnG_fvmtl2CJ8iathoKC3ygtl_Qps30olK&state=

load_dotenv()

EXPENSES_URL = 'https://api.freeagent.com/v2/expenses'
CATEGORIES_URL = 'https://api.freeagent.com/v2/categories'
USER_URL = 'https://api.freeagent.com/v2/users/me'
ATTACHMENTS_URL = 'https://api.freeagent.com/v2/attachments'
INVOICE_URL = 'https://api.freeagent.com/v2/invoices'

CATEGORIES_FOLDER = 'data/freeagent/categories'


def exchange_code_for_tokens():
    """
    Exchange the authorization code for access and refresh tokens.
    This function assumes you have set the necessary environment variables.
    """
    # Load environment variables
    client_id = os.getenv('FREEAGENT_CLIENT_ID')  # From FreeAgent Dashboard
    client_secret = os.getenv('FREEAGENT_CLIENT_SECRET')  # From FreeAgent Dashboard
    redirect_uri = os.getenv('FREEAGENT_REDIRECT_URI')  # Exactly as registered
    code = os.getenv('FREEAGENT_AUTH_CODE')  # Code from browser redirect

    # FreeAgent token endpoint
    token_url = 'https://api.freeagent.com/v2/token_endpoint'

    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri
    }

    response = requests.post(token_url, data=data)
    tokens = response.json()
    if 'error' in tokens:
        raise ValueError(f"Error in token response: {tokens['error']}")
    return tokens


def save_auth_tokens(tokens):
    """
    Save the access and refresh tokens to a file.
    """
    tokens['expires_at'] = int(time.time()) + tokens['expires_in']
    with open('freeagent_tokens.json', 'w') as f:
        json.dump(tokens, f)
    print("Tokens saved to freeagent_tokens.json")


def load_auth_tokens():
    """
    Load the access and refresh tokens from a file.
    """
    if os.path.exists('freeagent_tokens.json'):
        with open('freeagent_tokens.json', 'r') as f:
            return json.load(f)
    else:
        print("No tokens found. Please run exchange_code_for_tokens() first.")
        tokens = exchange_code_for_tokens()

        save_auth_tokens(tokens)
        return tokens


def refresh_access_token(refresh_token):
    """
    Refresh the access token using the refresh token.
    This function assumes you have set the necessary environment variables.
    """
    client_id = os.getenv('FREEAGENT_CLIENT_ID')
    client_secret = os.getenv('FREEAGENT_CLIENT_SECRET')

    # FreeAgent token endpoint
    token_url = 'https://api.freeagent.com/v2/token_endpoint'

    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret
    }

    response = requests.post(token_url, data=data)
    tokens = response.json()
    
    if 'error' in tokens:
        raise ValueError(f"Error in token refresh: {tokens['error']}")
    
    save_auth_tokens(tokens)
    return tokens


def get_valid_access_token():
    tokens = load_auth_tokens()
    now = int(time.time())
    if now >= tokens.get('expires_at', 0):
        # Expired or not set—refresh!
        print("Refreshing access token...")
        tokens = refresh_access_token(tokens['refresh_token'])
    return tokens


def check_connection(tokens):
    """
    Check if we can successfully connect to FreeAgent API using current tokens.
    Returns True if connection is successful, False otherwise.
    """
    try:
        headers = {
            'Authorization': f"Bearer {tokens['access_token']}",
            'Accept': 'application/json'
        }
        
        # Try to fetch user info as a simple test
        response = requests.get(
            'https://api.freeagent.com/v2/users/me', 
            headers=headers
        )
        
        if response.status_code == 200:
            print("Successfully connected to FreeAgent API")
            return True
        else:
            print(
                f"Failed to connect to FreeAgent API. "
                f"Status code: {response.status_code}"
            )
            return False
            
    except Exception as e:
        print(f"Error checking FreeAgent connection: {str(e)}")
        return False


def set_headers(tokens, call_type='expense'):
    """
    Set the headers for FreeAgent API requests.
    """
    if call_type == 'attachment':
        return {
            'Authorization': f"Bearer {tokens['access_token']}",
            'Accept': 'application/json'
        }
    return {
        'Authorization': f"Bearer {tokens['access_token']}",
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }


def get_current_user():
    """
    Get the current user's details from FreeAgent API
    Returns the user URL (which is the user ID)
    """
    tokens = load_auth_tokens()
    headers = set_headers(tokens)
    
    response = requests.get(USER_URL, headers=headers)
    if response.status_code == 200:
        user_data = response.json()
        return user_data['user']['url']
    else:
        msg = f"Failed to get user info. Status code: {response.status_code}"
        print(response.text)
        raise Exception(msg)


def get_invoice(id):
    """
    Fetch an invoice by ID from FreeAgent
    Returns the invoice data
    """
    tokens = load_auth_tokens()
    headers = set_headers(tokens)
    
    invoice_url = f'{INVOICE_URL}/{id}'
    response = requests.get(invoice_url, headers=headers)
    if response.status_code == 200:
        invoice_data = response.json()
        return invoice_data
    else:
        msg = f"Failed to get invoice. Status code: {response.status_code}"
        raise Exception(msg)



def get_categories():
    """
    Fetch all expense categories from FreeAgent
    Returns a dict mapping category names to their URLs
    """
    tokens = load_auth_tokens()
    headers = set_headers(tokens)
    
    response = requests.get(CATEGORIES_URL, headers=headers)
    if response.status_code == 200:
        categories = response.json()
        return categories
    else:
        msg = f"Failed to get categories. Status code: {response.status_code}"
        raise Exception(msg)


def save_categories_to_csv(categories_dict, output_folder=CATEGORIES_FOLDER):
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    for group, categories in categories_dict.items():
        output_path = Path(output_folder) / f"{group}.csv"
        if categories:
            with open(output_path, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=categories[0].keys())
                writer.writeheader()
                writer.writerows(categories)



def _encode_file_to_base64(file_path):
    """Helper function to encode file to base64 and detect mime type"""
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = 'image/jpeg'  # default to jpeg
    elif mime_type not in [
        'image/png', 'image/x-png', 'image/jpeg', 
        'image/jpg', 'image/gif', 'application/x-pdf', 'application/pdf'
    ]:
        raise ValueError(f"Unsupported file type: {mime_type}")
    
    with open(file_path, 'rb') as f:
        file_data = f.read()
        return base64.b64encode(file_data).decode(), mime_type


def create_expense(
    description, amount, dated_on=None, currency='GBP',
    vat_amount=None, items=None, attachment_path=None,
    category_code='285'
):
    """
    Create a new expense in FreeAgent
    Args:
        description: Description of the expense
        amount: Amount as a string (e.g. '15.00')
        dated_on: ISO format date string (defaults to today)
        currency: Currency code (defaults to GBP)
        vat_amount: Optional VAT amount as string
        items: Optional list of items included in expense
        attachment_path: Optional path to receipt image to attach
        category_code: FreeAgent category code (default '285' for Accommodation and Meals)
    Returns:
        The created expense data if successful
    """
    category_url = f'https://api.freeagent.com/v2/categories/{category_code}'
    tokens = load_auth_tokens()
    headers = set_headers(tokens)
    
    # Get user ID and categories
    user_url = get_current_user()
    print("Current user URL:", user_url)
    
    # Build full description including items if provided
    full_description = description
    if items:
        full_description = f"{description} - Items: {items}"
    
    expense_data = {
        'expense': {
            'user': user_url,
            'category': category_url,
            'dated_on': dated_on or date.today().isoformat(),
            'description': full_description,
            'gross_value': amount,
            'currency': currency
        }
    }
    
    # Add VAT amount if provided
    if vat_amount is not None:
        expense_data['expense']['manual_sales_tax_amount'] = vat_amount
    
    # Add attachment if provided
    if attachment_path:
        file_path = Path(attachment_path)
        if not file_path.exists():
            raise ValueError(f"Attachment file not found: {attachment_path}")
            
        base64_data, content_type = _encode_file_to_base64(attachment_path)
        expense_data['expense']['attachment'] = {
            'data': base64_data,
            'file_name': file_path.name,
            'description': 'Receipt photo',
            'content_type': content_type
        }
    
    response = requests.post(EXPENSES_URL, headers=headers, json=expense_data)
    if response.status_code == 201:
        return response.json()
    else:
        msg = (
            f"Failed to create expense. Status code: {response.status_code}, "
            f"Response: {response.text}"
        )
        raise Exception(msg)


def attach_to_expense(expense_id, file_path):
    """
    Attach a file to an existing expense in FreeAgent
    Args:
        expense_id: The ID of the expense to attach to
        file_path: Path to the file to attach
    Returns:
        The attachment data if successful
    """
    tokens = load_auth_tokens()
    headers = set_headers(tokens, call_type='attachment')
    
    expense_url = f'{EXPENSES_URL}/{expense_id}'
    file_name = Path(file_path).name

    # Detect MIME type based on file extension
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        # Default to image/jpeg for unknown types
        mime_type = 'image/jpeg'
    
    with open(file_path, 'rb') as f:
        files = {
            'attachment[attached-to]': (None, expense_url),
            'attachment[description]': (None, f'Receipt photo - {file_name}'),
            'attachment[content]': (file_path, f, mime_type),
        }
        response = requests.post(
            ATTACHMENTS_URL,
            headers=headers,
            files=files
        )
        
    if response.status_code == 201:
        return response.json()
    else:
        msg = (
            f"Failed to attach file. Status code: {response.status_code}, "
            f"Response: {response.text}"
        )
        raise Exception(msg)
