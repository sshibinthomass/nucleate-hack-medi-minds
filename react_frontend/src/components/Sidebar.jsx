import React, { useState, useEffect } from "react";

export function Sidebar({
  provider,
  model,
  models,
  useCase,
  useCases,
  onProviderChange,
  onModelChange,
  onUseCaseChange,
  backendUrl,
  backendStatus,
  backendStatusMessage,
  onWaterIncrease,
}) {
  const [healthData, setHealthData] = useState({});
  const [doctorStats, setDoctorStats] = useState({
    total_patients: 0,
    allergies: {},
    age_groups: {
      less_than_20: 0,
      "20_to_40": 0,
      more_than_40: 0
    }
  });

  // Fetch personal data from backend on mount and poll for updates
  useEffect(() => {
    const fetchPersonalData = async () => {
      try {
        const response = await fetch(`${backendUrl}/personal-data`);
        if (response.ok) {
          const data = await response.json();
          // Dynamically update with all fields from JSON
          setHealthData((prev) => {
            // Merge all data from JSON, preserving any local optimistic updates
            const newData = { ...data };
            // Preserve water intake if it was just updated optimistically
            if (prev.Water_Intake_cups !== undefined && 
                Math.abs((prev.Water_Intake_cups - (newData.Water_Intake_cups || 0))) < 0.1) {
              // If values are very close, keep the previous one to avoid flicker
              newData.Water_Intake_cups = prev.Water_Intake_cups;
            }
            return newData;
          });
        }
      } catch (error) {
        console.error("Error fetching personal data:", error);
      }
    };

    // Initial fetch
    fetchPersonalData();

    // Poll for updates every 2 seconds to reflect changes from LLM
    const intervalId = setInterval(fetchPersonalData, 2000);

    // Cleanup interval on unmount
    return () => clearInterval(intervalId);
  }, [backendUrl]);

  // Fetch doctor statistics when doctor_chatbot is selected
  useEffect(() => {
    if (useCase !== "doctor_chatbot") {
      return;
    }

    const fetchDoctorStats = async () => {
      try {
        const response = await fetch(`${backendUrl}/doctor-statistics`);
        if (response.ok) {
          const data = await response.json();
          setDoctorStats(data);
        }
      } catch (error) {
        console.error("Error fetching doctor statistics:", error);
      }
    };

    // Initial fetch
    fetchDoctorStats();

    // Poll for updates every 1.5 seconds to reflect changes from JSON updates (faster for real-time feel)
    const intervalId = setInterval(fetchDoctorStats, 1500);

    // Cleanup interval on unmount
    return () => clearInterval(intervalId);
  }, [backendUrl, useCase]);
  const activeUseCaseLabel =
    useCases.find((option) => option.value === useCase)?.label || "Chat";

  const statusLabel = (() => {
    switch (backendStatus) {
      case "online":
        return "Backend Online";
      case "offline":
        return "Backend Offline";
      case "checking":
      default:
        return "Checking Backend";
    }
  })();

  const formatSleepDuration = (hours) => {
    if (!hours || hours <= 0) return "N/A";
    const h = Math.floor(hours);
    const m = Math.round((hours % 1) * 60);
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  };

  // Calculate energy based on mood and water intake
  const calculateEnergy = (mood, waterIntake) => {
    // Mood factor (0-100 scale)
    const moodFactors = {
      "Happy": 90,
      "Surprised": 75,
      "Sad": 40,
      "Angry": 50,
    };
    const moodScore = moodFactors[mood] || 60;

    // Water intake factor (0-100 scale, optimal at 8 cups)
    // Formula: 100 * (1 - |waterIntake - 8| / 8), capped at 0-100
    const optimalWater = 8;
    const waterDeviation = Math.abs((waterIntake || 0) - optimalWater);
    const waterScore = Math.max(0, Math.min(100, 100 * (1 - waterDeviation / optimalWater)));

    // Combined energy: 60% mood + 40% water
    const energy = Math.round(moodScore * 0.6 + waterScore * 0.4);
    return Math.max(0, Math.min(100, energy));
  };

  // Define preferred limits for health metrics
  const healthLimits = {
    steps: 10000,
    calories_kcal: 2000,
    blood_oxygen_spo2_percent: 95,
    heart_rate_bpm: { min: 60, max: 100 },
    Water_Intake_cups: 6,
    sleep_duration_hours: 7,
    Energy_Level: 50,
  };

  // Check if a value is below preferred limit
  const isBelowLimit = (key, value) => {
    if (value === null || value === undefined) return false;
    
    const limit = healthLimits[key];
    if (!limit) return false;

    if (typeof limit === 'object') {
      // For heart rate, check if outside range
      return value < limit.min || value > limit.max;
    }
    
    return value < limit;
  };

  // Expose health alerts to parent component via effect
  useEffect(() => {
    const alerts = [];
    if (isBelowLimit('steps', healthData.steps)) {
      alerts.push(`Steps: ${healthData.steps || 0} (below recommended 10,000)`);
    }
    if (isBelowLimit('calories_kcal', healthData.calories_kcal)) {
      alerts.push(`Calories: ${healthData.calories_kcal || 0} kcal (below recommended 2,000)`);
    }
    if (isBelowLimit('blood_oxygen_spo2_percent', healthData.blood_oxygen_spo2_percent)) {
      alerts.push(`Blood Oxygen: ${healthData.blood_oxygen_spo2_percent || 0}% (below normal 95%)`);
    }
    if (isBelowLimit('heart_rate_bpm', healthData.heart_rate_bpm)) {
      alerts.push(`Heart Rate: ${healthData.heart_rate_bpm || 0} bpm (outside normal 60-100 range)`);
    }
    if (isBelowLimit('Water_Intake_cups', healthData.Water_Intake_cups)) {
      alerts.push(`Water Intake: ${healthData.Water_Intake_cups || 0} cups (below recommended 6 cups)`);
    }
    if (isBelowLimit('sleep_duration_hours', healthData.sleep_duration_hours)) {
      alerts.push(`Sleep: ${formatSleepDuration(healthData.sleep_duration_hours)} (below recommended 7 hours)`);
    }
    const energy = calculateEnergy(healthData.mood, healthData.Water_Intake_cups);
    if (isBelowLimit('Energy_Level', energy)) {
      alerts.push(`Energy Level: ${energy} (below recommended 50)`);
    }
    
    if (window.setHealthAlerts) {
      window.setHealthAlerts(alerts);
    }
  }, [healthData]);

  const handleWaterChange = async (delta) => {
    const currentWater = healthData.Water_Intake_cups || 0;
    const newWaterIntake = Math.max(0, currentWater + delta);
    
    // Trigger animation if water is increased
    if (delta > 0 && newWaterIntake > currentWater) {
      onWaterIncrease?.();
    }
    
    // Optimistically update UI
    setHealthData((prev) => ({
      ...prev,
      Water_Intake_cups: newWaterIntake,
    }));

    // Persist to backend
    try {
      const response = await fetch(`${backendUrl}/personal-data/water-intake`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          water_intake_cups: newWaterIntake,
        }),
      });

      if (!response.ok) {
        // Revert on error
        setHealthData((prev) => ({
          ...prev,
          Water_Intake_cups: currentWater,
        }));
        console.error("Failed to update water intake");
      }
    } catch (error) {
      // Revert on error
      setHealthData((prev) => ({
        ...prev,
        Water_Intake_cups: currentWater,
      }));
      console.error("Error updating water intake:", error);
    }
  };

  return (
    <aside className="sidebar">
      <div className="sidebar__form">
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '8px'
        }}>
          {useCases.map((option) => (
            <button
              key={option.value}
              onClick={() => onUseCaseChange(option.value)}
              style={{
                padding: '12px 16px',
                borderRadius: '8px',
                border: `2px solid ${useCase === option.value ? '#4CAF50' : '#e0e0e0'}`,
                backgroundColor: useCase === option.value ? '#f1f8f4' : '#ffffff',
                color: useCase === option.value ? '#2e7d32' : '#666666',
                fontWeight: useCase === option.value ? '600' : '400',
                fontSize: '14px',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                textAlign: 'left',
                width: '100%',
                outline: 'none',
                boxShadow: useCase === option.value ? '0 2px 4px rgba(76, 175, 80, 0.1)' : 'none',
              }}
              onMouseEnter={(e) => {
                if (useCase !== option.value) {
                  e.currentTarget.style.backgroundColor = '#f5f5f5';
                  e.currentTarget.style.borderColor = '#bdbdbd';
                }
              }}
              onMouseLeave={(e) => {
                if (useCase !== option.value) {
                  e.currentTarget.style.backgroundColor = '#ffffff';
                  e.currentTarget.style.borderColor = '#e0e0e0';
                }
              }}
            >
                {option.label}
            </button>
            ))}
        </div>
      </div>

      {useCase === "doctor_chatbot" ? (
        <div className="health-widgets">
          {/* Doctor Statistics Widgets */}
          <div className="health-widgets__row">
            <div className="health-widget health-widget--doctor" style={{ width: "100%" }}>
              <div className="health-widget__icon">👥</div>
              <div className="health-widget__content" style={{ width: "100%", justifyContent: "flex-start", alignItems: "flex-start" }}>
                <div className="health-widget__label">Total Patients</div>
                <div className="health-widget__value" style={{ fontSize: "20px", marginTop: "4px" }}>
                  {doctorStats.total_patients || 0}
                </div>
              </div>
            </div>
          </div>

          <div className="health-widgets__row">
            <div className="health-widget health-widget--doctor" style={{ width: "100%" }}>
              <div className="health-widget__icon">⚠️</div>
              <div className="health-widget__content" style={{ width: "100%", justifyContent: "flex-start", alignItems: "flex-start" }}>
                <div className="health-widget__label">Allergies</div>
                <div className="health-widget__value" style={{ fontSize: "14px", lineHeight: "1.4", display: "flex", flexDirection: "column", gap: "4px", alignItems: "flex-start", marginTop: "4px" }}>
                  {Object.keys(doctorStats.allergies || {}).length > 0 ? (
                    <>
                      {Object.entries(doctorStats.allergies || {})
                        .sort((a, b) => b[1] - a[1])
                        .slice(0, 3)
                        .map(([allergy, count]) => (
                          <div key={allergy} style={{ whiteSpace: "nowrap" }}>
                            {allergy}: {count}
                          </div>
                        ))}
                    </>
                  ) : (
                    <div>None</div>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="health-widgets__row">
            <div className="health-widget health-widget--doctor" style={{ width: "100%" }}>
              <div className="health-widget__icon">📊</div>
              <div className="health-widget__content" style={{ width: "100%", justifyContent: "flex-start", alignItems: "flex-start" }}>
                <div className="health-widget__label">Age Groups</div>
                <div className="health-widget__value" style={{ fontSize: "14px", lineHeight: "1.4", display: "flex", flexDirection: "column", gap: "4px", alignItems: "flex-start", marginTop: "4px" }}>
                  <div style={{ whiteSpace: "nowrap" }}>&lt;20: {doctorStats.age_groups?.less_than_20 || 0}</div>
                  <div style={{ whiteSpace: "nowrap" }}>20-40: {doctorStats.age_groups?.["20_to_40"] || 0}</div>
                  <div style={{ whiteSpace: "nowrap" }}>&gt;40: {doctorStats.age_groups?.more_than_40 || 0}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="health-widgets">
          <div className="health-widgets__row">
            <div className={`health-widget ${isBelowLimit('steps', healthData.steps) ? 'health-widget--alert' : ''}`}
              onClick={() => {
                var w=window.open('./steps_plot.html','stepsPopup','width=900,height=600,resizable=yes,scrollbars=yes'); 
                if(w) w.focus(); 
                else alert('Popup blocked — please allow popups or open ./steps_plot.html directly');
              }}
              style={{ cursor: 'pointer' }}
            >
              <div className="health-widget__icon">👣</div>
              <div className="health-widget__content">
                <div className="health-widget__label">Steps</div>
                <div className={`health-widget__value ${isBelowLimit('steps', healthData.steps) ? 'health-widget__value--alert' : ''}`}>
                  {(healthData.steps || 0).toLocaleString()}
                </div>
              </div>
            </div>
            <div className={`health-widget ${isBelowLimit('calories_kcal', healthData.calories_kcal) ? 'health-widget--alert' : ''}`}
            onClick={() => {
              var w=window.open('./calories_plot.html','stepsPopup','width=900,height=600,resizable=yes,scrollbars=yes'); 
              if(w) w.focus(); 
              else alert('Popup blocked — please allow popups or open ./steps_plot.html directly');
            }}
            style={{ cursor: 'pointer' }}
            
            >
              <div className="health-widget__icon">🔥</div>
              <div className="health-widget__content">
                <div className="health-widget__label">Calories</div>
                <div className={`health-widget__value ${isBelowLimit('calories_kcal', healthData.calories_kcal) ? 'health-widget__value--alert' : ''}`}>
                  {healthData.calories_kcal || 0} kcal
                </div>
              </div>
            </div>
          </div>

          <div className="health-widgets__row">
            <div className={`health-widget ${isBelowLimit('blood_oxygen_spo2_percent', healthData.blood_oxygen_spo2_percent) ? 'health-widget--alert' : ''}`}
            onClick={() => {
              var w=window.open('./spo2_plot.html','stepsPopup','width=900,height=600,resizable=yes,scrollbars=yes'); 
              if(w) w.focus(); 
              else alert('Popup blocked — please allow popups or open ./steps_plot.html directly');
            }}
            style={{ cursor: 'pointer' }}
            >
              <div className="health-widget__icon">🫁</div>
              <div className="health-widget__content">
                <div className="health-widget__label">Blood O₂</div>
                <div className={`health-widget__value ${isBelowLimit('blood_oxygen_spo2_percent', healthData.blood_oxygen_spo2_percent) ? 'health-widget__value--alert' : ''}`}
                >
                  {healthData.blood_oxygen_spo2_percent || 0}%
                </div>
              </div>
            </div>
            <div className={`health-widget ${isBelowLimit('heart_rate_bpm', healthData.heart_rate_bpm) ? 'health-widget--alert' : ''}`}
            onClick={() => {
              var w=window.open('./heart_rate_plot.html','stepsPopup','width=900,height=600,resizable=yes,scrollbars=yes'); 
              if(w) w.focus(); 
              else alert('Popup blocked — please allow popups or open ./steps_plot.html directly');
            }}
            style={{ cursor: 'pointer' }}
            >
              <div className="health-widget__icon health-widget__icon--heart">❤️</div>
              <div className="health-widget__content">
                <div className="health-widget__label">Heart</div>
                <div className={`health-widget__value ${isBelowLimit('heart_rate_bpm', healthData.heart_rate_bpm) ? 'health-widget__value--alert' : ''}`}>
                  {healthData.heart_rate_bpm || 0} bpm
                </div>
              </div>
            </div>
          </div>

          <div className="health-widgets__row">
            <div className={`health-widget health-widget--water ${isBelowLimit('Water_Intake_cups', healthData.Water_Intake_cups) ? 'health-widget--alert' : ''}`}
            onClick={() => {
              var w=window.open('./water_ml_plot.html','stepsPopup','width=900,height=600,resizable=yes,scrollbars=yes'); 
              if(w) w.focus(); 
              else alert('Popup blocked — please allow popups or open ./steps_plot.html directly');
            }}
            style={{ cursor: 'pointer' }}
            >
              <div className="health-widget__icon">💧</div>
              <div className="health-widget__content">
                <div className="health-widget__label">Water</div>
                <div className="health-widget__value-row">
                  <button 
                    className="health-widget__button"
                    onClick={() => handleWaterChange(-1)}
                    aria-label="Decrease water intake"
                  >
                    −
                  </button>
                  <span className={`health-widget__value ${isBelowLimit('Water_Intake_cups', healthData.Water_Intake_cups) ? 'health-widget__value--alert' : ''}`}>
                    {healthData.Water_Intake_cups || 0} 
                  </span>
                  <button 
                    className="health-widget__button"
                    onClick={() => handleWaterChange(1)}
                    aria-label="Increase water intake"
                  >
                    +
                  </button>
                </div>
              </div>
            </div>
            <div className={`health-widget ${
              healthData.mood === "Happy" ? "health-widget--happy" :
              healthData.mood === "Sad" ? "health-widget--sad" :
              healthData.mood === "Surprised" ? "health-widget--surprised" :
              healthData.mood === "Angry" ? "health-widget--angry" : ""
            }`}>
              <div className="health-widget__icon">
                {healthData.mood === "Happy" && "😊"}
                {healthData.mood === "Sad" && "😢"}
                {healthData.mood === "Surprised" && "😲"}
                {healthData.mood === "Angry" && "😡"}
                {!["Happy", "Sad", "Surprised", "Angry"].includes(healthData.mood) && "😊"}
              </div>
              <div className="health-widget__content">
                <div className="health-widget__label">Mood</div>
                <div className="health-widget__value">{healthData.mood || "N/A"}</div>
              </div>
            </div>
          </div>

          <div className="health-widgets__row">
            <div className={`health-widget ${isBelowLimit('sleep_duration_hours', healthData.sleep_duration_hours) ? 'health-widget--alert' : ''}`}>
              <div className="health-widget__icon">😴</div>
              <div className="health-widget__content">
                <div className="health-widget__label">Sleep</div>
                <div className={`health-widget__value ${isBelowLimit('sleep_duration_hours', healthData.sleep_duration_hours) ? 'health-widget__value--alert' : ''}`}>
                  {formatSleepDuration(healthData.sleep_duration_hours)}
                </div>
              </div>
            </div>
            <div className={`health-widget ${isBelowLimit('Energy_Level', calculateEnergy(healthData.mood, healthData.Water_Intake_cups)) ? 'health-widget--alert' : ''}`}>
              <div className="health-widget__icon">⚡</div>
              <div className="health-widget__content">
                <div className="health-widget__label">Energy</div>
                <div className={`health-widget__value ${isBelowLimit('Energy_Level', calculateEnergy(healthData.mood, healthData.Water_Intake_cups)) ? 'health-widget__value--alert' : ''}`}>
                  {calculateEnergy(healthData.mood, healthData.Water_Intake_cups)}
                </div>
              </div>
            </div>
          </div>

          {/* Activity Icons - Only visible for Medical Assistant use case */}
          <div className="activity-icons" style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: '16px',
            marginTop: '12px',
            padding: '8px 0',
            opacity: 0.5
          }}>
            <span style={{
              fontSize: '18px',
              color: '#666',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              border: '1px solid #ccc',
              backgroundColor: 'rgba(200, 200, 200, 0.1)'
            }}>🚶</span>
            <span style={{
              fontSize: '18px',
              color: '#666',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              border: '1px solid #ccc',
              backgroundColor: 'rgba(200, 200, 200, 0.1)'
            }}>🏃</span>
            <span style={{
              fontSize: '18px',
              color: '#666',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              border: '1px solid #ccc',
              backgroundColor: 'rgba(200, 200, 200, 0.1)'
            }}>🚴</span>
          </div>
        </div>
      )}

      <div className="sidebar__footer">
        <span className={`sidebar__status sidebar__status--${backendStatus}`}>
          <span className="sidebar__status-indicator" />
          {statusLabel}
        </span>
        <div className="sidebar__backend-url">
          <code>{backendUrl}</code>
        </div>
        {backendStatusMessage && (
          <div className="sidebar__footer-message">{backendStatusMessage}</div>
        )}
      </div>
    </aside>
  );
}
