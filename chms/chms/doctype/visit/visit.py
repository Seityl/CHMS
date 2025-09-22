import frappe
from frappe.model.document import Document
from frappe.utils import now, getdate, today


class Visit(Document):
	def before_save(self):
		"""Execute before saving the visit"""
		self.calculate_bmi()
		self.set_patient_name()
		self.validate_visit_data()
		self.set_created_by()
	
	def on_submit(self):
		"""Execute when visit is submitted"""
		self.update_corporate_screening_stats()
	
	def calculate_bmi(self):
		"""Calculate BMI from height and weight"""
		if self.height and self.weight and self.height > 0:
			height_m = self.height / 100  # Convert cm to meters
			self.bmi = round(self.weight / (height_m ** 2), 2)
	
	def set_patient_name(self):
		"""Set patient name from patient link"""
		if self.patient:
			patient_doc = frappe.get_doc("Patient", self.patient)
			self.patient_name = patient_doc.full_name
	
	def set_created_by(self):
		"""Set created by user"""
		if not self.created_by_user:
			self.created_by_user = frappe.session.user
	
	def validate_visit_data(self):
		"""Validate visit data"""
		# Validate visit date
		if self.visit_date and getdate(self.visit_date) > getdate(today()):
			frappe.throw("Visit date cannot be in the future")
		
		# Validate vital signs ranges
		if self.blood_pressure_systolic and self.blood_pressure_systolic > 250:
			frappe.throw("Systolic blood pressure seems unusually high. Please verify.")
		
		if self.blood_pressure_diastolic and self.blood_pressure_diastolic > 150:
			frappe.throw("Diastolic blood pressure seems unusually high. Please verify.")
		
		if self.heart_rate and (self.heart_rate < 30 or self.heart_rate > 220):
			frappe.throw("Heart rate seems unusual. Please verify.")
		
		if self.temperature and (self.temperature < 32 or self.temperature > 45):
			frappe.throw("Temperature reading seems unusual. Please verify.")
		
		if self.blood_glucose and self.blood_glucose > 600:
			frappe.throw("Blood glucose reading seems extremely high. Please verify.")
	
	def get_bmi_category(self):
		"""Get BMI category based on calculated BMI"""
		if not self.bmi:
			return None
		
		if self.bmi < 18.5:
			return "Underweight"
		elif self.bmi < 25:
			return "Healthy Weight"
		elif self.bmi < 30:
			return "Overweight"
		elif self.bmi < 35:
			return "Obesity Stage 1"
		elif self.bmi < 40:
			return "Obesity Stage 2"
		else:
			return "Morbidly Obese"
	
	def get_blood_pressure_category(self):
		"""Get blood pressure category"""
		if not (self.blood_pressure_systolic and self.blood_pressure_diastolic):
			return None
		
		systolic = self.blood_pressure_systolic
		diastolic = self.blood_pressure_diastolic
		
		if systolic < 120 and diastolic < 80:
			return "Normal"
		elif systolic < 130 and diastolic < 80:
			return "Elevated"
		elif systolic < 140 or diastolic < 90:
			return "High Blood Pressure Stage 1"
		elif systolic < 180 or diastolic < 120:
			return "High Blood Pressure Stage 2"
		else:
			return "Hypertensive Crisis"
	
	def get_glucose_category(self):
		"""Get blood glucose category"""
		if not self.blood_glucose:
			return None
		
		glucose = self.blood_glucose
		
		if glucose < 70:
			return "Low"
		elif glucose < 100:
			return "Normal"
		elif glucose < 140:
			return "Prediabetic"
		else:
			return "Diabetic"
	
	def update_corporate_screening_stats(self):
		"""Update corporate screening statistics if this visit is part of one"""
		# Find if this visit is part of a corporate screening
		screening = frappe.get_all(
			"Corporate Screening",
			filters={
				"company_name": self.get_patient_company(),
				"screening_date_from": ["<=", self.visit_date],
				"screening_date_to": [">=", self.visit_date],
				"status": ["in", ["In Progress", "Completed"]]
			},
			limit=1
		)
		
		if screening:
			# Update screening statistics
			self.recalculate_screening_stats(screening[0].name)
	
	def get_patient_company(self):
		"""Get patient's company"""
		if self.patient:
			patient_doc = frappe.get_doc("Patient", self.patient)
			return patient_doc.company
		return None
	
	def recalculate_screening_stats(self, screening_name):
		"""Recalculate statistics for corporate screening"""
		# This will be called from the corporate screening controller
		pass


@frappe.whitelist()
def get_visit_analytics(filters=None):
	"""Get visit analytics data"""
	if not filters:
		filters = {}
	
	# Base query conditions
	conditions = ["v.docstatus = 1"]
	
	if filters.get("from_date"):
		conditions.append(f"v.visit_date >= '{filters['from_date']}'")
	
	if filters.get("to_date"):
		conditions.append(f"v.visit_date <= '{filters['to_date']}'")
	
	if filters.get("clinic"):
		conditions.append(f"v.clinic = '{filters['clinic']}'")
	
	where_clause = " AND ".join(conditions)
	
	# Get visit statistics
	visit_stats = frappe.db.sql(f"""
		SELECT 
			COUNT(*) as total_visits,
			COUNT(DISTINCT v.patient) as unique_patients,
			AVG(v.bmi) as avg_bmi,
			AVG(v.blood_pressure_systolic) as avg_systolic,
			AVG(v.blood_pressure_diastolic) as avg_diastolic,
			AVG(v.blood_glucose) as avg_glucose
		FROM `tabVisit` v
		WHERE {where_clause}
	""", as_dict=True)
	
	# Get BMI distribution
	bmi_distribution = frappe.db.sql(f"""
		SELECT 
			CASE 
				WHEN v.bmi < 18.5 THEN 'Underweight'
				WHEN v.bmi < 25 THEN 'Healthy Weight'
				WHEN v.bmi < 30 THEN 'Overweight'
				ELSE 'Obese'
			END as bmi_category,
			COUNT(*) as count
		FROM `tabVisit` v
		WHERE {where_clause} AND v.bmi IS NOT NULL
		GROUP BY bmi_category
	""", as_dict=True)
	
	# Get hypertension prevalence
	hypertension_stats = frappe.db.sql(f"""
		SELECT 
			CASE 
				WHEN v.blood_pressure_systolic >= 140 OR v.blood_pressure_diastolic >= 90 THEN 'Hypertensive'
				ELSE 'Normal'
			END as bp_category,
			COUNT(*) as count
		FROM `tabVisit` v
		WHERE {where_clause} AND v.blood_pressure_systolic IS NOT NULL AND v.blood_pressure_diastolic IS NOT NULL
		GROUP BY bp_category
	""", as_dict=True)
	
	return {
		"visit_stats": visit_stats[0] if visit_stats else {},
		"bmi_distribution": bmi_distribution,
		"hypertension_stats": hypertension_stats
	}


@frappe.whitelist()
def get_wellness_wheel_data(patient=None, visit=None):
	"""Get wellness wheel assessment data"""
	filters = {"docstatus": 1}
	
	if patient:
		filters["patient"] = patient
	
	if visit:
		filters["name"] = visit
	
	wellness_data = frappe.get_all(
		"Visit",
		filters=filters,
		fields=["exercise_frequency", "sleep_hours", "stress_level", "smoking_habits", "alcohol_consumption"],
		order_by="visit_date desc",
		limit=10
	)
	
	return wellness_data