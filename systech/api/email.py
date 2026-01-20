# -*- coding: utf-8 -*-
# Copyright (c) 2026, TechStation and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

@frappe.whitelist()
def get_party_email(party_type, party_name):
    """
    Get primary email for customer or supplier.
    party_type: 'Customer' or 'Supplier'
    Returns email address or None if not found.
    """
    if not party_name:
        return None
    
    # Try to get email from party record directly
    email_field = "email_id" if party_type == "Customer" else "email_id"
    party_email = frappe.db.get_value(party_type, party_name, email_field)
    if party_email:
        return party_email
    
    # Try to get from primary contact
    primary_contact = frappe.db.get_value("Dynamic Link",
        {
            "link_doctype": party_type,
            "link_name": party_name,
            "parenttype": "Contact"
        },
        "parent"
    )
    
    if primary_contact:
        contact_email = frappe.db.get_value("Contact", primary_contact, "email_id")
        if contact_email:
            return contact_email
    
    return None
