import React, { useEffect, useState, useRef } from "react";
import "../App.css";

export function WaterAnimation({ show, onComplete }) {
  const [isVisible, setIsVisible] = useState(false);
  const onCompleteRef = useRef(onComplete);
  const hideTimerRef = useRef(null);

  // Keep onComplete ref updated
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => {
    if (show) {
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
  }, [show]);

  if (!show && !isVisible) return null;

  return (
    <div className={`water-animation ${isVisible ? "water-animation--show" : "water-animation--hide"}`}>
      <div className="water-animation__cup">💧</div>
      <div className="water-animation__message">Way to Go! 💙</div>
    </div>
  );
}

