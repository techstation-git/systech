app_name = "systech"
app_title = "Systech"
app_publisher = "Tati"
app_description = "For accounting, finance and warehouse"
app_email = "abedtatty@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "systech",
# 		"logo": "/assets/systech/logo.png",
# 		"title": "Systech",
# 		"route": "/systech",
# 		"has_permission": "systech.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "systech/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "systech.utils.jinja_methods",
# 	"filters": "systech.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "systech.install.before_install"
# after_install = "systech.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "systech.uninstall.before_uninstall"
# after_uninstall = "systech.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "systech.utils.before_app_install"
# after_app_install = "systech.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "systech.utils.before_app_uninstall"
# after_app_uninstall = "systech.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "systech.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Item": {
		"validate": "systech.services.rest.validate_item_barcode"
	},
	"Purchase Receipt": {
		"validate": "systech.services.rest.validate_transaction_barcodes"
	},
	"Stock Entry": {
		"validate": "systech.services.rest.validate_transaction_barcodes"
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"systech.tasks.all"
# 	],
# 	"daily": [
# 		"systech.tasks.daily"
# 	],
# 	"hourly": [
# 		"systech.tasks.hourly"
# 	],
# 	"weekly": [
# 		"systech.tasks.weekly"
# 	],
# 	"monthly": [
# 		"systech.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "systech.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "systech.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "systech.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["systech.utils.before_request"]
# after_request = ["systech.utils.after_request"]

# Job Events
# ----------
# before_job = ["systech.utils.before_job"]
# after_job = ["systech.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"systech.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

fixtures = [
	"Property Setter",
    "Custom Field",
    "Client Script",
]