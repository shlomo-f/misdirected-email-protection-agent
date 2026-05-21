import os
from email import policy
from email.parser import BytesParser
from typing import Dict, Any
import re

#parsing email files to structured python dictionaries, currently ignores attachments content

def parse_eml(file_path: str) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No email file found at {file_path}")

    with open(file_path, 'rb') as f:
        msg = BytesParser(policy=policy.default).parse(f)

    email_data = {
        "subject": msg.get('subject', 'No Subject'),
        "date": msg.get('date', 'Unknown Date'),
        "attachments": []
    }

    #TODO: more robust solution - needs to have the owner's email and compare it to that
    # Deals with who both types of email, outbound and inbound
    if "Authentication-Results" not in msg:
        email_data["inbound"] = False
    else:
        email_data["inbound"] = True

    # Determine which header to pull based on direction
    target_header = 'to' if not email_data["inbound"] else 'from'
    header_obj = msg.get(target_header)

    # Initialize default values
    contact_email = "Unknown"
    contact_name = ""

    if header_obj:
        # policy=policy.default parses headers into objects with an 'addresses' tuple
        if hasattr(header_obj, 'addresses') and header_obj.addresses:
            primary_address = header_obj.addresses[0]
            contact_email = primary_address.addr_spec
            contact_name = primary_address.display_name
        else:
            # Robust native fallback if the header object structure isn't populated
            from email.utils import parseaddr
            contact_name, contact_email = parseaddr(str(header_obj))

    # Add both fields cleanly to your data dictionary
    email_data["contact_email"] = contact_email
    email_data["contact_name"] = contact_name if contact_name else "[No Name Provided]"


    body_content = ""
    
    # 1. Try to get plain text first (best for LLMs)
    body = msg.get_body(preferencelist=('plain', 'html'))
    
    if body:
        # If it's HTML, we need to handle it differently
        if body.get_content_type() == 'text/html':
            html_text = body.get_content()
            # Simple way to strip HTML tags for now
            body_content = re.sub('<[^<]+?>', '', html_text)
        else:
            body_content = body.get_content()
    
    # 2. If it's a multipart message and the above failed, walk through parts
    if not body_content and msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body_content = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                break

    email_data["body"] = body_content.strip() if body_content else "[No content found]"

    for part in msg.walk():
        # Check if the part is an attachment
        if part.get_content_disposition() == 'attachment':
            attachment_info = {
                "filename": part.get_filename(),
                "content_type": part.get_content_type()  # e.g., 'application/pdf'
            }
            email_data["attachments"].append(attachment_info)

    return email_data

def clean_body(text: str) -> str:
    """
    Future home for logic to strip signatures, legal disclaimers, 
    and 'Sent from my iPhone' noise.
    """
    # For now, we'll just trim extra whitespace
    return " ".join(text.split())

if __name__ == "__main__":
    # Test the parser
    SAMPLE_PATH = r"data\raw_emails\Q3 Budget Draft & Hiring Update - Project Phoenix 2026-05-10T09_45_32+03_00.eml"
    
    try:
        data = parse_eml(SAMPLE_PATH)
        print("--- Parsed Email Success ---")
        print(f"Contact email: {data['contact_email']}")
        print(f'Contact name: {data['contact_name']}')
        print(f"Subject: {data['subject']}")
        print(f"Body Preview: {data['body'][:100]}...")
        print(f"Attachments: {data['attachments']}")
    except Exception as e:
        print(f"Error: {e}")