from frappe import _

def get_data(data=None):
	return {
		"fieldname": "reference_name", 
		"internal_links": {
			"Journal Entry": ["reference_name", "asset"],
		},
		"transactions": [
			{
				"label": _("References"),
				"items": ["Journal Entry"]
			}
		]
	}
