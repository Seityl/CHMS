import frappe
from frappe.model.document import Document
from frappe.utils import today, getdate, flt


class CorporateScreening(Document):
	def before_save(self):
		"""Execute before saving corporate screening"""
		self.set_created_by()
		self.validate_screening_data()
		self.calculate_statistics()
	
	def on_submit(self):
		"""Execute when screening is submitted"""
		self.status = "Completed"
		self.calculate_final_statistics()
	
	def set_created_by(self):
		"""Set created by user"""
		if not self.created_by_user:
			self.created_by_user = frappe.session.user
	
	def validate_screening_data(self):
		"""Validate screening data"""
		# Validate dates
		if self.screening_date_from and self.screening_date_to:
			if getdate(self.screening_date_from) > getdate(self.screening_date_to):
				frappe.throw("Screening start date cannot be after end date")
		
		# Validate company name
		if not self.company_name:
			frappe.throw("Company name is required")
	
	def calculate_statistics(self):
		"""Calculate screening statistics from visits"""
		# Get all visits for this screening period and company
		visits = self.get_screening_visits()
		
		if not visits:
			self.total_participants = 0
			return
		
		# Calculate demographics
		self.total_participants = len(visits)
		self.male_participants = len([v for v in visits if v.get('gender') == 'Male'])
		self.female_participants = len([v for v in visits if v.get('gender') == 'Female'])
		
		# Calculate age groups
		self.age_group_18_30 = len([v for v in visits if v.get('age') and 18 <= v['age'] <= 30])
		self.age_group_31_50 = len([v for v in visits if v.get('age') and 31 <= v['age'] <= 50])
		self.age_group_51_plus = len([v for v in visits if v.get('age') and v['age'] >= 51])
		
		# Calculate health prevalence
		self.calculate_health_prevalence(visits)
		
		# Calculate total cost
		if self.cost_per_participant and self.total_participants:
			self.total_cost = flt(self.cost_per_participant) * self.total_participants
	
	def calculate_health_prevalence(self, visits):
		"""Calculate health condition prevalence"""
		total_with_bmi = len([v for v in visits if v.get('bmi')])
		total_with_bp = len([v for v in visits if v.get('blood_pressure_systolic')])
		total_with_glucose = len([v for v in visits if v.get('blood_glucose')])
		
		# Obesity prevalence (BMI >= 30)
		if total_with_bmi > 0:
			obese_count = len([v for v in visits if v.get('bmi') and v['bmi'] >= 30])
			self.obesity_prevalence = round((obese_count / total_with_bmi) * 100, 1)
		
		# Hypertension prevalence (BP >= 140/90)
		if total_with_bp > 0:
			hypertensive_count = len([v for v in visits if v.get('blood_pressure_systolic') 
									and v.get('blood_pressure_diastolic') 
									and (v['blood_pressure_systolic'] >= 140 or v['blood_pressure_diastolic'] >= 90)])
			self.hypertension_prevalence = round((hypertensive_count / total_with_bp) * 100, 1)
		
		# Diabetes prevalence (glucose >= 140 mg/dL)
		if total_with_glucose > 0:
			diabetic_count = len([v for v in visits if v.get('blood_glucose') and v['blood_glucose'] >= 140])
			self.diabetes_prevalence = round((diabetic_count / total_with_glucose) * 100, 1)
		
		# Smoking prevalence
		total_with_smoking_data = len([v for v in visits if v.get('smoking_habits')])
		if total_with_smoking_data > 0:
			smoker_count = len([v for v in visits if v.get('smoking_habits') 
							  and v['smoking_habits'] in ['Occasionally', 'Daily']])
			self.smoking_prevalence = round((smoker_count / total_with_smoking_data) * 100, 1)
		
		# High risk participants (multiple risk factors)
		high_risk_count = 0
		for visit in visits:
			risk_factors = 0
			if visit.get('bmi') and visit['bmi'] >= 30:
				risk_factors += 1
			if (visit.get('blood_pressure_systolic') and visit.get('blood_pressure_diastolic') 
				and (visit['blood_pressure_systolic'] >= 140 or visit['blood_pressure_diastolic'] >= 90)):
				risk_factors += 1
			if visit.get('blood_glucose') and visit['blood_glucose'] >= 140:
				risk_factors += 1
			if visit.get('smoking_habits') and visit['smoking_habits'] in ['Occasionally', 'Daily']:
				risk_factors += 1
			
			if risk_factors >= 2:
				high_risk_count += 1
		
		self.high_risk_participants = high_risk_count
	
	def get_screening_visits(self):
		"""Get all visits for this screening"""
		# Get patient IDs from the company
		company_patients = frappe.get_all(
			"Patient",
			filters={"company": self.company_name},
			fields=["name"]
		)
		
		if not company_patients:
			return []
		
		patient_ids = [p.name for p in company_patients]
		
		# Date filters
		date_filters = {"visit_date": [">=", self.screening_date_from]}
		if self.screening_date_to:
			date_filters["visit_date"] = ["between", [self.screening_date_from, self.screening_date_to]]
		
		# Get visits for these patients in the screening period
		visits = frappe.db.sql("""
			SELECT 
				v.name, v.patient, v.visit_date, v.height, v.weight, v.bmi,
				v.blood_pressure_systolic, v.blood_pressure_diastolic, v.blood_glucose,
				v.body_fat_percentage, v.waist_circumference, v.smoking_habits,
				v.alcohol_consumption, v.exercise_frequency, v.sleep_hours, v.stress_level,
				p.gender, p.age, p.company
			FROM `tabVisit` v
			INNER JOIN `tabPatient` p ON v.patient = p.name
			WHERE v.patient IN %(patients)s 
				AND v.visit_date >= %(from_date)s
				AND (%(to_date)s IS NULL OR v.visit_date <= %(to_date)s)
				AND v.docstatus = 1
		""", {
			"patients": patient_ids,
			"from_date": self.screening_date_from,
			"to_date": self.screening_date_to
		}, as_dict=True)
		
		return visits
	
	def calculate_final_statistics(self):
		"""Calculate final statistics when screening is completed"""
		self.calculate_statistics()
		
		# Generate executive summary
		self.generate_executive_summary()
	
	def generate_executive_summary(self):
		"""Generate AI-assisted executive summary"""
		visits = self.get_screening_visits()
		
		if not visits:
			self.executive_summary = "No screening data available for analysis."
			return
		
		# Create summary based on key findings
		summary_points = []
		
		# Participation summary
		summary_points.append(f"A total of {self.total_participants} employees participated in the corporate wellness screening for {self.company_name}.")
		
		# Gender distribution
		if self.male_participants and self.female_participants:
			male_pct = round((self.male_participants / self.total_participants) * 100, 1)
			female_pct = round((self.female_participants / self.total_participants) * 100, 1)
			summary_points.append(f"Gender distribution: {male_pct}% male, {female_pct}% female.")
		
		# Key health findings
		if self.obesity_prevalence:
			summary_points.append(f"Obesity prevalence: {self.obesity_prevalence}% of screened employees.")
		
		if self.hypertension_prevalence:
			summary_points.append(f"Hypertension prevalence: {self.hypertension_prevalence}% showed elevated blood pressure readings.")
		
		if self.diabetes_prevalence:
			summary_points.append(f"Diabetes/Pre-diabetes prevalence: {self.diabetes_prevalence}% had elevated glucose levels.")
		
		if self.smoking_prevalence:
			summary_points.append(f"Smoking prevalence: {self.smoking_prevalence}% of employees reported smoking habits.")
		
		if self.high_risk_participants:
			high_risk_pct = round((self.high_risk_participants / self.total_participants) * 100, 1)
			summary_points.append(f"High-risk employees: {high_risk_pct}% have multiple risk factors requiring immediate attention.")
		
		# Recommendations
		recommendations = []
		if self.obesity_prevalence and self.obesity_prevalence > 25:
			recommendations.append("Implement weight management programs and nutritional counseling.")
		
		if self.hypertension_prevalence and self.hypertension_prevalence > 20:
			recommendations.append("Regular blood pressure monitoring and cardiovascular health initiatives.")
		
		if self.smoking_prevalence and self.smoking_prevalence > 10:
			recommendations.append("Smoking cessation programs and stress management alternatives.")
		
		if recommendations:
			summary_points.append("Recommended interventions: " + " ".join(recommendations))
		
		self.executive_summary = " ".join(summary_points)


@frappe.whitelist()
def generate_screening_report(screening_name):
	"""Generate comprehensive screening report"""
	screening_doc = frappe.get_doc("Corporate Screening", screening_name)
	visits = screening_doc.get_screening_visits()
	
	if not visits:
		frappe.throw("No visit data found for this screening")
	
	# Mark report as generated
	screening_doc.report_generated = 1
	screening_doc.report_date = today()
	screening_doc.report_generated_by = frappe.session.user
	screening_doc.save()
	
	return {
		"screening_info": {
			"company": screening_doc.company_name,
			"dates": f"{screening_doc.screening_date_from} to {screening_doc.screening_date_to or screening_doc.screening_date_from}",
			"total_participants": screening_doc.total_participants
		},
		"demographics": {
			"male_participants": screening_doc.male_participants,
			"female_participants": screening_doc.female_participants,
			"age_groups": {
				"18-30": screening_doc.age_group_18_30,
				"31-50": screening_doc.age_group_31_50,
				"51+": screening_doc.age_group_51_plus
			}
		},
		"health_metrics": {
			"obesity_prevalence": screening_doc.obesity_prevalence,
			"hypertension_prevalence": screening_doc.hypertension_prevalence,
			"diabetes_prevalence": screening_doc.diabetes_prevalence,
			"smoking_prevalence": screening_doc.smoking_prevalence,
			"high_risk_participants": screening_doc.high_risk_participants
		},
		"executive_summary": screening_doc.executive_summary
	}


@frappe.whitelist()
def get_screening_dashboard_data():
	"""Get dashboard data for corporate screenings"""
	# Get recent screenings
	recent_screenings = frappe.get_all(
		"Corporate Screening",
		fields=["name", "company_name", "screening_date_from", "status", "total_participants"],
		order_by="screening_date_from desc",
		limit=10
	)
	
	# Get screening statistics
	total_screenings = frappe.db.count("Corporate Screening")
	completed_screenings = frappe.db.count("Corporate Screening", {"status": "Completed"})
	
	# Get total participants across all screenings
	total_participants = frappe.db.sql("""
		SELECT SUM(total_participants) as total
		FROM `tabCorporate Screening`
		WHERE docstatus = 1 AND total_participants IS NOT NULL
	""", as_dict=True)
	
	total_participants = total_participants[0].get("total") or 0 if total_participants else 0
	
	return {
		"recent_screenings": recent_screenings,
		"stats": {
			"total_screenings": total_screenings,
			"completed_screenings": completed_screenings,
			"total_participants": total_participants
		}
	}