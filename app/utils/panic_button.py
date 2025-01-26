from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os

# Configure SendGrid API Key
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_EMAIL_SENDER = "Delevia <no-reply@delevia.com>"

def send_email(to_email: str, subject: str, html_content: str):
    """
    Sends an email using SendGrid.
    
    Args:
        to_email (str): Recipient's email address.
        subject (str): Subject of the email.
        html_content (str): HTML content of the email.
    
    Returns:
        dict: Confirmation message if the email is sent successfully.
    """
    if not SENDGRID_API_KEY:
        raise Exception("SendGrid API key is not configured")
    
    message = Mail(
        from_email=SENDGRID_EMAIL_SENDER,
        to_emails=to_email,
        subject=subject,
        html_content=html_content
    )
    
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        # Check if the response status code indicates success
        if response.status_code not in [200, 202]:
            raise Exception(f"SendGrid response error: {response.status_code}")
        
        return {"message": "Email sent successfully"}
    
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        raise Exception("An error occurred while sending the email")


async def send_panic_notification_email(
    to_email: str, ride_id: int, activator_role: str, pickup_location: str, dropoff_location: str
):
    """
    Sends a panic notification email when the panic button is activated.

    Args:
        to_email (str): Recipient's email address (e.g., admin or emergency contact).
        ride_id (int): The ID of the ride where the panic button was activated.
        activator_role (str): The role of the activator (e.g., 'rider' or 'driver').
        pickup_location (str): The pickup location of the ride.
        dropoff_location (str): The dropoff location of the ride.
    """
    subject = f"Panic Alert from {activator_role.capitalize()} - Ride #{ride_id}"
    html_content = f"""
    <html>
        <body>
            <h3>Panic Button Activated</h3>
            <p>
                A panic alert has been triggered by the <strong>{activator_role}</strong> during Ride ID: <strong>{ride_id}</strong>.
            </p>
            <p>
                <strong>Ride Details:</strong><br>
                Pickup Location: {pickup_location}<br>
                Dropoff Location: {dropoff_location}
            </p>
            <p>Please take immediate action to ensure safety.</p>
        </body>
    </html>
    """
    # Use the working email function to send the email
    return send_email(to_email=to_email, subject=subject, html_content=html_content)
