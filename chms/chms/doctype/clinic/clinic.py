import frappe
from frappe.model.document import Document
from frappe.utils import now, today


class Clinic(Document):
	def before_save(self):
		"""Execute before saving clinic"""
		self.set_created_by()
		self.validate_clinic_data()
		self.set_last_updated()
	
	def set_created_by(self):
		"""Set created by user"""
		if not self.created_by_user:
			self.created_by_user = frappe.session.user
	
	def set_last_updated(self):
		"""Set last updated timestamp"""
		self.last_updated = now()
	
	def validate_clinic_data(self):
		"""Validate clinic data"""
		# Check if clinic code already exists
		if self.clinic_code:
			existing = frappe.db.exists("Clinic", {"clinic_code": self.clinic_code})
			if existing and existing != self.name:
				frappe.throw(f"Clinic with code {self.clinic_code} already exists")
		
		# Validate email format
		if self.email:
			import re
			email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
			if not re.match(email_pattern, self.email):
				frappe.throw("Please enter a valid email address")
		
		# Validate capacity
		if self.capacity and self.capacity < 0:
			frappe.throw("Patient capacity cannot be negative")
		
		# Validate staff counts
		if self.total_staff and self.total_staff < 0:
			frappe.throw("Total staff count cannot be negative")
		
		if (self.practitioners_count and self.administrative_staff_count and 
			self.total_staff and 
			(self.practitioners_count + self.administrative_staff_count) > self.total_staff):
			frappe.throw("Sum of practitioners and administrative staff cannot exceed total staff")
	
	def get_clinic_statistics(self):
		"""Get clinic statistics and utilization data"""
		# Get visit count by period
		visit_stats = frappe.db.sql("""
			SELECT 
				COUNT(*) as total_visits,
				COUNT(DISTINCT patient) as unique_patients,
				COUNT(CASE WHEN visit_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) THEN 1 END) as visits_last_30_days,
				COUNT(CASE WHEN visit_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) THEN 1 END) as visits_last_7_days
			FROM `tabVisit`
			WHERE clinic = %s AND docstatus = 1
		""", self.name, as_dict=True)
		
		# Get visit type distribution
		visit_types = frappe.db.sql("""
			SELECT 
				visit_type,
				COUNT(*) as count
			FROM `tabVisit`
			WHERE clinic = %s AND docstatus = 1
			GROUP BY visit_type
			ORDER BY count DESC
		""", self.name, as_dict=True)
		
		# Get patient demographics
		patient_demographics = frappe.db.sql("""
			SELECT 
				p.gender,
				COUNT(*) as count,
				AVG(p.age) as avg_age
			FROM `tabVisit` v
			INNER JOIN `tabPatient` p ON v.patient = p.name
			WHERE v.clinic = %s AND v.docstatus = 1
			GROUP BY p.gender
		""", self.name, as_dict=True)
		
		# Calculate utilization rate
		utilization_rate = 0
		if self.capacity and visit_stats:
			daily_visits = visit_stats[0].get('visits_last_30_days', 0) / 30
			utilization_rate = round((daily_visits / self.capacity) * 100, 1)
		
		return {
			"visit_stats": visit_stats[0] if visit_stats else {},
			"visit_types": visit_types,
			"patient_demographics": patient_demographics,
			"utilization_rate": utilization_rate
		}
	
	def get_recent_screenings(self, limit=10):
		"""Get recent corporate screenings conducted at this clinic"""
		screenings = frappe.get_all(
			"Corporate Screening",
			filters={"clinic": self.name},
			fields=["name", "company_name", "screening_date_from", "status", "total_participants"],
			order_by="screening_date_from desc",
			limit=limit
		)
		return screenings
	
	def get_health_metrics_summary(self):
		"""Get health metrics summary for patients seen at this clinic"""
		metrics = frappe.db.sql("""
			SELECT 
				AVG(bmi) as avg_bmi,
				AVG(blood_pressure_systolic) as avg_systolic,
				AVG(blood_pressure_diastolic) as avg_diastolic,
				AVG(blood_glucose) as avg_glucose,
				COUNT(CASE WHEN bmi >= 30 THEN 1 END) * 100.0 / COUNT(CASE WHEN bmi IS NOT NULL THEN 1 END) as obesity_rate,
				COUNT(CASE WHEN blood_pressure_systolic >= 140 OR blood_pressure_diastolic >= 90 THEN 1 END) * 100.0 / 
					COUNT(CASE WHEN blood_pressure_systolic IS NOT NULL AND blood_pressure_diastolic IS NOT NULL THEN 1 END) as hypertension_rate,
				COUNT(CASE WHEN blood_glucose >= 126 THEN 1 END) * 100.0 / COUNT(CASE WHEN blood_glucose IS NOT NULL THEN 1 END) as diabetes_rate
			FROM `tabVisit`
			WHERE clinic = %s AND docstatus = 1
		""", self.name, as_dict=True)
		
		return metrics[0] if metrics else {}


@frappe.whitelist()
def get_clinic_dashboard_data(clinic):
	"""Get comprehensive dashboard data for a specific clinic"""
	clinic_doc = frappe.get_doc("Clinic", clinic)
	
	# Get clinic statistics
	clinic_stats = clinic_doc.get_clinic_statistics()
	
	# Get recent screenings
	recent_screenings = clinic_doc.get_recent_screenings()
	
	# Get health metrics
	health_metrics = clinic_doc.get_health_metrics_summary()
	
	# Get monthly visit trends
	visit_trends = frappe.db.sql("""
		SELECT 
			DATE_FORMAT(visit_date, '%%Y-%%m') as month,
			COUNT(*) as visit_count,
			COUNT(DISTINCT patient) as unique_patients
		FROM `tabVisit`
		WHERE clinic = %s 
		AND visit_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
		AND docstatus = 1
		GROUP BY DATE_FORMAT(visit_date, '%%Y-%%m')
		ORDER BY month
	""", clinic, as_dict=True)
	
	return {
		"clinic_info": {
			"name": clinic_doc.clinic_name,
			"type": clinic_doc.clinic_type,
			"capacity": clinic_doc.capacity,
			"total_staff": clinic_doc.total_staff,
			"status": clinic_doc.status
		},
		"statistics": clinic_stats,
		"recent_screenings": recent_screenings,
		"health_metrics": health_metrics,
		"visit_trends": visit_trends
	}


@frappe.whitelist()
def get_all_clinics_summary():
	"""Get summary data for all clinics"""
	clinics = frappe.get_all(
		"Clinic",
		fields=["name", "clinic_name", "clinic_type", "status", "capacity", "total_staff"],
		filters={"status": "Active"}
	)
	
	clinic_summaries = []
	
	for clinic in clinics:
		# Get basic visit statistics for each clinic
		visit_stats = frappe.db.sql("""
			SELECT 
				COUNT(*) as total_visits,
				COUNT(DISTINCT patient) as unique_patients,
				COUNT(CASE WHEN visit_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) THEN 1 END) as visits_last_30_days
			FROM `tabVisit`
			WHERE clinic = %s AND docstatus = 1
		""", clinic.name, as_dict=True)
		
		stats = visit_stats[0] if visit_stats else {}
		
		# Calculate utilization
		utilization_rate = 0
		if clinic.capacity and stats.get('visits_last_30_days'):
			daily_avg = stats['visits_last_30_days'] / 30
			utilization_rate = round((daily_avg / clinic.capacity) * 100, 1)
		
		clinic_summaries.append({
			"name": clinic.name,
			"clinic_name": clinic.clinic_name,
			"clinic_type": clinic.clinic_type,
			"capacity": clinic.capacity,
			"total_staff": clinic.total_staff,
			"total_visits": stats.get('total_visits', 0),
			"unique_patients": stats.get('unique_patients', 0),
			"visits_last_30_days": stats.get('visits_last_30_days', 0),
			"utilization_rate": utilization_rate
		})
	
	return clinic_summaries


@frappe.whitelist() 
def get_clinic_performance_metrics():
	"""Get performance metrics across all clinics"""
	
	# Get clinic performance data
	performance_data = frappe.db.sql("""
		SELECT 
			c.clinic_name,
			c.capacity,
			COUNT(v.name) as total_visits,
			COUNT(DISTINCT v.patient) as unique_patients,
			AVG(v.duration_minutes) as avg_visit_duration,
			COUNT(CASE WHEN v.status = 'Completed' THEN 1 END) * 100.0 / COUNT(v.name) as completion_rate,
			COUNT(CASE WHEN v.visit_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) THEN 1 END) as visits_last_30_days
		FROM `tabClinic` c
		LEFT JOIN `tabVisit` v ON c.name = v.clinic AND v.docstatus = 1
		WHERE c.status = 'Active'
		GROUP BY c.name, c.clinic_name, c.capacity
		ORDER BY total_visits DESC
	""", as_dict=True)
	
	# Add utilization calculations
	for clinic_data in performance_data:
		if clinic_data.capacity and clinic_data.visits_last_30_days:
			daily_avg = clinic_data.visits_last_30_days / 30
			clinic_data['utilization_rate'] = round((daily_avg / clinic_data.capacity) * 100, 1)
		else:
			clinic_data['utilization_rate'] = 0
		
		# Round numeric values
		if clinic_data.avg_visit_duration:
			clinic_data['avg_visit_duration'] = round(clinic_data.avg_visit_duration, 1)
		if clinic_data.completion_rate:
			clinic_data['completion_rate'] = round(clinic_data.completion_rate, 1)
	
	return performance_data


@frappe.whitelist()
def validate_clinic_capacity(clinic, visit_date, visit_time=None):
	"""Validate if clinic has capacity for new visit"""
	
	# Get existing visits for the date
	existing_visits = frappe.db.count("Visit", {
		"clinic": clinic,
		"visit_date": visit_date,
		"status": ["in", ["Scheduled", "In Progress"]],
		"docstatus": ["!=", 2]
	})
	
	# Get clinic capacity
	clinic_doc = frappe.get_doc("Clinic", clinic)
	
	if not clinic_doc.capacity:
		return {"available": True, "message": "No capacity limit set"}
	
	if existing_visits >= clinic_doc.capacity:
		return {
			"available": False, 
			"message": f"Clinic capacity ({clinic_doc.capacity}) exceeded for {visit_date}. Current bookings: {existing_visits}"
		}
	
	return {
		"available": True,
		"message": f"Capacity available. Current bookings: {existing_visits}/{clinic_doc.capacity}"
	}