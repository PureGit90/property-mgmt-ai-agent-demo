# Property Management AI Agent -- Working Automation Demo

## What This Does
Handles two daily jobs for a rental business: qualifies new inquiries from listing sites and drafts a reply with real price and availability, and triages maintenance requests by category and urgency, replying to the tenant and messaging the right vendor.

## How It Works
New message in Tenant Cloud -> extract the facts -> match a property or classify the problem -> draft the reply and notify the team or vendor -> log it for human review

## Details it handles
- Over-budget leads get the real price and a question about flexibility, not a "nothing fits"
- Vague messages get clarifying questions instead of a guessed property
- Gas smells and other emergencies go to the owner and the emergency line, never to a routine vendor

## Quick Start
1. `pip install -r requirements.txt`
2. `streamlit run app.py`
3. Pick the example messages in each tab, or write your own.

## Demo Limitations
- Mock property data and rule-based logic. No Tenant Cloud, Zillow or messaging connection, and it does not send anything.
- Production version would add: Tenant Cloud API and webhooks through Zapier or Make, an LLM to read free-form messages (with these rules as guardrails), showing scheduling, e-sign leasing, listing sync and rent categorization.
