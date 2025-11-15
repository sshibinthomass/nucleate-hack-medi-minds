import React, { useState, useEffect } from "react";

export function Topbar({ backendUrl, useCase }) {
  const [currentTime, setCurrentTime] = useState(new Date());
  const [weatherData, setWeatherData] = useState({
    temperature_c: 0,
    humidity_percent: 0,
    wind_kmh: 0,
    city: "",
  });

  // Update time every second
  useEffect(() => {
    const timerId = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timerId);
  }, []);

  useEffect(() => {
    const fetchWeatherData = async () => {
      try {
        const response = await fetch(`${backendUrl || "http://localhost:8000"}/personal-data`);
        if (response.ok) {
          const data = await response.json();
          setWeatherData({
            temperature_c: data.temperature_c || 0,
            humidity_percent: data.humidity_percent || 0,
            wind_kmh: data.wind_kmh || 0,
            city: data.city || "",
          });
        }
      } catch (error) {
        console.error("Error fetching weather data:", error);
      }
    };

    // Initial fetch
    fetchWeatherData();

    // Poll for updates every 5 seconds
    const intervalId = setInterval(fetchWeatherData, 5000);

    return () => clearInterval(intervalId);
  }, [backendUrl]);

  // Format date: "Saturday, Nov 15"
  const formatDate = (date) => {
    const options = { weekday: 'long', month: 'short', day: 'numeric' };
    return date.toLocaleDateString('en-US', options);
  };

  // Format time: "2:34 PM"
  const formatTime = (date) => {
    const options = { hour: 'numeric', minute: '2-digit', hour12: true };
    return date.toLocaleTimeString('en-US', options);
  };

  return (
    <header className="topbar">
      <div className="topbar__content">
        <h1 className="topbar__title">Medi-Mind</h1>
        <p className="topbar__subtitle">
          {useCase === "doctor_chatbot" 
            ? "Doctor Assistant for Healthcare Professionals" 
            : "Your Personal Medical Assistant"}
        </p>
      </div>
      <div className="topbar__right">
        <div className="topbar__weather">
          <div className="topbar__weather-icon">🌤️</div>
          <div className="topbar__weather-info">
            <div className="topbar__weather-header">
              <div className="topbar__weather-city">{weatherData.city}</div>
              <div className="topbar__weather-temp">{weatherData.temperature_c}°C</div>
            </div>
            <div className="topbar__weather-details">
              <span>{weatherData.humidity_percent}%</span>
              <span>•</span>
              <span>{weatherData.wind_kmh} km/h</span>
            </div>
          </div>
        </div>
        <div className="topbar__datetime">
          <div className="topbar__datetime-icon">📅</div>
          <div className="topbar__datetime-info">
            <div className="topbar__datetime-date">{formatDate(currentTime)}</div>
            <div className="topbar__datetime-time">{formatTime(currentTime)}</div>
          </div>
        </div>
      </div>
    </header>
  );
}

