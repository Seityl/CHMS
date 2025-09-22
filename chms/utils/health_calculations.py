def calculate_bmi(weight_kg, height_cm):
	"""Calculate BMI from weight in kg and height in cm"""
	if not weight_kg or not height_cm or height_cm == 0:
		return None
	
	height_m = height_cm / 100
	bmi = weight_kg / (height_m ** 2)
	return round(bmi, 2)


def get_bmi_category(bmi):
	"""Get BMI category based on WHO standards"""
	if not bmi:
		return None
	
	if bmi < 18.5:
		return "Underweight"
	elif bmi < 25:
		return "Healthy Weight"
	elif bmi < 30:
		return "Overweight"
	elif bmi < 35:
		return "Obesity Stage 1"
	elif bmi < 40:
		return "Obesity Stage 2"
	else:
		return "Morbidly Obese"


def get_blood_pressure_category(systolic, diastolic):
	"""Get blood pressure category based on AHA guidelines"""
	if not systolic or not diastolic:
		return None
	
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


def get_glucose_category(glucose_mg_dl):
	"""Get blood glucose category (fasting or random)"""
	if not glucose_mg_dl:
		return None
	
	if glucose_mg_dl < 70:
		return "Low"
	elif glucose_mg_dl < 100:
		return "Normal (Fasting)"
	elif glucose_mg_dl < 126:
		return "Prediabetic (Fasting)"
	elif glucose_mg_dl < 200:
		return "Diabetic (Fasting)"
	else:
		return "Severely Elevated"


def calculate_cardiovascular_risk_score(visit_data):
	"""Calculate basic cardiovascular risk score based on visit data"""
	risk_score = 0
	risk_factors = []
	
	# Age risk
	age = visit_data.get('age', 0)
	if age >= 45:
		risk_score += 1
		risk_factors.append("Age ≥45")
	
	# BMI risk
	bmi = visit_data.get('bmi')
	if bmi and bmi >= 30:
		risk_score += 2
		risk_factors.append("Obesity")
	elif bmi and bmi >= 25:
		risk_score += 1
		risk_factors.append("Overweight")
	
	# Blood pressure risk
	systolic = visit_data.get('blood_pressure_systolic')
	diastolic = visit_data.get('blood_pressure_diastolic')
	if systolic and diastolic:
		if systolic >= 140 or diastolic >= 90:
			risk_score += 2
			risk_factors.append("Hypertension")
		elif systolic >= 130 or diastolic >= 80:
			risk_score += 1
			risk_factors.append("Elevated BP")
	
	# Glucose risk
	glucose = visit_data.get('blood_glucose')
	if glucose:
		if glucose >= 126:
			risk_score += 2
			risk_factors.append("Diabetes")
		elif glucose >= 100:
			risk_score += 1
			risk_factors.append("Prediabetes")
	
	# Smoking risk
	smoking = visit_data.get('smoking_habits')
	if smoking in ['Daily', 'Occasionally']:
		risk_score += 2
		risk_factors.append("Smoking")
	
	# Physical activity risk
	exercise = visit_data.get('exercise_frequency')
	if exercise in ['None', 'Rarely']:
		risk_score += 1
		risk_factors.append("Physical Inactivity")
	
	# Determine risk level
	if risk_score <= 2:
		risk_level = "Low Risk"
	elif risk_score <= 4:
		risk_level = "Moderate Risk"
	elif risk_score <= 6:
		risk_level = "High Risk"
	else:
		risk_level = "Very High Risk"
	
	return {
		"risk_score": risk_score,
		"risk_level": risk_level,
		"risk_factors": risk_factors
	}


def calculate_metabolic_syndrome_criteria(visit_data):
	"""Check for metabolic syndrome criteria (3 out of 5 required)"""
	criteria_met = 0
	criteria_details = []
	
	# Waist circumference (≥40 inches men, ≥35 inches women)
	waist = visit_data.get('waist_circumference')
	gender = visit_data.get('gender')
	if waist and gender:
		threshold = 40 if gender == 'Male' else 35
		if waist >= threshold:
			criteria_met += 1
			criteria_details.append(f"Waist circumference ≥{threshold} inches")
	
	# Blood pressure (≥130/85)
	systolic = visit_data.get('blood_pressure_systolic')
	diastolic = visit_data.get('blood_pressure_diastolic')
	if systolic and diastolic and (systolic >= 130 or diastolic >= 85):
		criteria_met += 1
		criteria_details.append("Elevated blood pressure")
	
	# Fasting glucose (≥100 mg/dL)
	glucose = visit_data.get('blood_glucose')
	if glucose and glucose >= 100:
		criteria_met += 1
		criteria_details.append("Elevated fasting glucose")
	
	# HDL cholesterol (<40 mg/dL men, <50 mg/dL women) - would need additional field
	# Triglycerides (≥150 mg/dL) - would need additional field
	
	has_metabolic_syndrome = criteria_met >= 3
	
	return {
		"criteria_met": criteria_met,
		"has_metabolic_syndrome": has_metabolic_syndrome,
		"criteria_details": criteria_details
	}


def generate_health_recommendations(visit_data):
	"""Generate personalized health recommendations based on visit data"""
	recommendations = []
	
	# BMI recommendations
	bmi = visit_data.get('bmi')
	if bmi:
		if bmi >= 30:
			recommendations.append({
				"category": "Weight Management",
				"recommendation": "Consider a structured weight loss program with nutritional counseling and regular exercise",
				"priority": "High"
			})
		elif bmi >= 25:
			recommendations.append({
				"category": "Weight Management", 
				"recommendation": "Maintain healthy weight through balanced diet and regular physical activity",
				"priority": "Medium"
			})
		elif bmi < 18.5:
			recommendations.append({
				"category": "Weight Management",
				"recommendation": "Consider nutritional counseling to achieve healthy weight gain",
				"priority": "Medium"
			})
	
	# Blood pressure recommendations
	systolic = visit_data.get('blood_pressure_systolic')
	diastolic = visit_data.get('blood_pressure_diastolic')
	if systolic and diastolic:
		if systolic >= 140 or diastolic >= 90:
			recommendations.append({
				"category": "Cardiovascular Health",
				"recommendation": "Consult physician for blood pressure management and regular monitoring",
				"priority": "High"
			})
		elif systolic >= 130 or diastolic >= 80:
			recommendations.append({
				"category": "Cardiovascular Health",
				"recommendation": "Monitor blood pressure regularly and consider lifestyle modifications",
				"priority": "Medium"
			})
	
	# Glucose recommendations
	glucose = visit_data.get('blood_glucose')
	if glucose:
		if glucose >= 126:
			recommendations.append({
				"category": "Diabetes Management",
				"recommendation": "Follow up with healthcare provider for diabetes management and HbA1c testing",
				"priority": "High"
			})
		elif glucose >= 100:
			recommendations.append({
				"category": "Diabetes Prevention",
				"recommendation": "Consider diabetes prevention program with lifestyle modifications",
				"priority": "Medium"
			})
	
	# Lifestyle recommendations
	smoking = visit_data.get('smoking_habits')
	if smoking in ['Daily', 'Occasionally']:
		recommendations.append({
			"category": "Smoking Cessation",
			"recommendation": "Join smoking cessation program and consider stress management alternatives",
			"priority": "High"
		})
	
	exercise = visit_data.get('exercise_frequency')
	if exercise in ['None', 'Rarely']:
		recommendations.append({
			"category": "Physical Activity",
			"recommendation": "Start with 30 minutes of moderate exercise 3-4 times per week",
			"priority": "Medium"
		})
	
	# Stress recommendations
	stress = visit_data.get('stress_level')
	if stress == 'High (7-10)':
		recommendations.append({
			"category": "Stress Management",
			"recommendation": "Consider stress reduction techniques, counseling, or wellness programs",
			"priority": "Medium"
		})
	
	# Sleep recommendations
	sleep_hours = visit_data.get('sleep_hours')
	if sleep_hours and sleep_hours < 7:
		recommendations.append({
			"category": "Sleep Health",
			"recommendation": "Aim for 7-9 hours of quality sleep per night and practice good sleep hygiene",
			"priority": "Low"
		})
	
	return recommendations


def calculate_wellness_wheel_scores(visit_data):
	"""Calculate wellness wheel scores based on lifestyle factors"""
	scores = {}
	
	# Exercise score (1-10)
	exercise = visit_data.get('exercise_frequency')
	exercise_mapping = {
		'None': 1,
		'Rarely': 3,
		'1-2 times/week': 5,
		'3-4 times/week': 8,
		'5+ times/week': 10
	}
	scores['exercise'] = exercise_mapping.get(exercise, 5)
	
	# Sleep score (based on hours)
	sleep_hours = visit_data.get('sleep_hours', 7)
	if sleep_hours >= 7 and sleep_hours <= 9:
		scores['sleep'] = 8
	elif sleep_hours >= 6 and sleep_hours <= 10:
		scores['sleep'] = 6
	else:
		scores['sleep'] = 3
	
	# Stress score (inverted - lower stress = higher score)
	stress = visit_data.get('stress_level')
	stress_mapping = {
		'Low (1-3)': 9,
		'Moderate (4-6)': 5,
		'High (7-10)': 2
	}
	scores['stress'] = stress_mapping.get(stress, 5)
	
	# Smoking score (inverted)
	smoking = visit_data.get('smoking_habits')
	smoking_mapping = {
		'Never': 10,
		'Former Smoker': 7,
		'Occasionally': 3,
		'Daily': 1
	}
	scores['smoking'] = smoking_mapping.get(smoking, 10)
	
	# Alcohol score
	alcohol = visit_data.get('alcohol_consumption')
	alcohol_mapping = {
		'None': 8,
		'Occasionally': 9,
		'Social Drinking': 7,
		'Binge Drinking': 3,
		'Heavy Drinking': 1
	}
	scores['alcohol'] = alcohol_mapping.get(alcohol, 7)
	
	# Overall wellness score (average)
	scores['overall'] = round(sum(scores.values()) / len(scores), 1)
	
	return scores