import React, { useEffect, useState, useRef } from "react";
import "../App.css";

const MOOD_QUOTES = {
  happy: [
    "Keep spreading that joy! 😊",
    "Your happiness is contagious! 🌟",
    "Stay positive and keep smiling! ✨",
    "Every day is a fresh start! 🌈",
  ],
  sad: [
    "It's okay to feel this way. You're not alone. 💙",
    "This feeling will pass. Take care of yourself. 🤗",
    "Remember, even cloudy days have silver linings. ☁️",
    "You're stronger than you know. 💪",
  ],
  surprised: [
    "Life is full of wonderful surprises! 🎉",
    "Embrace the unexpected! ✨",
    "Surprises make life exciting! 🎊",
    "Stay curious and open-minded! 🌟",
  ],
  angry: [
    "Take a deep breath—this moment will pass. 🧘",
    "Channel that energy into something positive. ⚡",
    "It's okay to step back and reset. ♻️",
    "Pause, breathe, and respond with calm. 🌬️",
  ],
};

const MOOD_EMOJIS = {
  happy: "😊",
  sad: "😢",
  surprised: "😲",
  angry: "😡",
};

export function MoodAnimation({ show, mood, onComplete }) {
  const [isVisible, setIsVisible] = useState(false);
  const [quote, setQuote] = useState("");
  const onCompleteRef = useRef(onComplete);
  const hideTimerRef = useRef(null);

  // Keep onComplete ref updated
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => {
    if (show && mood) {
      // Select a random quote for the mood
      const quotes = MOOD_QUOTES[mood.toLowerCase()] || [];
      if (quotes.length > 0) {
        const randomQuote = quotes[Math.floor(Math.random() * quotes.length)];
        setQuote(randomQuote);
      }
      setIsVisible(true);
      
      const timer = setTimeout(() => {
        setIsVisible(false);
        // Wait for fade out animation before calling onComplete
        hideTimerRef.current = setTimeout(() => {
          onCompleteRef.current?.();
          hideTimerRef.current = null;
        }, 500); // Wait for fade out animation
      }, 2000); // Show for 2 seconds

      return () => {
        clearTimeout(timer);
        if (hideTimerRef.current) {
          clearTimeout(hideTimerRef.current);
          hideTimerRef.current = null;
        }
      };
    } else {
      // Reset visibility when show becomes false
      setIsVisible(false);
      // Clear any pending hide timer
      if (hideTimerRef.current) {
        clearTimeout(hideTimerRef.current);
        hideTimerRef.current = null;
      }
    }
  }, [show, mood]);

  if (!show || !mood || !isVisible) return null;

  const emoji = MOOD_EMOJIS[mood.toLowerCase()] || "😊";
  const moodName = mood.charAt(0).toUpperCase() + mood.slice(1);

  return (
    <div className={`mood-animation mood-animation--${mood} ${isVisible ? "mood-animation--show" : "mood-animation--hide"}`}>
      <div className="mood-animation__emoji">{emoji}</div>
      <div className="mood-animation__mood-name">{moodName}</div>
      <div className="mood-animation__quote">{quote}</div>
    </div>
  );
}

