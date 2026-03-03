import razorpay
import os

client = razorpay.Client(
    auth=(
        os.getenv("RAZORPAY_KEY_ID"),
        os.getenv("RAZORPAY_KEY_SECRET")
    )
)

def create_payment_link(platform, user_id, plan):

    if plan == "trial":
        amount = 1900  # ₹19 in paise
        description = "Maya 3-Day Trial"
    elif plan == "monthly":
        amount = 14900  # ₹149 in paise
        description = "Maya Monthly Premium"
    else:
        return None

    payment = client.payment_link.create({
        "amount": amount,
        "currency": "INR",
        "description": description,
        "customer": {
            "name": "Maya User"
        },
        "notify": {
            "sms": False,
            "email": False
        },
        "notes": {
            "platform": platform,
            "platform_user_id": user_id,
            "plan": plan
        }
    })

    return payment["short_url"]
