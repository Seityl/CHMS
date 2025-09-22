import frappe
from frappe.utils import add_days, today
import json


@frappe.whitelist()
def get_main_dashboard_data(date_range=None):
	"""Get main dashboard data with key metrics"""
	
	# Set date range
	if date_range:
		date_filter = json.loads(date_range)
		from_date = date_filter.get('from_date')
		to_date = date_filter.get('to_date')
	else:
		# Default to last 30 days
		to_date = today()
		from_date = add_days(to_date, -30)
	
	# Get visit statistics
	visit_stats = frappe.db.sql("""
		SELECT 
			COUNT(*) as total_visits,
			COUNT(DISTINCT patient) as unique_patients,
			COUNT(CASE WHEN visit_type = 'Corporate Screening' THEN 1 END) as screening_visits,
			COUNT(CASE WHEN status = 'Completed' THEN 1 END) as completed_visits
		FROM `tabVisit`
		WHERE visit_date BETWEEN %s AND %s
		AND docstatus = 1
	""", (from_date, to_date), as_dict=True)[0]
	
	# Get patient demographics
	patient_demographics = frappe.db.sql("""
		SELECT 
			gender,
			COUNT(*) as count
		FROM `tabPatient`
		GROUP BY gender
	""", as_dict=True)
	
	# Get BMI distribution from recent visits
	bmi_distribution = frappe.db.sql("""
		SELECT 
			CASE 
				WHEN bmi < 18.5 THEN 'Underweight'
				WHEN bmi < 25 THEN 'Healthy Weight'
				WHEN bmi < 30 THEN 'Overweight'
				ELSE 'Obese'
			END as category,
			COUNT(*) as count
		FROM `tabVisit`
		WHERE visit_date BETWEEN %s AND %s
		AND bmi IS NOT NULL
		AND docstatus = 1
		GROUP BY category
	""", (from_date, to_date), as_dict=True)
	
	# Get hypertension prevalence
	hypertension_data = frappe.db.sql("""
		SELECT 
			CASE 
				WHEN blood_pressure_systolic >= 140 OR blood_pressure_diastolic >= 90 THEN 'Hypertensive'
				WHEN blood_pressure_systolic >= 120 OR blood_pressure_diastolic >= 80 THEN 'Elevated'
				ELSE 'Normal'
			END as category,
			COUNT(*) as count
		FROM `tabVisit`
		WHERE visit_date BETWEEN %s AND %s
		AND blood_pressure_systolic IS NOT NULL 
		AND blood_pressure_diastolic IS NOT NULL
		AND docstatus = 1
		GROUP BY category
	""", (from_date, to_date), as_dict=True)
	
	# Get recent corporate screenings
	recent_screenings = frappe.get_all(
		"Corporate Screening",
		filters={
			"screening_date_from": ["between", [from_date, to_date]]
		},
		fields=["name", "company_name", "screening_date_from", "status", "total_participants"],
		order_by="screening_date_from desc",
		limit=5
	)
	
	# Get clinic utilization
	clinic_utilization = frappe.db.sql("""
		SELECT 
			c.clinic_name,
			COUNT(v.name) as visit_count,
			COUNT(DISTINCT v.patient) as unique_patients
		FROM `tabClinic` c
		LEFT JOIN `tabVisit` v ON c.name = v.clinic 
			AND v.visit_date BETWEEN %s AND %s
			AND v.docstatus = 1
		GROUP BY c.name
		ORDER BY visit_count DESC
	""", (from_date, to_date), as_dict=True)
	
	return {
		"date_range": {"from": from_date, "to": to_date},
		"visit_stats": visit_stats,
		"patient_demographics": patient_demographics,
		"bmi_distribution": bmi_distribution,
		"hypertension_data": hypertension_data,
		"recent_screenings": recent_screenings,
		"clinic_utilization": clinic_utilization
	}


@frappe.whitelist()
def get_corporate_wellness_summary():
	"""Get corporate wellness summary for management dashboard"""
	
	# Get all completed screenings in the last year
	screenings = frappe.db.sql("""
		SELECT 
			company_name,
			total_participants,
			obesity_prevalence,
			hypertension_prevalence,
			diabetes_prevalence,
			smoking_prevalence,
			high_risk_participants,
			screening_date_from
		FROM `tabCorporate Screening`
		WHERE status = 'Completed'
		AND screening_date_from >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
		AND docstatus = 1
		ORDER BY screening_date_from DESC
	""", as_dict=True)
	
	if not screenings:
		return {"message": "No completed corporate screenings found"}
	
	# Calculate aggregate statistics
	total_participants = sum(s.get("total_participants", 0) for s in screenings)
	
	# Calculate weighted averages for health metrics
	weighted_obesity = 0
	weighted_hypertension = 0
	weighted_diabetes = 0
	weighted_smoking = 0
	total_weight = 0
	
	for screening in screenings:
		participants = screening.get("total_participants", 0)
		if participants > 0:
			total_weight += participants
			weighted_obesity += (screening.get("obesity_prevalence", 0) * participants)
			weighted_hypertension += (screening.get("hypertension_prevalence", 0) * participants)
			weighted_diabetes += (screening.get("diabetes_prevalence", 0) * participants)
			weighted_smoking += (screening.get("smoking_prevalence", 0) * participants)
	
	avg_metrics = {}
	if total_weight > 0:
		avg_metrics = {
			"avg_obesity_prevalence": round(weighted_obesity / total_weight, 1),
			"avg_hypertension_prevalence": round(weighted_hypertension / total_weight, 1),
			"avg_diabetes_prevalence": round(weighted_diabetes / total_weight, 1),
			"avg_smoking_prevalence": round(weighted_smoking / total_weight, 1)
		}
	
	# Get top companies by screening frequency
	company_stats = frappe.db.sql("""
		SELECT 
			company_name,
			COUNT(*) as screening_count,
			SUM(total_participants) as total_participants,
			MAX(screening_date_from) as last_screening
		FROM `tabCorporate Screening`
		WHERE status = 'Completed'
		AND docstatus = 1
		GROUP BY company_name
		ORDER BY screening_count DESC, total_participants DESC
		LIMIT 10
	""", as_dict=True)
	
	return {
		"summary_stats": {
			"total_screenings": len(screenings),
			"total_participants": total_participants,
			"companies_served": len(set(s["company_name"] for s in screenings))
		},
		"health_metrics": avg_metrics,
		"recent_screenings": screenings[:5],
		"top_companies": company_stats
	}


@frappe.whitelist()
def get_health_trends_data(period="3_months"):
	"""Get health trends data over time"""
	
	# Define date range based on period
	periods = {
		"1_month": 30,
		"3_months": 90,
		"6_months": 180,
		"1_year": 365
	}
	
	days = periods.get(period, 90)
	from_date = add_days(today(), -days)
	
	# Get monthly trends for key metrics
	trends_data = frappe.db.sql("""
		SELECT 
			DATE_FORMAT(visit_date, '%%Y-%%m') as month,
			COUNT(*) as total_visits,
			AVG(bmi) as avg_bmi,
			AVG(blood_pressure_systolic) as avg_systolic,
			AVG(blood_glucose) as avg_glucose,
			COUNT(CASE WHEN bmi >= 30 THEN 1 END) * 100.0 / COUNT(CASE WHEN bmi IS NOT NULL THEN 1 END) as obesity_rate,
			COUNT(CASE WHEN blood_pressure_systolic >= 140 OR blood_pressure_diastolic >= 90 THEN 1 END) * 100.0 / 
				COUNT(CASE WHEN blood_pressure_systolic IS NOT NULL AND blood_pressure_diastolic IS NOT NULL THEN 1 END) as hypertension_rate
		FROM `tabVisit`
		WHERE visit_date >= %s
		AND docstatus = 1
		GROUP BY DATE_FORMAT(visit_date, '%%Y-%%m')
		ORDER BY month
	""", (from_date,), as_dict=True)
	
	return {
		"period": period,
		"from_date": from_date,
		"trends": trends_data
	}


@frappe.whitelist()
def get_risk_assessment_dashboard():
	"""Get risk assessment dashboard data"""
	
	# Get high-risk patients from recent visits
	high_risk_patients = frappe.db.sql("""
		SELECT DISTINCT
			v.patient,
			p.full_name,
			p.age,
			p.gender,
			p.company,
			v.visit_date,
			v.bmi,
			v.blood_pressure_systolic,
			v.blood_pressure_diastolic,
			v.blood_glucose,
			v.smoking_habits
		FROM `tabVisit` v
		INNER JOIN `tabPatient` p ON v.patient = p.name
		WHERE v.docstatus = 1
		AND v.visit_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
		AND (
			v.bmi >= 35 OR
			v.blood_pressure_systolic >= 160 OR
			v.blood_pressure_diastolic >= 100 OR
			v.blood_glucose >= 200 OR
			v.smoking_habits IN ('Daily', 'Occasionally')
		)
		ORDER BY v.visit_date DESC
		LIMIT 50
	""", as_dict=True)
	
	# Calculate risk factor distribution
	risk_factors = frappe.db.sql("""
		SELECT 
			'Obesity (BMI ≥35)' as risk_factor,
			COUNT(*) as count
		FROM `tabVisit`
		WHERE bmi >= 35 AND docstatus = 1
		AND visit_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
		
		UNION ALL
		
		SELECT 
			'Severe Hypertension' as risk_factor,
			COUNT(*) as count
		FROM `tabVisit`
		WHERE (blood_pressure_systolic >= 160 OR blood_pressure_diastolic >= 100)
		AND docstatus = 1
		AND visit_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
		
		UNION ALL
		
		SELECT 
			'Diabetes (Glucose ≥200)' as risk_factor,
			COUNT(*) as count
		FROM `tabVisit`
		WHERE blood_glucose >= 200 AND docstatus = 1
		AND visit_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
		
		UNION ALL
		
		SELECT 
			'Active Smoking' as risk_factor,
			COUNT(*) as count
		FROM `tabVisit`
		WHERE smoking_habits IN ('Daily', 'Occasionally')
		AND docstatus = 1
		AND visit_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
	""", as_dict=True)
	
	return {
		"high_risk_patients": high_risk_patients,
		"risk_factor_distribution": risk_factors,
		"total_high_risk": len(high_risk_patients)
	}


@frappe.whitelist()
def generate_executive_summary():
	"""Generate AI-assisted executive summary for management"""
	
	# Get key metrics for the last 3 months
	dashboard_data = get_main_dashboard_data(
		json.dumps({
			"from_date": add_days(today(), -90),
			"to_date": today()
		})
	)
	
	wellness_data = get_corporate_wellness_summary()
	
	# Generate summary points
	summary_points = []
	
	# Visit statistics
	visit_stats = dashboard_data["visit_stats"]
	if visit_stats["total_visits"] > 0:
		summary_points.append(
			f"In the last 3 months, {visit_stats['total_visits']} visits were completed "
			f"for {visit_stats['unique_patients']} unique patients, "
			f"with {visit_stats['screening_visits']} corporate screening visits."
		)
	
	# Health trends
	bmi_data = {item["category"]: item["count"] for item in dashboard_data["bmi_distribution"]}
	total_bmi_records = sum(bmi_data.values())
	
	if total_bmi_records > 0:
		obesity_rate = round((bmi_data.get("Obese", 0) / total_bmi_records) * 100, 1)
		overweight_rate = round((bmi_data.get("Overweight", 0) / total_bmi_records) * 100, 1)
		
		summary_points.append(
			f"Obesity prevalence stands at {obesity_rate}% with an additional "
			f"{overweight_rate}% of patients classified as overweight, indicating "
			f"significant opportunities for weight management interventions."
		)
	
	# Hypertension data
	bp_data = {item["category"]: item["count"] for item in dashboard_data["hypertension_data"]}
	total_bp_records = sum(bp_data.values())
	
	if total_bp_records > 0:
		hypertension_rate = round((bp_data.get("Hypertensive", 0) / total_bp_records) * 100, 1)
		summary_points.append(
			f"Hypertension affects {hypertension_rate}% of screened individuals, "
			f"requiring targeted cardiovascular health initiatives."
		)
	
	# Corporate wellness insights
	if wellness_data.get("summary_stats"):
		corp_stats = wellness_data["summary_stats"]
		summary_points.append(
			f"Corporate wellness programs have reached {corp_stats['total_participants']} "
			f"employees across {corp_stats['companies_served']} companies through "
			f"{corp_stats['total_screenings']} screening events."
		)
	
	# Recommendations
	recommendations = []
	if obesity_rate > 30:
		recommendations.append("Implement comprehensive weight management programs")
	if hypertension_rate > 25:
		recommendations.append("Expand cardiovascular health monitoring and interventions")
	
	if recommendations:
		summary_points.append(f"Priority recommendations: {', '.join(recommendations)}.")
	
	return {
		"executive_summary": " ".join(summary_points),
		"key_metrics": {
			"total_visits_3m": visit_stats.get("total_visits", 0),
			"obesity_rate": obesity_rate if 'obesity_rate' in locals() else 0,
			"hypertension_rate": hypertension_rate if 'hypertension_rate' in locals() else 0,
			"corporate_participants": wellness_data.get("summary_stats", {}).get("total_participants", 0)
		},
		"generated_date": today()
	}