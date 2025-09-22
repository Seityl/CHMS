import frappe
from frappe.model.document import Document
from frappe.utils import today, getdate, date_diff


class Patient(Document):
	def before_save(self):
		"""Calculate fields before saving"""
		self.set_full_name()
		self.calculate_age()
		self.validate_patient_data()
	
	def set_full_name(self):
		"""Set full name from first and last name"""
		if self.first_name and self.last_name:
			self.full_name = f"{self.first_name} {self.last_name}"
	
	def calculate_age(self):
		"""Calculate age from date of birth"""
		if self.date_of_birth:
			birth_date = getdate(self.date_of_birth)
			current_date = getdate(today())
			self.age = date_diff(current_date, birth_date) // 365
	
	def validate_patient_data(self):
		"""Validate patient data"""
		# Check if patient ID already exists
		if not self.is_new():
			return
			
		existing = frappe.db.exists("Patient", {"patient_id": self.patient_id})
		if existing and existing != self.name:
			frappe.throw(f"Patient with ID {self.patient_id} already exists")
		
		# Validate email format
		if self.email:
			import re
			email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
			if not re.match(email_pattern, self.email):
				frappe.throw("Please enter a valid email address")
		
		# Validate date of birth
		if self.date_of_birth and getdate(self.date_of_birth) > getdate(today()):
			frappe.throw("Date of birth cannot be in the future")
	
	def get_visit_history(self):
		"""Get all visits for this patient"""
		return frappe.get_all(
			"Visit",
			filters={"patient": self.name},
			fields=["name", "visit_date", "visit_type", "status", "clinic"],
			order_by="visit_date desc"
		)
	
	def get_latest_vitals(self):
		"""Get latest vital signs from most recent visit"""
		latest_visit = frappe.get_all(
			"Visit",
			filters={"patient": self.name, "docstatus": 1},
			fields=["name", "height", "weight", "bmi", "blood_pressure_systolic", 
					"blood_pressure_diastolic", "heart_rate", "visit_date"],
			order_by="visit_date desc",
			limit=1
		)
		return latest_visit[0] if latest_visit else None
	
	def get_health_summary(self):
		"""Get health summary with key metrics"""
		latest_vitals = self.get_latest_vitals()
		visit_count = frappe.db.count("Visit", {"patient": self.name})
		
		return {
			"total_visits": visit_count,
			"latest_vitals": latest_vitals,
			"last_visit_date": latest_vitals.get("visit_date") if latest_vitals else None
		}


@frappe.whitelist()
def search_patients(query):
	"""Search patients by name, patient ID, or phone"""
	filters = [
		["Patient", "patient_id", "like", f"%{query}%"],
		["Patient", "full_name", "like", f"%{query}%"],
		["Patient", "phone", "like", f"%{query}%"],
		["Patient", "email", "like", f"%{query}%"]
	]
	
	or_conditions = []
	for filter_condition in filters:
		or_conditions.append(filter_condition)
	
	patients = frappe.get_all(
		"Patient",
		fields=["name", "patient_id", "full_name", "gender", "age", "phone", "company"],
		limit=20,
		or_filters=or_conditions
	)
	
	return patients


@frappe.whitelist()
def get_patient_dashboard_data(patient):
	"""Get dashboard data for patient"""
	patient_doc = frappe.get_doc("Patient", patient)
	
	# Get visit statistics
	total_visits = frappe.db.count("Visit", {"patient": patient})
	completed_visits = frappe.db.count("Visit", {"patient": patient, "status": "Completed"})
	
	# Get latest screening data
	latest_screening = frappe.get_all(
		"Visit",
		filters={"patient": patient, "docstatus": 1},
		fields=["visit_date", "bmi", "blood_pressure_systolic", "blood_pressure_diastolic", 
				"blood_glucose", "body_fat_percentage"],
		order_by="visit_date desc",
		limit=1
	)
	
	# Calculate BMI category
	bmi_category = None
	if latest_screening and latest_screening[0].get("bmi"):
		bmi = latest_screening[0]["bmi"]
		if bmi < 18.5:
			bmi_category = "Underweight"
		elif bmi < 25:
			bmi_category = "Healthy Weight"
		elif bmi < 30:
			bmi_category = "Overweight"
		else:
			bmi_category = "Obese"
	
	return {
		"patient_info": {
			"name": patient_doc.full_name,
			"patient_id": patient_doc.patient_id,
			"age": patient_doc.age,
			"gender": patient_doc.gender,
			"company": patient_doc.company
		},
		"visit_stats": {
			"total_visits": total_visits,
			"completed_visits": completed_visits
		},
		"latest_metrics": latest_screening[0] if latest_screening else None,
		"bmi_category": bmi_category
	}