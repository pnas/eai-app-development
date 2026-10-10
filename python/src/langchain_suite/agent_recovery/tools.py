"""Domain Tools for Telecom Support Agent with Type-Safe Schemas."""

from __future__ import annotations

from typing import Dict
from langchain_core.tools import tool
from rich.console import Console

console = Console()

# In-memory mock database for customer records
CUSTOMER_DB: Dict[str, Dict[str, str]] = {
    "ACCT-1001": {
        "name": "Acme Logistics GmbH",
        "plan": "Enterprise 5G Ultra Unlimited",
        "msisdn": "+491701234567",
        "status": "ACTIVE",
        "balance": "€240.00",
    },
    "ACCT-2002": {
        "name": "Dr. Klaus Weber",
        "plan": "MagentaMobil L 5G",
        "msisdn": "+491519876543",
        "status": "ACTIVE",
        "balance": "€14.50",
    },
}


@tool
def lookup_telecom_account(account_id: str) -> str:
    """Look up subscriber details, MSISDN, active plan, and current balance.

    Args:
        account_id: Formatted account identifier, e.g. 'ACCT-1001'.
    """
    record = CUSTOMER_DB.get(account_id.strip().upper())
    if not record:
        return f"Error: Account ID '{account_id}' not found in subscriber registry."
    return (
        f"Subscriber: {record['name']} | Status: {record['status']} | "
        f"Plan: {record['plan']} | Phone: {record['msisdn']} | Balance: {record['balance']}"
    )


@tool
def diagnose_network_cell(msisdn: str) -> str:
    """Run real-time radio line and cell tower diagnostics for a phone number.

    Args:
        msisdn: International phone number starting with +49...
    """
    console.print(f"[bold magenta]⚡ Executing live RF tower probe for {msisdn}...[/bold magenta]")
    return (
        f"Diagnostic Result for {msisdn}: Attached Tower DE-FRA-088. "
        "5G NR RSRP -104 dBm (Degraded), Packet Loss 8.2%, BFD Jitter 45ms. "
        "Alert: Tower sector 2 undergoing scheduled active antenna maintenance."
    )


@tool
def apply_retention_credit(account_id: str, amount_eur: float, reason: str) -> str:
    """Apply goodwill financial compensation credit to a subscriber's account.

    Args:
        account_id: Formatted account identifier, e.g. 'ACCT-1001'.
        amount_eur: Credit amount in Euros (max €50.00).
        reason: Justification for credit approval.
    """
    account_key = account_id.strip().upper()
    if account_key not in CUSTOMER_DB:
        return f"Error: Cannot credit non-existent account '{account_id}'."

    if amount_eur > 50.0:
        return f"Error: Credit amount €{amount_eur:.2f} exceeds tier-1 supervisor limit of €50.00."

    return (
        f"SUCCESS: Credited €{amount_eur:.2f} to account {account_key}. "
        f"Reason: '{reason}'. Confirmation Token: TX-{hash(account_key + str(amount_eur)) % 1000000:06d}."
    )

